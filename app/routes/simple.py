from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import os
import mimetypes
import csv
import io
import re
import uuid
import logging
from datetime import datetime

from app.config import Config
from app.services.csv_db import CSVDatabase
from app.services.auth import auth_service
from app.services.settings import settings_service


logger = logging.getLogger(__name__)

router = APIRouter()
config = Config()
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))

# Register shared Jinja filters (keep in sync with app/main.py)
def _normalize_dashes(value: str) -> str:
    if not isinstance(value, str):
        return value
    s = value
    s = s.replace("â€“", "–").replace("â€”", "—")
    import re as _re
    s = _re.sub(r"(?<=\d)â(?=\d)", "–", s)
    s = s.replace("—", "–")
    s = _re.sub(r"\s*–\s*", "–", s)
    return s

templates.env.filters["normalize_dashes"] = _normalize_dashes

guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)

GUEST_FIELDS = [
    'ID', 'Name', 'Email', 'Institution', 'Phone',
    'Field1', 'Field2', 'Field3', 'Field4', 'Field5',
    'CreatedAt', 'UpdatedAt'
]

UPLOAD_ROOT = os.path.join(config.get('PATHS', 'StaticDir'), 'uploads')
os.makedirs(UPLOAD_ROOT, exist_ok=True)


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _validate_guest(name: str, email: str, institution: str, phone: str, extra: List[str]) -> List[str]:
    errors = []
    if not name or len(name.strip()) < 2:
        errors.append("Name is required (min 2 characters).")
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("Valid email is required.")
    if not institution or len(institution.strip()) < 2:
        errors.append("Institution is required.")
    phone_n = _normalize_phone(phone)
    if not phone_n or len(phone_n) < 7:
        errors.append("Valid phone number is required.")
    if len(extra) < 5:
        errors.append("Internal error: extra fields missing.")
    return errors


def _read_guests() -> List[dict]:
    guests = guests_db.read_all()
    return guests


def _normalize_record(rec: dict) -> dict:
    """Keep only allowed fields and ensure all keys exist for CSV writes."""
    return {k: rec.get(k, "") for k in GUEST_FIELDS}


def _write_guests(guests: List[dict]):
    cleaned = [_normalize_record(g) for g in guests]
    guests_db.write_all(cleaned, fieldnames=GUEST_FIELDS)


def _find_guest_by_phone(phone: str) -> Optional[dict]:
    phone_n = _normalize_phone(phone)
    for g in _read_guests():
        if _normalize_phone(g.get('Phone', '')) == phone_n:
            return g
    return None


def _find_guest_by_id(guest_id: str) -> Optional[dict]:
    for g in _read_guests():
        if g.get('ID') == guest_id:
            return g
    return None


def _guest_upload_dir(guest_id: str) -> str:
    d = os.path.join(UPLOAD_ROOT, guest_id)
    os.makedirs(d, exist_ok=True)
    return d


def _list_guest_files(guest_id: str) -> List[str]:
    d = _guest_upload_dir(guest_id)
    files = []
    if os.path.isdir(d):
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                files.append(f)
    return sorted(files)


def _save_upload(guest_id: str, file: UploadFile):
    # Max 2MB
    data = file.file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 2MB limit")
    safe_name = os.path.basename(file.filename or '') or f"upload_{uuid.uuid4().hex}"
    path = os.path.join(_guest_upload_dir(guest_id), safe_name)
    with open(path, 'wb') as f:
        f.write(data)
    logger.info(f"Guest {guest_id} uploaded file {safe_name} ({len(data)} bytes)")


def _template_ctx(request: Request, user_role: Optional[str] = None, active: str = ""):
    return {
        "request": request,
        "user_role": user_role,
        "active_page": active,
        "conference": settings_service.get(),
    }


