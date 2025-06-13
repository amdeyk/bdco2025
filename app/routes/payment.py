from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from typing import Optional, Dict
import os
import uuid
import shutil
import logging
import csv
import io

from app.services.payment_config import PaymentConfigService
from app.services.payment_processor import PaymentProcessor
from app.services.receipt_generator import ReceiptGenerator
from app.services.auth import get_current_admin, auth_service
from app.services.csv_db import CSVDatabase
from app.config import Config
from app.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["payment"])

config = Config()
payment_config_service = PaymentConfigService()
payment_processor = PaymentProcessor()
receipt_generator = ReceiptGenerator()

PAYMENT_PROOFS_DIR = os.path.join(config.get('PATHS', 'StaticDir'), 'uploads', 'payment_proofs')
os.makedirs(PAYMENT_PROOFS_DIR, exist_ok=True)

# Helper to authenticate guest users
def _get_current_guest(request: Request) -> Dict:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = auth_service.validate_session(session_id)
    if not session or session["role"] != "guest":
        raise HTTPException(status_code=401, detail="Not authenticated")

    guests_db = CSVDatabase(
        config.get('DATABASE', 'CSVPath'),
        config.get('DATABASE', 'BackupDir')
    )
    guests = guests_db.read_all()
    guest = next((g for g in guests if g.get('ID') == session['user_id']), None)
    if not guest:
        raise HTTPException(status_code=401, detail="Guest not found")
    return guest

@router.get('/config', response_class=HTMLResponse)
async def payment_config_page(request: Request, admin=Depends(get_current_admin)):
    try:
        configs = payment_config_service.get_all_configs()
        return templates.TemplateResponse(
            'admin/payment_config.html',
            {
                'request': request,
                'admin': admin,
                'configs': configs,
                'active_page': 'payment_config'
            }
        )
    except Exception as e:
        logger.error(f"Error loading payment config page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading payment configuration")

@router.post('/config/update')
async def update_payment_config(
    request: Request,
    admin=Depends(get_current_admin),
    role: str = Form(...),
    payment_required: bool = Form(...),
    amount: float = Form(...),
    description: str = Form('')
):
    try:
        success = payment_config_service.update_config(
            role=role,
            payment_required=payment_required,
            amount=amount,
            description=description,
            updated_by=admin['user_id']
        )
        if success:
            return JSONResponse({"success": True, "message": "Configuration updated"})
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to update"})
    except Exception as e:
        logger.error(f"Error updating payment config: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@router.get('/management', response_class=HTMLResponse)
async def payment_management_page(request: Request, admin=Depends(get_current_admin)):
    try:
        payments = payment_processor.get_all_payments()
        configs = payment_config_service.get_all_configs()
        stats = payment_processor.get_payment_statistics()
        return templates.TemplateResponse(
            'admin/payment_management.html',
            {
                'request': request,
                'admin': admin,
                'payments': payments,
                'configs': configs,
                'stats': stats,
                'active_page': 'payment_management'
            }
        )
    except Exception as e:
        logger.error(f"Error loading payment management page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading payment management")

@router.post('/record')
async def record_payment(
    request: Request,
    admin=Depends(get_current_admin),
    guest_id: str = Form(...),
    amount: float = Form(...),
    payment_method: str = Form(...),
    payment_status: str = Form('paid'),
    transaction_reference: str = Form(''),
    notes: str = Form(''),
    payment_proof: Optional[UploadFile] = File(None)
):
    try:
        proof_path = ''
        if payment_proof and payment_proof.filename:
            ext = os.path.splitext(payment_proof.filename)[1]
            filename = f"{guest_id}_{uuid.uuid4()}{ext}"
            dest = os.path.join(PAYMENT_PROOFS_DIR, filename)
            with open(dest, 'wb') as buffer:
                shutil.copyfileobj(payment_proof.file, buffer)
            proof_path = f"uploads/payment_proofs/{filename}"
        payment = payment_processor.record_payment(
            guest_id=guest_id,
            amount=amount,
            payment_method=payment_method,
            payment_status=payment_status,
            recorded_by=admin['user_id'],
            transaction_reference=transaction_reference,
            notes=notes,
            payment_proof_path=proof_path
        )
        if payment:
            return JSONResponse({"success": True, "payment_id": payment.payment_id, "receipt": payment.receipt_number})
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to record"})
    except Exception as e:
        logger.error(f"Error recording payment: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


@router.post('/record-guest')
async def record_payment_guest(
    request: Request,
    amount: float = Form(...),
    payment_method: str = Form(...),
    transaction_reference: str = Form(''),
    notes: str = Form(''),
    payment_proof: Optional[UploadFile] = File(None)
):
    """Record a payment submitted by a guest"""
    guest = _get_current_guest(request)
    try:
        proof_path = ''
        if payment_proof and payment_proof.filename:
            ext = os.path.splitext(payment_proof.filename)[1]
            filename = f"{guest['ID']}_{uuid.uuid4()}{ext}"
            dest = os.path.join(PAYMENT_PROOFS_DIR, filename)
            with open(dest, 'wb') as buffer:
                shutil.copyfileobj(payment_proof.file, buffer)
            proof_path = f"uploads/payment_proofs/{filename}"

        payment = payment_processor.record_payment(
            guest_id=guest['ID'],
            amount=amount,
            payment_method=payment_method,
            payment_status='pending',
            recorded_by='guest',
            transaction_reference=transaction_reference,
            notes=notes,
            payment_proof_path=proof_path
        )
        if payment:
            return JSONResponse({"success": True, "payment_id": payment.payment_id})
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to record"})
    except Exception as e:
        logger.error(f"Error recording guest payment: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@router.get('/status/{guest_id}')
async def get_payment_status(guest_id: str, guest_role: str):
    try:
        status = payment_processor.get_payment_status_for_guest(guest_id, guest_role)
        return JSONResponse({"success": True, "status": status})
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@router.get('/receipt/{payment_id}')
async def download_receipt(payment_id: str, admin=Depends(get_current_admin)):
    try:
        filename = receipt_generator.generate_receipt(payment_id)
        if not filename:
            raise HTTPException(status_code=404, detail="Receipt generation failed")
        path = receipt_generator.get_receipt_path(filename)
        return FileResponse(path, filename=filename)
    except Exception as e:
        logger.error(f"Error generating receipt: {str(e)}")
        raise HTTPException(status_code=500, detail="Receipt generation failed")


@router.get('/guest/status')
async def guest_payment_status(request: Request):
    """Get payment status for the logged in guest"""
    guest = _get_current_guest(request)
    try:
        status = payment_processor.get_payment_status_for_guest(guest['ID'], guest.get('GuestRole', ''))
        return JSONResponse({"success": True, "status": status})
    except Exception as e:
        logger.error(f"Error getting guest payment status: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


@router.get('/export')
async def export_payments(admin=Depends(get_current_admin)):
    """Export all payment records as CSV"""
    try:
        payments = payment_processor.get_all_payments()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Payment ID', 'Guest ID', 'Amount', 'Method', 'Status', 'Date', 'Recorded By', 'Receipt'])
        for p in payments:
            writer.writerow([
                p.payment_id,
                p.guest_id,
                p.amount,
                p.payment_method,
                p.payment_status,
                p.payment_date,
                p.recorded_by,
                p.receipt_number
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename=payments.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting payments")
