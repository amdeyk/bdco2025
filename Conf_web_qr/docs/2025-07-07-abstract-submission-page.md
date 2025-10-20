## Add public abstract submission page

- **Date:** 2025-07-07
- **Author:** codex

### Summary
Created a standalone page for abstract submissions that requires only a mobile number. The page verifies the number against existing guests, then allows file upload and sends a confirmation email.

### Files Affected
- `app/routes/common.py`
- `templates/abstract_submission.html`
- `templates/minimal_base.html`
- `CHANGELOG.md`

### Rationale
A simple public submission form lets registered attendees upload presentations without logging in. Using a minimal template keeps the page isolated from the rest of the site.
