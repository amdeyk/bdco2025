import configparser
import requests
import logging
import os


class SmsService:
    def __init__(self, config_path: str = "sms_config.ini"):
        self.logger = logging.getLogger(__name__)
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_path):
            self.logger.error(f"SMS configuration file {config_path} not found")
            self.api_key = None
            return

        self.config.read(config_path)

        try:
            self.api_key = self.config.get('SMS', 'APIKey')
            self.sender_id = self.config.get('SMS', 'SenderId')
            self.coordinator_template_id = self.config.get('SMS', 'CoordinatorTemplateId')
            self.guest_template_id = self.config.get('SMS', 'GuestTemplateId')
            self.coordinator_phones = [phone.strip() for phone in self.config.get('SMS', 'CoordinatorPhones').split(',')]
            self.api_url = "https://api.aoc-portal.com/v1/sms/template"
        except Exception as e:
            self.logger.error(f"Error reading SMS configuration: {e}")
            self.api_key = None

    def send_sms(self, to: str, template_id: str, custom_vars: list):
        """SMS sending is disabled for this project. No messages are sent."""
        try:
            self.logger.info(
                f"SMS sending disabled; skipping send to {to} using template {template_id}"
            )
        except Exception:
            pass
        return True

    def send_coordinator_message(self, guest_name: str, guest_phone: str):
        """Disabled: do not send coordinator SMS messages."""
        try:
            self.logger.info("SMS sending disabled; skipping coordinator messages")
        except Exception:
            pass

    def send_guest_confirmation(self, guest_phone: str, guest_id: str):
        """Disabled: do not send guest confirmation SMS messages."""
        try:
            self.logger.info("SMS sending disabled; skipping guest confirmation message")
        except Exception:
            pass
