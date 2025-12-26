"""
Channel Manager

Routes messages to appropriate providers based on channel type and message role.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from master.db import models
from master.core.security import decrypt_value
from master.core.communications.base import (
    CommunicationProvider,
    MessageResult,
    get_provider_class,
)

logger = logging.getLogger(__name__)


class ChannelManager:
    """
    Manages communication channels and routes messages.
    
    Loads channel configurations from database and instantiates
    appropriate providers for sending messages.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._channel_cache: Dict[int, models.CommunicationChannel] = {}
    
    def get_channels_for_type(
        self,
        channel_type: models.ChannelType,
        role: Optional[models.MessageRole] = None,
    ) -> List[models.CommunicationChannel]:
        """
        Get active channels for a channel type, optionally filtered by role.
        
        Returns channels ordered by priority (lower = higher priority).
        """
        query = self.db.query(models.CommunicationChannel).filter(
            models.CommunicationChannel.channel_type == channel_type,
            models.CommunicationChannel.is_active == True,
        )
        
        channels = query.order_by(models.CommunicationChannel.priority).all()
        
        # Filter by role if specified
        if role:
            filtered = []
            for channel in channels:
                allowed = self._get_allowed_roles(channel)
                if role.value in allowed or not allowed:  # Empty = all roles
                    filtered.append(channel)
            channels = filtered
        
        return channels
    
    def get_default_channel(
        self,
        channel_type: models.ChannelType,
        role: Optional[models.MessageRole] = None,
    ) -> Optional[models.CommunicationChannel]:
        """Get the default channel for a type, or first available."""
        channels = self.get_channels_for_type(channel_type, role)
        
        # Try to find default
        for channel in channels:
            if channel.is_default:
                return channel
        
        # Return first available
        return channels[0] if channels else None
    
    def _get_allowed_roles(self, channel: models.CommunicationChannel) -> List[str]:
        """Parse allowed_roles JSON field."""
        if not channel.allowed_roles:
            return []
        try:
            return json.loads(channel.allowed_roles)
        except json.JSONDecodeError:
            return []
    
    def _get_decrypted_config(self, channel: models.CommunicationChannel) -> Dict[str, Any]:
        """Decrypt channel configuration."""
        if not channel.config_encrypted:
            return {}
        try:
            decrypted = decrypt_value(channel.config_encrypted)
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt channel config: {e}")
            return {}
    
    def get_provider(
        self,
        channel: models.CommunicationChannel,
    ) -> Optional[CommunicationProvider]:
        """Instantiate a provider for a channel."""
        provider_class = get_provider_class(
            channel.channel_type.value,
            channel.provider,
        )
        
        if not provider_class:
            logger.error(
                f"No provider class for {channel.channel_type.value}:{channel.provider}"
            )
            return None
        
        config = self._get_decrypted_config(channel)
        return provider_class(config)
    
    async def send_message(
        self,
        channel_type: models.ChannelType,
        to: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        html: Optional[str] = None,
        role: Optional[models.MessageRole] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResult:
        """
        Send a message using the appropriate channel.
        
        Attempts to use the default channel first, falling back to
        other channels if sending fails.
        """
        channels = self.get_channels_for_type(channel_type, role)
        
        if not channels:
            return MessageResult(
                success=False,
                error=f"No active {channel_type.value} channels configured",
            )
        
        last_error = None
        for channel in channels:
            provider = self.get_provider(channel)
            if not provider:
                continue
            
            try:
                result = await provider.send(
                    to=to,
                    subject=subject,
                    body=body,
                    html=html,
                    template_id=template_id,
                    template_data=template_data,
                )
                
                if result.success:
                    result.provider = channel.name
                    logger.info(
                        f"Message sent via {channel.name} to {to}"
                    )
                    return result
                else:
                    last_error = result.error
                    logger.warning(
                        f"Failed to send via {channel.name}: {result.error}"
                    )
            except Exception as e:
                last_error = str(e)
                logger.exception(f"Error sending via {channel.name}")
        
        return MessageResult(
            success=False,
            error=last_error or "All channels failed",
        )


# Singleton pattern for convenience
_manager: Optional[ChannelManager] = None


def get_channel_manager(db: Session) -> ChannelManager:
    """Get or create the channel manager."""
    return ChannelManager(db)


async def send_message(
    db: Session,
    channel_type: models.ChannelType,
    to: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    html: Optional[str] = None,
    role: Optional[models.MessageRole] = None,
    template_id: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
) -> MessageResult:
    """Convenience function to send a message."""
    manager = get_channel_manager(db)
    return await manager.send_message(
        channel_type=channel_type,
        to=to,
        subject=subject,
        body=body,
        html=html,
        role=role,
        template_id=template_id,
        template_data=template_data,
    )
