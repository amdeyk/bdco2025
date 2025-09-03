# 2025-08-31 Agentic Workflow Fix

## Summary
- Add `astrologer_agents.py` implementing enhanced `QueryPreprocessorAgent` with explicit termination token to prevent infinite loops.
- Introduce `run_agentic_workflow` handling query preprocessing, rephrasing, and feedback.

## Testing
- `pytest`
