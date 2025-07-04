# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Fix admin journey update deleting records due to mismatched CSV columns.
  Admin updates now use normalized field names to prevent CSV corruption.
- Display guest phone numbers on the Presentations Management page for easier contact.
- Fix check-in failures caused by temporary `photo_url` field being saved to the CSV database during guest lookup.
- Send a confirmation email after successful guest registration using the
  configured SMTP settings.
- Improve email reliability by falling back to STARTTLS when the initial
  SSL connection is refused.
- Enhance `EmailService` to try multiple ports (587, 465, 25) and update
  `email_config.ini` default port to 587 for custom domain servers.
- Correct `email_config.ini` SMTP hostname to `mail.magnacode1.qubixvirtual.in`
  and add `test_correct_email.py` for verifying the configuration.
- Update mail server host to `mail.qubixvirtual.in` across configuration and
  test scripts after DNS troubleshooting confirmed it as the valid server.
- Switch default SMTP port to 587 with STARTTLS after confirming SSL on port 465 fails.
- Add enhanced HTML registration email template and update guest registration
  to send richly formatted confirmation emails using connection testing.
- Remove "Access Your Profile" button and email support line from the
  registration confirmation email.
- Add a standalone abstract submission page that verifies mobile numbers and sends
  a confirmation email after upload.
- Convert abstract submission into a two-step flow with mobile verification and
  expanded file type support. Confirmation now includes file details and
  timestamp.
- Fix presentation download failures by normalizing stored paths and stripping
  directory components before generating admin download links.
- Handle missing or malformed presentation file paths to prevent broken admin
  download links.
- Resolve admin presentation downloads when CSV headers were misaligned with older data.
