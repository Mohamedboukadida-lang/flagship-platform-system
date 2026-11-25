"""Process-wide clients, opened and closed by the app lifespan."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from lotse.core import db, storage
from lotse.core.auth import TokenVerifier
from lotse.settings import Settings


class Resources:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    platform_db: db.PlatformDB
    redis: Redis
    verifier: TokenVerifier
    objects: storage.ObjectStore

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def start(self) -> None:
        settings = self.settings
        self.verifier = TokenVerifier(
            jwks_url=settings.oidc_jwks_url,
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
        )
        self.engine = db.create_engine(settings.database_url)
        self.session_factory = db.create_session_factory(self.engine)
        self.redis = Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2)
        self.objects = storage.ObjectStore(storage.create_client(settings), settings.s3_bucket)
        self.platform_db = await db.PlatformDB.connect(settings.platform_database_url)

    async def stop(self) -> None:
        await self.platform_db.close()
        await self.redis.aclose()
        await self.engine.dispose()
