from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.csv_db import CSVDatabase
from app.config import Config
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal/guest", tags=["guest_portal"])

config = Config()
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))

def verify_guest_credentials(guest_id: str, phone: str):
    try:
        guests_db = CSVDatabase(
            config.get('DATABASE', 'CSVPath'),
            config.get('DATABASE', 'BackupDir')
        )
        guests = guests_db.read_all()
        for guest in guests:
            if guest.get('ID') == guest_id and guest.get('Phone') == phone:
                return guest
        return None
    except Exception:
        return None

@router.get('/login', response_class=HTMLResponse)
async def portal_guest_login_page(request: Request):
    try:
        return templates.TemplateResponse('portal/guest_login.html', {'request': request})
    except Exception as e:
        logger.error(f"Error rendering guest portal login: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading login page")

@router.post('/login')
async def portal_guest_login_process(request: Request, guest_id: str = Form(...), phone: str = Form(...)):
    try:
        guest = verify_guest_credentials(guest_id, phone)
        if not guest:
            return templates.TemplateResponse(
                'portal/guest_login.html',
                {'request': request, 'error': 'Invalid Guest ID or Phone Number. Please check your credentials.'}
            )
        return RedirectResponse(url=f"/portal/guest/dashboard?guest_id={guest_id}&phone={phone}", status_code=302)
    except Exception as e:
        logger.error(f"Error processing guest portal login: {str(e)}")
        return templates.TemplateResponse(
            'portal/guest_login.html',
            {'request': request, 'error': 'An error occurred during login. Please try again.'}
        )

@router.get('/register', response_class=HTMLResponse)
async def portal_guest_registration_page(request: Request):
    try:
        return templates.TemplateResponse('portal/guest_register.html', {'request': request})
    except Exception as e:
        logger.error(f"Error rendering guest portal registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading registration page")

