import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOADS_DIR = BASE_DIR / "uploads"
DOWNLOADS_DIR = BASE_DIR / "downloads"
SEPARATED_DIR = BASE_DIR / "separated"
SLOWED_DIR = BASE_DIR / "slowed_outputs"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

PORT = 8000
DEMUCS_MODEL = "htdemucs"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def ensure_dirs():
    """Create all runtime directories on startup."""
    for d in [UPLOADS_DIR, DOWNLOADS_DIR, SEPARATED_DIR / DEMUCS_MODEL, SLOWED_DIR, TRANSCRIPTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
