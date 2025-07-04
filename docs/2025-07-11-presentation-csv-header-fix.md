## Align presentation CSV headers and handle legacy rows

- **Date:** 2025-07-11
- **Author:** codex

### Summary
Presentation uploads were stored using `title` and `description` fields while the
admin database initializer expected `file_name` and extra metadata columns.
This mismatch corrupted later rows so admin download links pointed to the title
text instead of the real file.  A helper now resolves filenames by checking all
possible columns and the initializer creates the correct headers.

### Files Affected
- `app/routes/admin.py`
- `CHANGELOG.md`

### Rationale
Ensuring consistent CSV headers prevents link corruption and allows previously
misaligned rows to be downloaded without manual cleanup.
