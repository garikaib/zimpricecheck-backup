"""
Communications Module

Centralized communication system supporting multiple channels (email, SMS, WhatsApp, push)
and multiple providers (SendPulse API, SMTP, Twilio, etc.)
"""
from master.core.communications.manager import get_channel_manager, send_message
from master.core.communications.code_generator import generate_verification_code

# Import providers to trigger @register_provider decorator
from master.core.communications.providers.email import smtp, sendpulse_api  # noqa: F401

__all__ = [
    "get_channel_manager",
    "send_message", 
    "generate_verification_code",
]
