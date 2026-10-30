# CASE-003 False positive caused by customer travel

Case ID: CASE-003
Related policies: POL-007, POL-009
Outcome: dismissed as false positive

## Summary
An international travel purchase on a known device with a changed IP address was flagged at medium risk. The customer had set a travel notice. The analyst verified it through the app, approved the transaction and recorded the false positive under POL-009.

## Lesson
Checking for a travel notice first avoids unnecessary customer friction. Confirmed false positives should be fed back into threshold tuning.
