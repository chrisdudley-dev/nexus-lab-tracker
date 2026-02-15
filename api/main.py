"""
Canonical FastAPI entrypoint.

For now this imports the existing app from lims.api_fastapi to keep backward
compatibility while we migrate the code into api/.
"""
from lims.api_fastapi import app  # noqa: F401