def _set_session_cookie(resp, sid: str):
    # Respect configured session timeout and secure cookie setting
    try:
        timeout_min = Config().getint('SECURITY', 'SessionTimeout', fallback=10) or 10
    except Exception:
        timeout_min = 10
    max_age = timeout_min * 60
    secure = Config().getboolean('SECURITY', 'CookieSecure', fallback=False)
    resp.set_cookie("session_id", sid, httponly=True, max_age=max_age, samesite="lax", secure=secure)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    logger.debug("Render login page")
    return templates.TemplateResponse("simple/login.html", _template_ctx(request, None, "login"))


@router.post("/guest/login")
async def guest_login(request: Request, phone: str = Form(...)):
    logger.info(f"Guest login attempt with phone ending {_normalize_phone(phone)[-4:]}" )
    guest = _find_guest_by_phone(phone)
    if not guest:
        # Redirect to register with prefilled phone
        url = f"/register?phone={_normalize_phone(phone)}"
        return RedirectResponse(url=url, status_code=303)
    sid = auth_service.create_session(guest['ID'], 'guest')
    resp = RedirectResponse(url="/guest", status_code=303)
    _set_session_cookie(resp, sid)
    return resp


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, phone: Optional[str] = None):
    conf = settings_service.get()
    return templates.TemplateResponse("simple/register.html", {
        **_template_ctx(request, None, "register"),
        "prefill_phone": phone or "",
        "registration_closed": not conf.get("registration_open", True),
    })


@router.post("/register")
async def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    institution: str = Form(...),
    phone: str = Form(...),
    field1: str = Form("") ,
    field2: str = Form("") ,
    field3: str = Form("") ,
    field4: str = Form("") ,
    field5: str = Form("") ,
):
    if not settings_service.get().get("registration_open", True):
        return templates.TemplateResponse("simple/register.html", {
            **_template_ctx(request, None, "register"),
            "errors": ["Registration is currently closed."],
            "form": {
                "name": name, "email": email, "institution": institution, "phone": phone,
                "field1": field1, "field2": field2, "field3": field3, "field4": field4, "field5": field5,
            },
            "registration_closed": True,
        }, status_code=403)
    extras = [field1, field2, field3, field4, field5]
    errors = _validate_guest(name, email, institution, phone, extras)
    if errors:
        logger.debug(f"Registration validation errors: {errors}")
        return templates.TemplateResponse("simple/register.html", {
            **_template_ctx(request, None, "register"),
            "errors": errors,
            "form": {
                "name": name, "email": email, "institution": institution, "phone": phone,
                "field1": field1, "field2": field2, "field3": field3, "field4": field4, "field5": field5,
            }
        }, status_code=400)

    if _find_guest_by_phone(phone):
        errors = ["Phone already registered. Use login instead."]
        return templates.TemplateResponse("simple/register.html", {
            **_template_ctx(request, None, "register"),
            "errors": errors,
            "form": {
                "name": name, "email": email, "institution": institution, "phone": phone,
                "field1": field1, "field2": field2, "field3": field3, "field4": field4, "field5": field5,
            }
        }, status_code=400)

    guests = _read_guests()
    guest_id = uuid.uuid4().hex[:8]
    record = {
        'ID': guest_id,
        'Name': name.strip(),
        'Email': email.strip(),
        'Institution': institution.strip(),
        'Phone': _normalize_phone(phone),
        'Field1': field1, 'Field2': field2, 'Field3': field3, 'Field4': field4, 'Field5': field5,
        'CreatedAt': datetime.now().isoformat(),
        'UpdatedAt': "",
    }
    guests.append(record)
    _write_guests(guests)
    logger.info(f"New guest registered {guest_id} : {name}")

    sid = auth_service.create_session(guest_id, 'guest')
    resp = RedirectResponse(url="/guest", status_code=303)
    _set_session_cookie(resp, sid)
    return resp


