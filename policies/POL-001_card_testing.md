# POL-001 Card Testing and Micro-Transaction Attacks

Policy ID: POL-001
Applies to rules: MICRO_TRANSACTION_CARD_TEST, VELOCITY_SPIKE_CRITICAL, NEW_CARD_HIGH_RISK
Applies to personas: CARD_TESTING

## Definition
Card testing is the use of very small transactions (typically under 1.00 in the account currency) to confirm that a stolen card number is live before a high-value purchase is attempted. It is usually automated and arrives as a burst of attempts within minutes.

## Detection thresholds
- A transaction below 1.00 combined with 5 or more transactions in 24 hours is treated as a probable card-testing event.
- A card younger than 3 months showing micro-transactions raises the severity one level.

## Required actions
1. Place a temporary hold on the card for further online (card-not-present) transactions.
2. Decline any follow-up transaction from the same merchant or device within the hold window.
3. Contact the cardholder through the number on file to confirm whether the micro-transactions were theirs.
4. If the cardholder denies them, block the card and issue a replacement.

## Documentation
Record the number of probe transactions, the merchant identifiers involved and the time window in the case note.
