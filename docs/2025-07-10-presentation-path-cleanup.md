## Handle malformed presentation paths

- **Date:** 2025-07-10
- **Author:** codex

### Summary
Adds additional checks when generating admin presentation links and when serving
files. Missing or malformed `file_path` fields previously resulted in `/admin/download_presentation/` URLs which produced 404 errors. The logic now falls back to the `file_name` column and strips whitespace to ensure a valid filename.

### Files Affected
- `app/routes/admin.py`
- `CHANGELOG.md`

### Rationale
Some historical presentation records lacked a valid `file_path` or contained
extra whitespace. This caused broken download links for admins. Sanitizing the
filename and verifying the field prevents confusion and ensures reliable access
to uploaded materials.
