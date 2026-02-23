from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Handle SQLite-specific connection args
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Run simple schema migrations for new columns."""
    inspector = inspect(engine)

    # Check if cards table exists
    if "cards" not in inspector.get_table_names():
        return

    # Get existing columns
    columns = {col["name"] for col in inspector.get_columns("cards")}

    # Add mastered column if it doesn't exist
    if "mastered" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE cards ADD COLUMN mastered BOOLEAN DEFAULT 0"))
            conn.commit()
