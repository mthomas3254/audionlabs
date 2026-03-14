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

## Build Order
1. ~~Project setup + copy engines from both projects~~ DONE
2. ~~Merged main.py with all routes~~ DONE
3. ~~Landing page (index.html)~~ DONE
4. ~~Stems page~~ DONE
5. ~~Slowed+reverb page~~ DONE
6. ~~YouTube downloader page~~ DONE
7. ~~SEO meta tags on all pages~~ DONE

## Known Issues
- torch/torchaudio pinned to 2.10.0+cpu (Python 3.14)
- FFmpeg must be installed system-wide
- Run without --reload flag on Windows to avoid zombie processes
- Demucs not yet tested end-to-end in merged app
- Slowed+reverb not yet tested in merged app
- YouTube downloader → AudionLabs pipeline not yet tested
- SEO meta tags added but not verified

## Next Session Priorities
1. Full stress test — stems, slowed+reverb, YouTube downloader
2. Fix any bugs found during stress test
3. Deployment planning (Railway / Render / DigitalOcean)

## Important Notes
- This replaces both MVAT_stem_webapp and audionlabs-downloader
- Single port: 8000
- No cross-server calls — downloader and processor are in same app
- Keep MVAT_stem_webapp and audionlabs-downloader repos intact
  (archive, don't delete)
