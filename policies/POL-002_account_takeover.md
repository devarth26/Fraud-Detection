# POL-002 Account Takeover Response

Policy ID: POL-002
Applies to rules: TRIPLE_THREAT_VPN_LOCATION_DEVICE, VPN_DETECTED, LATE_NIGHT_HIGH_AMOUNT
Applies to personas: ACCOUNT_TAKEOVER

## Definition
Account takeover (ATO) occurs when a fraudster gains control of a legitimate customer's credentials or device and transacts as them. Typical signals are a new device, a VPN or proxy, an unusual location, a late-night session, and spending that deviates sharply from the customer's own baseline.

## Detection thresholds
- A new device combined with a VPN or proxy and a high-risk or international location is a critical ATO pattern.
- A transaction amount more than 3 times the customer's historical average, on a new device, is treated as behavioural deviation.

## Required actions
1. Suspend the session and require step-up authentication before any further transaction.
2. Force a credential reset and revoke active sessions and linked devices.
3. Call the customer on the registered number (never a number supplied in the session) to verify.
4. Freeze outgoing transfers and new payee additions for 24 hours.
5. Escalate to the fraud operations lead if the customer cannot be reached.

## Documentation
Record device identifiers, IP and geolocation details, and the baseline deviation observed.
