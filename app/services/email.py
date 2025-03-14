# Example of email service (email.py)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Email sending service for guest communication"""
    
    def __init__(self, smtp_server, smtp_port, username, password, sender):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender
    
    def send_email(self, recipient, subject, html_content, text_content=None):
        """Send an email with HTML and optional text content"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender
            msg['To'] = recipient
            
            # Add text part if provided, otherwise generate from HTML
            if text_content is None:
                # Simple HTML to text conversion
                text_content = html_content.replace('<br>', '\n').replace('</p>', '\n').replace('</div>', '\n')
                # Remove HTML tags
                import re
                text_content = re.sub('<[^<]+?>', '', text_content)
            
            # Attach parts
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                
            logger.info(f"Email sent to {recipient}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_bulk_email(self, recipients, subject, html_content, text_content=None):
        """Send emails to multiple recipients"""
        results = []
        for recipient in recipients:
            success = self.send_email(recipient, subject, html_content, text_content)
            results.append((recipient, success))
        
        return results