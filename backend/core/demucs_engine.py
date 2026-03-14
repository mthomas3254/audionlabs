import sys
from pathlib import Path
import subprocess
from typing import Dict

from ..config import SEPARATED_DIR, DEMUCS_MODEL

# Use venv python if available, fall back to sys.executable
VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
from ..services.file_manager import TrackPaths

STEM_NAMES = ["bass", "drums", "other", "vocals"]


def split_stems(track_paths: TrackPaths) -> Dict[str, Path]:
    """
    Run Demucs on the original file and return a dict of stem_name -> Path.
    Raises RuntimeError if Demucs fails or stems are missing.
    """
    input_path = track_paths.original_path

    if not input_path.exists():
        raise FileNotFoundError(f"Original file not found: {input_path}")

    cmd = [
        PYTHON,
        "-m",
        "demucs",
        "-n",
        DEMUCS_MODEL,
        "-o",
        str(SEPARATED_DIR),
        str(input_path),
    ]

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"Demucs failed.\nCOMMAND: {' '.join(cmd)}\n"
            f"STDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}"
        )

    stems_dir = track_paths.stems_dir

    if not stems_dir.exists():
        raise RuntimeError(f"Expected stems directory not found: {stems_dir}")

    stems: Dict[str, Path] = {}
    missing = []

    for name in STEM_NAMES:
        stem_path = stems_dir / f"{name}.wav"
        if stem_path.exists():
            stems[name] = stem_path
        else:
            missing.append(name)

    if missing:
        raise RuntimeError(f"Missing expected stems: {', '.join(missing)}")

    return stems
