import sys
import subprocess
from pathlib import Path

from ..config import DOWNLOADS_DIR

# Use venv python if available, fall back to sys.executable
VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def download_media(url: str, format: str) -> Path:
    """Download a YouTube video as MP3 or MP4 using yt-dlp.

    Returns the path to the downloaded file.
    Raises ValueError for bad input, RuntimeError for download failures.
    """
    if format not in ("mp3", "mp4"):
        raise ValueError(f"Unsupported format: {format!r}. Use 'mp3' or 'mp4'.")

    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL — must start with http:// or https://")

    output_template = str(DOWNLOADS_DIR / "%(title)s.%(ext)s")

    cmd = [PYTHON, "-m", "yt_dlp", "--no-playlist", "--restrict-filenames",
           "--print", "after_move:filepath"]

    if format == "mp3":
        cmd += [
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "-o", output_template,
            url,
        ]
    else:
        cmd += [
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
            "--merge-output-format", "mp4",
            "--postprocessor-args", "ffmpeg:-c:a aac",
            "-o", output_template,
            url,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        error_msg = result.stderr.strip().split("\n")[-1] if result.stderr else "Unknown error"
        raise RuntimeError(f"yt-dlp failed: {error_msg}")

    # yt-dlp prints the final filepath to stdout via --print after_move:filepath
    filepath = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    output_path = Path(filepath)

    if not output_path.is_file():
        raise RuntimeError("Download completed but output file not found")

    return output_path
