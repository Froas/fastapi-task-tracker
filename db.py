import os
from pathlib import Path

from sqlmodel import create_engine, SQLModel, Session

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "db.sqlite"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH}")

engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
        
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
        
        
# alembic revision --autogenerate -m "MSG" | for migration
# alembic upgrade head
