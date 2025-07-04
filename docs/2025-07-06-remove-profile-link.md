## Remove profile and email contact from registration email

- **Date:** 2025-07-06
- **Author:** codex

### Summary
The registration confirmation email no longer includes the "Access Your Profile" button or the "Email Support" line. Attendees will still see the helpline number and website link for assistance.

### Files Affected
- `app/routes/guest.py`
- `CHANGELOG.md`

### Rationale
Simplifying the message keeps the focus on key conference details and avoids sending users to the profile portal from the welcome email.
