import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import DATABASE_URL, ENVIRONMENT

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=(ENVIRONMENT == "development"),
    # Supabase transaction pooler (:6543) multiplexes backends per checkout and cannot
    # retain psycopg3's server-side prepared statements — disable them to avoid
    # DuplicatePreparedStatement ("_pg3_N already exists") at runtime.
    connect_args={"prepare_threshold": None},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
