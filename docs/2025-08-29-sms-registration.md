# Add SMS notifications to guest registration

- Introduced `sms_config.ini` for managing SMS API credentials and template IDs.
- Implemented `SmsService` to send templated messages through the AOC portal API.
- Updated guest registration to notify coordinators and guests via SMS upon successful signup.
