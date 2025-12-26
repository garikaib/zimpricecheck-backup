from datetime import timedelta
from typing import Any
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from master import schemas
from master.api import deps
from master.core import security
from master.db import models
from master.core.config import get_settings
from master.core.activity_logger import log_action, get_client_ip
from master.core.turnstile import verify_turnstile_token, get_turnstile_secret, is_turnstile_enabled

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()

@router.post("/login", response_model=schemas.Token)
def login_access_token(
    request: Request,
    login_data: schemas.LoginRequest,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    JSON token login, get an access token for future requests.
    """
    logger.info(f"[LOGIN] Login attempt for: {login_data.username}")
    
    # Verify Turnstile if enabled
    if is_turnstile_enabled(db):
        secret = get_turnstile_secret(db)
        if secret:
            client_ip = get_client_ip(request)
            if not login_data.turnstile_token:
                log_action(
                    action=models.ActionType.LOGIN_FAILED,
                    request=request,
                    user_email=login_data.username,
                    details={"reason": "missing_turnstile_token"},
                )
                raise HTTPException(status_code=400, detail="Turnstile verification required")
            
            if not verify_turnstile_token(login_data.turnstile_token, secret, client_ip):
                log_action(
                    action=models.ActionType.LOGIN_FAILED,
                    request=request,
                    user_email=login_data.username,
                    details={"reason": "invalid_turnstile_token"},
                )
                raise HTTPException(status_code=400, detail="Turnstile verification failed")
    
    user = db.query(models.User).filter(models.User.email == login_data.username).first()
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        logger.warning(f"[LOGIN] Failed login attempt for: {login_data.username}")
        log_action(
            action=models.ActionType.LOGIN_FAILED,
            request=request,
            user_email=login_data.username,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not user.is_active:
        logger.warning(f"[LOGIN] Inactive user attempted login: {login_data.username}")
        log_action(
            action=models.ActionType.LOGIN_FAILED,
            request=request,
            user=user,
            details={"reason": "inactive_user"},
        )
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires,
    )
    
    logger.info(f"[LOGIN] Token created successfully for: {user.email} (role: {user.role})")
    
    # Log successful login (non-blocking)
    log_action(
        action=models.ActionType.LOGIN,
        user=user,
        request=request,
        details={"role": str(user.role)},
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
