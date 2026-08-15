import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from models import User

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/token")
db_dependency = Annotated[Session, Depends(get_db)]

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

if not SECRET_KEY or not ALGORITHM:
        raise RuntimeError("No environment variable found for either secret key or algorithm")

def hash_password(password:str):
        return pwd_context.hash(password)

def verify_password(plain_password:str,hashed_password:str):
        return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta=timedelta(minutes=30)):
    to_encode = data.copy()   # copy, not mutate the caller's dict directly
    expires = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(db:db_dependency, token:str=Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload =jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if user_id is None or username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username==username,User.id==user_id).first()
    if user is None:
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return user
       
            
            