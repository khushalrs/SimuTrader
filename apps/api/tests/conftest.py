import sys
from pathlib import Path

# Ensure `app` package resolves when running tests from apps/api
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
