# audionlabs — Claude Code Context

## Product Type
Public SaaS — unified AudionLabs platform

## Owner
Malik Thomas

## What This Does
AudionLabs is a professional audio processing suite for
YouTube creators, DJs, and remix artists. Four tools in
one platform: stem splitting, slowed+reverb, YouTube
downloading, and AI transcription. Each tool has its own
SEO-optimized page.

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
- openai-whisper (transcription — small model)
- anthropic SDK (Claude API — summary + key topics)
- HTML + CSS + JS frontend (multi-page)

## Pages
- / → index.html (landing page — all four tools)
- /stems → stems.html (stem splitter tool)
- /slowed-reverb → slowed-reverb.html (slowed+reverb tool)
- /youtube-downloader → youtube-downloader.html (YT downloader)
- /transcribe → transcribe.html (AI transcription tool)

## API Endpoints
- POST /process_audio → stem split + slowed+reverb
- POST /download → YouTube MP3/MP4 download
- POST /transcribe → Whisper transcription + Claude AI summary
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
│       ├── downloader.py
│       └── transcribe_engine.py
│   └── services/
│       ├── __init__.py
│       └── file_manager.py
├── backend/static/
│   ├── index.html
│   ├── stems.html
│   ├── slowed-reverb.html
│   ├── youtube-downloader.html
│   ├── transcribe.html
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
- Stem splitting end-to-end test -- DONE (working)
- Slowed+reverb end-to-end test -- DONE (working)
- YouTube downloader end-to-end test -- DONE (working)
- YouTube → AudionLabs pipeline test -- DONE (working)
- All three tools fully tested end-to-end -- DONE
- Progress bar on YouTube downloader processing -- DONE
- Transcribe page frontend -- DONE
- Transcribe backend (Whisper + Claude API) -- DONE
- Transcribe end-to-end test -- DONE (working)
- Navbar update (Transcribe + Sign In + Join) -- DONE

## Known Issues
- torch/torchaudio pinned to 2.10.0+cpu (Python 3.14)
- FFmpeg must be installed system-wide (static build — no shared DLLs)
- Run without --reload flag on Windows to avoid zombie processes
- Whisper small model downloads ~462MB on first run
- Whisper CPU processing takes 1-2 mins per track
- Pro PDF export is placeholder (alert only) — needs real implementation

## Next Session Priorities
1. Deploy to Railway (live URL)
2. Custom domain (audionlabs.ai)
3. File cleanup — auto-delete uploads/transcripts after processing
4. Rate limiting before public launch
5. Auth system (Sign In / Join AudionLabs — currently placeholders)
6. Stripe payments (Pro tier — AI summary, PDF export)

## PLANNED FEATURES

### Transcribe Tool (/transcribe)
- Input: Audio file upload OR YouTube URL
- Free outputs: Full transcript, SRT subtitle file, .txt download
- Paid outputs (Pro): AI summary, Key topics, Timestamps/chapters, PDF export
- Tech: openai-whisper (local) + Claude API (summary/topics)
- Status: DONE (free + pro UI built, PDF gating is placeholder)

### Auth System
- Email + password accounts
- Free tier vs Pro tier
- JWT tokens
- Status: NOT STARTED — placeholder Sign In / Join buttons in nav

### Payments
- Stripe integration
- Pro subscription gates: AI summary, key topics, PDF export, transcription paid features
- Status: NOT STARTED

### UI Updates Planned
- Navbar: Add Transcribe nav item + Sign In + Join AudionLabs buttons (all pages)
- transcribe.html: Full working UI with tab input, progress, results
- Status: DONE

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

### Bug 3: New venv setup checklist
- **Symptom:** Multiple bugs appear when setting up
  a new venv from requirements.txt alone
- **Root cause:** Several fixes exist outside of
  requirements.txt that won't be replicated by just
  running pip install
- **Fix:** When setting up a new venv, always do ALL
  of these steps in order:
  1. pip install -r requirements.txt
  2. pip install soundfile
  3. Copy sitecustomize_backup.py to
     .venv/Lib/site-packages/sitecustomize.py
  4. Verify demucs_engine.py and downloader.py use
     VENV_PYTHON not sys.executable
  5. Test with: .venv/Scripts/python.exe -c
     "import torchaudio, torch, demucs; print('OK')"
- **Status:** DOCUMENTED — follow checklist on new
  environment setup

## ENVIRONMENT SETUP CHECKLIST
Run these steps IN ORDER when setting up on a new machine:

1. python -m venv .venv
2. .venv\Scripts\pip install -r requirements.txt
3. .venv\Scripts\pip install soundfile
4. Copy sitecustomize_backup.py to
   .venv\Lib\site-packages\sitecustomize.py
5. Verify FFmpeg is installed system-wide: ffmpeg -version
6. Verify yt-dlp works: .venv\Scripts\python -m yt_dlp --version
7. Test all imports: .venv\Scripts\python -c
   "import fastapi, demucs, torchaudio, torch, yt_dlp; print('ALL OK')"
8. Start server: python -m uvicorn backend.main:app --port 8000
9. Health check: curl http://localhost:8000/health
