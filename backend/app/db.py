from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Text, JSON, ForeignKey, Integer, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL

def uid(): return uuid4().hex

def now(): return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

engine = create_engine(DATABASE_URL, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False, 'timeout': 30}} if DATABASE_URL.startswith('sqlite') else {}))
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_settings(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class Record:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
class User(Record, Base):
    __tablename__ = 'users'
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default='tester')
class Project(Record, Base):
    __tablename__ = 'projects'
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default='')
    base_url: Mapped[str] = mapped_column(String(500))
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
class Requirement(Record, Base):
    __tablename__ = 'requirements'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    points: Mapped[list] = mapped_column(JSON)
class Generation(Record, Base):
    __tablename__ = 'generations'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey('requirements.id'))
    method: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40))
    input_hash: Mapped[str] = mapped_column(String(64))
    duration_ms: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
class Case(Record, Base):
    __tablename__ = 'cases'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey('requirements.id'))
    generation_id: Mapped[str | None] = mapped_column(ForeignKey('generations.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    version: Mapped[int] = mapped_column(Integer, default=1)
    body: Mapped[dict] = mapped_column(JSON)
class Revision(Record, Base):
    __tablename__ = 'case_revisions'
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    body: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text, default='')
class Run(Record, Base):
    __tablename__ = 'runs'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    browser: Mapped[str] = mapped_column(String(20))
    repeat: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
class Result(Record, Base):
    __tablename__ = 'results'
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'))
    ordinal: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[dict] = mapped_column(JSON)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
class Audit(Record, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
class Experiment(Record, Base):
    __tablename__ = 'experiments'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    method: Mapped[str] = mapped_column(String(32))
    observations: Mapped[dict] = mapped_column(JSON)

def serialize(obj):
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns}
