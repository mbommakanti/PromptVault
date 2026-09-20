import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


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

class Execution(Base):
    user = relationship("User")
    prompt = relationship("Prompt")
    prompt_version = relationship("PromptVersion")
    __tablename__="executions"

    id = Column(Integer,primary_key=True)
    user_id = Column(Integer,ForeignKey("users.id"),index=True,nullable=False)
    prompt_id = Column(Integer,ForeignKey("prompts.id"),index=True,nullable=False)
    prompt_version_id = Column(Integer,ForeignKey("prompt_versions.id"),nullable=False)
    model_name = Column(Text, nullable=False)
    temperature = Column(Float,nullable=False)
    max_tokens = Column(Integer,nullable=False)
    input = Column(Text,nullable=False)
    output = Column(Text)
    error_message = Column(Text,nullable=True)
    status = Column(String, nullable=False)
    incomplete_reason = Column(String,nullable=True)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)
    provider_response_id = Column(String)
    latency_ms = Column(Integer,nullable=False)
    retry_attempts = Column(Integer,nullable=False,server_default=sa.text("1"))
    created_at = Column(DateTime, nullable=False,server_default=func.now())




