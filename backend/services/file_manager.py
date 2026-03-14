from dataclasses import dataclass
from pathlib import Path
import uuid

from ..config import (
    UPLOAD_DIR,
    SEPARATED_ROOT,
    LOFI_OUTPUT_DIR,
    SLOWED_OUTPUT_DIR,
    DEMUCS_MODEL_NAME,
)


@dataclass
class TrackPaths:
    track_id: str
    original_path: Path
    stems_dir: Path
    slowed_dir: Path
    lofi_dir: Path


def generate_track_id() -> str:
    """Generate a unique track ID."""
    return uuid.uuid4().hex


def create_track_paths(file_extension: str) -> TrackPaths:
    """
    Create per-track directories and return all important paths.
    file_extension should include the dot, e.g. '.mp3' or '.wav'.
    """
    track_id = generate_track_id()

    # Per-track folders
    upload_track_dir = UPLOAD_DIR / track_id
    stems_dir = SEPARATED_ROOT / DEMUCS_MODEL_NAME / track_id
    slowed_dir = SLOWED_OUTPUT_DIR / track_id
    lofi_dir = LOFI_OUTPUT_DIR / track_id

    for d in [upload_track_dir, stems_dir, slowed_dir, lofi_dir]:
        d.mkdir(parents=True, exist_ok=True)

    original_filename = f"{track_id}{file_extension}"
    original_path = upload_track_dir / original_filename

    return TrackPaths(
        track_id=track_id,
        original_path=original_path,
        stems_dir=stems_dir,
        slowed_dir=slowed_dir,
        lofi_dir=lofi_dir,
    )

