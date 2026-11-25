"""Against the local S3 server (RustFS in compose and CI)."""

import base64
import hashlib
from collections.abc import AsyncIterator

import httpx
import pytest

from lotse.core import storage
from lotse.core.ids import new_id
from lotse.core.storage import ObjectInfo, ObjectStore, object_key
from lotse.settings import Settings

BODY = b"%PDF-1.7 synthetic test document\n" * 100


def sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


@pytest.fixture
async def store(settings: Settings) -> ObjectStore:
    objects = ObjectStore(storage.create_client(settings), settings.s3_bucket)
    await objects.ensure_bucket()
    await objects.ensure_bucket()  # idempotent
    return objects


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
        yield client


async def upload(http: httpx.AsyncClient, url: str, body: bytes, sha: str) -> httpx.Response:
    headers = {"Content-Type": "application/pdf", "x-amz-checksum-sha256": sha}
    return await http.put(url, content=body, headers=headers)


async def test_presigned_upload_then_download_round_trips(
    store: ObjectStore, http: httpx.AsyncClient
) -> None:
    tenant = new_id()
    key = object_key(tenant, "documents", str(new_id()), "v1")
    sha = sha256_b64(BODY)
    put = store.presign_put(
        tenant, key, content_type="application/pdf", content_length=len(BODY), sha256_b64=sha
    )
    assert (await upload(http, put, BODY, sha)).status_code == 200

    assert await store.head(tenant, key) == ObjectInfo(size=len(BODY), sha256_b64=sha)
    got = await http.get(store.presign_get(tenant, key))
    assert got.status_code == 200
    assert got.content == BODY


async def test_store_rejects_a_body_that_does_not_match_the_signed_checksum(
    store: ObjectStore, http: httpx.AsyncClient
) -> None:
    tenant = new_id()
    key = object_key(tenant, "documents", str(new_id()), "v1")
    sha = sha256_b64(BODY)
    put = store.presign_put(
        tenant, key, content_type="application/pdf", content_length=len(BODY), sha256_b64=sha
    )
    tampered = b"X" + BODY[1:]
    assert (await upload(http, put, tampered, sha)).status_code == 400
    assert (await upload(http, put, tampered, sha256_b64(tampered))).status_code == 403
    assert await store.head(tenant, key) is None


async def test_a_signature_is_valid_for_its_own_key_only(
    store: ObjectStore, http: httpx.AsyncClient
) -> None:
    tenant = new_id()
    key = object_key(tenant, "documents", "a", "v1")
    sha = sha256_b64(BODY)
    put = store.presign_put(
        tenant, key, content_type="application/pdf", content_length=len(BODY), sha256_b64=sha
    )
    other = put.replace("/documents/a/", "/documents/b/")
    assert (await upload(http, other, BODY, sha)).status_code == 403


async def test_missing_object_and_idempotent_delete(
    store: ObjectStore, http: httpx.AsyncClient
) -> None:
    tenant = new_id()
    key = object_key(tenant, "documents", str(new_id()), "v1")
    assert await store.head(tenant, key) is None
    await store.delete(tenant, key)  # missing: no error

    sha = sha256_b64(BODY)
    put = store.presign_put(
        tenant, key, content_type="application/pdf", content_length=len(BODY), sha256_b64=sha
    )
    assert (await upload(http, put, BODY, sha)).status_code == 200
    await store.delete(tenant, key)
    assert await store.head(tenant, key) is None
