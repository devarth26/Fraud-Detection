# CASE-001 Card testing burst on new card

Case ID: CASE-001
Related policies: POL-001, POL-008
Outcome: confirmed fraud

## Summary
A card issued 2 months earlier saw 9 transactions below 1.00 in 40 minutes across several online merchants, followed by an attempted 4,200 electronics purchase. The model score was high and the micro-transaction rule fired. The analyst placed a hold under POL-001, the customer denied all activity, and the card was blocked and replaced.

## Lesson
The burst of micro-transactions was the early warning. Holding after the first few probes would have prevented the larger attempt.
