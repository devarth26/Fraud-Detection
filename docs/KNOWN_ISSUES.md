# Known issues in FraudShield (found while building the agent)

The agent explains what FraudShield outputs. If the underlying outputs are weak, the explanations inherit that.
Items are labelled by how I established them.

## Fixed in this package
| Issue | How established | Fix |
|---|---|---|
| `hash()` used for `card_id` and categorical encodings. Python randomises string hashes per process, so card history is lost on every restart. | Read the code (`api/main.py`) and confirmed with a cross-process test (`tests/test_scoring.py`) | `api/scoring.py` uses a stable CRC32 hash; `/predict` now uses it. Existing `card_profiles` rows were keyed by random hashes and are effectively orphaned. |
| `/predict` has side effects (DB writes, LLM call), so it cannot be used to re-analyse a transaction. | Read the code | `api/scoring.py::score_transaction()` is the same pipeline with no side effects; `/score` exposes it. |
| `COPY . .` in the old Dockerfile can bake `.env` (your Groq key) and `venv/` into the image. `requirements.txt` includes all of Jupyter. | Read the Dockerfile and requirements | New Dockerfile copies only runtime folders, `.dockerignore` added, slim `requirements-deploy.txt`. |

## Not fixed: decide before you interview on this project
1. **Training data is synthetic, not the Kaggle dataset.** *(read notebooks)* The README says 284,807 Kaggle transactions; the models are
   trained on a generated 100K-row dataset (1.5% fraud) and the LSTM on generated card sequences. AUC 0.98 on rule-generated data does not
   say how it would perform on real fraud. Say "synthetic data built to demonstrate the architecture" and correct the README.
2. **`TRIPLE_THREAT_VPN_LOCATION_DEVICE` can never fire.** *(verified in code + notebook)* It requires `"VPN"` and `"New device"` to both appear in
   `device_match`, but the training data has five mutually exclusive values (`"VPN / proxy detected"`, `"New device, new IP"`, ...). The hard
   override attached to this rule is dead code, and the persona logic cannot add the new-device and VPN points together either.
3. **Persona logic over-reports synthetic identity, and its indicators are fixed text.** *(observed in the eval run; indicator lists verified in `api/main.py`)* The `indicators` lists (e.g. `["no_history", "new_card", "high_value_immediately"]`) are hardcoded strings returned whenever that persona wins, not evidence computed from the transaction, so a 24-month-old card still reports `new_card`. The agent therefore does not repeat the indicators, and adds a Data note to the report when the label contradicts the card age.  A card with no stored history gets +3 synthetic-identity points, so a
   36-month-old card with a large late-night purchase scored higher as "Synthetic Identity" than as "Account Takeover". The agent mitigates this
   by retrieving policy for every detected persona, but the persona output itself is questionable.
4. **"Card" is really "device type".** *(read the code)* The schema has no card identifier; `card_id` is derived from `device_match`, which has
   five values, so up to 1,000 "cards" collapse to ~5 histories. Card-history features and the LSTM's sequences are therefore not per-card. Add a real `card_id` to the schema.
5. **Possible LSTM train/serve skew.** *(from memory of both files; please verify)* The training notebook's 12 features (including `amount_zscore`,
   `amount_rolling_mean`, `velocity_3`) appear to differ in content and order from the 12 that `predict_lstm` builds at inference. To check:
   compare `feature_cols` in `notebooks/ 04_lstm.ipynb` with the vector built in `api/model.py`. If they differ, the LSTM's scores are unreliable.
6. **Autoencoder wiring.** *(read the code)* `ae_scaler` is loaded but unused; inputs are padded/trimmed to fit and max-normalised per sample, which
   suggests a mismatch with how it was trained.
7. Smaller: `/metrics` hardcodes the LSTM numbers; `/predict` has no authentication; CORS is open to all origins.
