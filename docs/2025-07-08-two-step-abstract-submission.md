## Improve abstract submission flow

- **Date:** 2025-07-08
- **Author:** codex

### Summary
Converted the abstract submission page into a two-step form. Users now verify their mobile number before uploading files. Allowed file types include JPEG and Mac formats. After submission, a detailed confirmation is shown and emailed to the user.

### Files Affected
- `app/routes/common.py`
- `templates/abstract_submission.html`
- `CHANGELOG.md`

### Rationale
The previous single form caused confusion when numbers were invalid. A stepwise process ensures only registered attendees can upload files and receive confirmation.
