from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.types import TypeDecorator, String
import uuid
from app.core.config import settings

# Cross-database UUID type (works with SQLite and PostgreSQL)
class GUID(TypeDecorator):
    """Platform-independent GUID type. Uses String for SQLite, UUID for PostgreSQL."""
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)

# Switch to SQLite if the URL is postgresql (for local dev without Docker)
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql") and "sqlite" not in _db_url:
    print("[DB] PostgreSQL configured but not available. Falling back to SQLite for local dev.")
    _db_url = "sqlite+aiosqlite:///./novel_workstation.db"

engine = create_async_engine(_db_url, echo=settings.DEBUG)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"[DB] Warning: Could not initialize database: {e}")
        print(f"[DB] The server will start but DB operations will fail.")
        print(f"[DB] Make sure PostgreSQL is running, or set DATABASE_URL to a SQLite URL.")