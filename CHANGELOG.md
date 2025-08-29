# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Make admin dashboard stat cards link to filtered guest lists for quick navigation.
- Add admin CSV guest upload with robust validation, duplicate checks, and dashboard link.
- Standardize branding to "Magna Endocrine Update 2025" across templates, backend emails, badges, and tests.
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
- Generate shorter 4-character guest IDs and remove the unused Batch field from registration and profile pages.
- Update admin dashboard stats: delegates count replaces checked-in, and new attendance count covers faculty and delegates with check-in or meal coupon.
- Enforce unique phone and KMC numbers during guest registration with server validation and frontend error messaging.
- Generate badges using role-specific background images and reposition guest details and QR codes accordingly.
- Add step-by-step abstract upload guide images below mobile number verification on the abstract submission page.
- Fix abstract submission template's static asset links by using the correct `path` parameter with `url_for` to avoid missing route errors.
- Provide a mobile number lookup on the guest login page to fetch forgotten IDs instantly.
- Introduce presentation approval workflow with dedicated approver login and CSV fields for selection status, marks, remarks, and approval date.
- Lock presentation approvals after first decision and display approval status and remarks on admin and guest views with direct links to the review page.
- Show KMC Number field in the first step of guest registration for Delegate and Faculty roles.
- Add CSV export of presentations with judging details and an Export Report button on the admin presentations page.
- Track guest availability for day 1, day 2, or both days across registration, admin views, profiles, and reports.
- Resolve CSV upload failures by standardizing guest fieldnames against the model and enriching validation and error messages for admins.
- Include journey fields in admin guest CSV uploads by defining a comprehensive master field list to prevent missing-field errors.
- Make registration fields mandatory only when Delegate or Faculty role is selected.
- Send SMS notifications to coordinators and guests after successful registration using configurable templates.
