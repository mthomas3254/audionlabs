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
    """Optional yt-dlp network arguments taken from the environment.

    A last resort if YouTube still shows its "confirm you're not a bot" wall even
    with a working JavaScript runtime and PO token provider (see runtime_args):

        YTDLP_PROXY          for example http://user:pass@host:port
        YTDLP_COOKIES_FILE   path to a Netscape cookies.txt
    """
    args: List[str] = []
    proxy = os.getenv("YTDLP_PROXY", "").strip()
    if proxy:
        args += ["--proxy", proxy]
    cookies = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    if cookies and Path(cookies).is_file():
        args += ["--cookies", cookies]
    return args


def runtime_args() -> List[str]:
    """Tell yt-dlp which JavaScript runtime to use.

    YouTube extraction needs a JS runtime to solve its challenges. Without one,
    yt-dlp falls back to a single degraded client that YouTube answers with the
    bot wall for many videos. That was the real cause of Bug 14. yt-dlp enables
    only Deno by default, and the Docker image ships Node 22, so Node is named
    here. Override with YTDLP_JS_RUNTIME, for example "deno:/usr/local/bin/deno".
    """
    runtime = os.getenv("YTDLP_JS_RUNTIME", "").strip() or "node"
    return ["--js-runtimes", runtime]


# YouTube gates each client type differently depending on the requesting IP. Asking for
# several lets yt-dlp use whichever one answers, and the verbose trace records the
# playability status of each, which shows exactly what YouTube allows from this server.
DEFAULT_PLAYER_CLIENTS = "default,tv,tv_simply,tv_downgraded,web_safari,web_embedded,mweb,android_vr,ios"
_CLIENTS_RE = re.compile(r"^[a-z_]+(,[a-z_]+)*$")


def client_args() -> List[str]:
    """yt-dlp player client selection. Override with YTDLP_PLAYER_CLIENTS, or "off"."""
    value = os.getenv("YTDLP_PLAYER_CLIENTS", "").strip().lower()
    if value == "off":
        return []
    if not value or not _CLIENTS_RE.match(value):
        value = DEFAULT_PLAYER_CLIENTS
    return ["--extractor-args", f"youtube:player_client={value}"]


# Lines of the verbose trace worth keeping. "Proxy map" is deliberately absent,
# because yt-dlp prints the proxy URL there, credentials included.
_TRACE_RE = re.compile(
    r"yt-dlp version|Python |exe versions|JS runtime|JavaScript|Optional libraries|Plugin|"
    r"\[pot|\[youtube\]|\[jsc|client|WARNING|ERROR|Request Handlers", re.I)
_CREDENTIALS_RE = re.compile(r"://[^/\s@]+@")
_UNPRINTABLE_RE = re.compile(r"[^\x20-\x7e]")


def _scrub(text: str) -> str:
    """Remove URL credentials and anything that could forge or corrupt a log line."""
    text = _CREDENTIALS_RE.sub("://<redacted>@", text)
    return _UNPRINTABLE_RE.sub("?", text)


def _log_trace(url: str, returncode: int, stderr: str) -> None:
    """Write the informative lines of yt-dlp's verbose output to the server log.

    Visitors see friendly_error(). This keeps the real cause readable in Railway logs.
    Every line is scrubbed, since both the URL and yt-dlp's output are untrusted.
    """
    lines = [ln for ln in (stderr or "").splitlines()
             if _TRACE_RE.search(ln) and "proxy map" not in ln.lower()]
    print(f"[ytdlp] exit={returncode} url={_scrub(url)[:300]}", file=sys.stderr, flush=True)
    for ln in lines[-80:]:
        print(f"[ytdlp] {_scrub(ln)[:400]}", file=sys.stderr, flush=True)


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

    if len(url) > 2000 or _UNPRINTABLE_RE.search(url) or " " in url:
        raise ValueError("Invalid URL — it contains characters a link cannot have")

    output_template = str(DOWNLOADS_DIR / "%(title)s.%(ext)s")

    # --verbose only adds detail to stderr, which is logged below. It does not change behavior.
    cmd = [PYTHON, "-m", "yt_dlp", "--no-playlist", "--restrict-filenames", "--verbose",
           "--print", "after_move:filepath"]
    cmd += runtime_args()
    cmd += client_args()
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
