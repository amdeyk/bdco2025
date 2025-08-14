# app/routes/approvals.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.config import Config
from app.templates import templates
from datetime import datetime
import csv
import os

router = APIRouter()
config = Config()
PRESENTATIONS_CSV = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'presentations.csv')

@router.get("/approvals/login", response_class=HTMLResponse)
async def approver_login_page(request: Request):
    """Render the login page for presentation approvers."""
    return templates.TemplateResponse("admin/approver_login.html", {"request": request})

@router.post("/approvals/login")
async def process_approver_login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process login credentials for approvers."""
    if username in ["abstract01", "abstract02", "abstract03"] and password == "magna123!@abs":
        response = RedirectResponse(url="/approvals/dashboard", status_code=303)
        response.set_cookie(key="approver_user", value=username)
        return response
    return templates.TemplateResponse("admin/approver_login.html", {"request": request, "error": "Invalid credentials"})

@router.get("/approvals/dashboard", response_class=HTMLResponse)
async def approvals_dashboard(request: Request):
    """Display all presentations for approval."""
    approver_user = request.cookies.get("approver_user")
    if not approver_user:
        return RedirectResponse(url="/approvals/login")

    presentations = []
    if os.path.exists(PRESENTATIONS_CSV):
        with open(PRESENTATIONS_CSV, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                presentations.append(row)

    return templates.TemplateResponse(
        "admin/presentation_approval.html",
        {"request": request, "presentations": presentations, "approver": approver_user}
    )

@router.post("/approvals/save")
async def save_approval(
    request: Request,
    presentation_id: str = Form(...),
    status: str = Form(...),
    marks: int = Form(...),
    remarks: str = Form(...)
):
    """Save approval details for a presentation. Once saved, it cannot be modified."""
    approver_user = request.cookies.get("approver_user")
    if not approver_user:
        return RedirectResponse(url="/approvals/login")

    rows = []
    fieldnames = []
    if os.path.exists(PRESENTATIONS_CSV):
        with open(PRESENTATIONS_CSV, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames or []
            if "selected_status" not in fieldnames:
                fieldnames.extend(["selected_status", "marks_allotted", "remarks_by", "approval_date"])
            for row in reader:
                if row["id"] == presentation_id:
                    # Prevent modifications if already approved
                    if row.get("selected_status") or row.get("marks_allotted") or row.get("remarks_by"):
                        rows.append(row)
                        continue
                    row["selected_status"] = status
                    row["marks_allotted"] = str(marks)
                    row["remarks_by"] = f"{remarks} ({approver_user})"
                    row["approval_date"] = datetime.now().isoformat()
                rows.append(row)
    else:
        fieldnames = [
            "id", "guest_id", "title", "description", "file_path", "file_type", "upload_date",
            "selected_status", "marks_allotted", "remarks_by", "approval_date"
        ]

    with open(PRESENTATIONS_CSV, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return RedirectResponse(url="/approvals/dashboard", status_code=303)
