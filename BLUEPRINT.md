# AudionLabs — Project Blueprint

## Project Overview

AudionLabs is a professional audio processing SaaS platform built for YouTube
creators, DJs, remix artists, and producers. It combines three audio tools into
a single web application:

1. **Stem Splitter** — Isolates vocals, drums, bass, and other from any song
   using Meta's Demucs AI model
2. **Slowed + Reverb** — Applies the chopped & screwed aesthetic (0.9x speed,
   lowpass filter, loudness normalization)
3. **YouTube Downloader** — Downloads YouTube videos as MP3 or MP4, with an
   option to pipe the downloaded audio directly into stem splitting or
   slowed+reverb processing

No installs. No setup. Everything runs in the browser.

**Owner:** Malik Thomas
**Repository:** https://github.com/mthomas3254/audionlabs
**Port:** 8000
**Status:** All three tools tested and working. Ready for deployment.

---

## Architecture

### Backend

```
Python 3.14 + FastAPI + Uvicorn (ASGI)
```

Single FastAPI application serving both the API and the frontend. No
microservices, no cross-server calls. All processing happens in-process
via subprocess calls to external tools.

**API Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/process_audio` | Stem split and/or slowed+reverb processing |
| POST | `/download` | YouTube MP3/MP4 download via yt-dlp |
| GET | `/file?path=` | Serve downloaded files from the downloads directory |
| GET | `/health` | Status check (returns demucs model name) |

**Processing Pipeline:**
1. User uploads audio (or downloads from YouTube)
2. File is saved to `uploads/<uuid>/<uuid>.mp3|wav`
3. If stems requested: Demucs subprocess writes to `separated/htdemucs/<uuid>/`
4. If slowed+reverb requested: FFmpeg subprocess writes to `slowed_outputs/<uuid>/`
5. API returns JSON with URLs to all output files
6. Frontend renders download buttons for each result

**Key Design Decisions:**
- Demucs runs as a CLI subprocess (`python -m demucs`), not as a library import.
  This avoids memory management issues and allows the model to load/unload cleanly.
- FFmpeg runs as a subprocess for slowed+reverb. No Python audio processing
  libraries are used for the actual effect chain.
- yt-dlp runs as a subprocess (`python -m yt_dlp`) for the same isolation reasons.
- All subprocess calls use the venv Python explicitly (`VENV_PYTHON`) rather than
  `sys.executable` to avoid the Windows venv resolution bug (see Bug 2 below).

### Frontend

```
HTML + CSS + vanilla JavaScript (no framework)
```

Four pages served as static files by FastAPI:

| Route | File | Purpose |
|-------|------|---------|
| `/` | `index.html` | Landing page with tool grid |
| `/stems` | `stems.html` | Stem splitter upload + processing |
| `/slowed-reverb` | `slowed-reverb.html` | Slowed+reverb upload + processing |
| `/youtube-downloader` | `youtube-downloader.html` | YouTube download + AudionLabs pipeline |

**UI Features:**
- Tubelight floating navbar with animated indicator
- Aurora blob background (CSS animations, div-based — no SVG)
- Glassmorphism cards with backdrop blur
- Pill-shaped toggle switches for processing options
- Simulated progress bars with shimmer animation and stage labels
- Drag-and-drop file upload with file info bar
- Blob-based file downloads (no page navigation)

**Single `app.js`** auto-detects the page via `window.location.pathname` and
binds the appropriate handlers. No build step, no bundling.

### Folder Structure

```
audionlabs/
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, all routes
│   ├── config.py                # Paths, directories, model config
│   ├── core/
│   │   ├── __init__.py
│   │   ├── demucs_engine.py     # Stem separation (Demucs CLI wrapper)
│   │   ├── slowed_engine.py     # Slowed + reverb (FFmpeg)
│   │   └── downloader.py        # YouTube download (yt-dlp)
│   └── services/
│       ├── __init__.py
│       └── file_manager.py      # TrackPaths dataclass, UUID track IDs
├── backend/static/
│   ├── index.html               # Landing page
│   ├── stems.html               # Stem splitter page
│   ├── slowed-reverb.html       # Slowed+reverb page
│   ├── youtube-downloader.html  # YouTube downloader page
│   ├── style.css                # All styles (single file)
│   └── app.js                   # All frontend logic (single file)
├── uploads/                     # Runtime: uploaded audio files
├── downloads/                   # Runtime: YouTube downloads
├── separated/                   # Runtime: Demucs stem output
├── slowed_outputs/              # Runtime: slowed+reverb output
├── sitecustomize_backup.py      # Backup of torchaudio monkey-patch
├── requirements.txt
├── .env.example
├── .gitignore
├── CLAUDE.md
└── BLUEPRINT.md
```

---

## Build History (Session by Session)

### Phase 1: MVAT Stem WebApp (March 9–13, 2026)

**Repository:** `MVAT_stem_webapp/` (archived — kept intact)

**Session 1 (March 9):**
- Project created from scratch: FastAPI backend, Demucs integration,
  slowed+reverb engine, lofi engine, frontend UI
- v1 shipped with working stem separation, slowed reverb, and lofi processing
- Audio files and `__pycache__` removed from git tracking
- CLAUDE.md established as the project context file

**Session 2 (March 10):**
- Tuned slowed+reverb filter chain extensively:
  - 3kHz lowpass = too muffled
  - 4.5kHz lowpass = still too dark
  - **6kHz lowpass = confirmed sweet spot** (LOCKED IN)
- Speed locked at 0.9x with FFmpeg `asetrate` + `aresample`
- Loudnorm set to I=-16 LUFS, TP=-1.5dB, LRA=11
- LoFi feature removed — shelved for Phase 2 roadmap
- Full frontend redesign: v5 with tubelight nav, aurora blobs, floating
  process button, progress bar, pill toggles
- v7/v8/v9 attempted with SVG background paths — broke z-index layering,
  all deleted. Reverted to v5 (div-based aurora blobs)

**Session 3 (March 13):**
- Overhauled lofi engine (0.9x slowing, per-stem reverb, loudnorm mix) —
  but feature remained shelved
- Ported the downloader UI aesthetic back to the webapp (tubelight nav,
  aurora blobs, glassmorphism cards — unified brand)
- Session complete, documented in CLAUDE.md

**Session 4 (March 14):**
- Archived: added note that this project is replaced by `audionlabs`

### Phase 2: AudionLabs Downloader (March 13, 2026)

**Repository:** `audionlabs-downloader/` (archived — kept intact)

This was originally built as a separate sister site running on port 8001,
intended to call the MVAT webapp API on port 8000.

**Session 1 (March 13):**
- Full project setup: backend, yt-dlp downloader engine, frontend UI
- Styled to match the MVAT webapp aesthetic
- Vertically centered main content

**Session 2 (March 13, continued):**
- Two-step download flow implemented: POST `/download` returns server file
  path, then GET `/file?path=` streams the blob to the browser
- Fixed video title filenames via yt-dlp `--restrict-filenames`

**Session 3 (March 13, continued):**
- Send-to-AudionLabs integration built: forwards downloaded MP3 to the
  MVAT webapp's `/process_audio` endpoint with stem/slowed flags
- Fixed flag name mapping between downloader and MVAT webapp
- Blob download for AudionLabs results — prevents page navigation and
  state loss when downloading processed files
- Fixed AAC audio codec in MP4 downloads for universal playback
  (`--postprocessor-args "ffmpeg:-c:a aac"`)
- Fixed `--print after_move:filepath` to correctly capture final file path
  after yt-dlp's post-processing moves

**Session 4 (March 14):**
- Archived: added note that this project is replaced by `audionlabs`

### Phase 3: AudionLabs Unified Platform (March 13–14, 2026)

**Repository:** `audionlabs/` (active)

Decision to merge both projects into a single app. No more cross-server
calls. One port, one codebase.

**Session 1 (March 13):**
- Project initialized: merged backend from MVAT + downloader into single
  FastAPI app
- All 4 pages built (index, stems, slowed-reverb, youtube-downloader)
- Unified `app.js` with page detection via `window.location.pathname`
- Layout fixes: hero sizing, tool grid centering, page-header spacing,
  about/footer positioning (8 commits of layout iteration)

**Session 2 (March 14, morning):**
- Upgraded torch from 2.5.1 to 2.10.0+cpu for Python 3.14 compatibility
- **Bug 1 discovered:** torchaudio torchcodec save error. Fixed with
  `sitecustomize.py` monkey-patch (see Bugs section)
- **Bug 2 discovered:** `sys.executable` resolving to system Python instead
  of venv Python. Fixed with explicit `VENV_PYTHON` path construction
- Stem splitting tested end-to-end — working
- Full session save with all bugs documented and setup checklist added

**Session 3 (March 14, afternoon):**
- Slowed+reverb tested end-to-end — working
- YouTube downloader tested end-to-end — working
- YouTube → AudionLabs pipeline tested end-to-end — working
- Added progress bar with shimmer animation for AudionLabs processing
  on the YouTube downloader page (matching existing download progress bar)
- All three tools confirmed fully functional
- CLAUDE.md updated: all tests passing, deployment planning is next

---

## All Errors Encountered & Fixes Applied

### Error 1: torchaudio torchcodec ImportError
- **When:** Phase 3, Session 2 (audionlabs unified project)
- **Symptom:** Demucs completes successfully (progress bar finishes) then
  throws `ImportError: TorchCodec is required for save_with_torchcodec`
- **Root cause:** torchaudio 2.9+ hardcodes torchcodec as the default
  audio save backend. torchcodec requires FFmpeg shared DLLs
  ("full-shared" build). This system uses a static FFmpeg build —
  incompatible. No torchaudio 2.8.x exists for Python 3.14.
- **Fix:** Created `sitecustomize.py` in `.venv/Lib/site-packages/` that
  monkey-patches `torchaudio.save` to use `soundfile.write` instead.
  Also installed `soundfile` via pip.
- **History:** First hit in MVAT_stem_webapp (Python 3.11, torch 2.5.1).
  Reappeared in audionlabs (Python 3.14, torch 2.10.0). Will reappear
  on any new environment.
- **Prevention:** Always copy `sitecustomize_backup.py` and install
  soundfile when setting up a new venv. Never install torchcodec.

### Error 2: sys.executable wrong Python on Windows
- **When:** Phase 3, Session 2
- **Symptom:** `subprocess.run([sys.executable, "-m", "demucs", ...])` fails
  with "No module named demucs" even though demucs is installed in the venv
- **Root cause:** On Windows, `sys.executable` resolves to the system Python
  (`C:\Python314\python.exe`) instead of the venv Python when uvicorn is
  started from certain contexts
- **Fix:** Both `demucs_engine.py` and `downloader.py` now construct the
  venv Python path explicitly:
  ```python
  VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
  PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
  ```

### Error 3: SVG background paths broke z-index
- **When:** Phase 1, Session 2 (MVAT_stem_webapp)
- **Symptom:** After adding animated SVG background paths (72 curved lines
  with CSS dashoffset animation), all interactive elements became
  unclickable. Cards, buttons, inputs — nothing responded.
- **Root cause:** The SVG element covered the full viewport and intercepted
  all pointer events. CSS `pointer-events: none` was applied but the
  z-index stacking was still broken across multiple browser versions.
- **Fix:** Deleted v7/v8/v9 entirely. Reverted to v5 which uses div-based
  aurora blobs with `pointer-events: none` — simpler and proven to work.
- **Lesson:** Stick with CSS-based background effects. Full-viewport SVGs
  are fragile for z-index layering.

### Error 4: yt-dlp file path capture
- **When:** Phase 2, Session 3 (audionlabs-downloader)
- **Symptom:** After downloading, the server couldn't find the output file.
  The file existed but the captured path was wrong.
- **Root cause:** yt-dlp moves files during post-processing (e.g., converting
  to MP3). The original output path becomes stale.
- **Fix:** Use `--print after_move:filepath` flag which prints the final
  file path after all post-processing moves. Parse the last line of stdout.

### Error 5: MP4 audio codec compatibility
- **When:** Phase 2, Session 3
- **Symptom:** Downloaded MP4 videos had no audio in some players
- **Root cause:** yt-dlp's default merge didn't guarantee AAC audio codec
- **Fix:** Added `--postprocessor-args "ffmpeg:-c:a aac"` to force AAC
  audio in all MP4 downloads

### Error 6: Blob download navigation
- **When:** Phase 2, Session 3
- **Symptom:** Clicking download links for AudionLabs results navigated
  the browser away from the page, losing all state
- **Root cause:** Direct `<a href="/file?path=...">` links trigger
  browser navigation
- **Fix:** Implemented blob-based downloads: fetch the file as a blob,
  create a temporary object URL, trigger a click on a dynamically created
  `<a>` element, then revoke the URL. No page navigation.

### Error 7: Flag name mismatch between downloader and processor
- **When:** Phase 2, Session 3
- **Symptom:** Send-to-AudionLabs sent the wrong flag names, causing the
  processor to ignore the selected options
- **Root cause:** Downloader UI used different checkbox IDs than what the
  processor API expected
- **Fix:** Mapped flag names correctly: `flag-stems` → `split_stems_flag`,
  `flag-slowed` → `slowed_reverb_flag`

### Error 8: Slowed+reverb lowpass too aggressive
- **When:** Phase 1, Session 2
- **Symptom:** Slowed+reverb output sounded muffled and lifeless
- **Root cause:** Initial lowpass cutoff was too low
- **Tuning history:**
  - 3kHz = too muffled, lost all presence
  - 4.5kHz = better but still noticeably dark
  - 6kHz = warm character without muddiness — **locked in**
- **Final settings:** `asetrate=sr*0.9, aresample=sr, lowpass=f=6000,
  loudnorm=I=-16:TP=-1.5:LRA=11`

---

## Known Bugs (Permanent Reference)

These bugs are documented here and in CLAUDE.md. They will reappear on new
environments. Do not delete this section.

### Bug 1: torchaudio torchcodec save error
- **Symptom:** Demucs processes audio successfully (progress bar completes)
  but then throws: `ImportError: TorchCodec is required for save_with_torchcodec`
- **Root cause:** torchaudio 2.9+ hardcodes torchcodec as the default audio
  save backend. torchcodec requires FFmpeg shared DLLs ("full-shared" build)
  which conflicts with the static FFmpeg build installed on this system.
  No torchaudio 2.8.x exists for Python 3.14.
- **Fix:** `sitecustomize.py` monkey-patch in `.venv` that replaces
  `torchaudio.save` with `soundfile.write`. Located at:
  `.venv/Lib/site-packages/sitecustomize.py`
  Also requires: `pip install soundfile`
- **First encountered:** MVAT_stem_webapp (Python 3.11, torch 2.5.1).
  Reappeared in audionlabs (Python 3.14, torch 2.10.0). Will likely
  reappear on any new environment.
- **Prevention:** Always copy `sitecustomize.py` and install soundfile
  when setting up a new venv. Do NOT install torchcodec.
- **Status:** FIXED — sitecustomize.py patch active

### Bug 2: sys.executable wrong Python on Windows
- **Symptom:** Demucs or yt-dlp subprocess calls fail with
  "No module named demucs/yt_dlp" even though they are installed in the venv
- **Root cause:** `sys.executable` resolves to the system Python
  (`C:\Python314\python.exe`) instead of the venv Python when uvicorn is
  started from a different context
- **Fix:** Use explicit venv Python path in subprocess:
  ```python
  VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
  PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
  ```
- **First encountered:** audionlabs merged project
- **Status:** FIXED — both `demucs_engine.py` and `downloader.py` use VENV_PYTHON

### Bug 3: New venv setup checklist
- **Symptom:** Multiple bugs appear when setting up a new venv from
  `requirements.txt` alone
- **Root cause:** Several fixes exist outside of `requirements.txt` that
  won't be replicated by just running `pip install`
- **Fix:** When setting up a new venv, always do ALL of these steps in order:
  1. `pip install -r requirements.txt`
  2. `pip install soundfile`
  3. Copy `sitecustomize_backup.py` to `.venv/Lib/site-packages/sitecustomize.py`
  4. Verify `demucs_engine.py` and `downloader.py` use VENV_PYTHON not sys.executable
  5. Test with: `.venv/Scripts/python.exe -c "import torchaudio, torch, demucs; print('OK')"`
- **Status:** DOCUMENTED — follow checklist on new environment setup

---

## Environment Setup Checklist

Run these steps IN ORDER when setting up on a new machine:

```
1.  python -m venv .venv
2.  .venv\Scripts\pip install -r requirements.txt
3.  .venv\Scripts\pip install soundfile
4.  Copy sitecustomize_backup.py to .venv\Lib\site-packages\sitecustomize.py
5.  Verify FFmpeg is installed system-wide:
      ffmpeg -version
