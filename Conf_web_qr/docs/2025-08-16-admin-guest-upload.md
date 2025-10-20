# Admin CSV Guest Upload

## Summary
Introduced an admin-only interface to upload guest records from CSV files with thorough validation and error reporting.

## Changes
- `templates/admin/upload_guests.html`: new upload page with client-side handling for success and error display.
- `app/routes/admin.py`: backend endpoints to validate CSV rows, prevent duplicates, and append verified guests to `guests.csv`.
- `templates/admin/dashboard.html`: quick action link to access the upload page.
- `CHANGELOG.md`: document the new feature.

## Rationale
Simplifies bulk registration by letting administrators import guest lists while protecting data integrity through comprehensive pre-flight checks.
