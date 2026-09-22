"""Stem separation. Two backends, chosen by DEMUCS_BACKEND:

    local   run Demucs on this machine's CPU (default). A full song takes about
            two minutes on Railway.
    modal   send the file to the GPU function in modal_app/demucs_gpu.py, which
            takes 10 to 30 seconds. Needs MODAL_TOKEN_ID and MODAL_TOKEN_SECRET.
            If the GPU call fails for any reason, the CPU path runs instead, so
            a Modal outage slows splits down rather than breaking them.

Either way the result is stems_dir/{bass,drums,other,vocals}.wav, which is
what main.py and the live mixer expect.
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

from ..config import SEPARATED_DIR, DEMUCS_MODEL
from ..services.file_manager import TrackPaths

# Use venv python if available, fall back to sys.executable
VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

STEM_NAMES = ["bass", "drums", "other", "vocals"]

# Must match modal_app/demucs_gpu.py. tests/test_demucs_backend.py checks this.
MODAL_APP_NAME = "audionlabs-demucs"
MODAL_FUNCTION_NAME = "separate"


def backend() -> str:
    value = os.getenv("DEMUCS_BACKEND", "").strip().lower()
    return "modal" if value == "modal" else "local"


def _separate_on_modal(audio: bytes, ext: str) -> Dict[str, bytes]:
    """Run the deployed GPU function. Returns {stem_name: wav_bytes}."""
    import modal  # imported here so the local path never needs the SDK

    fn = modal.Function.from_name(MODAL_APP_NAME, MODAL_FUNCTION_NAME)
    return fn.remote(audio, ext)


def _separate_locally(track_paths: TrackPaths) -> None:
    """Run the Demucs CLI on this machine. Writes stems into track_paths.stems_dir."""
    cmd = [
        PYTHON,
        "-m",
        "demucs",
        "-n",
        DEMUCS_MODEL,
        "-o",
        str(SEPARATED_DIR),
        str(track_paths.original_path),
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


def _collect(stems_dir: Path) -> Dict[str, Path]:
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


def split_stems(track_paths: TrackPaths) -> Dict[str, Path]:
    """
    Separate the original file and return a dict of stem_name -> Path.
    Raises RuntimeError if separation fails or stems are missing.
    """
    input_path = track_paths.original_path

    if not input_path.exists():
        raise FileNotFoundError(f"Original file not found: {input_path}")

    if backend() == "modal":
        try:
            result = _separate_on_modal(input_path.read_bytes(), input_path.suffix.lower())
            if set(result) < set(STEM_NAMES):
                raise RuntimeError(f"GPU returned only {sorted(result)}")
            track_paths.stems_dir.mkdir(parents=True, exist_ok=True)
            for name in STEM_NAMES:
                (track_paths.stems_dir / f"{name}.wav").write_bytes(result[name])
            return _collect(track_paths.stems_dir)
        except Exception as exc:  # noqa: BLE001 - any GPU failure degrades to CPU
            print(f"[demucs] GPU backend failed ({exc.__class__.__name__}: {exc}); "
                  f"falling back to local CPU", file=sys.stderr, flush=True)

    _separate_locally(track_paths)
    return _collect(track_paths.stems_dir)
