from datetime import date as dt_date, datetime, timezone
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now():
    return datetime.now(timezone.utc)

class TimestampMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

# Many-to-Many Association Table: Projects <-> Members
project_members = Table(
    "project_members",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("member_id", Integer, ForeignKey("members.id", ondelete="CASCADE"), primary_key=True)
)

class Event(TimestampMixin, Base):
    __tablename__ = "events"
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="general", index=True, nullable=False)
    date: Mapped[dt_date | None] = mapped_column(Date, nullable=True)
    venue: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    registrations: Mapped[list["Registration"]] = relationship(back_populates="event", cascade="all, delete-orphan")

class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stack: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    github: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    demo: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    image: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    team_members: Mapped[list["Member"]] = relationship(secondary=project_members, back_populates="projects")

class Member(TimestampMixin, Base):
    __tablename__ = "members"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    projects: Mapped[list[Project]] = relationship(secondary=project_members, back_populates="team_members")

class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    roll_no: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    branch: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    why: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True, nullable=False) # new | accepted | rejected

class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

class Registration(TimestampMixin, Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_event_email"),)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    event: Mapped[Event] = relationship(back_populates="registrations")
    user: Mapped["User | None"] = relationship()

class Admin(TimestampMixin, Base):
    __tablename__ = "admins"
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    hash: Mapped[str] = mapped_column(String(300), nullable=False)

class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"), UniqueConstraint("username", name="uq_users_username"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    admin_email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False) # CREATE, UPDATE, DELETE
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    changes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
