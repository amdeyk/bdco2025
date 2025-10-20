# Fix guest CSV upload fieldname mismatch and validation messaging

- Ensure CSV writes use the complete field set from `Guest` model to avoid `ValueError` when older files lack new columns.
- Expand `process_guest_csv` to validate headers, provide detailed row-level error messages, and log issues for debugging.
- Improve admin upload page with clearer failure messaging and tips for resolving common CSV problems.
