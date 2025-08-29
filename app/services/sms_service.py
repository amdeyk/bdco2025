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
        if not self.api_key:
            self.logger.warning("SMS service not configured, skipping SMS send")
            return False

        headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }

        payload = {
            "sender": self.sender_id,
            "to": to,
            "templateId": template_id,
            "custom": custom_vars,
            "type": "TRANS"
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            self.logger.info(f"SMS sent successfully to {to} for template {template_id}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send SMS to {to}: {e}")
            return False

    def send_coordinator_message(self, guest_name: str, guest_phone: str):
        for phone in self.coordinator_phones:
            self.send_sms(
                to=phone,
                template_id=self.coordinator_template_id,
                custom_vars=[guest_name, guest_phone]
            )

    def send_guest_confirmation(self, guest_phone: str, guest_id: str):
        self.send_sms(
            to=f"91{guest_phone}",
            template_id=self.guest_template_id,
            custom_vars=[guest_phone, guest_id]
        )
