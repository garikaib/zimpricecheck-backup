from datetime import timedelta, datetime
from typing import Any
import logging
import random
import string
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from master import schemas
from master.api import deps
from master.core import security
from master.db import models
from master.core.config import get_settings
from master.core.activity_logger import log_action, get_client_ip
from master.core.turnstile import verify_turnstile_token, get_turnstile_secret, is_turnstile_enabled
from master.core.rate_limiter import limiter
from master.core.communications.manager import ChannelManager

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()

@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
async def login_access_token(
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
        # Use unified error message to prevent enumeration
        logger.warning(f"[LOGIN] Failed login attempt for: {login_data.username}")
        log_action(
            action=models.ActionType.LOGIN_FAILED,
            request=request,
            user_email=login_data.username,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    if not user.is_active:
        # Unified error messages
        logger.warning(f"[LOGIN] Inactive user attempted login: {login_data.username}")
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # MFA Check
    if user.mfa_enabled:
        # Generate OTP
        otp = ''.join(random.choices(string.digits, k=6))
        user.login_otp = otp
        user.login_otp_expires = datetime.utcnow() + timedelta(minutes=5)
        db.commit()
        
        # Send OTP via preferred channel
        try:
            comm_manager = ChannelManager(db)
            channel = None
            if user.mfa_channel_id:
                channel = db.query(models.CommunicationChannel).filter(models.CommunicationChannel.id == user.mfa_channel_id).first()
            
            # Fallback to default email if specific channel not set or not found
            if not channel:
                # Find default email channel
                channel = db.query(models.CommunicationChannel).filter(
                    models.CommunicationChannel.type == "email",
                    models.CommunicationChannel.is_default == True
                ).first()
            
            if channel:
                # Get provider and send directly
                provider = comm_manager.get_provider(channel)
                if provider:
                    await provider.send(
                        to=user.email,
                        subject="Your Login Verification Code",
                        body=f"Your verification code is: {otp}. It expires in 5 minutes.",
                        template_data={"otp": otp}
                    )
                else:
                    logger.error(f"[MFA] No provider found for channel {channel.name}")
                    raise HTTPException(status_code=500, detail="MFA configuration error: Invalid provider")
            else:
                 logger.error(f"[MFA] No channel found for user {user.id}")
                 raise HTTPException(status_code=500, detail="MFA configuration error: No sending channel")

        except Exception as e:
            logger.error(f"[MFA] Failed to send OTP: {e}")
            raise HTTPException(status_code=500, detail="Failed to send verification code")

        # Create temporary MFA token
        mfa_token = security.create_access_token(
            data={"sub": user.email, "scope": "mfa_pending"},
            expires_delta=timedelta(minutes=5)
        )
        
        # Return 202 Accepted with mfa info
        # Note: We return JSON with access_token as empty string or specific structure?
        # Standard OAUTH2 expects access_token. We can use a different response model or overload it.
        # But for strictly following schemas.Token, we can provide mfa_token there.
        return schemas.Token(
            access_token="", 
            token_type="bearer", 
            mfa_required=True, 
            mfa_token=mfa_token
        )

    # Check if user email is verified (only checks if MFA was NOT enabled, 
    # logic flow: if MFA enabled, we verify 2nd factor THEN check email verified status in verify_mfa?
    # Or check email verified BEFORE sending OTP? 
    # Better to check email verif BEFORE MFA.
    
    # Check if user email is verified
    if not user.is_verified:
        logger.warning(f"[LOGIN] Unverified user attempted login: {login_data.username}")
        log_action(
            action=models.ActionType.LOGIN_FAILED,
            request=request,
            user=user,
            details={"reason": "email_not_verified"},
        )
        # Create verification token for IDOR protection
        verification_token = security.create_access_token(
            data={"sub": user.email, "scope": "verification_flow"},
            expires_delta=timedelta(minutes=15)
        )
        
        # Return structured error with token
        raise HTTPException(
            status_code=403,
            detail={
                "error": "email_not_verified",
                "message": "Email not verified. Please enter your verification code.",
                "email": user.email,
                "verification_token": verification_token,
            }
        )
    
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
@limiter.limit("3/hour")
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


@router.post("/verify-email", response_model=schemas.VerifyEmailResponse)
@limiter.limit("5/minute")
def verify_email_public(
    request: Request,
    # user_id verification removed to prevent IDOR
    verify_request: schemas.VerifyEmailRequest,
    token: str = None, # Token can be passed in query or body (verify_request.token)
    db: Session = Depends(deps.get_db),
):
    """
    Public endpoint for users to verify their email after login attempt.
    Requires verification token from login 403 response.
    """
    from datetime import datetime
    from jose import jwt, JWTError
    
    # Check if token is in body (preferred) or query
    verification_token = verify_request.token or token
    
    if not verification_token:
        raise HTTPException(status_code=400, detail="Missing verification token")
    
    try:
        payload = jwt.decode(verification_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        scope: str = payload.get("scope")
        
        if not email or scope != "verification_flow":
            raise HTTPException(status_code=401, detail="Invalid verification token")
            
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_verified:
        return schemas.VerifyEmailResponse(success=True, message="Email already verified")
    
    # Check code
    if not user.email_verification_code:
        raise HTTPException(status_code=400, detail="No verification code found. Please request a new one.")
    
    if user.email_verification_expires and user.email_verification_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")
    
    if user.email_verification_code.upper() != verify_request.code.upper():
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Mark as verified
    user.is_verified = True
    user.email_verification_code = None
    user.email_verification_expires = None
    db.commit()
    
    logger.info(f"[VERIFY] Email verified for: {user.email}")
    log_action(
        action=models.ActionType.PROFILE_UPDATE,
        user=user,
        request=request,
        details={"action": "email_verified"},
    )
    
    return schemas.VerifyEmailResponse(success=True, message="Email verified successfully. You can now log in.")


@router.post("/mfa/verify", response_model=schemas.Token)
@limiter.limit("5/minute")
def verify_mfa(
    request: Request,
    verify_request: schemas.MfaVerifyRequest,
    db: Session = Depends(deps.get_db),
):
    """
    Verify MFA OTP and return access token.
    If scope is 'mfa_setup', also enables MFA for the user.
    """
    from jose import jwt, JWTError
    from datetime import datetime
    
    if not verify_request.mfa_token:
        raise HTTPException(status_code=400, detail="Missing MFA token")

    try:
        payload = jwt.decode(verify_request.mfa_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        scope: str = payload.get("scope")
        
        # Accept both pending (login) and setup (enable) scopes
        if not email or scope not in ["mfa_pending", "mfa_setup"]:
            raise HTTPException(status_code=401, detail="Invalid MFA token")
            
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA token")
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Verify OTP
    if not user.login_otp or not user.login_otp_expires:
        raise HTTPException(status_code=400, detail="Invalid request")
        
    if datetime.utcnow() > user.login_otp_expires:
         raise HTTPException(status_code=400, detail="OTP expired")
         
    if verify_request.code != user.login_otp:
         raise HTTPException(status_code=400, detail="Invalid OTP")
         
    # Clear OTP
    user.login_otp = None
    user.login_otp_expires = None
    
    # Enable MFA if this was a setup flow
    if scope == "mfa_setup":
        user.mfa_enabled = True
        logger.info(f"[MFA] Enabled for user {user.email}")
        log_action(
            action=models.ActionType.PROFILE_UPDATE,
            user=user,
            request=request,
            details={"action": "enable_mfa_confirmed"},
        )
        
    db.commit()
    
    # Issue real tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role, "scope": "access_token"},
        expires_delta=access_token_expires
    )
    
    return schemas.Token(access_token=access_token, token_type="bearer")


@router.post("/mfa/enable", response_model=schemas.Token)
@limiter.limit("5/minute")
async def enable_mfa(
    request: Request,
    request_data: schemas.MfaEnableRequest,
    current_user: models.User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Initiate MFA setup. Sends OTP to confirm channel.
    Does NOT enable MFA until verified.
    """
    # Verify channel exists
    channel = db.query(models.CommunicationChannel).filter(models.CommunicationChannel.id == request_data.channel_id).first()
    if not channel:
         raise HTTPException(status_code=404, detail="Channel not found")
         
    # Prepare User (but don't enable yet)
    current_user.mfa_channel_id = request_data.channel_id
    
    # Generate OTP
    otp = ''.join(random.choices(string.digits, k=6))
    current_user.login_otp = otp
    current_user.login_otp_expires = datetime.utcnow() + timedelta(minutes=5)
    db.commit()
    
    # Send OTP to confirm channel working
    try:
        comm_manager = ChannelManager(db)
        provider = comm_manager.get_provider(channel)
        if provider:
            await provider.send(
                to=current_user.email,
                subject="Confirm MFA Setup",
                body=f"Your MFA setup code is: {otp}. It expires in 5 minutes.",
                template_data={"otp": otp}
            )
        else:
            raise HTTPException(status_code=500, detail="Invalid channel provider")
            
    except Exception as e:
        logger.error(f"[MFA] Setup failed to send OTP: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification code")
    
    # Return Setup Token
    mfa_token = security.create_access_token(
        data={"sub": current_user.email, "scope": "mfa_setup"},
        expires_delta=timedelta(minutes=5)
    )
    
    return schemas.Token(
        access_token="", 
        token_type="bearer",
        mfa_required=True,
        mfa_token=mfa_token
    )