@router.post('/register')
async def portal_guest_registration_process(
    request: Request,
    registration_type: str = Form(...),
    existing_id: str = Form(None),
    guest_role: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(None),
    batch: str = Form(None),
    organization: str = Form(None),
    designation: str = Form(None),
    institution: str = Form(None),
    accommodation_needed: str = Form(None),
    company_name: str = Form(None),
    sponsorship_type: str = Form(None),
    notes: str = Form(None)
):
    try:
        guests_db = CSVDatabase(
            config.get('DATABASE', 'CSVPath'),
            config.get('DATABASE', 'BackupDir')
        )

        if registration_type == 'existing' and existing_id:
            guests = guests_db.read_all()
            existing_guest = None
            for g in guests:
                if g.get('ID') == existing_id:
                    existing_guest = g
                    break
            if not existing_guest:
                return templates.TemplateResponse(
                    'portal/guest_register.html',
                    {'request': request, 'error': 'Invalid registration ID. Please check and try again.'}
                )
            updated_guest = existing_guest.copy()
            updated_guest.update({
                'Name': name,
                'Phone': phone,
                'Email': email or existing_guest.get('Email', ''),
                'GuestRole': guest_role,
                'RegistrationStatus': 'Active',
                'RegistrationDate': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            if guest_role == 'Delegate':
                updated_guest.update({'Batch': batch or '', 'Organization': organization or ''})
            elif guest_role == 'Faculty':
                updated_guest.update({'Designation': designation or '', 'Institution': institution or '', 'AccommodationNeeded': 'True' if accommodation_needed else 'False'})
            elif guest_role == 'Sponsor':
                updated_guest.update({'CompanyName': company_name or '', 'SponsorshipType': sponsorship_type or ''})
            if notes:
                updated_guest['Notes'] = notes
            success = guests_db.update_record(existing_id, updated_guest)
            if success:
                return templates.TemplateResponse(
                    'portal/guest_register.html',
                    {'request': request, 'success': True, 'guest_id': existing_id, 'guest_name': name, 'guest_role': guest_role}
                )
        else:
            new_guest_id = f"G{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:4].upper()}"
            new_guest = {
                'ID': new_guest_id,
                'Name': name,
                'Phone': phone,
                'Email': email or '',
                'GuestRole': guest_role,
                'RegistrationDate': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'RegistrationStatus': 'Active',
                'DailyAttendance': 'False',
                'BadgePrinted': 'False',
                'BadgeGiven': 'False',
                'KitReceived': 'False',
                'PaymentStatus': 'Pending',
                'PaymentAmount': '0',
                'GiftsGiven': 'False',
                'FoodCouponsDay1': 'False',
                'FoodCouponsDay2': 'False',
                'JourneyDetailsUpdated': 'False',
                'JourneyCompleted': 'False'
            }
            if guest_role == 'Delegate':
                new_guest.update({'Batch': batch or '', 'Organization': organization or ''})
            elif guest_role == 'Faculty':
                new_guest.update({'Designation': designation or '', 'Institution': institution or '', 'AccommodationNeeded': 'True' if accommodation_needed else 'False'})
            elif guest_role == 'Sponsor':
                new_guest.update({'CompanyName': company_name or '', 'SponsorshipType': sponsorship_type or ''})
            if notes:
                new_guest['Notes'] = notes
            success = guests_db.create_record(new_guest)
            if success:
                return templates.TemplateResponse(
                    'portal/guest_register.html',
                    {'request': request, 'success': True, 'guest_id': new_guest_id, 'guest_name': name, 'guest_role': guest_role}
                )
        return templates.TemplateResponse(
            'portal/guest_register.html',
            {'request': request, 'error': 'Failed to process registration. Please try again.'}
        )
    except Exception as e:
        logger.error(f"Error processing guest portal registration: {str(e)}")
        return templates.TemplateResponse(
            'portal/guest_register.html',
            {'request': request, 'error': 'An error occurred during registration. Please try again.'}
        )

@router.get('/dashboard', response_class=HTMLResponse)
async def portal_guest_dashboard(request: Request, guest_id: str = Query(None), phone: str = Query(None)):
    try:
        if not guest_id or not phone:
            return RedirectResponse(url='/portal/guest/login', status_code=302)
        guest = verify_guest_credentials(guest_id, phone)
        if not guest:
            return RedirectResponse(url='/portal/guest/login', status_code=302)
        presentations = []
        messages = []
        inward_journey = {
            'date': guest.get('InwardJourneyDate', ''),
            'origin': guest.get('InwardJourneyFrom', ''),
            'destination': guest.get('InwardJourneyTo', ''),
            'remarks': guest.get('InwardJourneyRemarks', '')
        }
        outward_journey = {
            'date': guest.get('OutwardJourneyDate', ''),
            'origin': guest.get('OutwardJourneyFrom', ''),
            'destination': guest.get('OutwardJourneyTo', ''),
            'remarks': guest.get('OutwardJourneyRemarks', '')
        }
        return templates.TemplateResponse(
            'portal/guest_dashboard.html',
            {
                'request': request,
                'guest': guest,
                'presentations': presentations,
                'messages': messages,
                'inward_journey': inward_journey,
                'outward_journey': outward_journey,
                'guest_id': guest_id,
                'phone': phone
            }
        )
    except Exception as e:
        logger.error(f"Error loading guest portal dashboard: {str(e)}")
        return RedirectResponse(url='/portal/guest/login', status_code=302)

@router.get('/logout')
async def portal_guest_logout():
    return RedirectResponse(url='/portal/guest/login', status_code=302)

@router.post('/update-profile')
async def portal_update_profile(
    request: Request,
    guest_id: str = Form(...),
    phone: str = Form(...),
    email: str = Form(None),
    new_phone: str = Form(None)
):
    try:
        guest = verify_guest_credentials(guest_id, phone)
        if not guest:
            return RedirectResponse(url='/portal/guest/login', status_code=302)
        guests_db = CSVDatabase(
            config.get('DATABASE', 'CSVPath'),
            config.get('DATABASE', 'BackupDir')
        )
        updated_guest = guest.copy()
        if email:
            updated_guest['Email'] = email
        if new_phone:
            updated_guest['Phone'] = new_phone
            phone = new_phone
        success = guests_db.update_record(guest_id, updated_guest)
        redirect_url = f"/portal/guest/dashboard?guest_id={guest_id}&phone={phone}"
        if success:
            redirect_url += "&success=Profile updated successfully"
        else:
            redirect_url += "&error=Failed to update profile"
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception as e:
        logger.error(f"Error updating profile in portal: {str(e)}")
        return RedirectResponse(url='/portal/guest/login', status_code=302)
