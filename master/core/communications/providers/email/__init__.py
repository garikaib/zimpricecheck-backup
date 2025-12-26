"""
Email Providers Package
"""
from master.core.communications.providers.email.smtp import SMTPProvider
from master.core.communications.providers.email.sendpulse_api import SendPulseAPIProvider

__all__ = ["SMTPProvider", "SendPulseAPIProvider"]
