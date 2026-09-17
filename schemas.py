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

class AdapterResponse(BaseModel):

    model_response:str
    model_name:str
    response_status:str
    max_tokens:int
    temperature:float
    input_tokens:int
    output_tokens:int
    total_tokens:int
    incomplete_reason:str | None = None
    response_id:str

class ExecutionRequest(BaseModel):

    input:str=Field(min_length=5, max_length=2000)
    model:str | None = None
    temperature:float | None = Field(ge=0, le=2, default=None)
    max_tokens:int|None = Field(ge=16, le=10000,default=None)

class ExecutionOut(BaseModel):

    id:int
    user_id:int
    prompt_id:int
    prompt_version_id:int
    model_name:str 
    temperature:float
    max_tokens:int
    input:str
    output:str|None
    status:str
    incomplete_reason:str|None=None
    input_tokens:int|None
    output_tokens:int|None
    total_tokens:int|None
    provider_response_id:str|None
    latency_ms:int
    retry_attempts:int
    created_at:datetime

    class Config:
        from_attributes = True



