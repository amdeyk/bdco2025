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
        """Send email with multiple connection attempts optimized for custom domains"""
        if not self.is_configured():
            self.logger.warning("Email service not configured, skipping email send")
            return False

        msg = MIMEMultipart('alternative')
        msg['From'] = f"{self.sender_name} <{self.sender_email}>"
        msg['To'] = recipient
        msg['Subject'] = subject

        plain_text = html_message.replace('<br>', '\n').replace('<p>', '').replace('</p>', '\n')
        text_part = MIMEText(plain_text, 'plain')
        html_part = MIMEText(html_message, 'html')

        msg.attach(text_part)
        msg.attach(html_part)

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Method 1: STARTTLS on configured port
        try:
            self.logger.info(
                f"Attempting STARTTLS connection to {self.smtp_server}:{self.smtp_port}"
            )
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls(context=context)
                server.login(self.username, self.password)
                server.sendmail(self.sender_email, recipient, msg.as_string())
            self.logger.info(
                f"Email sent successfully to {recipient} via STARTTLS on port {self.smtp_port}"
            )
            return True
        except Exception as e:
            self.logger.warning(f"STARTTLS on port {self.smtp_port} failed: {e}")

        # Method 2: STARTTLS on port 587
        if self.smtp_port != 587:
            try:
                self.logger.info(
                    f"Attempting STARTTLS connection to {self.smtp_server}:587"
                )
                with smtplib.SMTP(self.smtp_server, 587, timeout=30) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.sendmail(self.sender_email, recipient, msg.as_string())
                self.logger.info(
                    f"Email sent successfully to {recipient} via STARTTLS on port 587"
                )
                return True
            except Exception as e:
                self.logger.warning(f"STARTTLS on port 587 failed: {e}")

        # Method 3: SSL on port 465
        if self.smtp_port != 465:
            try:
                self.logger.info(
                    f"Attempting SSL connection to {self.smtp_server}:465"
                )
                with smtplib.SMTP_SSL(
                    self.smtp_server, 465, context=context, timeout=30
                ) as server:
                    server.login(self.username, self.password)
                    server.sendmail(self.sender_email, recipient, msg.as_string())
                self.logger.info(
                    f"Email sent successfully to {recipient} via SSL on port 465"
                )
                return True
            except Exception as e:
                self.logger.warning(f"SSL on port 465 failed: {e}")

        # Method 4: SSL on configured port if it's 465
        if self.smtp_port == 465:
            try:
                self.logger.info(
                    f"Attempting SSL connection to {self.smtp_server}:{self.smtp_port}"
                )
                with smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, context=context, timeout=30
                ) as server:
                    server.login(self.username, self.password)
                    server.sendmail(self.sender_email, recipient, msg.as_string())
                self.logger.info(
                    f"Email sent successfully to {recipient} via SSL on port {self.smtp_port}"
                )
                return True
            except Exception as e:
                self.logger.warning(f"SSL on port {self.smtp_port} failed: {e}")

        # Method 5: plain SMTP on port 25
        try:
            self.logger.info(
                f"Attempting plain SMTP connection to {self.smtp_server}:25"
            )
            with smtplib.SMTP(self.smtp_server, 25, timeout=30) as server:
                server.login(self.username, self.password)
                server.sendmail(self.sender_email, recipient, msg.as_string())
            self.logger.info(
                f"Email sent successfully to {recipient} via plain SMTP on port 25"
            )
            return True
        except Exception as e:
            self.logger.warning(f"Plain SMTP on port 25 failed: {e}")

        self.logger.error(f"All email sending methods failed for {recipient}")
        return False

    def test_connection(self) -> bool:
        """Test the email connection without sending an email"""
        if not self.is_configured():
            self.logger.error("Email service not configured")
            return False

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        test_methods = [
            ("STARTTLS", self.smtp_port, "starttls"),
            ("STARTTLS", 587, "starttls") if self.smtp_port != 587 else None,
            ("SSL", 465, "ssl") if self.smtp_port != 465 else None,
            ("SSL", self.smtp_port, "ssl") if self.smtp_port == 465 else None,
        ]

        test_methods = [m for m in test_methods if m is not None]

        for method_name, port, conn_type in test_methods:
            try:
                self.logger.info(
                    f"Testing {method_name} connection to {self.smtp_server}:{port}"
                )
                if conn_type == "starttls":
                    with smtplib.SMTP(self.smtp_server, port, timeout=10) as server:
                        server.starttls(context=context)
                        server.login(self.username, self.password)
                        self.logger.info(
                            f"\u2705 Email connection test successful ({method_name} on port {port})"
                        )
                        return True
                elif conn_type == "ssl":
                    with smtplib.SMTP_SSL(
                        self.smtp_server, port, context=context, timeout=10
                    ) as server:
                        server.login(self.username, self.password)
                        self.logger.info(
                            f"\u2705 Email connection test successful ({method_name} on port {port})"
                        )
                        return True
            except Exception as e:
                self.logger.warning(
                    f"\u274c {method_name} connection test on port {port} failed: {e}"
                )

        self.logger.error("\u274c All email connection tests failed")
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
