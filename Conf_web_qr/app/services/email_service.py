import logging
import configparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl
import os

class EmailService:
    """Enhanced SMTP email sender optimized for custom domain servers."""

    def __init__(self, config_path: str = "email_config.ini"):
        self.logger = logging.getLogger(__name__)
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_path):
            self.logger.error(f"Email configuration file {config_path} not found")
            self.smtp_server = None
            return

        self.config.read(config_path)

        try:
            self.smtp_server = self.config.get('EMAIL', 'SMTPServer')
            self.smtp_port = self.config.getint('EMAIL', 'SMTPPort')
            self.username = self.config.get('EMAIL', 'Username')
            self.password = self.config.get('EMAIL', 'Password')
            self.sender_email = self.config.get('EMAIL', 'SenderEmail')
            self.sender_name = self.config.get('EMAIL', 'SenderName')

            self.logger.info(
                f"Email service configured with SMTP server: {self.smtp_server}:{self.smtp_port}"
            )
        except Exception as e:
            self.logger.error(f"Error reading email configuration: {e}")
            self.smtp_server = None

    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return self.smtp_server is not None

    def send_email(self, recipient: str, subject: str, html_message: str) -> bool:
        """Email sending is disabled for this project. No messages are sent."""
        try:
            self.logger.info(
                f"Email sending disabled; skipping send to {recipient} with subject '{subject}'"
            )
        except Exception:
            # Ensure we never raise from a no-op
            pass
        return True

    def test_connection(self) -> bool:
        """Always disabled: no email connections are attempted."""
        try:
            self.logger.info("Email service disabled; skipping connection test")
        except Exception:
            pass
        return False

    def get_connection_info(self) -> dict:
        """Get current connection information for debugging"""
        return {
            "configured": self.is_configured(),
            "smtp_server": getattr(self, 'smtp_server', None),
            "smtp_port": getattr(self, 'smtp_port', None),
            "username": getattr(self, 'username', None),
            "sender_email": getattr(self, 'sender_email', None),
            "sender_name": getattr(self, 'sender_name', None),
        }