def _require_guest(request: Request) -> dict:
    sid = request.cookies.get("session_id")
    session = auth_service.validate_session(sid)
    if not session or session["role"] != "guest":
        raise HTTPException(status_code=401, detail="Not authenticated")
    guest = _find_guest_by_id(session["user_id"]) or {}
    return guest


@router.get("/guest", response_class=HTMLResponse)
async def guest_home(request: Request):
    guest = _require_guest(request)
    files = _list_guest_files(guest['ID'])
    return templates.TemplateResponse("simple/guest_dashboard.html", {
        **_template_ctx(request, 'guest', 'profile'),
        "guest": guest,
        "files": files,
    })


@router.post("/guest/update")
async def guest_update(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    institution: str = Form(...),
    field1: str = Form("") ,
    field2: str = Form("") ,
    field3: str = Form("") ,
    field4: str = Form("") ,
    field5: str = Form("") ,
):
    guest = _require_guest(request)
    errors = _validate_guest(name, email, institution, guest.get('Phone', ''), [field1, field2, field3, field4, field5])
    if errors:
        files = _list_guest_files(guest['ID'])
        return templates.TemplateResponse("simple/guest_dashboard.html", {
            **_template_ctx(request, 'guest', 'profile'),
            "guest": {**guest, 'Name': name, 'Email': email, 'Institution': institution, 'Field1': field1, 'Field2': field2, 'Field3': field3, 'Field4': field4, 'Field5': field5},
            "files": files,
            "errors": errors,
        }, status_code=400)

    guests = _read_guests()
    for g in guests:
        if g['ID'] == guest['ID']:
            g['Name'] = name.strip()
            g['Email'] = email.strip()
            g['Institution'] = institution.strip()
            g['Field1'] = field1
            g['Field2'] = field2
            g['Field3'] = field3
            g['Field4'] = field4
            g['Field5'] = field5
            g['UpdatedAt'] = datetime.now().isoformat()
            break
    try:
        _write_guests(guests)
    except TimeoutError:
        files = _list_guest_files(guest['ID'])
        return templates.TemplateResponse("simple/guest_dashboard.html", {
            **_template_ctx(request, 'guest', 'profile'),
            "guest": guest,
            "files": files,
            "errors": ["The system is busy. Please try again in a moment."],
        }, status_code=503)
    logger.info(f"Guest {guest['ID']} updated profile")
    return RedirectResponse(url="/guest", status_code=303)


@router.post("/guest/upload")
async def guest_upload(request: Request, file: UploadFile = File(...)):
    guest = _require_guest(request)
    try:
        _save_upload(guest['ID'], file)
    except TimeoutError:
        return templates.TemplateResponse("simple/guest_dashboard.html", {
            **_template_ctx(request, 'guest', 'profile'),
            "guest": guest,
            "files": _list_guest_files(guest['ID']),
            "errors": ["The system is busy. Please try again in a moment."],
        }, status_code=503)
    return RedirectResponse(url="/guest", status_code=303)


@router.get("/guest/download/{filename}")
async def guest_download(request: Request, filename: str):
    guest = _require_guest(request)
    path = os.path.join(_guest_upload_dir(guest['ID']), os.path.basename(filename))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    download_name = os.path.basename(path)
    return FileResponse(
        path,
        media_type=media_type,
        filename=download_name
    )


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("simple/admin_login.html", _template_ctx(request, None, "admin_login"))


@router.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    conf_pw = config.get('DEFAULT', 'AdminPassword')
    if password != conf_pw:
        logger.warning("Admin login failed: bad password")
        return templates.TemplateResponse("simple/admin_login.html", {**_template_ctx(request, None, "admin_login"), "error": "Invalid password"}, status_code=401)
    sid = auth_service.create_session("admin", "admin")
    resp = RedirectResponse(url="/admin", status_code=303)
    _set_session_cookie(resp, sid)
    return resp


def _require_admin(request: Request):
    sid = request.cookies.get("session_id")
    if not auth_service.require_admin(sid):
        raise HTTPException(status_code=401, detail="Not authorized")


