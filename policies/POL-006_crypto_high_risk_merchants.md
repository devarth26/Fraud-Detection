# POL-006 Cryptocurrency and High-Risk Merchant Controls

Policy ID: POL-006
Applies to rules: CRYPTO_NEWCARD_INTERNATIONAL
Applies to personas: SYNTHETIC_IDENTITY, MULE_ACTIVITY

## Scope
High-risk merchant categories are crypto exchanges, ATM withdrawals and online transfers. These channels convert card funds into hard-to-reverse value, so they receive stricter controls.

## Rules
- Crypto purchases on a card younger than 6 months require step-up authentication.
- Crypto purchases routed internationally on a new card are held for manual review.
- Repeated crypto purchases within 24 hours trigger a velocity review under POL-008.

## Required actions
1. Hold the transaction and require step-up authentication or verification with the cardholder.
2. Check whether the cardholder has any prior crypto activity on record.
3. If there is no history and the card is new, treat the case as possible synthetic identity or stolen card use and apply POL-003.

## Documentation
Record the exchange name, the destination country and the verification outcome.
