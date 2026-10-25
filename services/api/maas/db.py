import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Record(Base):
    """Demo aggregates. Stable primary keys also guard idempotent operations."""

    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Counter(Base):
    __tablename__ = "counters"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


url = os.environ.get("DATABASE_URL", "sqlite:///./maas.db")
engine = create_engine(url, **({"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}))
Session = sessionmaker(engine, expire_on_commit=False)


def initialize():
    Base.metadata.create_all(engine)