@router.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    _require_admin(request)
    guests = _read_guests()
    return templates.TemplateResponse("simple/admin_dashboard.html", {**_template_ctx(request, 'admin', 'admin'), "count": len(guests)})


@router.get("/admin/guests", response_class=HTMLResponse)
async def admin_guests(request: Request):
    _require_admin(request)
    guests = _read_guests()
    return templates.TemplateResponse("simple/admin_guests.html", {**_template_ctx(request, 'admin', 'guests'), "guests": guests})


@router.get("/admin/guest/{guest_id}", response_class=HTMLResponse)
async def admin_guest_view(request: Request, guest_id: str):
    _require_admin(request)
    g = _find_guest_by_id(guest_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guest not found")
    files = _list_guest_files(guest_id)
    return templates.TemplateResponse("simple/admin_guest_view.html", {**_template_ctx(request, 'admin', 'guests'), "guest": g, "files": files})


@router.post("/admin/guest/{guest_id}/update")
async def admin_guest_update(
    request: Request,
    guest_id: str,
    name: str = Form(...),
    email: str = Form(...),
    institution: str = Form(...),
    phone: str = Form(...),
    field1: str = Form("") ,
    field2: str = Form("") ,
    field3: str = Form("") ,
    field4: str = Form("") ,
    field5: str = Form("") ,
):
    _require_admin(request)
    errors = _validate_guest(name, email, institution, phone, [field1, field2, field3, field4, field5])
    if errors:
        g = {
            'ID': guest_id,
            'Name': name, 'Email': email, 'Institution': institution, 'Phone': phone,
            'Field1': field1, 'Field2': field2, 'Field3': field3, 'Field4': field4, 'Field5': field5,
        }
        files = _list_guest_files(guest_id)
        return templates.TemplateResponse("simple/admin_guest_view.html", {**_template_ctx(request, 'admin', 'guests'), "guest": g, "files": files, "errors": errors}, status_code=400)

    guests = _read_guests()
    for g in guests:
        if g['ID'] == guest_id:
            g['Name'] = name.strip()
            g['Email'] = email.strip()
            g['Institution'] = institution.strip()
            g['Phone'] = _normalize_phone(phone)
            g['Field1'] = field1
            g['Field2'] = field2
            g['Field3'] = field3
            g['Field4'] = field4
            g['Field5'] = field5
            g['UpdatedAt'] = templates.env.globals.get("now")().isoformat() if callable(templates.env.globals.get("now")) else ""
            break
    try:
        _write_guests(guests)
    except TimeoutError:
        files = _list_guest_files(guest_id)
        return templates.TemplateResponse("simple/admin_guest_view.html", {**_template_ctx(request, 'admin', 'guests'), "guest": g, "files": files, "errors": ["The system is busy. Please try again in a moment."]}, status_code=503)
    logger.info(f"Admin updated guest {guest_id}")
    return RedirectResponse(url=f"/admin/guest/{guest_id}", status_code=303)


@router.get("/admin/guest/{guest_id}/download/{filename}")
async def admin_guest_download(request: Request, guest_id: str, filename: str):
    _require_admin(request)
    path = os.path.join(_guest_upload_dir(guest_id), os.path.basename(filename))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    download_name = os.path.basename(path)
    return FileResponse(
        path,
        media_type=media_type,
        filename=download_name
    )


@router.post("/admin/bulk_upload")
async def admin_bulk_upload(request: Request, csv_file: UploadFile = File(...)):
    _require_admin(request)
    data = csv_file.file.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(data))
    guests = _read_guests()
    existing_phones = {_normalize_phone(g.get('Phone', '')) for g in guests}
    added = 0
    for row in reader:
        name = (row.get('Name') or row.get('name') or '').strip()
        email = (row.get('Email') or row.get('email') or '').strip()
        institution = (row.get('Institution') or row.get('institution') or '').strip()
        phone = _normalize_phone(row.get('Phone') or row.get('phone') or '')
        field1 = row.get('Field1', '')
        field2 = row.get('Field2', '')
        field3 = row.get('Field3', '')
        field4 = row.get('Field4', '')
        field5 = row.get('Field5', '')
        errs = _validate_guest(name, email, institution, phone, [field1, field2, field3, field4, field5])
        if errs:
            logger.debug(f"Skipping row due validation: {errs}")
            continue
        if phone in existing_phones:
            logger.debug("Skipping duplicate phone in bulk upload")
            continue
        guest_id = uuid.uuid4().hex[:8]
        guests.append({
            'ID': guest_id,
            'Name': name,
            'Email': email,
            'Institution': institution,
            'Phone': phone,
            'Field1': field1, 'Field2': field2, 'Field3': field3, 'Field4': field4, 'Field5': field5,
            'CreatedAt': datetime.now().isoformat(),
            'UpdatedAt': "",
        })
        existing_phones.add(phone)
        added += 1
    try:
        _write_guests(guests)
    except TimeoutError:
        return templates.TemplateResponse("simple/admin_guests.html", {**_template_ctx(request, 'admin', 'guests'), "guests": _read_guests(), "errors": ["Bulk upload paused: database busy, please retry."]}, status_code=503)
    logger.info(f"Admin bulk upload added {added} guests")
    return RedirectResponse(url="/admin/guests", status_code=303)


