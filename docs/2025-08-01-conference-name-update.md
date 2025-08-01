## Standardize conference branding

- **Date:** 2025-08-01
- **Author:** codex

### Summary
Replaced the old "MAGNACODE 2025" branding with "Magna Endocrine Update 2025" across templates, backend logic, configuration, and tests. The badge generation font size was reduced to fit the longer title.

### Files Affected
- `templates/components/footer.html`
- `templates/guest/profile.html`
- `templates/admin/single_guest.html`
- `templates/single_guest.html`
- `app/routes/guest.py`
- `app/routes/admin.py`
- `app/routes/common.py`
- `email_config.ini`
- `test_correct_email.py`
- `CHANGELOG.md`

### Rationale
To maintain consistent branding following the conference name change, hardcoded labels and dynamically generated text were updated. Fonts were adjusted to ensure badges render correctly with the longer name.

