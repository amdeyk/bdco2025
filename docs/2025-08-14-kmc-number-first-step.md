## Move KMC Number field to first registration step

- **Date:** 2025-08-14
- **Author:** codex

### Summary
Relocated the KMC Number input from the second step of the guest registration form to the first step. The field now appears immediately when the user selects either the Delegate or Faculty role, and validation is enforced accordingly.

### Files Affected
- `templates/guest_registration.html`
- `CHANGELOG.md`

### Rationale
Collecting KMC numbers early improves data accuracy and streamlines registration for delegates and faculty by ensuring their professional credentials are captured before proceeding.
