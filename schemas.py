from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PromptCreate(BaseModel):

    title:str = Field(min_length=5,max_length=100)
    content:str=Field(min_length=5,max_length=20000)
    description:str | None = Field(min_length=5,max_length=1000,default=None)
    tags:list[str] = Field(default_factory=list)
    model_target : str | None = Field(default=None)

class PromptUpdate(BaseModel):

    title:str | None = Field(default=None,min_length=5,max_length=100)
    content:str | None = Field(default=None,min_length=5,max_length=20000)
    description:str | None=Field(default=None,min_length=5,max_length=1000,)
    tags:list[str] | None=Field(default=None)
    model_target:str | None=Field(default=None)

class PromptOut(BaseModel):

    id:int
    owner_id:int
    title:str 
    description:str | None
    tags:list[str] | None
    model_target:str | None
    is_published:bool
    current_version:int
    created_at:datetime
    updated_at:datetime

    class Config:
        from_attributes = True

class PromptVersionOut(BaseModel):

    id:int
    prompt_id:int
    version_number:int
    content:str
    created_at:datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):

    username:str=Field(min_length=3)
    email:EmailStr
    password:str=Field(min_length=5)
    first_name:str
    last_name:str

class UserOut(BaseModel):

    id:int
    username:str
    email:EmailStr
    first_name:str
    last_name:str
    is_active:bool
    role:str

    class Config:
        from_attributes = True

class UserLogin(BaseModel):

    username:str
    password:str

class Token(BaseModel):

    access_token:str
    token_type:str
    expires_in:int


