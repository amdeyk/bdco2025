## Add presentation approval workflow

- Introduced dedicated approver login with hardcoded credentials for abstract reviewers.
- Added dashboard to review uploaded presentations and record selection status, marks, remarks, and timestamp.
- Extended `presentations.csv` with columns: `selected_status`, `marks_allotted`, `remarks_by`, and `approval_date`.
- Stored approvals are immutable and require confirmation before saving.