@router.post("/admin/clear_database")
async def admin_clear_db(request: Request, password: str = Form(...)):
    _require_admin(request)
    if password != config.get('DEFAULT', 'AdminPassword'):
        raise HTTPException(status_code=403, detail="Invalid confirmation password")
    # Write empty CSV with header
    try:
        guests_db.write_all([], fieldnames=GUEST_FIELDS)
    except TimeoutError:
        return templates.TemplateResponse("simple/admin_dashboard.html", {**_template_ctx(request, 'admin', 'admin'), "count": len(_read_guests()), "errors": ["Database busy. Try clearing again in a moment."]}, status_code=503)
    logger.warning("Admin cleared entire guest database")
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    _require_admin(request)
    return templates.TemplateResponse("simple/admin_settings.html", {**_template_ctx(request, 'admin', 'settings'), "settings": settings_service.get()})


@router.post("/admin/settings")
async def admin_settings_submit(
    request: Request,
    name: str = Form("") ,
    dates: str = Form("") ,
    contact_name: str = Form("") ,
    contact_email: str = Form("") ,
    location: str = Form("") ,
    tagline: str = Form("") ,
    chairperson_name: str = Form("") ,
    chairperson_phone: str = Form("") ,
    secretary_name: str = Form("") ,
    secretary_phone: str = Form("") ,
    scientific_chair_name: str = Form("") ,
    scientific_chair_phone: str = Form("") ,
    show_chairperson_phone: str = Form(None),
    show_secretary_phone: str = Form(None),
    show_scientific_chair_phone: str = Form(None),
    registration_open: str = Form(None),
):
    _require_admin(request)
    settings_service.update(
        name=name,
        dates=dates,
        contact_name=contact_name,
        contact_email=contact_email,
        location=location,
        tagline=tagline,
        chairperson_name=chairperson_name,
        chairperson_phone=chairperson_phone,
        secretary_name=secretary_name,
        secretary_phone=secretary_phone,
        scientific_chair_name=scientific_chair_name,
        scientific_chair_phone=scientific_chair_phone,
        show_chairperson_phone=bool(show_chairperson_phone),
        show_secretary_phone=bool(show_secretary_phone),
        show_scientific_chair_phone=bool(show_scientific_chair_phone),
        registration_open=bool(registration_open),
    )
    return RedirectResponse(url="/admin/settings", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("session_id")
    return resp
