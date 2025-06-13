import csv
import os
import logging
from datetime import datetime
from typing import List, Optional

from app.models.payment import PaymentConfig
from app.config import Config

logger = logging.getLogger(__name__)

class PaymentConfigService:
    """Service for managing payment configurations"""

    def __init__(self):
        self.config = Config()
        self.config_csv_path = os.path.join(
            os.path.dirname(self.config.get('DATABASE', 'CSVPath')),
            'payment_config.csv'
        )
        self._initialize_config_file()

    def _initialize_config_file(self):
        """Create CSV with defaults if missing"""
        if not os.path.exists(self.config_csv_path):
            fieldnames = [
                'role', 'payment_required', 'amount', 'currency',
                'description', 'updated_by', 'updated_at'
            ]
            os.makedirs(os.path.dirname(self.config_csv_path), exist_ok=True)
            with open(self.config_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                default_configs = [
                    {
                        'role': 'Delegates',
                        'payment_required': 'True',
                        'amount': '2000',
                        'currency': 'INR',
                        'description': 'Conference registration fee',
                        'updated_by': 'system',
                        'updated_at': datetime.now().isoformat()
                    },
                    {
                        'role': 'Faculty',
                        'payment_required': 'False',
                        'amount': '0',
                        'currency': 'INR',
                        'description': 'No payment required',
                        'updated_by': 'system',
                        'updated_at': datetime.now().isoformat()
                    },
                    {
                        'role': 'Sponsors',
                        'payment_required': 'True',
                        'amount': '5000',
                        'currency': 'INR',
                        'description': 'Sponsorship fee',
                        'updated_by': 'system',
                        'updated_at': datetime.now().isoformat()
                    },
                ]
                writer.writerows(default_configs)
            logger.info(f"Created payment config file: {self.config_csv_path}")

    def get_all_configs(self) -> List[PaymentConfig]:
        configs: List[PaymentConfig] = []
        try:
            with open(self.config_csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    configs.append(PaymentConfig.from_dict(row))
        except Exception as e:
            logger.error(f"Error reading payment configs: {str(e)}")
        return configs

    def get_config_by_role(self, role: str) -> Optional[PaymentConfig]:
        configs = self.get_all_configs()
        return next((c for c in configs if c.role == role), None)

    def update_config(self, role: str, payment_required: bool, amount: float,
                      description: str = '', updated_by: str = 'admin') -> bool:
        try:
            configs = self.get_all_configs()
            updated = False
            for c in configs:
                if c.role == role:
                    c.payment_required = payment_required
                    c.amount = amount
                    c.description = description
                    c.updated_by = updated_by
                    c.updated_at = datetime.now().isoformat()
                    updated = True
                    break
            if not updated:
                new_config = PaymentConfig(role, payment_required, amount)
                new_config.description = description
                new_config.updated_by = updated_by
                configs.append(new_config)
            fieldnames = [
                'role', 'payment_required', 'amount', 'currency',
                'description', 'updated_by', 'updated_at'
            ]
            with open(self.config_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows([c.to_dict() for c in configs])
            logger.info(f"Updated payment config for role: {role}")
            return True
        except Exception as e:
            logger.error(f"Error updating payment config: {str(e)}")
            return False

    def is_payment_required(self, role: str) -> bool:
        config = self.get_config_by_role(role)
        return config.payment_required if config else False

    def get_payment_amount(self, role: str) -> float:
        config = self.get_config_by_role(role)
        return config.amount if config else 0.0
