# Guest Availability Tracking

## Summary
Added an `Availability` field to capture whether a guest will attend day 1, day 2, or both days of the conference.

## Changes
- `app/models/guest.py`: store availability with default "Not Specified" and include in CSV serialization.
- `templates/guest_registration.html`: collect availability via required radio buttons during registration.
- `app/routes/guest.py`: accept the new form field and persist it to the database.
- `templates/admin/single_guest.html`: display and allow admins to update availability.
- `app/routes/admin.py`: support availability in database initialization, field sanitization, basic info updates, and guest list exports.
- `templates/guest/profile.html`: show availability on the guest's profile page.

## Rationale
Knowing which days guests plan to attend helps organizers plan resources and logistics accurately.
