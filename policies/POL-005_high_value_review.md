# POL-005 High-Value Transaction Review

Policy ID: POL-005
Applies to rules: EXTREME_AMOUNT, HIGH_AMOUNT, LATE_NIGHT_HIGH_AMOUNT
Applies to personas: none

## Thresholds (illustrative)
- Above 10,000: transaction is queued for analyst review before settlement.
- Above 50,000: transaction is held automatically and requires a second analyst approval (four-eyes review).
- Above 5,000 between 12am and 5am local time: treated as elevated risk and verified with the cardholder.

## Required actions
1. Verify the transaction with the cardholder through a registered channel.
2. Confirm the merchant and the purpose of the purchase for amounts above the thresholds.
3. For amounts above 50,000, obtain two independent analyst approvals and record both names.
4. Release or decline the transaction within the service level in POL-010.

## Documentation
Record the threshold crossed, the verification channel used and the approver names.
