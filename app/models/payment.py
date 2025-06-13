from typing import Dict, List
from datetime import datetime
import uuid

class Payment:
    """Model for payment records"""

    def __init__(
        self,
        guest_id: str = "",
        amount: float = 0.0,
        payment_method: str = "cash",
        payment_status: str = "pending"
    ):
        """Initialize a new payment record"""
        self.payment_id = str(uuid.uuid4())
        self.guest_id = guest_id
        self.amount = amount
        self.payment_method = payment_method
        self.payment_status = payment_status
        self.payment_date = datetime.now().isoformat()
        self.recorded_by = ""
        self.receipt_number = ""
        self.payment_proof_path = ""
        self.transaction_reference = ""
        self.notes = ""
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    @classmethod
    def from_dict(cls, data: Dict) -> 'Payment':
        """Create payment instance from dictionary data"""
        instance = cls()
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "payment_id": self.payment_id,
            "guest_id": self.guest_id,
            "amount": str(self.amount),
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "payment_date": self.payment_date,
            "recorded_by": self.recorded_by,
            "receipt_number": self.receipt_number,
            "payment_proof_path": self.payment_proof_path,
            "transaction_reference": self.transaction_reference,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def validate(self) -> List[str]:
        """Validate payment data"""
        errors = []
        if not self.guest_id:
            errors.append("Guest ID is required")
        if self.amount <= 0:
            errors.append("Payment amount must be greater than 0")
        valid_methods = ["cash", "card", "upi", "bank_transfer", "online"]
        if self.payment_method not in valid_methods:
            errors.append(
                f"Invalid payment method. Must be one of: {', '.join(valid_methods)}"
            )
        valid_statuses = ["pending", "partial", "paid", "refunded"]
        if self.payment_status not in valid_statuses:
            errors.append(
                f"Invalid payment status. Must be one of: {', '.join(valid_statuses)}"
            )
        return errors


class PaymentConfig:
    """Model for payment configuration"""

    def __init__(
        self,
        role: str = "",
        payment_required: bool = False,
        amount: float = 0.0
    ):
        """Initialize payment configuration"""
        self.role = role
        self.payment_required = payment_required
        self.amount = amount
        self.currency = "INR"
        self.description = ""
        self.updated_by = ""
        self.updated_at = datetime.now().isoformat()

    @classmethod
    def from_dict(cls, data: Dict) -> 'PaymentConfig':
        instance = cls()
        for key, value in data.items():
            if hasattr(instance, key):
                if key == "payment_required":
                    value = str(value).lower() == "true"
                elif key == "amount":
                    value = float(value) if value else 0.0
                setattr(instance, key, value)
        return instance

    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "payment_required": str(self.payment_required),
            "amount": str(self.amount),
            "currency": self.currency,
            "description": self.description,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at
        }
