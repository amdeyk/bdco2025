# Make registration fields mandatory for Delegate and Faculty roles

## Context
Previously, the registration form required basic information for all roles.

## Change
JavaScript now toggles the required attribute for basic and role-specific fields so that they become mandatory only when the user selects **Delegate** or **Faculty**.

## Rationale
Ensures complete data for conference participants while allowing other roles to register without unnecessary mandatory fields.
