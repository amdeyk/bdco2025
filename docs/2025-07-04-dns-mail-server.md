## Update mail server after DNS troubleshooting

- **Date:** 2025-07-04
- **Author:** codex

### Summary
DNS checks revealed that `mail.qubixvirtual.in` is the real SMTP host. The
configuration and test utilities now use this server.

### Files Affected
- `email_config.ini`
- `test_correct_email.py`
- `scripts/test_email_server.py`
- `CHANGELOG.md`

### Rationale
Attempts to send mail continued to fail even after switching to
`mail.magnacode1.qubixvirtual.in`. DNS lookups confirmed that only
`mail.qubixvirtual.in` is registered and reachable on ports 25, 465, 587 and
2525. Updating the configuration ensures reliable email delivery.
