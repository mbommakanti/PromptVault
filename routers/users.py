from fastapi import APIRouter, Depends, HTTPException
from schemas import UserCreate, UserOut, UserLogin, Token
from models import User
from auth import hash_password, verify_password, create_access_token, db_dependency
from database import get_db
from starlette import status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta


router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/signup",response_model=UserOut,status_code=status.HTTP_201_CREATED)
def create_user(db:db_dependency,user_request:UserCreate):
    user_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="User already exists"
    )
    user = db.query(User).filter(
        (User.username==user_request.username) | (User.email==user_request.email)
     ).first()
    if user:
        raise user_exception
    new_user = User(
        username = user_request.username,
        email = user_request.email,
        hashed_password = hash_password(user_request.password),
        first_name  = user_request.first_name,
        last_name = user_request.last_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/token",response_model=Token,status_code=status.HTTP_200_OK)
def user_login(db:db_dependency,form_data:OAuth2PasswordRequestForm=Depends()):
    user_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Username or Password"
    )
    user = db.query(User).filter(
        (User.username==form_data.username)
    ).first()
    if not user:
        raise user_exception   
    password = form_data.password
    if verify_password(password,user.hashed_password):
        token_data = {
            "sub":user.username,
            "user_id":user.id,
            "role":user.role
        }
        access_token = create_access_token(token_data,timedelta(minutes=10))
        return Token(access_token=access_token,token_type="bearer",expires_in=600)
    raise user_exception
    
