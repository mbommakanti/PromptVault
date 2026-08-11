from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

#SQLALCHEMY_DATABASE_URI = "postgresql://postgres:admin@localhost:5432/PromptVaultDB"
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()