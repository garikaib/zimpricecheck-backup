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
    
    # Check if user email is verified
    if not user.is_verified:
        logger.warning(f"[LOGIN] Unverified user attempted login: {login_data.username}")
        log_action(
            action=models.ActionType.LOGIN_FAILED,
            request=request,
            user=user,
            details={"reason": "email_not_verified"},
        )
        raise HTTPException(status_code=403, detail="Email not verified. Please check your inbox for the verification code.")
    
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


@router.post("/magic-link", response_model=schemas.MagicLinkResponse)
async def request_magic_link(
    request: Request,
    magic_link_data: schemas.MagicLinkRequest,
    db: Session = Depends(deps.get_db),
):
    """
    Request a magic link for passwordless login.
    """
    from datetime import datetime
    from master.core.communications.code_generator import generate_magic_link_token
    from master.core.communications import send_message
    from master.core.communications.templates import render_magic_link_email
    
    user = db.query(models.User).filter(models.User.email == magic_link_data.email).first()
    
    # Always return success to prevent email enumeration
    if not user or not user.is_active:
        logger.info(f"[MAGIC_LINK] No valid user for: {magic_link_data.email}")
        return schemas.MagicLinkResponse(
            success=True,
            message="If the email exists, a login link will be sent.",
        )
    
    # Generate token
    token = generate_magic_link_token()
    user.magic_link_token = token
    user.magic_link_expires = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    # Build login URL
    base_url = request.headers.get("origin", "https://wp.zimpricecheck.com")
    login_url = f"{base_url}/auth/magic-link?token={token}"
    
    # Send email
    subject, html, text = render_magic_link_email(login_url, user.full_name)
    result = await send_message(
        db=db,
        channel_type=models.ChannelType.EMAIL,
        to=user.email,
        subject=subject,
        body=text,
        html=html,
        role=models.MessageRole.LOGIN_LINK,
    )
    
    if not result.success:
        logger.error(f"[MAGIC_LINK] Failed to send email: {result.error}")
    
    return schemas.MagicLinkResponse(
        success=True,
        message="If the email exists, a login link will be sent.",
    )


@router.get("/magic-link/{token}", response_model=schemas.Token)
def login_with_magic_link(
    request: Request,
    token: str,
    db: Session = Depends(deps.get_db),
):
    """
    Login using a magic link token.
    """
    from datetime import datetime
    
    user = db.query(models.User).filter(
        models.User.magic_link_token == token,
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired login link")
    
    if not user.magic_link_expires or user.magic_link_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Login link has expired")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User account is inactive")
    
    # Clear magic link token
    user.magic_link_token = None
    user.magic_link_expires = None
    
    # Mark as verified if not already (magic link confirms email ownership)
    if not user.is_verified:
        user.is_verified = True
    
    db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires,
    )
    
    logger.info(f"[MAGIC_LINK] Login successful for: {user.email}")
    log_action(
        action=models.ActionType.LOGIN,
        user=user,
        request=request,
        details={"method": "magic_link"},
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
