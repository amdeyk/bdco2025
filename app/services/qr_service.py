# app/services/qr_service.py
import qrcode
from io import BytesIO
import base64
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class QRService:
    """Service for generating QR codes for guest badges and check-in"""
    
    def __init__(self, static_dir: str):
        """
        Initialize QR service
        
        Args:
            static_dir: Path to static directory for saving QR images
        """
        self.static_dir = static_dir
        self.qr_dir = os.path.join(static_dir, "qr_codes")
        
        # Ensure QR directory exists
        os.makedirs(self.qr_dir, exist_ok=True)
        
    def generate_qr_base64(self, data: str, box_size: int = 10) -> str:
        """
        Generate QR code and return as base64 encoded string
        
        Args:
            data: Data to encode in QR
            box_size: Size of QR code boxes
            
        Returns:
            Base64 encoded string of the QR code image
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=box_size,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Error generating QR code: {str(e)}")
            return ""
            
    def generate_and_save_qr(self, data: str, filename: str) -> str:
        """
        Generate QR code and save to file
        
        Args:
            data: Data to encode in QR
            filename: Filename to save QR code (without extension)
            
        Returns:
            Path to saved QR code image, relative to static directory
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to file
            file_path = os.path.join(self.qr_dir, f"{filename}.png")
            img.save(file_path)
            
            # Return relative path for use in templates
            return os.path.join("qr_codes", f"{filename}.png")
            
        except Exception as e:
            logger.error(f"Error generating and saving QR code: {str(e)}")
            return ""
            
    def generate_guest_badge_qr(self, guest_id: str) -> str:
        """
        Generate QR code for guest badge
        
        Args:
            guest_id: Guest ID
            
        Returns:
            Path to saved QR code image, relative to static directory
        """
        data = f"GUEST:{guest_id}"
        return self.generate_and_save_qr(data, f"guest_{guest_id}")
        
    def generate_check_in_qr(self, guest_id: str) -> str:
        """
        Generate QR code for quick check-in
        
        Args:
            guest_id: Guest ID
            
        Returns:
            Path to saved QR code image, relative to static directory
        """
        data = f"CHECKIN:{guest_id}"
        return self.generate_and_save_qr(data, f"checkin_{guest_id}")