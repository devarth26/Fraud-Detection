# POL-004 Money Mule Activity and Structuring

Policy ID: POL-004
Applies to rules: HIGH_AMOUNT, EXTREME_AMOUNT
Applies to personas: MULE_ACTIVITY

## Definition
Money mules move illicit funds on behalf of others. Indicators include round-number amounts, repeated use of transfer or ATM merchants, international routing, and funds that arrive and leave the account within a short period. Structuring means splitting amounts to stay under reporting or review thresholds.

## Detection thresholds
- Round amounts of 500 or more (multiples of 100) at transfer or ATM merchants.
- Several transactions at the same merchant type with very low merchant diversity on the card.
- Multiple transactions just below an internal review threshold within a week.

## Required actions
1. Restrict outgoing transfers and cash withdrawals while the review is open.
2. Request an explanation of the source and purpose of funds from the account holder.
3. Refer the case to the compliance team for a suspicious activity assessment.
4. Do not tip off the customer that a suspicious activity report may be filed.

## Documentation
Record the pattern of amounts, counterparties and timing. Keep the record for the retention period set in POL-010.
