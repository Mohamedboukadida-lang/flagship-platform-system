"""Configuration from the environment (prefix LOTSE_). No defaults for anything secret."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """The object store. Also used alone by `python -m lotse.core.storage`."""

    model_config = SettingsConfigDict(env_prefix="LOTSE_", env_file=".env", extra="ignore")

    s3_bucket: str
    s3_region: str = "eu-central-1"
    # Set locally (RustFS); unset in AWS, where the SDK finds the real endpoint.
    s3_endpoint_url: str | None = None
    # Set locally; unset in AWS, where the SDK uses the workload's role.
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None


class Settings(StorageSettings):
    model_config = SettingsConfigDict(env_prefix="LOTSE_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "demo", "prod"] = "dev"
    # Path prefix the API is served under, e.g. "/api" behind the ingress. Empty locally.
    api_prefix: str = Field(default="", pattern=r"^(/[a-z0-9-]+)*$")

    # SQLAlchemy URL for the lotse_app role (NOBYPASSRLS).
    database_url: str
    # asyncpg DSN for the lotse_platform role (membership resolution only).
    platform_database_url: str
    redis_url: str

    oidc_issuer: str
    oidc_jwks_url: str
    oidc_audience: str = "lotse-api"

    # OTLP/HTTP traces endpoint, e.g. http://otel-collector:4318/v1/traces. Unset: no export.
    otlp_endpoint: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


class MigrationSettings(BaseSettings):
    """What migrations and the seed need: the admin URL and nothing else."""

    model_config = SettingsConfigDict(env_prefix="LOTSE_", env_file=".env", extra="ignore")

    migrations_database_url: str
