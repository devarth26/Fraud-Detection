import os
import sys
from pathlib import Path

# Must be set before any `api.*` import: api.database creates its engine at import time.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_agent.db")
os.environ.setdefault("EMBEDDINGS_PROVIDER", "hashing")  # no model download in tests/CI
os.environ.setdefault("LLM_PROVIDER", "none")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
