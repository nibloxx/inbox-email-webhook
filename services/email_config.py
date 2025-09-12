"""
Email Configuration Service

Handles different email provider configurations and connection settings.
"""

import os
from typing import Dict, Any, Optional
from enum import Enum

class EmailProvider(Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    YAHOO = "yahoo"
    CUSTOM = "custom"

class EmailConfig:
    """Email configuration manager for different providers"""
    
    # Predefined configurations for popular email providers
    PROVIDER_CONFIGS = {
        EmailProvider.GMAIL: {
            "host": "imap.gmail.com",
            "port": 993,
            "use_ssl": True,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_use_tls": True
        },
        EmailProvider.OUTLOOK: {
            "host": "outlook.office365.com",
            "port": 993,
            "use_ssl": True,
            "smtp_host": "smtp-mail.outlook.com",
            "smtp_port": 587,
            "smtp_use_tls": True
        },
        EmailProvider.YAHOO: {
            "host": "imap.mail.yahoo.com",
            "port": 993,
            "use_ssl": True,
            "smtp_host": "smtp.mail.yahoo.com",
            "smtp_port": 587,
            "smtp_use_tls": True
        }
    }
    
    def __init__(self, provider: EmailProvider = None):
        self.provider = provider or self._detect_provider()
        self.config = self._get_config()
    
    def _detect_provider(self) -> EmailProvider:
        """Detect email provider from username"""
        username = os.getenv("EMAIL_USERNAME", "")
        
        if "@gmail.com" in username.lower():
            return EmailProvider.GMAIL
        elif "@outlook.com" in username.lower() or "@hotmail.com" in username.lower():
            return EmailProvider.OUTLOOK
        elif "@yahoo.com" in username.lower():
            return EmailProvider.YAHOO
        else:
            return EmailProvider.CUSTOM
    
    def _get_config(self) -> Dict[str, Any]:
        """Get configuration for the detected provider"""
        if self.provider == EmailProvider.CUSTOM:
            return self._get_custom_config()
        
        return self.PROVIDER_CONFIGS.get(self.provider, {})
    
    def _get_custom_config(self) -> Dict[str, Any]:
        """Get custom configuration from environment variables"""
        return {
            "host": os.getenv("EMAIL_HOST", "imap.gmail.com"),
            "port": int(os.getenv("EMAIL_PORT", "993")),
            "use_ssl": os.getenv("EMAIL_USE_SSL", "true").lower() == "true",
            "smtp_host": os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
            "smtp_use_tls": os.getenv("EMAIL_SMTP_USE_TLS", "true").lower() == "true"
        }
    
    def get_imap_config(self) -> Dict[str, Any]:
        """Get IMAP configuration"""
        return {
            "host": self.config["host"],
            "port": self.config["port"],
            "use_ssl": self.config["use_ssl"]
        }
    
    def get_smtp_config(self) -> Dict[str, Any]:
        """Get SMTP configuration"""
        return {
            "host": self.config["smtp_host"],
            "port": self.config["smtp_port"],
            "use_tls": self.config["smtp_use_tls"]
        }
    
    def get_credentials(self) -> Dict[str, str]:
        """Get email credentials"""
        return {
            "username": os.getenv("EMAIL_USERNAME", ""),
            "password": os.getenv("EMAIL_PASSWORD", "")
        }
    
    def validate_config(self) -> bool:
        """Validate email configuration"""
        credentials = self.get_credentials()
        return bool(credentials["username"] and credentials["password"])
    
    def get_connection_string(self) -> str:
        """Get connection string for logging"""
        config = self.get_imap_config()
        return f"{config['host']}:{config['port']} (SSL: {config['use_ssl']})"

# Global email config instance
email_config = EmailConfig()
