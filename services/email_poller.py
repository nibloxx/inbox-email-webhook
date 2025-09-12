"""
Email Polling Service

Polls email accounts for new emails and stores them in Firebase.
Supports IMAP for Gmail, Outlook, and other email providers.
"""

import imaplib
import email
import asyncio
import os
import base64
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging

from models.schemas import EmailDataSchema, EmailAttachmentSchema
from services.firebase_service import FirebaseService
from config.settings import settings

# Set up logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

class EmailPoller:
    """Service for polling email accounts and storing emails in Firebase"""
    
    def __init__(self):
        self.firebase_service = FirebaseService()
        self.email_host = os.getenv("EMAIL_HOST", "imap.gmail.com")
        self.email_port = int(os.getenv("EMAIL_PORT", "993"))
        self.email_username = os.getenv("EMAIL_USERNAME", "zeework98@gmail.com")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.email_use_ssl = os.getenv("EMAIL_USE_SSL", "true").lower() == "true"
        self.poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL", "60"))
        self.poll_enabled = os.getenv("EMAIL_POLL_ENABLED", "true").lower() == "true"
        
        # Log configuration
        logger.info(f"Email Poller configured for: {self.email_username}")
        logger.info(f"Email Host: {self.email_host}:{self.email_port}")
        logger.info(f"Polling enabled: {self.poll_enabled}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        
        if not all([self.email_username, self.email_password]):
            logger.warning("Email credentials not configured. Email polling will be disabled.")
            self.poll_enabled = False
    
    async def start_polling(self):
        """Start the email polling loop"""
        if not self.poll_enabled:
            logger.info("Email polling is disabled")
            return
        
        logger.info(f"Starting email polling every {self.poll_interval} seconds")
        
        while True:
            try:
                await self.poll_emails()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in email polling loop: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds before retrying
    
    async def poll_emails(self):
        """Poll for new emails and store them in Firebase"""
        try:
            # Connect to email server
            if self.email_use_ssl:
                mail = imaplib.IMAP4_SSL(self.email_host, self.email_port)
            else:
                mail = imaplib.IMAP4(self.email_host, self.email_port)
            
            # Login
            if not self.email_username or not self.email_password:
                logger.error("Email credentials are missing or empty")
                return
            
            # Ensure credentials are strings and strip whitespace
            username = str(self.email_username).strip()
            password = str(self.email_password).strip()
            
            logger.info(f"Attempting to login with username: {username}")
            try:
                mail.login(username, password)
                logger.info("Successfully logged in to email server")
            except imaplib.IMAP4.error as e:
                logger.error(f"IMAP login error: {e}")
                return
            except Exception as e:
                logger.error(f"Unexpected login error: {e}")
                return
            
            # Select inbox
            mail.select('INBOX')
            
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            
            if status != 'OK':
                logger.error("Failed to search emails")
                return
            
            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} new emails")
            
            # Process each email
            for email_id in email_ids:
                try:
                    await self.process_email(mail, email_id)
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    continue
            
            # Close connection
            mail.close()
            mail.logout()
            
        except Exception as e:
            logger.error(f"Error polling emails: {e}")
    
    async def process_email(self, mail: imaplib.IMAP4_SSL, email_id: bytes):
        """Process a single email and store it in Firebase"""
        try:
            # Fetch email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return
            
            # Parse email
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract email data
            email_data = await self.parse_email(email_message)
            
            if email_data:
                # Store in Firebase
                email_id_str = await self.firebase_service.store_email(email_data)
                logger.info(f"Stored email {email_id_str} in Firebase")
                
                # Mark as read
                mail.store(email_id, '+FLAGS', '\\Seen')
            
        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}")
    
    async def parse_email(self, email_message) -> Optional[EmailDataSchema]:
        """Parse email message and extract data"""
        try:
            # Extract basic fields
            subject = email_message.get('Subject', '')
            from_email = email_message.get('From', '')
            to_email = email_message.get('To', '')
            message_id = email_message.get('Message-ID', '')
            date_str = email_message.get('Date', '')
            
            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                received_at = parsedate_to_datetime(date_str)
            except:
                received_at = datetime.now(timezone.utc)
            
            # Extract body
            body = ""
            html_body = ""
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    # Skip attachments for now
                    if "attachment" in content_disposition:
                        continue
                    
                    if content_type == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif content_type == "text/html":
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                content_type = email_message.get_content_type()
                if content_type == "text/plain":
                    body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == "text/html":
                    html_body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Extract attachments
            attachments = []
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            content_type = part.get_content_type()
                            size = len(part.get_payload(decode=True))
                            data = base64.b64encode(part.get_payload(decode=True)).decode('utf-8')
                            
                            attachment = EmailAttachmentSchema(
                                filename=filename,
                                content_type=content_type,
                                size=size,
                                data=data
                            )
                            attachments.append(attachment)
            
            # Create email data schema
            email_data = EmailDataSchema(
                subject=subject,
                from_email=from_email,
                to_email=to_email,
                body=body,
                html_body=html_body if html_body else None,
                attachments=attachments if attachments else None,
                received_at=received_at,
                message_id=message_id,
                user_token=None  # Will be set later if needed
            )
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return None
    
    async def get_email_by_message_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get email from Firebase by message ID"""
        try:
            # This would require implementing a search by message_id in FirebaseService
            # For now, we'll return None
            return None
        except Exception as e:
            logger.error(f"Error getting email by message ID: {e}")
            return None

# Global email poller instance
email_poller = EmailPoller()
