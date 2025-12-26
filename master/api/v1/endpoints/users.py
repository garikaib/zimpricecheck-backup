from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models
from master.core import security
from master.core.activity_logger import log_action

router = APIRouter()


@router.get("/me", response_model=schemas.UserResponse)
def read_current_user(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current authenticated user profile.
    """
    return current_user


@router.put("/me", response_model=schemas.UserResponse)
def update_current_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.UserUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update own profile. Users cannot change their own role.
    """
    # Users cannot change their own role
    if user_in.role is not None:
        raise HTTPException(status_code=403, detail="Cannot change your own role")
    
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = security.get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    # Log profile update
    log_action(
        action=models.ActionType.PROFILE_UPDATE,
        user=current_user,
        details={"fields_updated": list(update_data.keys())},
    )
    
    return current_user


@router.get("/", response_model=schemas.UserListResponse)
def read_users(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List users based on role:
    - Super Admin: See all users
    - Node Admin: See Site Admins assigned to their nodes
    """
    if current_user.role == models.UserRole.SUPER_ADMIN:
        users = db.query(models.User).offset(skip).limit(limit).all()
        total = db.query(models.User).count()
    else:
        # Node Admin: Get Site Admins managing sites on their nodes
        node_ids = [node.id for node in current_user.nodes]
        users = (
            db.query(models.User)
            .join(models.Site, models.User.id == models.Site.admin_id)
            .filter(models.Site.node_id.in_(node_ids))
            .filter(models.User.role == models.UserRole.SITE_ADMIN)
            .distinct()
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = (
            db.query(models.User)
            .join(models.Site, models.User.id == models.Site.admin_id)
            .filter(models.Site.node_id.in_(node_ids))
            .filter(models.User.role == models.UserRole.SITE_ADMIN)
            .distinct()
            .count()
        )
    
    return {"users": users, "total": total}


@router.post("/", response_model=schemas.UserResponse)
async def create_user(
    request: Request,
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.UserCreate,
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Create a new user.
    User will receive a verification email with a code.
    """
    from datetime import datetime, timedelta
    from master.core.communications.code_generator import generate_verification_code
    from master.core.communications import send_message
    from master.core.communications.templates import render_verification_email
    
    # Check if email already exists
    existing = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists."
        )
    
    # Generate verification code
    verification_code = generate_verification_code()
    
    # Create user with hashed password
    user = models.User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        role=user_in.role,
        is_verified=False,
        email_verification_code=verification_code,
        email_verification_expires=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Send verification email
    subject, html, text = render_verification_email(verification_code, user.full_name)
    result = await send_message(
        db=db,
        channel_type=models.ChannelType.EMAIL,
        to=user.email,
        subject=subject,
        body=text,
        html=html,
        role=models.MessageRole.VERIFICATION,
    )
    
    if not result.success:
        # Log failure but don't fail the request
        import logging
        logging.getLogger(__name__).error(f"Failed to send verification email: {result.error}")
    
    # Log user creation
    log_action(
        action=models.ActionType.USER_CREATE,
        user=current_superuser,
        target_type="user",
        target_id=user.id,
        target_name=user.email,
        details={"role": str(user.role)},
    )
    
    return user


@router.get("/{user_id}", response_model=schemas.UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get user by ID.
    - Super Admin: Can view any user
    - Node Admin: Can view Site Admins on their nodes
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Permission check for non-super admins
    if current_user.role != models.UserRole.SUPER_ADMIN:
        # Node Admin can only view Site Admins on their nodes
        if user.role != models.UserRole.SITE_ADMIN:
            raise HTTPException(status_code=403, detail="Cannot view this user")
        
        # Check if user manages a site on one of current_user's nodes
        node_ids = [node.id for node in current_user.nodes]
        has_access = (
            db.query(models.Site)
            .filter(models.Site.admin_id == user.id)
            .filter(models.Site.node_id.in_(node_ids))
            .first()
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Cannot view this user")
    
    return user


@router.put("/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int,
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.UserUpdate,
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Update a user.
    - Super Admin: Can update any user
    - Node Admin: Can update Site Admins on their nodes (limited fields)
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Permission check for non-super admins
    if current_user.role != models.UserRole.SUPER_ADMIN:
        # Node Admin can only update Site Admins on their nodes
        if user.role != models.UserRole.SITE_ADMIN:
            raise HTTPException(status_code=403, detail="Cannot update this user")
        
        # Cannot change role (only Super Admin can)
        if user_in.role is not None:
            raise HTTPException(status_code=403, detail="Cannot change user role")
        
        # Check access to user's sites
        node_ids = [node.id for node in current_user.nodes]
        has_access = (
            db.query(models.Site)
            .filter(models.Site.admin_id == user.id)
            .filter(models.Site.node_id.in_(node_ids))
            .first()
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Cannot update this user")
    
    # Apply updates
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = security.get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=schemas.UserResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Delete a user.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_superuser.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    deleted_email = user.email
    
    db.delete(user)
    db.commit()
    
    # Log user deletion
    log_action(
        action=models.ActionType.USER_DELETE,
        user=current_superuser,
        target_type="user",
        target_id=user_id,
        target_name=deleted_email,
    )
    
    return user


@router.post("/{user_id}/verify-email", response_model=schemas.VerifyEmailResponse)
def verify_email(
    user_id: int,
    verify_request: schemas.VerifyEmailRequest,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Verify a user's email with the provided code.
    - For new users: verifies initial email
    - For email changes: confirms the pending email change
    """
    from datetime import datetime
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check code
    if not user.email_verification_code:
        raise HTTPException(status_code=400, detail="No pending verification")
    
    if user.email_verification_expires and user.email_verification_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification code has expired")
    
    if user.email_verification_code != verify_request.code.upper():
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Handle email change vs initial verification
    if user.pending_email:
        # Email change - update email
        old_email = user.email
        user.email = user.pending_email
        user.pending_email = None
        message = f"Email changed from {old_email} to {user.email}"
    else:
        # Initial verification
        user.is_verified = True
        message = "Email verified successfully"
    
    # Clear verification fields
    user.email_verification_code = None
    user.email_verification_expires = None
    
    db.commit()
    
    return schemas.VerifyEmailResponse(success=True, message=message)


@router.post("/{user_id}/resend-verification", response_model=schemas.VerifyEmailResponse)
async def resend_verification(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Resend the verification email for a user.
    """
    from datetime import datetime, timedelta
    from master.core.communications.code_generator import generate_verification_code
    from master.core.communications import send_message
    from master.core.communications.templates import render_verification_email, render_email_change_email
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate new code
    verification_code = generate_verification_code()
    user.email_verification_code = verification_code
    user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    
    # Determine target email and template
    if user.pending_email:
        target_email = user.pending_email
        subject, html, text = render_email_change_email(verification_code, user.pending_email, user.full_name)
    else:
        target_email = user.email
        subject, html, text = render_verification_email(verification_code, user.full_name)
    
    # Send email
    result = await send_message(
        db=db,
        channel_type=models.ChannelType.EMAIL,
        to=target_email,
        subject=subject,
        body=text,
        html=html,
        role=models.MessageRole.VERIFICATION,
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {result.error}")
    
    return schemas.VerifyEmailResponse(success=True, message="Verification email sent")


@router.post("/{user_id}/force-verify", response_model=schemas.VerifyEmailResponse)
def force_verify_email(
    user_id: int,
    confirm_request: schemas.ConfirmEmailChangeRequest,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Force verify a user's email without code.
    Requires force_verify=True in request body.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not confirm_request.force_verify:
        raise HTTPException(status_code=400, detail="force_verify must be true to use this endpoint")
    
    # Cannot force-verify own email change (must use code)
    if user.id == current_superuser.id and user.pending_email:
        raise HTTPException(
            status_code=400,
            detail="You cannot force-verify your own email change. Please use the verification code."
        )
    
    # Handle email change vs initial verification
    if user.pending_email:
        old_email = user.email
        user.email = user.pending_email
        user.pending_email = None
        message = f"Email force-changed from {old_email} to {user.email}"
    else:
        user.is_verified = True
        message = "Email force-verified successfully"
    
    # Clear verification fields
    user.email_verification_code = None
    user.email_verification_expires = None
    
    db.commit()
    
    return schemas.VerifyEmailResponse(success=True, message=message)
