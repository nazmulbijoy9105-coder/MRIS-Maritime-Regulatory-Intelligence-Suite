"""Vercel serverless entry — exposes the FastAPI app as a Python function.

Deploy with the repo root as the Vercel project root; `vercel.json` routes
/v1/* and /health here and serves frontend/ statically everywhere else.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mris.api.app import app  # noqa: E402,F401  (Vercel ASGI entry: `app`)
