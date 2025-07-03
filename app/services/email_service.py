import logging
import configparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl

class EmailService:
    """Simple SMTP email sender."""

    def __init__(self, config_path: str = "email_config.ini"):
        self.logger = logging.getLogger(__name__)
        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        self.smtp_server = self.config.get('EMAIL', 'SMTPServer')
        self.smtp_port = self.config.getint('EMAIL', 'SMTPPort')
        self.username = self.config.get('EMAIL', 'Username')
        self.password = self.config.get('EMAIL', 'Password')
        self.sender_email = self.config.get('EMAIL', 'SenderEmail')
        self.sender_name = self.config.get('EMAIL', 'SenderName')

    def send_email(self, recipient: str, subject: str, html_message: str) -> bool:
        msg = MIMEMultipart()
        msg['From'] = f"{self.sender_name} <{self.sender_email}>"
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(html_message, 'html'))

        context = ssl.create_default_context()

        try:
            # First attempt an SSL connection (commonly used with port 465)
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(self.username, self.password)
                server.sendmail(self.sender_email, recipient, msg.as_string())
            return True
        except ConnectionRefusedError as exc:
            # If the SSL connection is refused, try STARTTLS (typically port 587)
            self.logger.warning(
                f"SMTP SSL connection to {self.smtp_server}:{self.smtp_port} failed: {exc}. "
                "Attempting STARTTLS."
            )
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.sendmail(self.sender_email, recipient, msg.as_string())
                return True
            except Exception as tls_exc:
                self.logger.error(
                    f"Failed to send email to {recipient} using STARTTLS: {tls_exc}"
                )
                return False
        except Exception as exc:
            self.logger.error(f"Failed to send email to {recipient}: {exc}")
            return False
