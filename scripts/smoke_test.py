"""Post-deploy smoke test against a running service.

    python scripts/smoke_test.py https://<your-service-url>
Exits non-zero on failure so CI can gate on it.
"""
import sys

import httpx

HIGH_RISK_TX = {
    "amount": 75000.0, "merchant_category": "Online transfer", "location": "International",
    "time_of_day": "Evening", "transactions_last_24h": 2, "card_age_months": 24,
    "device_match": "Known device, matching IP",
}


def main(base: str) -> int:
    with httpx.Client(base_url=base.rstrip("/"), timeout=120) as c:
        health = c.get("/agent/health")
        health.raise_for_status()
        print("health:", health.json())

        r = c.post("/agent/investigate", json={
            "query": "Why was this transaction flagged, and what should I do?", "transaction": HIGH_RISK_TX})
        r.raise_for_status()
        body = r.json()
        print("investigate:", body["status"], body["risk_tier"], body["tools_used"], body["policies_cited"])
        assert body["status"] == "pending_review", "a 75,000 international transfer must pause for human review"
        assert body["tools_used"], "agent called no tools"

        done = c.post(f"/agent/review/{body['thread_id']}", json={"decision": "escalate", "note": "smoke test"})
        done.raise_for_status()
        assert done.json()["status"] == "reviewed"
        print("review: ok")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
