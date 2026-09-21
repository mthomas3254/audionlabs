import sys
import uuid
from pathlib import Path
from typing import Optional, Dict

from fastapi import FastAPI, File, Request, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pages
from .jobs import JobStore

from .config import (
    UPLOADS_DIR,
    DOWNLOADS_DIR,
    SEPARATED_DIR,
    SLOWED_DIR,
    TRANSCRIPTS_DIR,
    DEMUCS_MODEL,
    ANTHROPIC_API_KEY,
    PORT,
    ensure_dirs,
)
from .services.file_manager import create_track_paths, TrackPaths

ensure_dirs()

app = FastAPI(title="AudionLabs", version="1.0.0")

# Background jobs for Demucs and Whisper. See backend/jobs.py for why.
jobs = JobStore()

STATIC_DIR = Path(__file__).resolve().parent / "static"

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Media mounts ---
app.mount("/media/original", StaticFiles(directory=UPLOADS_DIR), name="original")
app.mount("/media/stems", StaticFiles(directory=SEPARATED_DIR / DEMUCS_MODEL), name="stems")
app.mount("/media/slowed", StaticFiles(directory=SLOWED_DIR), name="slowed")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Request models ---

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp3"


# --- Middleware ---

@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# --- Page routes ---

# Every public page is assembled by pages.render_page, which fills in the shared
# partials, the asset version stamp, and AdSense tags when they are configured.

def _register_page(path: str, filename: str, active: str, ads: bool) -> None:
    async def page():
        return pages.render_page(filename, active=active, ads=pages.ads_allowed(path, ads))

    page.__name__ = "page_" + (filename.replace("-", "_").replace(".html", ""))
    app.get(path, include_in_schema=False)(page)


for _path, _filename, _active, _ads in pages.PAGES:
    _register_page(_path, _filename, _active, _ads)


@app.get("/ads.txt", include_in_schema=False)
async def ads_txt():
    body = pages.ads_txt()
    if not body:
        raise HTTPException(status_code=404, detail="Not found")
    return PlainTextResponse(body)


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    return PlainTextResponse(pages.robots_txt())


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    return Response(pages.sitemap_xml(), media_type="application/xml")


# --- API routes ---


def _job_failed(what: str, exc: Exception, visitor_message: str) -> RuntimeError:
    """Log the full failure for the operator and hand the visitor a short message."""
    print(f"[{what}] {exc}", file=sys.stderr, flush=True)
    return RuntimeError(visitor_message)


@app.post("/transcribe", status_code=202)
async def transcribe_endpoint(
    file: UploadFile = File(None),
    youtube_url: str = Form(None),
):
    """Queue a transcription and return its job id. Poll /jobs/{id} for the result."""
    if not file and not youtube_url:
        raise HTTPException(status_code=400, detail="Provide either a file or a YouTube URL.")

    audio_path: Optional[Path] = None
    if not youtube_url:
        ext = Path(file.filename or "audio.mp3").suffix.lower()
        if ext not in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
            raise HTTPException(status_code=400, detail="Unsupported audio format.")
        audio_path = TRANSCRIPTS_DIR / f"{uuid.uuid4()}{ext}"
        try:
            with audio_path.open("wb") as f:
                f.write(await file.read())
        finally:
            await file.close()

    def work(set_stage):
        path = audio_path
        try:
            if youtube_url:
                set_stage("Fetching audio from YouTube")
                from .core.downloader import download_media
                try:
                    path = download_media(youtube_url, "mp3")
                except (ValueError, RuntimeError) as e:
                    raise RuntimeError(str(e))
            set_stage("Transcribing audio")
            from .core.transcribe_engine import transcribe_audio
            try:
                return transcribe_audio(path, ANTHROPIC_API_KEY)
            except Exception as e:
                raise _job_failed("transcribe", e, "Transcription failed. Try a shorter or different file.")
        finally:
            if audio_path and audio_path.exists():
                audio_path.unlink(missing_ok=True)

    job = jobs.submit("transcribe", work)
    return {"job_id": job.id, "status": job.status}


@app.get("/health")
async def health():
    return {"status": "ok", "demucs_model": DEMUCS_MODEL}


@app.get("/jobs/{job_id}")
async def job_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job.")
    data = job.public()
    if job.status == "queued":
        data["position"] = jobs.queue_position(job)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@app.post("/process_audio", status_code=202)
async def process_audio(
    file: UploadFile = File(...),
    split_stems_flag: bool = Form(False),
    slowed_reverb_flag: bool = Form(False),
):
    """Save the upload, queue the processing, and return a job id at once.

    Demucs takes minutes on this CPU, far past Cloudflare's 100 second limit,
    so the work happens in the background and the page polls /jobs/{id}.
    """
    allowed_types = ("audio/mpeg", "audio/wav", "audio/x-wav")
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only MP3 and WAV files are supported.")

    original_name = file.filename or "uploaded"
    ext = Path(original_name).suffix.lower()
    if ext not in [".mp3", ".wav"]:
        raise HTTPException(status_code=400, detail="File extension must be .mp3 or .wav.")

    if not split_stems_flag and not slowed_reverb_flag:
        raise HTTPException(status_code=400, detail="Select at least one processing option.")

    song_name = Path(original_name).stem
    track_paths: TrackPaths = create_track_paths(ext)

    try:
        with track_paths.original_path.open("wb") as buffer:
            buffer.write(await file.read())
    finally:
        await file.close()

    def work(set_stage):
        response: Dict[str, Optional[object]] = {
            "track_id": track_paths.track_id,
            "original": {"url": f"/media/original/{track_paths.track_id}/{track_paths.original_path.name}"},
            "stems": None,
            "slowed_mix": None,
        }

        if split_stems_flag:
            set_stage("Separating stems")
            from .core.demucs_engine import split_stems
            try:
                stems_paths = split_stems(track_paths)
            except Exception as e:
                raise _job_failed("demucs", e, "Stem separation failed. Try a shorter MP3 or WAV file.")
            response["stems"] = {
                stem_name: {
                    "url": f"/media/stems/{track_paths.track_id}/{path.name}",
                    "download_name": f"{song_name}_{stem_name}.wav",
                }
                for stem_name, path in stems_paths.items()
            }

        if slowed_reverb_flag:
            set_stage("Applying slowed + reverb")
            from .core.slowed_engine import create_slowed_reverb_mix
            slowed_output_path = track_paths.slowed_dir / "slowed_mix.wav"
            try:
                create_slowed_reverb_mix(track_paths.original_path, slowed_output_path)
            except Exception as e:
                raise _job_failed("slowed", e, "The slowed render failed. Try a different file.")
            response["slowed_mix"] = {
                "url": f"/media/slowed/{track_paths.track_id}/{slowed_output_path.name}",
                "download_name": f"{song_name}_slowed_reverb.wav",
            }

        return response

    job = jobs.submit("process_audio", work)
    return {"job_id": job.id, "status": job.status}


@app.post("/download")
def download(req: DownloadRequest):
    from .core.downloader import download_media
    try:
        path = download_media(req.url, req.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"file_path": str(path), "filename": path.name}


@app.get("/file")
def serve_file(path: str):
    file_path = Path(path)

    try:
        file_path.resolve().relative_to(DOWNLOADS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = file_path.suffix.lower()
    media_type = "audio/mpeg" if suffix == ".mp3" else "video/mp4"
    return FileResponse(path=str(file_path), media_type=media_type, filename=file_path.name)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT)
