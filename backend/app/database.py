"""Database connection and session management."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Create async engine
# Pool notes for Render free tier (single asyncio worker):
# - pool_size=2: two connections cover the concurrent requests that asyncio can
#   interleave; >2 is unnecessary and wastes Supabase Session Pooler slots.
# - max_overflow=0: never go above 2; queue instead of opening extra connections.
# - pool_pre_ping=True: validate connection health before use so a connection
#   left in a bad state by an asyncio.wait_for cancellation is discarded
#   instead of handed to the next request (root cause of intermittent 500s).
# - pool_recycle=300: recycle connections every 5 minutes to avoid Supabase
#   session-pooler idle timeouts (default 30 min but conservative is safer).
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.sql_echo,
    future=True,
    pool_size=2,
    max_overflow=0,
    pool_pre_ping=True,
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
