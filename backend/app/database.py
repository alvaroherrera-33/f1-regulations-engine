"""Database connection and session management."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Create async engine
# Pool notes for Render free tier (single asyncio worker):
# - pool_size=2 / max_overflow=0: two connections cover concurrent asyncio coroutines
#   on the single worker; avoids opening excess Supabase Session Pooler slots.
# - pool_recycle=300: recycle connections every 5 min to avoid Supabase idle timeouts.
# - pool_pre_ping intentionally omitted: with asyncpg, pre_ping fires during the
#   session's lazy connection provisioning phase.  If a second coroutine hits
#   execute() while the ping is in flight, SQLAlchemy raises
#   "This session is provisioning a new connection; concurrent operations are not
#   permitted" — a warning that degrades FTS quality.  The sequential retrieval
#   (no asyncio.gather) already prevents true concurrency on the same session, so
#   pre_ping provides no additional safety here.
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.sql_echo,
    future=True,
    pool_size=2,
    max_overflow=0,
    pool_recycle=300,
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for ORM models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
