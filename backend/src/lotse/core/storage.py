"""Object store access: the only module that talks to S3 (enforced by import-linter).

Every key lives under `tenants/<tenant_id>/`. Each operation takes the caller's tenant and
refuses a key outside that prefix before anything is signed or sent, so one tenant can never
be handed a URL for another tenant's file (spec section 6, object store isolation).

The API never moves file bytes: browsers upload and download with presigned URLs.
"""

import argparse
import asyncio
import base64
import binascii
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from lotse.settings import StorageSettings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_NOT_FOUND = {"404", "NoSuchKey", "NotFound"}

PUT_URL_SECONDS = 600  # spec section 8: an upload URL is valid for 10 minutes
GET_URL_SECONDS = 300


class KeyOutsideTenant(ValueError):
    """A key that is malformed or not under the caller's tenant prefix."""


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    size: int
    sha256_b64: str | None


def tenant_prefix(tenant_id: UUID) -> str:
    return f"tenants/{tenant_id}/"


def object_key(tenant_id: UUID, *parts: str) -> str:
    """`tenants/<tenant_id>/<part>/<part>...`. Parts are plain names: no slashes, no `..`."""
    if not parts:
        raise KeyOutsideTenant("a key needs at least one part below the tenant prefix")
    for part in parts:
        if not _SEGMENT.fullmatch(part) or ".." in part:
            raise KeyOutsideTenant(f"invalid key part {part!r}")
    return tenant_prefix(tenant_id) + "/".join(parts)


def _check(tenant_id: UUID, key: str) -> str:
    prefix = tenant_prefix(tenant_id)
    rest = key.removeprefix(prefix)
    if rest == key or not rest:
        raise KeyOutsideTenant("key is not under the caller's tenant prefix")
    # Rebuild from the parts so `tenants/<a>/../<b>/x` and similar tricks cannot pass.
    return object_key(tenant_id, *rest.split("/"))


def _sha256_b64(value: str) -> str:
    try:
        raw = base64.b64decode(value, validate=True)
    except binascii.Error as exc:
        raise ValueError("sha256 must be base64") from exc
    if len(raw) != 32:
        raise ValueError("sha256 must be 32 bytes")
    return value


def create_client(settings: StorageSettings) -> "S3Client":
    secret = settings.s3_secret_access_key
    client: S3Client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        # Unset in AWS: the default chain picks up the workload's role.
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=secret.get_secret_value() if secret else None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.s3_endpoint_url else "virtual"},
            connect_timeout=3,
            read_timeout=10,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
    return client


class ObjectStore:
    def __init__(self, client: "S3Client", bucket: str) -> None:
        self._client = client
        self.bucket = bucket

    def presign_put(
        self,
        tenant_id: UUID,
        key: str,
        *,
        content_type: str,
        content_length: int,
        sha256_b64: str,
        expires: int = PUT_URL_SECONDS,
    ) -> str:
        """A URL that accepts exactly this body: the size and SHA-256 are part of the signature,
        and the store rejects a body whose checksum does not match. The client must send the
        `Content-Type` and `x-amz-checksum-sha256` headers with the same values."""
        if content_length <= 0:
            raise ValueError("content_length must be positive")
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": _check(tenant_id, key),
                "ContentType": content_type,
                "ContentLength": content_length,
                "ChecksumSHA256": _sha256_b64(sha256_b64),
            },
            ExpiresIn=expires,
        )

    def presign_get(self, tenant_id: UUID, key: str, *, expires: int = GET_URL_SECONDS) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": _check(tenant_id, key)},
            ExpiresIn=expires,
        )

    async def head(self, tenant_id: UUID, key: str) -> ObjectInfo | None:
        """Size and stored SHA-256 of an object, or None if it does not exist."""
        checked = _check(tenant_id, key)
        try:
            response = await asyncio.to_thread(
                self._client.head_object, Bucket=self.bucket, Key=checked, ChecksumMode="ENABLED"
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND:
                return None
            raise
        return ObjectInfo(size=response["ContentLength"], sha256_b64=response.get("ChecksumSHA256"))

    async def delete(self, tenant_id: UUID, key: str) -> None:
        """Idempotent: deleting a missing object succeeds."""
        checked = _check(tenant_id, key)
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=checked)

    async def ensure_bucket(self) -> None:
        """Create the bucket if it is missing. Local development and tests only: in AWS the
        bucket is created by Terraform and the workload has no permission to create one."""
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self.bucket)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in _NOT_FOUND:
                raise
            await asyncio.to_thread(self._client.create_bucket, Bucket=self.bucket)


def main() -> None:
    """`python -m lotse.core.storage ensure-bucket`: used by `make up`."""
    parser = argparse.ArgumentParser(prog="python -m lotse.core.storage")
    parser.add_argument("command", choices=["ensure-bucket"])
    parser.parse_args()
    settings = StorageSettings()
    store = ObjectStore(create_client(settings), settings.s3_bucket)
    asyncio.run(store.ensure_bucket())
    print(f"bucket {store.bucket} is ready")  # noqa: T201 - a CLI reports its result


if __name__ == "__main__":
    main()
