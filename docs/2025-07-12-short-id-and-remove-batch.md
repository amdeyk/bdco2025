## Shorter guest IDs and remove Batch field

- **Date:** 2025-07-12
- **Author:** codex

### Summary
Guest registration now uses a 4-character alphanumeric ID. The form and single guest pages no longer display the Batch field.

### Files Affected
- `app/models/guest.py`
- `app/routes/guest.py`
- `app/utils/helpers.py`
- `scripts/db_sanity_check.py`
- `templates/guest_registration.html`
- `templates/single_guest.html`
- `templates/admin/single_guest.html`
- `templates/components/help_system.html`
- `CHANGELOG.md`

### Rationale
Shorter IDs are easier to share while remaining unique. Batch information was unused and removed from the interface.
