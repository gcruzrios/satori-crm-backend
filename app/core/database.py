from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def _asyncpg_url(raw_url: str) -> tuple[str, dict]:
    """asyncpg rejects libpq-only query params like sslmode/channel_binding."""
    parts = urlsplit(raw_url)
    query = parse_qs(parts.query)
    needs_ssl = query.pop("sslmode", [None])[0] not in (None, "disable")
    query.pop("channel_binding", None)
    clean_url = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
    connect_args = {"ssl": True} if needs_ssl else {}
    return clean_url, connect_args


settings = get_settings()
_db_url, _connect_args = _asyncpg_url(settings.database_url)
engine = create_async_engine(_db_url, echo=False, future=True, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def test_db_connection() -> bool:
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
