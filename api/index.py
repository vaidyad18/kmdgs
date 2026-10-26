import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Serverless filesystem is read-only except /tmp.
os.environ.setdefault("SNAPSHOT_DIR", str(BACKEND / "data" / "snapshot"))
os.environ.setdefault("DATA_CACHE_DIR", "/tmp/data_cache")
# The React app is served by Vercel's CDN, not by FastAPI.
os.environ.setdefault("STATIC_DIR", str(ROOT / "_no_static_dir"))
# Live refresh is too slow for a serverless request; keep it locked.
os.environ.setdefault("REFRESH_TOKEN", secrets.token_hex(16))

from app.main import app  # noqa: E402,F401