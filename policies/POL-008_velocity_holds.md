# POL-008 Velocity Limits and Temporary Holds

Policy ID: POL-008
Applies to rules: VELOCITY_SPIKE_CRITICAL, VELOCITY_ELEVATED
Applies to personas: CARD_TESTING

## Thresholds (illustrative)
- 6 to 9 transactions in 24 hours: elevated velocity, send for review and monitor.
- 10 or more transactions in 24 hours: critical velocity, apply an automatic temporary hold.

## Temporary hold rules
- A temporary hold lasts up to 24 hours and must be reviewed by an analyst within 4 hours.
- During a hold, card-present transactions at known merchants may continue at the analyst's discretion.
- Holds must be communicated to the customer by SMS or app notification with a path to dispute.

## Required actions
1. Apply the hold and notify the customer.
2. Review the merchants involved for card-testing patterns (POL-001).
3. Lift the hold if the customer confirms the activity, and note this as a confirmed false positive.
