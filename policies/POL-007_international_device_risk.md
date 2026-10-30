# POL-007 International, High-Risk Country and Device Risk

Policy ID: POL-007
Applies to rules: TRIPLE_THREAT_VPN_LOCATION_DEVICE, VPN_DETECTED, CRYPTO_NEWCARD_INTERNATIONAL
Applies to personas: ACCOUNT_TAKEOVER

## Scope
This policy covers transactions from international or high-risk countries and sessions using VPNs, proxies or unrecognised devices.

## Rules
- A VPN or proxy alone is a mild signal. A VPN with a new device and a high-risk location is a critical signal.
- A transaction from a high-risk country on a card with no prior international activity requires verification before approval.
- A location change that is not physically possible given the previous transaction is treated as probable compromise.

## Required actions
1. Request step-up authentication for the session.
2. If the customer has notified the bank of travel, record it and lower the severity one level.
3. Otherwise decline and contact the customer. Apply POL-002 if account takeover is suspected.

## Documentation
Record the device fingerprint, IP address, claimed location and any travel notice found.
