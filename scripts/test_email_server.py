#!/usr/bin/env python3
"""
MAGNACODE Email configuration test script
Specifically designed to test magnacode1.qubixvirtual.in server
"""

import sys
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.email_service import EmailService


def probe_direct_smtp_connection():
    """Probe direct SMTP connection with different methods"""

    smtp_server = "magnacode1.qubixvirtual.in"
    username = "magnacode@magnacode1.qubixvirtual.in"
    password = "Hello!@12345"

    print(f"Testing direct SMTP connection to {smtp_server}")
    print("=" * 60)

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    test_configs = [
        (587, "STARTTLS", False),
        (465, "SSL", True),
        (25, "Plain SMTP", False),
        (2525, "Alternative STARTTLS", False),
    ]

    successful_configs = []

    for port, method, use_ssl in test_configs:
        print(f"\n🔍 Testing {method} on port {port}...")
        try:
            if use_ssl:
                with smtplib.SMTP_SSL(
                    smtp_server, port, context=context, timeout=10
                ) as server:
                    server.login(username, password)
                    print(f"✅ {method} on port {port} - LOGIN SUCCESSFUL")
                    successful_configs.append((port, method, use_ssl))
            else:
                with smtplib.SMTP(smtp_server, port, timeout=10) as server:
                    if method == "STARTTLS" or port == 587:
                        server.starttls(context=context)
                    server.login(username, password)
                    print(f"✅ {method} on port {port} - LOGIN SUCCESSFUL")
                    successful_configs.append((port, method, use_ssl))
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ {method} on port {port} - AUTHENTICATION FAILED: {e}")
        except smtplib.SMTPServerDisconnected as e:
            print(f"❌ {method} on port {port} - SERVER DISCONNECTED: {e}")
        except ConnectionRefusedError as e:
            print(f"❌ {method} on port {port} - CONNECTION REFUSED: {e}")
        except Exception as e:
            print(f"❌ {method} on port {port} - ERROR: {e}")

    return successful_configs


def send_test_email(port, method, use_ssl, recipient):
    """Send a test email using the specified configuration"""

    smtp_server = "magnacode1.qubixvirtual.in"
    username = "magnacode@magnacode1.qubixvirtual.in"
    password = "Hello!@12345"
    sender_email = "magnacode@magnacode1.qubixvirtual.in"
    sender_name = "MAGNACODE Admin"

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = recipient
    msg['Subject'] = f"Email Test - MAGNACODE 2025 ({method} on port {port})"

    html_content = f"""
    <html>
    <body>
        <h2>Email Test Successful - MAGNACODE 2025</h2>
        <p>This test email was sent successfully using:</p>
        <ul>
            <li><strong>Method:</strong> {method}</li>
            <li><strong>Port:</strong> {port}</li>
            <li><strong>Server:</strong> {smtp_server}</li>
            <li><strong>Timestamp:</strong> {datetime.now()}</li>
        </ul>
        <p>Your email configuration is working correctly!</p>
        <br>
        <p>Best regards,<br>MAGNACODE 2025 System</p>
    </body>
    </html>
    """

    text_content = f"""
    Email Test Successful - MAGNACODE 2025

    This test email was sent successfully using:
    - Method: {method}
    - Port: {port}
    - Server: {smtp_server}
    - Timestamp: {datetime.now()}

    Your email configuration is working correctly!

    Best regards,
    MAGNACODE 2025 System
    """

    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(
                smtp_server, port, context=context, timeout=30
            ) as server:
                server.login(username, password)
                server.sendmail(sender_email, recipient, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, port, timeout=30) as server:
                if method == "STARTTLS" or port == 587:
                    server.starttls(context=context)
                server.login(username, password)
                server.sendmail(sender_email, recipient, msg.as_string())
        print(f"✅ Test email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"❌ Failed to send test email: {e}")
        return False


def probe_with_email_service():
    """Probe using the EmailService class"""
    print("\n🔍 Testing with EmailService class...")
    email_service = EmailService()
    if not email_service.is_configured():
        print("❌ EmailService not configured")
        return False
    print("✅ EmailService configured")
    print(f"   Server: {email_service.smtp_server}:{email_service.smtp_port}")
    if email_service.test_connection():
        print("✅ EmailService connection test successful")
        return True
    else:
        print("❌ EmailService connection test failed")
        return False


def main():
    print("MAGNACODE 2025 - Email Server Test")
    print("=" * 50)
    print("Testing magnacode1.qubixvirtual.in email server...")

    successful_configs = probe_direct_smtp_connection()
    if successful_configs:
        print(f"\n🎉 Found {len(successful_configs)} working configuration(s):")
        for port, method, use_ssl in successful_configs:
            print(f"   ✅ {method} on port {port}")

        email_service_works = probe_with_email_service()
        print("\n📧 Would you like to send a test email?")
        recipient = input(
            "Enter recipient email address (or press Enter to skip): "
        ).strip()
        if recipient:
            port, method, use_ssl = successful_configs[0]
            print(f"\nSending test email using {method} on port {port}...")
            if send_test_email(port, method, use_ssl, recipient):
                print("🎉 Test email sent successfully!")
            else:
                print("❌ Failed to send test email")

        print("\n📋 RECOMMENDATIONS:")
        print("=" * 30)
        if any(
            cfg[1] == "STARTTLS" and cfg[0] == 587 for cfg in successful_configs
        ):
            print("✅ RECOMMENDED: Use STARTTLS on port 587")
            print("   Update your email_config.ini:")
            print("   SMTPPort = 587")
        elif any(
            cfg[1] == "SSL" and cfg[0] == 465 for cfg in successful_configs
        ):
            print("✅ ALTERNATIVE: Use SSL on port 465")
            print("   Update your email_config.ini:")
            print("   SMTPPort = 465")
        if email_service_works:
            print("✅ EmailService is working correctly")
        else:
            print("⚠️  EmailService needs updates - use the improved version provided")
    else:
        print("\n❌ No working email configurations found!")
        print("\nTroubleshooting steps:")
        print("1. Verify the server hostname: magnacode1.qubixvirtual.in")
        print("2. Check username: magnacode@magnacode1.qubixvirtual.in")
        print("3. Verify the password is correct")
        print("4. Contact your hosting provider for SMTP settings")
        print("5. Check if your server IP is whitelisted")


if __name__ == "__main__":
    main()

