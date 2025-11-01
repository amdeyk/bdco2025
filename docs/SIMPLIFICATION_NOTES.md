Simplification Overview (2025-11-01)

Scope
- Replace complex guest management with a minimal system:
  - Guest: register, login via phone (no password), edit details, upload/download files (<=2MB).
  - Admin: login with fixed password, list/view/edit guests, bulk CSV upload, clear database with password, manage conference settings (name/dates/contact/email/location/tagline) applied to header/footer.

Key Changes
- New router: `app/routes/simple.py` implements all minimal endpoints.
- Removed advanced features from app wiring (QR codes, journey sync, reports, faculty, etc.).
- Updated `app/main.py` to include only `simple.router`, redirect `/` -> `/login`, and reduce startup logic.
- New settings service: `app/services/settings.py` (JSON-backed, cached) used to populate dynamic header/footer globally.
- Templates:
  - New: `templates/simple/` pages for login, register, guest dashboard, admin login, admin dashboard, admin guests list, guest view, and settings.
  - Simplified `templates/components/navbar.html` to minimal nav for guest/admin/anonymous and added tooltips.
  - Updated `templates/components/header.html` and `footer.html` to use dynamic conference settings.
  - Removed legacy templates (`templates/admin`, `templates/guest`, `templates/faculty`, `templates/common`, `templates/email` and unused pages like `index.html`, `checkin.html`, etc.).
- Config: Set admin password to `admin123change` in `config.ini`.
 - Bulk upload sample: `docs/sample_bulk_upload.csv` with minimal headers.

Data Model
- Uses CSV at `data/guests.csv` via `CSVDatabase`.
- Fields: `ID, Name, Email, Institution, Phone, Field1..Field5, CreatedAt, UpdatedAt`.
- Uploads stored under `static/uploads/{guest_id}/`.
 - Existing CSVs with extra columns are automatically normalized (extra columns are dropped) on the next write operation.

Validation
- Server-side validation for required fields and email/phone format.
- Upload limit: max 2MB per file.

Security & Sessions
- Guest login by phone only; sessions via existing `AuthService` with `session_id` cookie.
- Admin login password from config (`admin123change`).
- Admin endpoints require admin session.

UI/UX
- Bootstrap-based responsive pages for mobile/tablet/desktop.
- All action buttons have tooltips; help link in footer toggles help overlay.
- Default conference settings prepopulated in `data/settings.json` (AISMOC 2025 / Bengaluru). Update any time via Admin → Settings.
- Admin can configure additional contacts: Chairperson, Organizing Secretary, Scientific Chairperson; and toggle phone visibility globally.
 - Per-role phone visibility toggles: show/hide phone for each role independently.
 - Registration control: admin can open/close new registrations; when closed, Register links/buttons are disabled and POST /register is blocked.

Notes for Future Edits
- Extend guest fields by adding columns to `GUEST_FIELDS` in `app/routes/simple.py` and adjusting forms/templates.
- Conference settings live in `data/settings.json`; update via Admin > Settings.
- Bulk CSV upload accepts `Name, Email, Institution, Phone, Field1..Field5` headers (case-insensitive for core fields).

Debug Logging
- Each major action logs to console (info/debug) via `logger` in `app/routes/simple.py` and services.
