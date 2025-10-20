from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Dict
import os
import logging

from app.config import Config
from app.services.csv_db import CSVDatabase
from app.services.auth import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operator", tags=["operator"])

config = Config()
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))

guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)


def get_current_operator(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = auth_service.validate_session(session_id)
    if not session or session.get("role") != "operator":
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


@router.get("/login", response_class=HTMLResponse)
async def operator_login_page(request: Request):
    return templates.TemplateResponse(
        "operator/login.html",
        {"request": request}
    )


@router.post("/login")
async def operator_login(request: Request, password: str = Form(...)):
    expected = config.get('OPERATOR', 'Password', fallback='12345')
    if password != expected:
        return templates.TemplateResponse(
            "operator/login.html",
            {"request": request, "error": "Invalid password"},
            status_code=401,
        )

    # Create operator session
    session_id = auth_service.create_session("operator", "operator")
    response = RedirectResponse(url="/operator", status_code=303)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def operator_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_id")
    return response


@router.get("", response_class=HTMLResponse)
async def operator_dashboard(request: Request, session=Depends(get_current_operator)):
    return templates.TemplateResponse(
        "operator/dashboard.html",
        {"request": request}
    )


@router.get("/api/guest/{code}")
async def api_get_guest(code: str, session=Depends(get_current_operator)):
    # code may be like PREFIX:ID, extract the ID part
    guest_id = code.split(":")[-1].strip()
    guests = guests_db.read_all()
    g = next((x for x in guests if x.get("ID") == guest_id or x.get("Phone") == guest_id), None)
    if not g:
        return JSONResponse({"found": False}, status_code=404)

    # Ensure expected fields exist
    for k in ["LunchGiven", "DinnerGiven", "CertificateGiven", "GiftsGiven", "DailyAttendance"]:
        g.setdefault(k, "False")

    return {
        "found": True,
        "id": g.get("ID"),
        "name": g.get("Name"),
        "phone": g.get("Phone"),
        "lunch": g.get("LunchGiven") == "True",
        "dinner": g.get("DinnerGiven") == "True",
        "gift": g.get("GiftsGiven") == "True",
        "certificate": g.get("CertificateGiven") == "True",
        "attendance": g.get("DailyAttendance") == "True",
    }


@router.post("/api/update")
async def api_update_guest(
    request: Request,
    guest_id: str = Form(...),
    lunch: str = Form(None),
    dinner: str = Form(None),
    gift: str = Form(None),
    certificate: str = Form(None),
    attendance: str = Form(None),
    session=Depends(get_current_operator),
):
    guests = guests_db.read_all()
    idx = None
    for i, g in enumerate(guests):
        if g.get("ID") == guest_id:
            idx = i
            break
    if idx is None:
        return JSONResponse({"success": False, "message": "Guest not found"}, status_code=404)

    g = guests[idx]

    def set_bool(field, val):
        if val is None:
            return
        g[field] = "True" if val.lower() in ("true", "1", "on", "yes") else "False"

    set_bool("LunchGiven", lunch)
    set_bool("DinnerGiven", dinner)
    set_bool("GiftsGiven", gift)
    set_bool("CertificateGiven", certificate)
    set_bool("DailyAttendance", attendance)
    if g.get("DailyAttendance") == "True":
        g["CheckInTime"] = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    guests[idx] = g
    # Ensure all fields present in headers
    fieldnames = set()
    for row in guests:
        fieldnames.update(row.keys())
    guests_db.write_all(guests, fieldnames=sorted(list(fieldnames)))
    return {"success": True}
