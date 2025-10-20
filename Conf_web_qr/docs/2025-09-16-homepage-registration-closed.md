## Replace homepage registration link with "Registration Closed" notice

- **Date:** 2025-09-16
- **Author:** codex

### Summary
- Removed the homepage "New Registration" hyperlink and replaced it with a disabled button labelled "Registration Closed" so visitors know registration has ended.
- Added styling for `.registration-closed-btn` to preserve the card layout while visually indicating the action is unavailable.

### Files Affected
- `templates/index.html`
- `CHANGELOG.md`

### Rationale
The conference is no longer accepting new registrations, but the homepage previously invited visitors to register. Replacing the call-to-action with a closed notice prevents confusion while keeping the layout intact.

### Implementation Notes
- The button markup lives in `templates/index.html` under the "Primary Guest Actions" card. Look for the `registration-closed-btn` class when replicating this deployment.
- To reopen registration in a future deployment, swap the `<button>` element back to an `<a href="/guest_registration">` link (or update the href to the new registration URL) and remove the `disabled` attribute.
- The helper styles ensure the disabled button keeps consistent spacing and coloring. Adjust them or the button text as needed for other events.
