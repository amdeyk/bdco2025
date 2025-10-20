## Correct SMTP hostname in configuration

- **Date:** 2025-07-03
- **Author:** codex

### Summary
Updated `email_config.ini` to use `mail.magnacode1.qubixvirtual.in` on port `465`.
A new script `test_correct_email.py` helps verify the server connection.

### Files Affected
- `email_config.ini`
- `test_correct_email.py`
- `CHANGELOG.md`

### Rationale
The previous configuration pointed to `magnacode1.qubixvirtual.in`, resulting in
connection errors. The hosting provider's documentation lists
`mail.magnacode1.qubixvirtual.in` as the correct SMTP server. Adjusting the
settings resolves the connection issue and the test script confirms the updated
values.
