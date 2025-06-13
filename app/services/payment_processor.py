import csv
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict

from app.models.payment import Payment
from app.services.payment_config import PaymentConfigService
from app.config import Config

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Service for processing payments"""

    def __init__(self):
        self.config = Config()
        self.payments_csv_path = os.path.join(
            os.path.dirname(self.config.get('DATABASE', 'CSVPath')),
            'payments.csv'
        )
        self.payment_config_service = PaymentConfigService()
        self._initialize_payments_file()

    def _initialize_payments_file(self):
        if not os.path.exists(self.payments_csv_path):
            fieldnames = [
                'payment_id', 'guest_id', 'amount', 'payment_method',
                'payment_status', 'payment_date', 'recorded_by',
                'receipt_number', 'payment_proof_path', 'transaction_reference',
                'notes', 'created_at', 'updated_at'
            ]
            os.makedirs(os.path.dirname(self.payments_csv_path), exist_ok=True)
            with open(self.payments_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            logger.info(f"Created payments file: {self.payments_csv_path}")

    def generate_receipt_number(self) -> str:
        prefix = 'RCP'
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        payments = self.get_all_payments()
        existing = [p.receipt_number for p in payments if p.receipt_number]
        counter = 1
        while True:
            number = f"{prefix}{timestamp}{counter:03d}"
            if number not in existing:
                return number
            counter += 1

    def get_all_payments(self) -> List[Payment]:
        payments: List[Payment] = []
        try:
            with open(self.payments_csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    payments.append(Payment.from_dict(row))
        except Exception as e:
            logger.error(f"Error reading payments: {str(e)}")
        return payments

    def get_payments_by_guest(self, guest_id: str) -> List[Payment]:
        return [p for p in self.get_all_payments() if p.guest_id == guest_id]

    def get_payment_by_id(self, payment_id: str) -> Optional[Payment]:
        payments = self.get_all_payments()
        return next((p for p in payments if p.payment_id == payment_id), None)

    def record_payment(self, guest_id: str, amount: float, payment_method: str,
                       payment_status: str = 'paid', recorded_by: str = 'admin',
                       transaction_reference: str = '', notes: str = '',
                       payment_proof_path: str = '') -> Optional[Payment]:
        try:
            payment = Payment(guest_id, amount, payment_method, payment_status)
            payment.recorded_by = recorded_by
            payment.receipt_number = self.generate_receipt_number()
            payment.transaction_reference = transaction_reference
            payment.notes = notes
            payment.payment_proof_path = payment_proof_path
            errors = payment.validate()
            if errors:
                logger.error(f"Payment validation failed: {errors}")
                return None
            fieldnames = [
                'payment_id', 'guest_id', 'amount', 'payment_method',
                'payment_status', 'payment_date', 'recorded_by',
                'receipt_number', 'payment_proof_path', 'transaction_reference',
                'notes', 'created_at', 'updated_at'
            ]
            with open(self.payments_csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerow(payment.to_dict())
            logger.info(f"Payment recorded for guest {guest_id}: {payment.payment_id}")
            return payment
        except Exception as e:
            logger.error(f"Error recording payment: {str(e)}")
            return None

    def update_payment_status(self, payment_id: str, status: str) -> bool:
        try:
            payments = self.get_all_payments()
            updated = False
            for p in payments:
                if p.payment_id == payment_id:
                    p.payment_status = status
                    p.updated_at = datetime.now().isoformat()
                    updated = True
                    break
            if updated:
                fieldnames = [
                    'payment_id', 'guest_id', 'amount', 'payment_method',
                    'payment_status', 'payment_date', 'recorded_by',
                    'receipt_number', 'payment_proof_path', 'transaction_reference',
                    'notes', 'created_at', 'updated_at'
                ]
                with open(self.payments_csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows([p.to_dict() for p in payments])
                logger.info(f"Updated payment status: {payment_id} -> {status}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating payment status: {str(e)}")
            return False

    def get_payment_status_for_guest(self, guest_id: str, guest_role: str) -> Dict:
        config = self.payment_config_service.get_config_by_role(guest_role)
        payments = self.get_payments_by_guest(guest_id)
        if not config or not config.payment_required:
            return {
                'payment_required': False,
                'amount_required': 0,
                'amount_paid': 0,
                'status': 'not_required',
                'payments': []
            }
        total_paid = sum(float(p.amount) for p in payments if p.payment_status == 'paid')
        required = config.amount
        if total_paid >= required:
            status = 'paid'
        elif total_paid > 0:
            status = 'partial'
        else:
            status = 'pending'
        return {
            'payment_required': True,
            'amount_required': required,
            'amount_paid': total_paid,
            'amount_remaining': max(0, required - total_paid),
            'status': status,
            'payments': [p.to_dict() for p in payments],
            'config': config.to_dict()
        }

    def get_payment_statistics(self) -> Dict:
        payments = self.get_all_payments()
        stats = {
            'total_payments': len(payments),
            'total_amount': sum(float(p.amount) for p in payments if p.payment_status == 'paid'),
            'pending_payments': len([p for p in payments if p.payment_status == 'pending']),
            'paid_payments': len([p for p in payments if p.payment_status == 'paid']),
            'partial_payments': len([p for p in payments if p.payment_status == 'partial']),
            'payment_methods': {}
        }
        for p in payments:
            method = p.payment_method
            if method not in stats['payment_methods']:
                stats['payment_methods'][method] = {'count': 0, 'amount': 0}
            stats['payment_methods'][method]['count'] += 1
            if p.payment_status == 'paid':
                stats['payment_methods'][method]['amount'] += float(p.amount)
        return stats
