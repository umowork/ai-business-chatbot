"""
SQLAlchemy async database engine and session management.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, event, select
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base with AsyncAttrs for async relationship loading."""
    pass


# ── Models ──────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    dialogs: Mapped[list["Dialog"]] = relationship(back_populates="user", lazy="selectin")
    leads: Mapped[list["Lead"]] = relationship(back_populates="user", lazy="selectin")


class Dialog(Base):
    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="dialogs")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    service: Mapped[str | None] = mapped_column(String(256), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    budget: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")  # new | qualified | crm_created
    crm_deal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(
        String(32), nullable=True  # sales | support | other
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="leads")


# ── Database ────────────────────────────────────────────────────────────


class Database:
    """Async database wrapper with session management."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        # SQLite WAL mode for concurrent reads
        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_tables(self):
        """Create all tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield an async session (for dependency injection)."""
        async with self.session_factory() as session:
            yield session

    # ── User operations ──────────────────────────────────────────────

    async def get_or_create_user(
        self, telegram_id: int, username: str | None, full_name: str
    ) -> User:
        async with self.session_factory() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    full_name=full_name,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
                # Update username in case it changed
                if username and user.username != username:
                    user.username = username
                    await session.commit()
            return user

    async def get_user_by_id(self, user_id: int) -> User | None:
        async with self.session_factory() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_all_users(self) -> list[User]:
        async with self.session_factory() as session:
            result = await session.execute(select(User))
            return list(result.scalars().all())

    async def update_user_phone(self, user_id: int, phone: str) -> User | None:
        async with self.session_factory() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.phone = phone
                await session.commit()
                await session.refresh(user)
            return user

    # ── Dialog operations ────────────────────────────────────────────

    async def add_dialog(self, user_id: int, role: str, content: str) -> Dialog:
        async with self.session_factory() as session:
            dialog = Dialog(user_id=user_id, role=role, content=content)
            session.add(dialog)
            await session.commit()
            await session.refresh(dialog)
            return dialog

    async def get_dialog_history(
        self, user_id: int, limit: int = 20
    ) -> list[Dialog]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Dialog)
                .where(Dialog.user_id == user_id)
                .order_by(Dialog.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_dialog_history_ordered(
        self, user_id: int, limit: int = 20
    ) -> list[Dialog]:
        """Get dialog history in chronological order (oldest first)."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(Dialog)
                .where(Dialog.user_id == user_id)
                .order_by(Dialog.created_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def clear_dialog_history(self, user_id: int) -> int:
        """Delete all dialogs for a user. Returns count of deleted records."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(Dialog).where(Dialog.user_id == user_id)
            )
            dialogs = list(result.scalars().all())
            count = len(dialogs)
            for d in dialogs:
                await session.delete(d)
            await session.commit()
            return count

    # ── Lead operations ──────────────────────────────────────────────

    async def create_lead(self, user_id: int, **kwargs) -> Lead:
        async with self.session_factory() as session:
            lead = Lead(user_id=user_id, **kwargs)
            session.add(lead)
            await session.commit()
            await session.refresh(lead)
            return lead

    async def get_lead_by_id(self, lead_id: int) -> Lead | None:
        async with self.session_factory() as session:
            result = await session.execute(select(Lead).where(Lead.id == lead_id))
            return result.scalar_one_or_none()

    async def get_leads_by_user(self, user_id: int) -> list[Lead]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Lead).where(Lead.user_id == user_id)
            )
            return list(result.scalars().all())

    async def update_lead_crm(self, lead_id: int, crm_deal_id: str):
        async with self.session_factory() as session:
            result = await session.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one()
            lead.crm_deal_id = crm_deal_id
            lead.status = "crm_created"
            await session.commit()

    async def get_all_leads(self, limit: int = 50) -> list[Lead]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Lead).order_by(Lead.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())

    async def get_leads_by_status(self, status: str, limit: int = 50) -> list[Lead]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Lead)
                .where(Lead.status == status)
                .order_by(Lead.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_stats(self) -> dict:
        """Get basic statistics for admin panel."""
        async with self.session_factory() as session:
            users_count = (
                await session.execute(select(User.id).limit(10000))
            ).scalars().all()
            leads_count = (
                await session.execute(select(Lead.id).limit(10000))
            ).scalars().all()
            dialogs_count = (
                await session.execute(select(Dialog.id).limit(100000))
            ).scalars().all()
            return {
                "users": len(users_count),
                "leads": len(leads_count),
                "dialog_messages": len(dialogs_count),
            }
