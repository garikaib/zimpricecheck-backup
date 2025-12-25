from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models
from master.core import security

router = APIRouter()


@router.get("/me", response_model=schemas.UserResponse)
def read_current_user(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current authenticated user profile.
    """
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
def create_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.UserCreate,
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Create a new user.
    """
    # Check if email already exists
    existing = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists."
        )
    
    # Create user with hashed password
    user = models.User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
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
    
    db.delete(user)
    db.commit()
    return user
