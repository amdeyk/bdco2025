## Fix presentation download links

- **Date:** 2025-07-09
- **Author:** codex

### Summary
Normalizes presentation file paths when generating download links for admins. Previously some records stored the full `uploads/presentations` path while others stored only the filename. This inconsistency produced broken links and 404 errors. The admin views now strip any directory components before building the download URL.

### Files Affected
- `app/routes/admin.py`
- `CHANGELOG.md`

### Rationale
Ensures all existing presentation records, regardless of how their path was saved, can be downloaded reliably without re-uploading files.
