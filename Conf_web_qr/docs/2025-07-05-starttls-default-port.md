## Default to STARTTLS on port 587

- **Date:** 2025-07-05
- **Author:** codex

### Summary
Updated the email configuration to use port 587 with STARTTLS by default.
Tests confirmed that SSL on port 465 times out, while STARTTLS on 587 works reliably.

### Files Affected
- `email_config.ini`
- `test_correct_email.py`
- `CHANGELOG.md`

### Rationale
Server logs showed successful delivery only when the application fell back to STARTTLS on port 587.
Switching the primary configuration to this port avoids the initial failure and speeds up email sending.