6.  Verify yt-dlp works:
      .venv\Scripts\python -m yt_dlp --version
7.  Test all imports:
      .venv\Scripts\python -c "import fastapi, demucs, torchaudio, torch, yt_dlp; print('ALL OK')"
8.  Start server:
      python -m uvicorn backend.main:app --port 8000
9.  Health check:
      curl http://localhost:8000/health
```

**Critical:** Do NOT skip steps 3 and 4. Without them, Demucs will appear
to work but will fail at the file-save stage with the torchcodec error.

**Critical:** Do NOT use `--reload` flag on Windows. It causes zombie
uvicorn processes that hold the port open.

---

## Tech Stack Decisions & Why

### Python 3.14
- Latest stable Python at time of development
- Required torch 2.10.0+cpu (no 2.5.1 wheels available for 3.14)
- Caused the torchaudio version jump that triggered Bug 1

### FastAPI + Uvicorn
- Async-capable for file uploads and downloads
- Built-in static file serving (no separate nginx needed for dev)
- Pydantic request validation
- Single process serves both API and frontend

### Demucs (htdemucs model)
- Meta's open-source stem separation model
- Best quality-to-speed ratio for CPU-only inference
- Runs as subprocess to avoid memory leaks from repeated model loading
- htdemucs chosen over htdemucs_ft (fine-tuned) for speed

### FFmpeg (static build, system-wide)
- Used for slowed+reverb processing and yt-dlp post-processing
- Static build chosen over shared build because:
  - Simpler installation (single binary, no DLL management)
  - But: incompatible with torchcodec (which needs shared DLLs)
  - This tradeoff led to the sitecustomize.py monkey-patch solution
- `ffprobe` used to detect input sample rate (avoids hardcoding 44100)

### yt-dlp (via pip, not standalone binary)
- Installed in the venv so it uses the venv's Python and FFmpeg
- `--restrict-filenames` for safe filenames across all OS
- `--print after_move:filepath` for reliable output path capture
- Must be kept updated — YouTube regularly breaks older versions

### Vanilla HTML/CSS/JS (no framework)
- Four pages, each relatively simple
- No build step, no node_modules, no bundler config
- Single `app.js` with page detection — keeps the JS unified
- CSS custom properties for theming consistency

### soundfile (torchaudio replacement)
- Pure Python audio I/O library backed by libsndfile
- Used as the monkey-patched replacement for `torchaudio.save`
- No FFmpeg dependency for saving — works with static FFmpeg builds

---

## What Was Shelved & Why

### LoFi Mix Engine
- **What:** EQ filter + vinyl noise + compression + tape saturation + reverb
  applied to stems to create a lofi cover version
- **Why shelved:** Scope creep. The core product (stems + slowed+reverb +
  YouTube download) needed to ship first. LoFi processing also required
  stems as input, making it a compound operation that would complicate
  the UI and processing pipeline.
- **Code status:** `lofi_engine.py` exists in MVAT_stem_webapp with a
  working implementation. Can be ported to audionlabs when ready.
- **Planned for:** Phase 2 roadmap

### AI LoFi Cover Module
- **What:** Full AI-powered lofi cover generation pipeline
  (analysis → generation → rendering)
- **Why shelved:** R&D project, not production-ready. Lives in
  `MVAT_stem_webapp/mvat_lofi_cover/` as a separate module.
  Not integrated into any web UI.
- **Planned for:** Phase 3+ if demand exists

### User Accounts & Authentication
- **Why shelved:** Ship the tool first, add accounts later. Current
  architecture doesn't require auth — all processing is stateless
  and ephemeral.
- **Planned for:** Phase 2, after deployment

### API Key Auth Layer
- **What:** API key header for protecting endpoints
- **Why shelved:** Was needed when downloader and processor were separate
  apps calling each other. Merged architecture eliminated the need for
  inter-service auth. Will be revisited for rate limiting.

### Two-Server Architecture
- **What:** MVAT webapp on port 8000, downloader on port 8001, with
  cross-server API calls
- **Why shelved:** Replaced by the unified audionlabs app. Two servers
  meant two deployments, CORS issues, and the 502 error when one
  server wasn't running. Single app eliminated all of these.
- **Old repos kept intact** for reference but marked as archived.

---

## Deployment Plan

### Target Platforms (in evaluation order)
1. **Railway** — Simple Git-based deploys, supports Python + FFmpeg
2. **Render** — Free tier available, Docker support
3. **DigitalOcean App Platform** — More control, custom domains

### Requirements for Deployment
- FFmpeg must be available in the container/server
- Python 3.14 runtime
- Sufficient CPU for Demucs inference (no GPU required — using CPU-only torch)
- At minimum 2GB RAM for Demucs model loading
- Disk space for temporary upload/download/output files
- File cleanup strategy (cron job or on-demand cleanup)

### Pre-Deployment Checklist
1. Rate limiting on all endpoints (prevent abuse)
2. File size validation (reject uploads > X MB before processing)
3. Input sanitization on YouTube URLs
4. File cleanup — auto-delete processed files after N hours
5. HTTPS enforcement
6. Custom domain: **audionlabs.ai**
7. Error monitoring / logging
8. Health check endpoint already exists (`/health`)

### Deployment Considerations
- `--reload` flag must NOT be used in production (or dev on Windows)
- `sitecustomize.py` must be deployed with the venv
- FFmpeg must be a static build or the torchcodec issue must be handled
- yt-dlp should be pinned to a known-good version in production
- CORS is currently set to `allow_origins=["*"]` — tighten for production

---

## Future Roadmap

### Phase 2 (Post-Launch)
1. Rate limiting + file size validation
2. Custom domain (audionlabs.ai)
3. File cleanup automation (cron-based TTL on output files)
4. LoFi mix engine (port from MVAT_stem_webapp)
5. Zip download for batch stems
6. Real-time progress tracking (WebSocket or SSE instead of simulated bar)

### Phase 3 (Growth)
1. User accounts + authentication
2. Free/Pro subscription tiers:
   - Free: 3 songs/day, 100MB limit, slower processing
   - Pro: unlimited, faster queue, batch downloads
3. Processing queue system for heavy load
4. GPU-accelerated Demucs (RunPod or dedicated GPU server)

### Phase 4 (Scale)
1. CDN for processed file delivery
2. Multi-region deployment
3. API access for third-party integrations
4. Mobile-responsive redesign
5. AI LoFi cover generation (from MVAT R&D module)
