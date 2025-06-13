import os
import logging
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

from app.config import Config
from app.services.payment_processor import PaymentProcessor
from app.services.csv_db import CSVDatabase

logger = logging.getLogger(__name__)

class ReceiptGenerator:
    """Service for generating PDF receipts"""

    def __init__(self):
        self.config = Config()
        self.processor = PaymentProcessor()
        self.guests_db = CSVDatabase(
            self.config.get('DATABASE', 'CSVPath'),
            self.config.get('DATABASE', 'BackupDir')
        )
        self.receipts_dir = os.path.join(self.config.get('PATHS', 'StaticDir'), 'receipts')
        os.makedirs(self.receipts_dir, exist_ok=True)

    def generate_receipt(self, payment_id: str) -> Optional[str]:
        try:
            payment = self.processor.get_payment_by_id(payment_id)
            if not payment:
                logger.error(f"Payment not found: {payment_id}")
                return None
            guests = self.guests_db.read_all()
            guest = next((g for g in guests if g.get('ID') == payment.guest_id), None)
            if not guest:
                logger.error(f"Guest not found: {payment.guest_id}")
                return None
            filename = f"receipt_{payment.receipt_number}.pdf"
            filepath = os.path.join(self.receipts_dir, filename)
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER)
            story.append(Paragraph('MAGNACODE 2025 - Payment Receipt', title_style))
            story.append(Spacer(1, 20))
            table_data = [
                ['Receipt Number:', payment.receipt_number],
                ['Payment Date:', datetime.fromisoformat(payment.payment_date).strftime('%B %d, %Y')],
                ['Guest Name:', guest.get('Name', '')],
                ['Guest Role:', guest.get('GuestRole', '')],
                ['Amount Paid:', f"₹{payment.amount}"],
                ['Payment Method:', payment.payment_method]
            ]
            table = Table(table_data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ]))
            story.append(table)
            story.append(Spacer(1, 20))
            footer_style = ParagraphStyle('Footer', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8)
            story.append(Paragraph('This is a computer generated receipt.', footer_style))
            story.append(Paragraph(datetime.now().strftime('%B %d, %Y %H:%M'), footer_style))
            doc.build(story)
            logger.info(f"Receipt generated: {filepath}")
            return filename
        except Exception as e:
            logger.error(f"Error generating receipt: {str(e)}")
            return None

    def get_receipt_path(self, filename: str) -> str:
        return os.path.join(self.receipts_dir, filename)
