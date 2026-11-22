import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./c2c.db")

engine_args = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    engine_args["pool_size"] = 10
    engine_args["max_overflow"] = 20

engine = create_engine(DATABASE_URL, **engine_args)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

def migrate_schema():
    """Apply the small additive migrations needed by databases created before member accounts."""
    inspector = inspect(engine)
    if inspector.has_table("registrations"):
        columns = {column["name"] for column in inspector.get_columns("registrations")}
        with engine.begin() as connection:
            if "user_id" not in columns:
                connection.execute(text("ALTER TABLE registrations ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
            indexes = {index["name"] for index in inspect(connection).get_indexes("registrations")}
            if "ix_registrations_user_id" not in indexes:
                connection.execute(text("CREATE INDEX ix_registrations_user_id ON registrations (user_id)"))
