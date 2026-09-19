import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List

from ..config import DOWNLOADS_DIR

# Use venv python if available, fall back to sys.executable
VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def network_args() -> List[str]:
    """Extra yt-dlp arguments taken from the environment.

    YouTube blocks most datacenter IP addresses with a "confirm you're not a bot"
    wall. PO tokens do not lift that block. A residential proxy does, so the proxy
    is configurable without a code change:

        YTDLP_PROXY          for example http://user:pass@host:port
        YTDLP_COOKIES_FILE   path to a Netscape cookies.txt, as a fallback
    """
    args: List[str] = []
    proxy = os.getenv("YTDLP_PROXY", "").strip()
    if proxy:
        args += ["--proxy", proxy]
    cookies = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    if cookies and Path(cookies).is_file():
        args += ["--cookies", cookies]
    return args


_TRACE_RE = re.compile(
    r"yt-dlp version|Python |exe versions|JS runtime|JavaScript|Optional libraries|Plugin|"
    r"\[pot|\[youtube\]|\[jsc|client|WARNING|ERROR|Proxy map|Request Handlers", re.I)


def _log_trace(url: str, returncode: int, stderr: str) -> None:
    """Write the informative lines of yt-dlp's verbose output to the server log.

    Visitors see friendly_error(). This keeps the real cause readable in Railway logs.
    """
    lines = [ln for ln in (stderr or "").splitlines() if _TRACE_RE.search(ln)]
    print(f"[ytdlp] exit={returncode} url={url}", file=sys.stderr, flush=True)
    for ln in lines[-80:]:
        print(f"[ytdlp] {ln[:400]}", file=sys.stderr, flush=True)


def friendly_error(stderr: str) -> str:
    """Turn yt-dlp's stderr into a message a visitor can act on."""
    text = (stderr or "").strip()
    low = text.lower()
    if "not a bot" in low or "sign in to confirm" in low:
        return ("YouTube is blocking requests from our server right now. "
                "Save the audio another way, then upload the file instead.")
    if "private video" in low or "video unavailable" in low or "has been removed" in low:
        return "That video is private or unavailable."
    if "unsupported url" in low or "is not a valid url" in low:
        return "That link is not a supported video URL."
    if "age" in low and "restricted" in low:
        return "That video is age-restricted and cannot be fetched."
    last = text.split("\n")[-1] if text else "Unknown error"
    return f"Download failed: {last}"


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

    # --verbose only adds detail to stderr, which is logged below. It does not change behavior.
    cmd = [PYTHON, "-m", "yt_dlp", "--no-playlist", "--restrict-filenames", "--verbose",
           "--print", "after_move:filepath"]
    cmd += network_args()

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
    _log_trace(url, result.returncode, result.stderr)

    if result.returncode != 0:
        raise RuntimeError(friendly_error(result.stderr))

    # yt-dlp prints the final filepath to stdout via --print after_move:filepath
    filepath = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    output_path = Path(filepath)

    if not output_path.is_file():
        raise RuntimeError("Download completed but output file not found")

    return output_path
