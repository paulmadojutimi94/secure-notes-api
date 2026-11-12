"""Register, log in, and 'who am I?'."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import CurrentUser, DbSession, unauthorized
from ..models import User
from ..schemas import Token, UserCreate, UserOut
from ..security import create_access_token, dummy_hash, hash_password, needs_rehash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_TAKEN = "Email already registered"
BAD_LOGIN = "Incorrect email or password"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DbSession) -> User:
    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> Token:
    email = form.username.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(form.password, dummy_hash())  # burn the same time as a real check
        raise unauthorized(BAD_LOGIN)
    if not verify_password(form.password, user.password_hash):
        raise unauthorized(BAD_LOGIN)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(form.password)
        db.commit()
    token, expires_in = create_access_token(user.id)
    return Token(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser) -> User:
    return user
