from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status

from auth import create_access_token, db_dependency, hash_password, verify_password
from models import User
from rate_limit import limiter
from schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/signup",response_model=UserOut,status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_user(request:Request,db:db_dependency,user_request:UserCreate):
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
@limiter.limit("5/minute")
def user_login(request:Request,db:db_dependency,form_data:OAuth2PasswordRequestForm=Depends()):
    user_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Username or Password"
    )
    user = db.query(User).filter(
        User.username==form_data.username
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
    
