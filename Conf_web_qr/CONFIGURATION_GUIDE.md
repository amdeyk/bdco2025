# Conference Website Configuration Guide

This guide lists the key locations in the project that reference the current conference ("MAGNA ENDO UPDATE 2025") so they can be updated for a different event. Search the indicated files and adjust the text, contact information, dates and assets accordingly.

## Templates

- **templates/index.html** – Hero section and general information.
  - Lines 318‑331 contain the conference name, tagline and venue details.
  - Lines 324‑411 contain the schedule overview and related details (days, sessions, credits).
  - Lines 472‑498 list the organizing committee and contact numbers.
  - Lines 574‑595 inside the JavaScript section show contact/venue info for help pop‑ups.
- **templates/components/footer.html** – Footer contact info and copyright.
  - Lines 6‑16 specify the event title and contact phone numbers.
  - Line 33 includes the copyright notice.
- **templates/guest/profile.html** – Guest profile page schedule and venue.
  - Lines 338‑362 show the schedule header and venue details.
  - Lines 474‑500 contain the venue name, support numbers and conference theme.
- **templates/faculty/profile.html** – Faculty profile and schedule info.
  - Lines 145‑151 display the conference name, dates and venue.
  - Lines 160‑200 describe the day‑wise schedule blocks.
- **static/css/styles.css** – Header styling.
  - Header now uses a text-based banner; update styles as needed. No image required.

## Python Routes

- **app/routes/common.py** – Badge generation and footer text for downloaded badges.
  - Lines 915‑939 draw the badge header with the event name and dates.
  - Lines 1028‑1068 define the corporate badge template using the conference name and date.
  - Lines 1145‑1147 list venue and website information printed at the bottom of each badge.
- **app/routes/guest.py** – Guest badge creation.
  - Lines 748‑776 include the event name, dates and QR code prefix `MAGNACODE2025`.
  - Lines 848‑855 define footer text with venue and website details.
- **app/routes/admin.py** – Admin badge export templates.
  - Lines 2961‑2964 and 3148‑3150 embed the venue and website information.

## Configuration Files

- **app/config.py** – Default settings such as `AdminPassword`, database paths and `SecretKey` (lines 30‑45). Adjust if your deployment requires different defaults.
- Email and SMS sending are disabled for this project. Any legacy references to `email_config.ini` or `sms_config.ini` are no longer used.

## Assets

- Header image removed. Update text in `config.ini [CONFERENCE]` to change header.
- **static/schedule/** – PDF schedule referenced in guest pages (`MAGNACODE2025_Schedule.pdf`). Update this file and its links if necessary.

## Additional Notes

Search the repository for the existing conference name "MAGNACODE" or specific contact numbers to ensure no references are missed. After updating the templates and Python files, verify badge generation and page layouts by running the application locally.

