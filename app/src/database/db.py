from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker,AsyncSession
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

#SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://postgres:pwd@postgres:5432/history_db"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL,echo=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]: 

    async with AsyncSessionLocal() as session:
        yield session