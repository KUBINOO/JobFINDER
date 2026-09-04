import os
from sqlmodel import SQLModel, create_engine, Session

from sqlalchemy import event, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
sqlite_url = f"sqlite:///{DB_PATH}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False, "timeout": 30})

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

def migrate_db():
    try:
        with engine.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(userpreferences)"))
            columns = [row[1] for row in cursor.fetchall()]
            if columns and "smtp_host" not in columns:
                conn.execute(text("ALTER TABLE userpreferences ADD COLUMN smtp_host VARCHAR DEFAULT ''"))
                conn.commit()
    except Exception:
        pass

def create_db_and_tables():
    # Import models here to avoid circular imports and ensure they are registered
    import models 
    SQLModel.metadata.create_all(engine)
    migrate_db()

def get_session():
    with Session(engine) as session:
        yield session

