from pathlib import Path
from typing import Optional, Dict

from fastapi import FastAPI, File, Request, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import (
    UPLOADS_DIR,
    DOWNLOADS_DIR,
    SEPARATED_DIR,
    SLOWED_DIR,
    DEMUCS_MODEL,
    PORT,
    ensure_dirs,
)
from .services.file_manager import create_track_paths, TrackPaths
from .core.demucs_engine import split_stems
from .core.slowed_engine import create_slowed_reverb_mix
from .core.downloader import download_media

ensure_dirs()

app = FastAPI(title="AudionLabs", version="1.0.0")

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

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/stems")
async def stems_page():
    return FileResponse(STATIC_DIR / "stems.html")


@app.get("/slowed-reverb")
async def slowed_reverb_page():
    return FileResponse(STATIC_DIR / "slowed-reverb.html")


@app.get("/youtube-downloader")
async def youtube_downloader_page():
    return FileResponse(STATIC_DIR / "youtube-downloader.html")


@app.get("/transcribe")
async def transcribe_page():
    return FileResponse(STATIC_DIR / "transcribe.html")


# --- API routes ---

@app.get("/health")
async def health():
    return {"status": "ok", "demucs_model": DEMUCS_MODEL}


@app.post("/process_audio")
async def process_audio(
    file: UploadFile = File(...),
    split_stems_flag: bool = Form(False),
    slowed_reverb_flag: bool = Form(False),
):
    allowed_types = ("audio/mpeg", "audio/wav", "audio/x-wav")
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only MP3 and WAV files are supported.")

    original_name = file.filename or "uploaded"
    ext = Path(original_name).suffix.lower()
    if ext not in [".mp3", ".wav"]:
        raise HTTPException(status_code=400, detail="File extension must be .mp3 or .wav.")

    song_name = Path(original_name).stem
    track_paths: TrackPaths = create_track_paths(ext)

    try:
        with track_paths.original_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)
    finally:
        await file.close()

    base_original_url = f"/media/original/{track_paths.track_id}/{track_paths.original_path.name}"

    response: Dict[str, Optional[object]] = {
        "track_id": track_paths.track_id,
        "original": {"url": base_original_url},
        "stems": None,
        "slowed_mix": None,
    }

    stems_paths: Optional[Dict[str, Path]] = None

    if split_stems_flag:
        try:
            stems_paths = split_stems(track_paths)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Demucs error: {e}")

    if split_stems_flag and stems_paths:
        stems_urls = {
            stem_name: {
                "url": f"/media/stems/{track_paths.track_id}/{path.name}",
                "download_name": f"{song_name}_{stem_name}.wav",
            }
            for stem_name, path in stems_paths.items()
        }
        response["stems"] = stems_urls

    if slowed_reverb_flag:
        slowed_output_path = track_paths.slowed_dir / "slowed_mix.wav"
        try:
            create_slowed_reverb_mix(track_paths.original_path, slowed_output_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Slowed+reverb error: {e}")

        response["slowed_mix"] = {
            "url": f"/media/slowed/{track_paths.track_id}/{slowed_output_path.name}",
            "download_name": f"{song_name}_slowed_reverb.wav",
        }

    return JSONResponse(response)


@app.post("/download")
def download(req: DownloadRequest):
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
