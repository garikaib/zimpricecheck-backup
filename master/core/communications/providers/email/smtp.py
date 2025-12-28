"""
SMTP Email Provider

Standard SMTP email sender supporting TLS/SSL.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List, Tuple
import logging

from master.core.communications.base import (
    CommunicationProvider,
    MessageResult,
    register_provider,
)

logger = logging.getLogger(__name__)


@register_provider
class SMTPProvider(CommunicationProvider):
    """
    SMTP email provider.
    
    Configuration:
    - host: SMTP server hostname
    - port: SMTP port (25, 465, 587)
    - encryption: "tls", "ssl", or "none"
    - username: SMTP username
    - password: SMTP password
    - from_email: Sender email address
    - from_name: Sender display name
    """
    
    channel_type = "email"
    provider_name = "smtp"
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "host": {"type": "string", "required": True},
            "port": {"type": "integer", "required": True},
            "encryption": {"type": "string", "required": False},  # tls, ssl, none
            "username": {"type": "string", "required": True},
            "password": {"type": "string", "required": True, "secret": True},
            "from_email": {"type": "string", "required": True},
            "from_name": {"type": "string", "required": False},
        }
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        is_valid, errors = super().validate_config(config)
        
        # Additional validation
        if "from_email" in config:
            if not cls.validate_email_address(config["from_email"]):
                errors.append("Invalid 'from_email' format")
                is_valid = False
                
        return is_valid, errors
    
    async def send(
        self,
        to: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        html: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResult:
        """Send email via SMTP."""
        try:
            # Build message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject or "(No Subject)"
            msg["To"] = to
            
            from_name = self.config.get("from_name", "")
            from_email = self.config["from_email"]
            if from_name:
                msg["From"] = f"{from_name} <{from_email}>"
            else:
                msg["From"] = from_email
            
            # Add body parts
            if body:
                msg.attach(MIMEText(body, "plain", "utf-8"))
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))
            
            # Connect and send
            host = self.config["host"]
            port = int(self.config["port"])
            encryption = self.config.get("encryption", "tls").lower()
            
            if encryption == "ssl":
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=context)
            else:
                server = smtplib.SMTP(host, port)
                if encryption == "tls":
                    server.starttls()
            
            server.login(self.config["username"], self.config["password"])
            server.sendmail(from_email, [to], msg.as_string())
            server.quit()
            
            logger.info(f"SMTP email sent to {to}")
            return MessageResult(success=True, provider=self.provider_name)
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth error: {e}")
            return MessageResult(success=False, error="SMTP authentication failed")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return MessageResult(success=False, error=str(e))
        except Exception as e:
            logger.exception(f"SMTP send error")
            return MessageResult(success=False, error=str(e))
