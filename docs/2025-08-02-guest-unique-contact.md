## Enforce unique guest contact info

- **Date:** 2025-08-02
- **Author:** codex

### Summary
Adds validation to reject duplicate phone or KMC numbers during guest registration and surfaces server errors to users on the registration page.

### Files Affected
- `app/routes/guest.py`
- `templates/guest_registration.html`
- `CHANGELOG.md`

### Rationale
Ensuring unique contact details prevents conflicting records and improves data integrity while offering clear feedback to registrants.
