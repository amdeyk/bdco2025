## Email fallback update

- **Date:** 2025-07-03
- **Author:** codex

### Summary
Implemented a fallback mechanism in `EmailService.send_email` to attempt STARTTLS when an SSL connection is refused. This improves reliability when the SMTP server does not accept SSL connections on the configured port.

### Files Affected
- `app/services/email_service.py`
- `CHANGELOG.md`

### Rationale
Server logs showed `Connection refused` errors when sending emails via `SMTP_SSL`. Adding a STARTTLS fallback ensures that registration emails are still delivered if the server only supports TLS.
