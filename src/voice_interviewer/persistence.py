from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from voice_interviewer.domain import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    FailureCode,
    Session,
    SessionState,
)
from voice_interviewer.errors import InvalidTransitionError


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    meeting_url: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    resume_name: Mapped[str] = mapped_column(Text)
    job_description_name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    events: Mapped[list[SessionEventRow]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class SessionEventRow(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    state: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    session: Mapped[SessionRow] = relationship(back_populates="events")


def _as_domain(row: SessionRow) -> Session:
    return Session(
        id=__import__("uuid").UUID(row.id),
        meeting_url=row.meeting_url,
        duration_minutes=row.duration_minutes,
        resume_name=row.resume_name,
        job_description_name=row.job_description_name,
        state=SessionState(row.state),
        created_at=row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
        updated_at=row.updated_at.replace(tzinfo=row.updated_at.tzinfo or UTC),
        consented_at=row.consented_at,
        ended_at=row.ended_at,
        failure_code=FailureCode(row.failure_code) if row.failure_code else None,
        failure_detail=row.failure_detail,
    )


class SqlAlchemySessionRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def create(self, session: Session) -> Session:
        row = SessionRow(
            id=str(session.id),
            meeting_url=session.meeting_url,
            duration_minutes=session.duration_minutes,
            resume_name=session.resume_name,
            job_description_name=session.job_description_name,
            state=session.state,
            created_at=session.created_at,
            updated_at=session.updated_at,
            consented_at=session.consented_at,
            ended_at=session.ended_at,
        )
        row.events.append(
            SessionEventRow(
                state=session.state,
                occurred_at=session.created_at,
                detail="Session created",
            )
        )
        async with self.sessions() as db:
            db.add(row)
            await db.commit()
        return session

    async def get(self, session_id: str) -> Session | None:
        async with self.sessions() as db:
            row = await db.get(SessionRow, session_id)
            return _as_domain(row) if row else None

    async def transition(
        self,
        session_id: str,
        target: SessionState,
        *,
        detail: str | None = None,
    ) -> Session:
        async with self.sessions() as db, db.begin():
            row = await db.get(SessionRow, session_id)
            if row is None:
                raise LookupError(session_id)
            current = SessionState(row.state)
            if target not in ALLOWED_TRANSITIONS[current]:
                raise InvalidTransitionError(f"Cannot transition from {current} to {target}")
            now = datetime.now(UTC)
            row.state = target
            row.updated_at = now
            if target in TERMINAL_STATES:
                row.ended_at = now
            db.add(
                SessionEventRow(
                    session_id=session_id,
                    state=target,
                    occurred_at=now,
                    detail=detail,
                )
            )
        return _as_domain(row)

    async def set_consent(self, session_id: str) -> Session:
        async with self.sessions() as db, db.begin():
            row = await db.get(SessionRow, session_id)
            if row is None:
                raise LookupError(session_id)
            row.consented_at = datetime.now(UTC)
            row.updated_at = row.consented_at
        return _as_domain(row)

    async def fail(self, session_id: str, code: str, detail: str) -> Session:
        async with self.sessions() as db, db.begin():
            row = await db.get(SessionRow, session_id)
            if row is None:
                raise LookupError(session_id)
            current = SessionState(row.state)
            if current in TERMINAL_STATES:
                return _as_domain(row)
            now = datetime.now(UTC)
            row.state = SessionState.FAILED
            row.updated_at = now
            row.ended_at = now
            row.failure_code = code
            row.failure_detail = detail
            db.add(
                SessionEventRow(
                    session_id=session_id,
                    state=SessionState.FAILED,
                    occurred_at=now,
                    detail=f"{code}: {detail}",
                )
            )
        return _as_domain(row)

    async def has_active(self) -> bool:
        terminal = tuple(state.value for state in TERMINAL_STATES)
        async with self.sessions() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(SessionRow)
                .where(SessionRow.state.not_in(terminal))
            )
        return bool(count)

    async def fail_interrupted(self) -> int:
        terminal = tuple(state.value for state in TERMINAL_STATES)
        async with self.sessions() as db, db.begin():
            rows = list(
                await db.scalars(select(SessionRow).where(SessionRow.state.not_in(terminal)))
            )
            now = datetime.now(UTC)
            for row in rows:
                row.state = SessionState.FAILED
                row.updated_at = now
                row.ended_at = now
                row.failure_code = FailureCode.INTERNAL_ERROR
                row.failure_detail = "Service restarted during the interview"
                db.add(
                    SessionEventRow(
                        session_id=row.id,
                        state=SessionState.FAILED,
                        occurred_at=now,
                        detail=row.failure_detail,
                    )
                )
        return len(rows)

    async def delete(self, session_id: str) -> bool:
        async with self.sessions() as db, db.begin():
            result = await db.execute(delete(SessionRow).where(SessionRow.id == session_id))
        return bool(cast(CursorResult[Any], result).rowcount)
