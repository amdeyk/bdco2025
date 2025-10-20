## Enhanced email connection logic

- **Date:** 2025-07-03
- **Author:** codex

### Summary
Expanded `EmailService` to attempt multiple connection methods across common SMTP ports (587, 465 and 25). The service now starts with STARTTLS on the configured port and falls back to other ports and SSL/plain connections as needed. A helper script `scripts/test_email_server.py` was added to test server connectivity.

### Files Affected
- `app/services/email_service.py`
- `scripts/test_email_server.py`
- `email_config.ini`
- `CHANGELOG.md`

### Rationale
Server logs continued to show `Connection refused` errors on port 465. Trying multiple ports and protocols improves compatibility with custom domain mail servers. The new test script assists in diagnosing configuration issues.
