from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from master import schemas
from master.api import deps
from master.core import security
from master.db import models
from master.core.config import get_settings

router = APIRouter()
settings = get_settings()

@router.post("/login", response_model=schemas.Token)
def login_access_token(
    login_data: schemas.LoginRequest,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    JSON token login, get an access token for future requests.
    """
    user = db.query(models.User).filter(models.User.email == login_data.username).first()
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
