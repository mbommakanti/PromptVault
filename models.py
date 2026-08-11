from database import Base, engine, SessionLocal
from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime, Text, JSON, func, UniqueConstraint
from sqlalchemy.orm import relationship
import sqlalchemy as sa

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True,index=True)
    email = Column(String,unique=True,index=True)
    hashed_password = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    is_active = Column(Boolean,default=True)
    role = Column(String, default="user")

class Prompt(Base):
    versions = relationship("PromptVersion",back_populates="prompt",order_by="PromptVersion.version_number")
    __tablename__ = "prompts"

    id = Column(Integer,primary_key=True,index=True)
    owner_id = Column(Integer, ForeignKey("users.id"),nullable=False)
    title = Column(String,nullable=False)
    description = Column(String)
    tags = Column(JSON, default=list)
    model_target = Column(String)
    is_published = Column(Boolean,server_default=sa.false(),nullable=False)
    current_version = Column(Integer,nullable=False,server_default=sa.text("0"))
    created_at = Column(DateTime,server_default=func.now())
    updated_at = Column(DateTime,server_default=func.now(),onupdate=func.now())
    deleted_at = Column(DateTime)

class PromptVersion(Base):
    prompt = relationship("Prompt",back_populates="versions")
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version_number", name="uq_prompt_version"),)

    id = Column(Integer,primary_key=True)
    prompt_id = Column(Integer, ForeignKey("prompts.id"))
    version_number = Column(Integer)
    content = Column(Text,nullable=False)
    created_at = Column(DateTime, server_default=func.now())

