# audionlabs — Claude Code Context

## Product Type
Public SaaS — unified AudionLabs platform

## Owner
Malik Thomas

## What This Does
AudionLabs is a professional audio processing suite for
YouTube creators, DJs, and remix artists. Three tools in
one platform: stem splitting, slowed+reverb, and YouTube
downloading. Each tool has its own SEO-optimized page.

## Target Users
YouTube creators, TikTok creators, DJs, remix artists, producers

## Current Stack
- Python 3.14 + FastAPI (backend)
- Uvicorn (ASGI server)
- torch==2.10.0+cpu / torchaudio==2.10.0+cpu (Python 3.14 compatible)
- Demucs (stem separation via CLI subprocess)
- FFmpeg + ffprobe (system-wide install required)
- yt-dlp (YouTube downloading)
- Pydub (audio utility)
- HTML + CSS + JS frontend (multi-page)

## Pages
- / → index.html (landing page — all three tools)
- /stems → stems.html (stem splitter tool)
- /slowed-reverb → slowed-reverb.html (slowed+reverb tool)
- /youtube-downloader → youtube-downloader.html (YT downloader)

## API Endpoints
- POST /process_audio → stem split + slowed+reverb
- POST /download → YouTube MP3/MP4 download
- GET /file?path= → serve downloaded file
- GET /health → status check

## Folder Structure
audionlabs/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── core/
│       ├── __init__.py
│       ├── demucs_engine.py
│       ├── slowed_engine.py
│       └── downloader.py
│   └── services/
│       ├── __init__.py
│       └── file_manager.py
├── backend/static/
│   ├── index.html
│   ├── stems.html
│   ├── slowed-reverb.html
│   ├── youtube-downloader.html
│   ├── style.css
│   └── app.js
├── uploads/
├── downloads/
├── requirements.txt
├── .env.example
├── .gitignore
└── CLAUDE.md

## Audio Settings (LOCKED — do not change)
- Slowed+reverb: 0.9x speed, 6kHz lowpass,
  loudnorm I=-16 TP=-1.5 LRA=11
- Demucs model: htdemucs

## Current Status
- Project setup -- DONE
- Landing page (index.html) -- DONE
- Stems page (stems.html) -- DONE
- Slowed+reverb page (slowed-reverb.html) -- DONE
- YouTube downloader page (youtube-downloader.html) -- DONE
- Merged backend (main.py + config.py) -- DONE
- SEO meta tags on all pages -- DONE

## Known Issues
- torch/torchaudio pinned to 2.10.0+cpu (Python 3.14)
- FFmpeg must be installed system-wide
- Run without --reload flag on Windows to avoid zombie processes
- Demucs not yet tested end-to-end in merged app
- Slowed+reverb not yet tested in merged app
- YouTube downloader → AudionLabs pipeline not yet tested

## Next Session Priorities
1. Full stress test — stems, slowed+reverb, YouTube downloader
2. Fix any bugs found during stress test
3. Deployment planning (Railway / Render / DigitalOcean)

## Important Notes
- This replaces both MVAT_stem_webapp and audionlabs-downloader
- Single port: 8000
- No cross-server calls — downloader and processor are in same app
- Keep MVAT_stem_webapp and audionlabs-downloader repos intact
- Run server: uvicorn backend.main:app --port 8000

## KNOWN BUGS — DO NOT REMOVE OR MODIFY THIS SECTION

### Bug 1: torchaudio torchcodec save error
- **Symptom:** Demucs processes audio successfully
  (progress bar completes) but then throws:
  "ImportError: TorchCodec is required for
  save_with_torchcodec"
- **Root cause:** torchaudio 2.9+ hardcodes torchcodec
  as the default audio save backend. torchcodec requires
  FFmpeg shared DLLs ("full-shared" build) which conflicts
  with the static FFmpeg build installed on this system.
  No torchaudio 2.8.x exists for Python 3.14.
- **Fix:** sitecustomize.py monkey-patch in .venv that
  replaces torchaudio.save with soundfile.write. Located at:
  .venv/Lib/site-packages/sitecustomize.py
  Also requires: pip install soundfile
- **First encountered:** MVAT_stem_webapp (Python 3.11,
  torch 2.5.1). Reappeared in audionlabs (Python 3.14,
  torch 2.10.0). Will likely reappear on any new
  environment.
- **Prevention:** Always copy sitecustomize.py and install
  soundfile when setting up a new venv. Do NOT install
  torchcodec — it will fail on static FFmpeg builds.
- **Status:** FIXED — sitecustomize.py patch active

### Bug 2: sys.executable wrong Python on Windows
- **Symptom:** Demucs or yt-dlp subprocess calls fail
  with "No module named demucs/yt_dlp" even though
  they are installed in the venv
- **Root cause:** sys.executable resolves to the system
  Python (C:\Python314\python.exe) instead of the venv
  Python when uvicorn is started from a different context
- **Fix:** Use explicit venv Python path in subprocess:
  VENV_PYTHON = Path(__file__).resolve().parents[2] /
  ".venv" / "Scripts" / "python.exe"
  PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists()
  else sys.executable
- **First encountered:** audionlabs merged project
- **Status:** FIXED — both demucs_engine.py and
  downloader.py use VENV_PYTHON
