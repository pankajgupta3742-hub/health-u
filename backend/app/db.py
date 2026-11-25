"""Database engine and session management (SQLite by default, PostgreSQL via DATABASE_URL)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(bind=engine)
