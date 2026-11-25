"""Key rules and presigning. Presigning is local computation, so no server is needed."""

import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest

from lotse.core import storage
from lotse.core.ids import new_id
from lotse.core.storage import KeyOutsideTenant, ObjectStore, object_key, tenant_prefix
from lotse.settings import StorageSettings

TENANT, OTHER = new_id(), new_id()
SHA = base64.b64encode(hashlib.sha256(b"body").digest()).decode()


@pytest.fixture
def store() -> ObjectStore:
    settings = StorageSettings(
        _env_file=None,
        s3_bucket="unit-bucket",
        s3_endpoint_url="http://objects.test:9000",
        s3_access_key_id="unit-key",
        s3_secret_access_key="unit-secret",
    )
    return ObjectStore(storage.create_client(settings), settings.s3_bucket)


def test_object_key_is_under_the_tenant_prefix() -> None:
    assert object_key(TENANT, "documents", "d1", "v1") == f"tenants/{TENANT}/documents/d1/v1"
    assert tenant_prefix(TENANT) == f"tenants/{TENANT}/"


@pytest.mark.parametrize(
    "part", ["", "..", "a/b", "../x", ".hidden", "a..b", "x" * 200, "white space", "ü"]
)
def test_object_key_rejects_unsafe_parts(part: str) -> None:
    with pytest.raises(KeyOutsideTenant):
        object_key(TENANT, "documents", part)


def test_object_key_needs_a_part() -> None:
    with pytest.raises(KeyOutsideTenant):
        object_key(TENANT)


@pytest.mark.parametrize(
    "key",
    [
        f"tenants/{OTHER}/documents/d1",  # another tenant
        f"tenants/{TENANT}/",  # the prefix itself
        f"tenants/{TENANT}/../{OTHER}/documents/d1",  # climbing out
        f"tenants/{TENANT}//d1",  # empty part
        f"tenants/{TENANT}",  # no trailing slash
        "documents/d1",  # no prefix at all
        f"/tenants/{TENANT}/d1",  # leading slash
    ],
)
def test_every_operation_refuses_a_key_outside_the_tenant(store: ObjectStore, key: str) -> None:
    with pytest.raises(KeyOutsideTenant):
        store.presign_get(TENANT, key)
    with pytest.raises(KeyOutsideTenant):
        store.presign_put(TENANT, key, content_type="text/plain", content_length=4, sha256_b64=SHA)


async def test_async_operations_refuse_before_any_network_call(store: ObjectStore) -> None:
    key = object_key(OTHER, "documents", "d1")
    with pytest.raises(KeyOutsideTenant):
        await store.head(TENANT, key)
    with pytest.raises(KeyOutsideTenant):
        await store.delete(TENANT, key)


def test_put_url_signs_size_type_and_checksum(store: ObjectStore) -> None:
    key = object_key(TENANT, "documents", "d1", "v1")
    url = store.presign_put(
        TENANT, key, content_type="application/pdf", content_length=4, sha256_b64=SHA
    )
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert parts.path == f"/unit-bucket/{key}"
    signed = query["X-Amz-SignedHeaders"][0].split(";")
    assert {"content-type", "content-length", "x-amz-checksum-sha256"} <= set(signed)
    assert query["X-Amz-Expires"] == ["600"]


@pytest.mark.parametrize("bad", ["not base64!", base64.b64encode(b"short").decode()])
def test_put_url_needs_a_real_sha256(store: ObjectStore, bad: str) -> None:
    key = object_key(TENANT, "documents", "d1")
    with pytest.raises(ValueError, match="sha256"):
        store.presign_put(TENANT, key, content_type="text/plain", content_length=4, sha256_b64=bad)


def test_put_url_needs_a_positive_size(store: ObjectStore) -> None:
    key = object_key(TENANT, "documents", "d1")
    with pytest.raises(ValueError, match="content_length"):
        store.presign_put(TENANT, key, content_type="text/plain", content_length=0, sha256_b64=SHA)
