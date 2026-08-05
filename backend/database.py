from sqlmodel import SQLModel, create_engine, Session

sqlite_url = "sqlite:///./app.db"
engine = create_engine(sqlite_url)

def create_db_and_tables():
    # Import models here to avoid circular imports and ensure they are registered
    import models 
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
