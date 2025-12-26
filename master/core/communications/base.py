"""
Base Communication Channel

Abstract base class for all communication providers.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MessageResult:
    """Result of sending a message."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None


class CommunicationProvider(ABC):
    """
    Abstract base class for communication providers.
    
    Each provider must implement:
    - channel_type: Type of channel (email, sms, etc.)
    - provider_name: Provider identifier
    - send(): Send a message
    - validate_config(): Check if config is valid
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with decrypted configuration."""
        self.config = config
    
    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Return channel type (email, sms, whatsapp, push)."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name (sendpulse_api, smtp, twilio)."""
        pass
    
    @abstractmethod
    async def send(
        self,
        to: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        html: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResult:
        """
        Send a message.
        
        Args:
            to: Recipient address (email, phone number)
            subject: Message subject (for email)
            body: Plain text body
            html: HTML body (for email)
            template_id: Provider template ID (optional)
            template_data: Data for template (optional)
        
        Returns:
            MessageResult with success status
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Return JSON schema for provider configuration.
        
        Example:
        {
            "api_id": {"type": "string", "required": True},
            "api_secret": {"type": "string", "required": True, "secret": True},
        }
        """
        pass
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration against schema.
        
        Returns (is_valid, error_messages)
        """
        schema = cls.get_config_schema()
        errors = []
        
        for key, spec in schema.items():
            if spec.get("required") and key not in config:
                errors.append(f"Missing required config: {key}")
            elif key in config:
                expected_type = spec.get("type", "string")
                if expected_type == "string" and not isinstance(config[key], str):
                    errors.append(f"Config {key} must be a string")
                elif expected_type == "integer" and not isinstance(config[key], int):
                    errors.append(f"Config {key} must be an integer")
        
        return len(errors) == 0, errors


# Registry of available providers
_providers: Dict[str, type] = {}


def register_provider(provider_class: type):
    """Register a communication provider class."""
    key = f"{provider_class.channel_type}:{provider_class.provider_name}"
    _providers[key] = provider_class
    logger.info(f"Registered communication provider: {key}")
    return provider_class


def get_provider_class(channel_type: str, provider_name: str) -> Optional[type]:
    """Get a registered provider class."""
    key = f"{channel_type}:{provider_name}"
    return _providers.get(key)


def list_providers() -> List[str]:
    """List all registered provider keys."""
    return list(_providers.keys())
