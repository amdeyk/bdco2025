#!/usr/bin/env python3
"""
MAGNACODE Email test script using correct mail server settings
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def test_email_configurations():
    """Test both SSL and non-SSL configurations"""

    # Your correct server configurations from the hosting provider
    configs = [
        {
            "name": "Secure SSL/TLS (Recommended)",
            "server": "mail.qubixvirtual.in",
            "port": 465,
            "use_ssl": True,
            "username": "magnacode@magnacode1.qubixvirtual.in",
            "password": "Hello!@12345",
        },
        {
            "name": "Non-SSL (Alternative)",
            "server": "mail.qubixvirtual.in",
            "port": 2525,
            "use_ssl": False,
            "username": "magnacode@magnacode1.qubixvirtual.in",
            "password": "Hello!@12345",
        },
    ]

    print("MAGNACODE 2025 - Correct Email Server Test")
    print("=" * 50)

    successful_configs = []

    for config in configs:
        print(f"\nTesting {config['name']}...")
        print(f"   Server: {config['server']}:{config['port']}")
        print(f"   Method: {'SSL' if config['use_ssl'] else 'Plain SMTP'}")

        try:
            # Create SSL context
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            if config['use_ssl']:
                # SSL connection (port 465)
                with smtplib.SMTP_SSL(config['server'], config['port'], context=context, timeout=10) as server:
                    server.set_debuglevel(0)
                    server.login(config['username'], config['password'])
                    print(f"\u2705 {config['name']} - LOGIN SUCCESSFUL")
                    successful_configs.append(config)
            else:
                # Plain SMTP connection (port 2525)
                with smtplib.SMTP(config['server'], config['port'], timeout=10) as server:
                    server.set_debuglevel(0)
                    server.login(config['username'], config['password'])
                    print(f"\u2705 {config['name']} - LOGIN SUCCESSFUL")
                    successful_configs.append(config)

        except smtplib.SMTPAuthenticationError as e:
            print(f"\u274c {config['name']} - AUTHENTICATION FAILED: {e}")
        except smtplib.SMTPServerDisconnected as e:
            print(f"\u274c {config['name']} - SERVER DISCONNECTED: {e}")
        except ConnectionRefusedError as e:
            print(f"\u274c {config['name']} - CONNECTION REFUSED: {e}")
        except Exception as e:
            print(f"\u274c {config['name']} - ERROR: {e}")

    return successful_configs


def send_test_email(config, recipient):
    """Send a test email using the specified configuration"""

    # Create message
    msg = MIMEMultipart('alternative')
    msg['From'] = f"MAGNACODE Admin <{config['username']}>"
    msg['To'] = recipient
    msg['Subject'] = f"Email Test - MAGNACODE 2025 ({config['name']})"

    html_content = f"""
    <html>
    <body>
        <h2>Email Test Successful - MAGNACODE 2025</h2>
        <p>This test email was sent successfully using:</p>
        <ul>
            <li><strong>Configuration:</strong> {config['name']}</li>
            <li><strong>Server:</strong> {config['server']}</li>
            <li><strong>Port:</strong> {config['port']}</li>
            <li><strong>Method:</strong> {'SSL' if config['use_ssl'] else 'Plain SMTP'}</li>
            <li><strong>Timestamp:</strong> {datetime.now()}</li>
        </ul>
        <p>Your email configuration is working correctly!</p>
        <br>
        <p>Best regards,<br>MAGNACODE 2025 Team</p>
    </body>
    </html>
    """

    text_content = f"""
    Email Test Successful - MAGNACODE 2025

    This test email was sent successfully using:
    - Configuration: {config['name']}
    - Server: {config['server']}
    - Port: {config['port']}
    - Method: {'SSL' if config['use_ssl'] else 'Plain SMTP'}
    - Timestamp: {datetime.now()}

    Your email configuration is working correctly!

    Best regards,
    MAGNACODE 2025 Team
    """

    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))

    # Create SSL context
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        if config['use_ssl']:
            with smtplib.SMTP_SSL(config['server'], config['port'], context=context, timeout=30) as server:
                server.login(config['username'], config['password'])
                server.sendmail(config['username'], recipient, msg.as_string())
        else:
            with smtplib.SMTP(config['server'], config['port'], timeout=30) as server:
                server.login(config['username'], config['password'])
                server.sendmail(config['username'], recipient, msg.as_string())

        print(f"\u2705 Test email sent successfully to {recipient}")
        return True

    except Exception as e:
        print(f"\u274c Failed to send test email: {e}")
        return False


def main():
    print("Testing MAGNACODE email server configurations...")

    # Test connections
    successful_configs = test_email_configurations()

    if successful_configs:
        print(f"\n\ud83c\udf89 Found {len(successful_configs)} working configuration(s):")
        for config in successful_configs:
            print(f"   \u2705 {config['name']} - {config['server']}:{config['port']}")

        # Recommend the best configuration
        print(f"\nRECOMMENDATIONS:")
        print("=" * 30)

        ssl_configs = [c for c in successful_configs if c['use_ssl']]
        if ssl_configs:
            recommended = ssl_configs[0]
            print(f"\u2705 RECOMMENDED: {recommended['name']}")
            print(f"   Update your email_config.ini with:")
            print(f"   SMTPServer = {recommended['server']}")
            print(f"   SMTPPort = {recommended['port']}")
            print(f"   (SSL will be used automatically)")
        else:
            recommended = successful_configs[0]
            print(f"\u2705 USE: {recommended['name']}")
            print(f"   Update your email_config.ini with:")
            print(f"   SMTPServer = {recommended['server']}")
            print(f"   SMTPPort = {recommended['port']}")

        # Ask for test email
        print(f"\nWould you like to send a test email?")
        recipient = input("Enter recipient email address (or press Enter to skip): ").strip()

        if recipient:
            print(f"\nSending test email using {recommended['name']}...")

            if send_test_email(recommended, recipient):
                print("\ud83c\udf89 Test email sent successfully!")
                print("Your email configuration is working!")
            else:
                print("\u274c Failed to send test email")

        print(f"\n\u2705 NEXT STEPS:")
        print("1. Update your email_config.ini file with the recommended settings")
        print("2. Restart your application")
        print("3. Test registration - emails should now work!")

    else:
        print("\n\u274c No working email configurations found!")
        print("\nPossible issues:")
        print("1. Verify your email password is correct")
        print("2. Check if your hosting provider has changed settings")
        print("3. Ensure your server IP is not blocked")
        print("4. Contact your hosting provider for updated SMTP settings")


if __name__ == "__main__":
    main()
