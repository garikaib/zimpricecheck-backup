"""
SendPulse API Email Provider

Sends emails via SendPulse REST API (recommended for transactional emails).
Uses pysendpulse library: pip install pysendpulse
"""
import logging
from typing import Optional, Dict, Any

from master.core.communications.base import (
    CommunicationProvider,
    MessageResult,
    register_provider,
)

logger = logging.getLogger(__name__)


@register_provider
class SendPulseAPIProvider(CommunicationProvider):
    """
    SendPulse Web API email provider.
    
    Configuration:
    - api_id: SendPulse API ID
    - api_secret: SendPulse API Secret
    - from_email: Sender email address
    - from_name: Sender display name
    """
    
    channel_type = "email"
    provider_name = "sendpulse_api"
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "api_id": {"type": "string", "required": True},
            "api_secret": {"type": "string", "required": True, "secret": True},
            "from_email": {"type": "string", "required": True},
            "from_name": {"type": "string", "required": False},
        }
    
    def _get_client(self):
        """Get SendPulse API client."""
        try:
            from pysendpulse.pysendpulse import PySendPulse
        except ImportError:
            raise ImportError(
                "pysendpulse is required. Install with: pip install pysendpulse"
            )
        
        return PySendPulse(
            self.config["api_id"],
            self.config["api_secret"],
            "file",  # Token storage
            "/tmp/sendpulse_tokens",
        )
    
    async def send(
        self,
        to: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        html: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResult:
        """Send email via SendPulse API."""
        try:
            client = self._get_client()
            
            from_name = self.config.get("from_name", "WordPress Backup")
            from_email = self.config["from_email"]
            
            email_data = {
                "html": html or body or "",
                "text": body or "",
                "subject": subject or "(No Subject)",
                "from": {
                    "name": from_name,
                    "email": from_email,
                },
                "to": [{"email": to}],
            }
            
            # Send email
            result = client.smtp_send_mail(email_data)
            
            if result and result.get("result"):
                message_id = result.get("id")
                logger.info(f"SendPulse email sent to {to}, id: {message_id}")
                return MessageResult(
                    success=True,
                    message_id=str(message_id) if message_id else None,
                    provider=self.provider_name,
                )
            else:
                error_msg = result.get("message", "Unknown error") if result else "No response"
                logger.error(f"SendPulse send failed: {error_msg}")
                return MessageResult(success=False, error=error_msg)
                
        except ImportError as e:
            logger.error(f"SendPulse library not installed: {e}")
            return MessageResult(success=False, error=str(e))
        except Exception as e:
            logger.exception("SendPulse send error")
            return MessageResult(success=False, error=str(e))
