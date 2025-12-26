"""
Communications API Endpoints

CRUD for communication channels and test endpoints.
Super Admin only.
"""
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from master.api import deps
from master.db import models
from master.core.security import encrypt_value, decrypt_value
from master import schemas

router = APIRouter()
logger = logging.getLogger(__name__)


def channel_to_response(channel: models.CommunicationChannel) -> schemas.CommunicationChannelResponse:
    """Convert channel model to response schema."""
    allowed_roles = None
    if channel.allowed_roles:
        try:
            allowed_roles = json.loads(channel.allowed_roles)
        except json.JSONDecodeError:
            allowed_roles = []
    
    return schemas.CommunicationChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type.value,
        provider=channel.provider,
        allowed_roles=allowed_roles,
        is_default=channel.is_default,
        is_active=channel.is_active,
        priority=channel.priority,
        created_at=channel.created_at,
    )


@router.get("/channels", response_model=schemas.CommunicationChannelListResponse)
def list_channels(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """List all communication channels. Super Admin only."""
    channels = db.query(models.CommunicationChannel).order_by(
        models.CommunicationChannel.channel_type,
        models.CommunicationChannel.priority,
    ).all()
    
    return schemas.CommunicationChannelListResponse(
        channels=[channel_to_response(c) for c in channels],
        total=len(channels),
    )


@router.get("/channels/{channel_id}", response_model=schemas.CommunicationChannelResponse)
def get_channel(
    channel_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """Get a specific channel. Super Admin only."""
    channel = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.id == channel_id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel_to_response(channel)


@router.post("/channels", response_model=schemas.CommunicationChannelResponse)
def create_channel(
    channel_in: schemas.CommunicationChannelCreate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """Create a new communication channel. Super Admin only."""
    # Check for duplicate name
    existing = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.name == channel_in.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel name already exists")
    
    # Validate channel type
    try:
        channel_type = models.ChannelType(channel_in.channel_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid channel type: {channel_in.channel_type}")
    
    # Encrypt config
    config_encrypted = encrypt_value(json.dumps(channel_in.config))
    
    # If setting as default, unset other defaults for this type
    if channel_in.is_default:
        db.query(models.CommunicationChannel).filter(
            models.CommunicationChannel.channel_type == channel_type,
            models.CommunicationChannel.is_default == True,
        ).update({"is_default": False})
    
    channel = models.CommunicationChannel(
        name=channel_in.name,
        channel_type=channel_type,
        provider=channel_in.provider,
        config_encrypted=config_encrypted,
        allowed_roles=json.dumps(channel_in.allowed_roles) if channel_in.allowed_roles else None,
        is_default=channel_in.is_default,
        priority=channel_in.priority,
    )
    
    db.add(channel)
    db.commit()
    db.refresh(channel)
    
    logger.info(f"Created channel: {channel.name} ({channel.provider})")
    return channel_to_response(channel)


@router.put("/channels/{channel_id}", response_model=schemas.CommunicationChannelResponse)
def update_channel(
    channel_id: int,
    channel_in: schemas.CommunicationChannelUpdate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """Update a communication channel. Super Admin only."""
    channel = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.id == channel_id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Update fields
    if channel_in.name is not None:
        channel.name = channel_in.name
    
    if channel_in.config is not None:
        channel.config_encrypted = encrypt_value(json.dumps(channel_in.config))
    
    if channel_in.allowed_roles is not None:
        channel.allowed_roles = json.dumps(channel_in.allowed_roles)
    
    if channel_in.is_default is not None:
        if channel_in.is_default:
            # Unset other defaults
            db.query(models.CommunicationChannel).filter(
                models.CommunicationChannel.channel_type == channel.channel_type,
                models.CommunicationChannel.id != channel_id,
                models.CommunicationChannel.is_default == True,
            ).update({"is_default": False})
        channel.is_default = channel_in.is_default
    
    if channel_in.is_active is not None:
        channel.is_active = channel_in.is_active
    
    if channel_in.priority is not None:
        channel.priority = channel_in.priority
    
    db.commit()
    db.refresh(channel)
    
    logger.info(f"Updated channel: {channel.name}")
    return channel_to_response(channel)


@router.delete("/channels/{channel_id}")
def delete_channel(
    channel_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """Delete a communication channel. Super Admin only."""
    channel = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.id == channel_id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    db.delete(channel)
    db.commit()
    
    logger.info(f"Deleted channel: {channel.name}")
    return {"message": "Channel deleted"}


@router.post("/channels/{channel_id}/test", response_model=schemas.CommunicationTestResponse)
async def test_channel(
    channel_id: int,
    test_request: schemas.CommunicationTestRequest,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """Send a test message through a channel. Super Admin only."""
    from master.core.communications.manager import get_channel_manager
    from master.core.communications.templates import render_notification_email
    
    channel = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.id == channel_id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    manager = get_channel_manager(db)
    provider = manager.get_provider(channel)
    
    if not provider:
        raise HTTPException(status_code=400, detail="Provider not available")
    
    # Send test email
    subject, html, text = render_notification_email(
        title="Test Message",
        message="This is a test message from WordPress Backup. If you received this, your email channel is configured correctly!",
        user_name=current_user.full_name,
    )
    
    result = await provider.send(
        to=test_request.to,
        subject=subject,
        body=text,
        html=html,
    )
    
    return schemas.CommunicationTestResponse(
        success=result.success,
        message="Test message sent successfully" if result.success else f"Failed: {result.error}",
        provider=channel.name,
    )
