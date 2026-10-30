# POL-009 Friendly Fraud and Dispute Handling

Policy ID: POL-009
Applies to rules: none
Applies to personas: FRIENDLY_FRAUD

## Definition
Friendly fraud occurs when a genuine cardholder disputes a transaction they actually made, for example after delivery, or because they do not recognise a merchant descriptor.

## Handling
- Low-risk borderline cases are not blocked. They are approved and monitored.
- If a dispute arrives, collect evidence: delivery confirmation, device and IP match, prior purchases from the same merchant, and customer communications.
- Repeated disputes from the same cardholder across three or more merchants in 90 days go to the disputes team for pattern review.

## Required actions
1. Contact the cardholder to confirm whether they recognise the transaction and merchant descriptor.
2. If they recognise it, close the case as a confirmed false positive and add a note.
3. If they dispute it despite strong evidence of authorisation, follow the chargeback representment process.

## Documentation
Record the evidence gathered and the outcome. Confirmed false positives feed back into threshold tuning.
