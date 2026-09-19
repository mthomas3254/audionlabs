# AudionLabs — BLUEPRINT.md
*Single source of truth. Read this before touching any code.*

**Owner:** Malik Thomas | **GitHub:** mthomas3254/audionlabs
**Live:** https://audionlabs.ai | **Railway:** audionlabs-production.up.railway.app
**Local:** python -m uvicorn backend.main:app --port 8000
**Status:** LIVE IN PRODUCTION — v2 revamp shipped Sep 19, 2026 (see Section 15)

---

## 1. Product Overview

AudionLabs is a professional audio processing SaaS platform for YouTube creators,
DJs, remix artists, and producers. Four AI-powered tools in one clean interface.
No installs. No setup. Everything runs in the browser.

**Tools:**
1. **Stem Splitter** — Demucs AI isolates vocals, drums, bass, other, then a LIVE in-browser
   mixer (mute, solo, rebalance, export the mix, send it to the studio)
2. **Slowed + Reverb** — LIVE in-browser studio (Web Audio): speed, reverb, warmth, bass,
   presets, WAV export. Nothing uploads. The server FFmpeg render keeps its locked settings
   and is still used by the downloader page option "Signature slowed render"
3. **YouTube Downloader** — yt-dlp downloads any YouTube video as MP3 or MP4
4. **AI Transcription** — Whisper (local) + Claude Sonnet (summary/topics)

**Target users:** YouTube creators, TikTok creators, DJs, remix artists, producers

---

## 2. Architecture

### Backend
```
Python 3.14 + FastAPI + Uvicorn (single ASGI app)
```
Single FastAPI application serving both API and frontend static files.
No microservices. All processing via subprocess calls to external tools.

### Processing Pipeline
```
User uploads file / pastes YouTube URL
        ↓
FastAPI receives request (POST /process_audio or /download or /transcribe)
        ↓
File saved to uploads/<uuid>/
        ↓
Subprocess: Demucs → separated/htdemucs/<uuid>/   (if stems requested)
Subprocess: FFmpeg → slowed_outputs/<uuid>/        (if slowed+reverb requested)
Subprocess: yt-dlp → downloads/<title>.mp3|mp4    (if YouTube download)
Subprocess: Whisper → transcript text              (if transcription)
API: Claude Sonnet → summary + topics              (if transcription, Pro)
        ↓
JSON response with URLs to output files
        ↓
Frontend renders download buttons
```

### API Endpoints
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| POST | /process_audio | Stems + slowed+reverb | WORKING |
| POST | /download | YouTube yt-dlp download | MOSTLY FAILING on Railway (Bug 14, IP refused) |
| POST | /transcribe | Whisper + Claude AI | WORKING |
| GET | /file?path= | Serve output files | WORKING |
| GET | /health | Status check | WORKING |

### Frontend
```
HTML + CSS + Vanilla JavaScript (no framework, no build step)
```
Five pages, single `app.js` auto-detects page via `window.location.pathname`.

| Route | File | Status |
|-------|------|--------|
| / | index.html | LIVE |
| /stems | stems.html | LIVE |
| /slowed-reverb | slowed-reverb.html | LIVE |
| /youtube-downloader | youtube-downloader.html | LIVE |
| /transcribe | transcribe.html | LIVE |

**UI system (v2):** White Apple-style page, floating frosted pill navbar with sliding
indicator, bottom tab bar on phones, pill buttons and segmented controls, iOS switches,
stem colors (vocals pink, drums orange, bass blue, other green). All tokens live at the
top of style.css. Pages are assembled server-side by backend/pages.py from partials.

---

## 3. Folder Structure

```
audionlabs/
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, all routes, lazy imports
│   ├── pages.py                 # Page assembly: partials, cache-busting, AdSense injection
│   ├── config.py                # Paths, env vars, ensure_dirs()
│   ├── core/
│   │   ├── __init__.py
│   │   ├── demucs_engine.py     # split_stems() — Demucs CLI subprocess
│   │   ├── slowed_engine.py     # create_slowed_reverb_mix() — FFmpeg
│   │   ├── downloader.py        # download_media() — yt-dlp subprocess
│   │   └── transcribe_engine.py # transcribe_audio() — Whisper + Claude API
│   └── services/
│       ├── __init__.py
│       └── file_manager.py      # TrackPaths dataclass, UUID track IDs
├── backend/static/
│   ├── index.html               # Landing page — 4 tool cards
│   ├── stems.html               # Stem splitter
│   ├── slowed-reverb.html       # Slowed + reverb
│   ├── youtube-downloader.html  # YouTube download
│   ├── transcribe.html          # AI transcription
│   ├── privacy.html, terms.html
│   ├── partials/                # head.html, sprite.html, nav.html, footer.html
│   ├── style.css                # v2 light design system, tokens at the top
│   ├── app.js                   # Nav, landing, stems upload flow, downloader, transcribe
│   ├── audio-core.js            # Shared Web Audio helpers
│   ├── studio.js                # Live Slowed + Reverb studio
│   ├── mixer.js                 # Live stem mixer
│   └── favicon.svg
├── tests/                       # pytest: pages, AdSense, id contract, downloader
├── uploads/                     # Runtime: uploaded audio (ephemeral on Railway)
├── downloads/                   # Runtime: YouTube downloads (ephemeral)
├── separated/                   # Runtime: Demucs output (ephemeral)
├── slowed_outputs/              # Runtime: FFmpeg output (ephemeral)
├── transcripts/                 # Runtime: transcription temp files (ephemeral)
├── sitecustomize_backup.py      # CRITICAL: torchaudio monkey-patch backup
├── Dockerfile                   # Railway deployment (python:3.11-slim)
├── railway.toml                 # Railway build config (Dockerfile builder)
├── .dockerignore
├── DEPLOYMENT.md                # Railway + Cloudflare setup guide
├── requirements.txt             # Python 3.11 (Docker) deps
├── .env.example
├── .gitignore
├── CLAUDE.md                    # Short context file (pointer to this)
└── BLUEPRINT.md                 # This file
```

---

## 4. Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | Python 3.14 + FastAPI | Async, Pydantic validation, static serving |
| ASGI server | Uvicorn | Production-grade, no --reload on Windows |
| Stem separation | Demucs (htdemucs) | Best CPU quality/speed ratio |
| Slowed+reverb | FFmpeg | Precise filter chain control |
| YouTube download | yt-dlp | Best maintained YouTube extractor |
| Transcription | openai-whisper (small) | Free, local, no API cost |
| AI summary | Claude Sonnet (claude-sonnet-4-20250514) | Best summarization quality |
| Frontend | Vanilla HTML/CSS/JS | No build step, simple, fast |
| Hosting | Railway (Dockerfile) | Simple Git deploys, Python+FFmpeg support |
| DNS/CDN | Cloudflare (free) | CNAME flattening, DDoS protection, SSL |
| Domain | audionlabs.ai (Atom registrar) | Custom domain live |

---

## 5. Audio Settings (LOCKED — NEVER CHANGE)

```
Slowed+reverb:
  Speed:     0.9x (asetrate + aresample via FFmpeg)
  Lowpass:   6kHz (confirmed sweet spot after testing 3kHz, 4.5kHz, 6kHz)
  Loudnorm:  I=-16 LUFS, TP=-1.5dB, LRA=11

Demucs model: htdemucs (not htdemucs_ft — speed vs quality tradeoff)
```

---

## 6. Current Build Status

| Feature | Status | Notes |
|---------|--------|-------|
| Landing page | ✅ DONE | 4 tool cards, aurora bg |
| Stems tool | ✅ DONE | Demucs, all 4 stems |
| Slowed+reverb tool | ✅ DONE | Settings locked |
| YouTube downloader | ⚠️ PARTIAL | Tooling fixed. YouTube refuses the Railway IP. Needs proxy, cookies, or retirement |
| AI Transcription | ✅ DONE | Whisper + Claude, free+Pro UI |
| Railway deployment | ✅ DONE | Dockerfile, python:3.11-slim |
| Custom domain | ✅ DONE | audionlabs.ai via Cloudflare |
| SSL/HTTPS | ✅ DONE | Cloudflare handles it |
| Rate limiting | ❌ NOT STARTED | Next session priority |
| File size limits | ❌ NOT STARTED | 100MB max needed |
| File type validation | ❌ NOT STARTED | MP3/WAV/M4A only |
| Cloudflare WAF | ❌ NOT STARTED | Block bad bots |
| Google Analytics 4 | ❌ NOT STARTED | Add to all pages |
| Email capture | ❌ NOT STARTED | Mailchimp on landing page |
| Stripe + Pro tier | ❌ NOT STARTED | $9.99/mo |
| Auth system | ❌ NOT STARTED | JWT, email+password |
| Persistent storage | ❌ NOT STARTED | Files ephemeral on Railway |
| AdSense | ❌ NOT STARTED | After 1K monthly visitors |

---

## 7. Known Bugs (PERMANENT — Never Delete)

### Bug 1 — torchaudio torchcodec save error (FIXED)
**Symptom:** Demucs completes but throws ImportError: TorchCodec is required
**Root cause:** torchaudio 2.9+ hardcodes torchcodec. torchcodec needs FFmpeg
shared DLLs. System has static FFmpeg build. No torchaudio 2.8.x for Python 3.14.
**Fix:** sitecustomize.py monkey-patch replaces torchaudio.save with soundfile.write.
Backup at sitecustomize_backup.py. Also requires: pip install soundfile.
**DO NOT install torchcodec.** Fails on static FFmpeg builds.
**Status:** FIXED — patch active in local venv AND Docker image

### Bug 2 — sys.executable wrong Python on Windows (FIXED)
**Symptom:** ModuleNotFoundError for demucs/yt_dlp in subprocess
**Root cause:** sys.executable → system Python, not venv Python on Windows
**Fix:** Both demucs_engine.py and downloader.py use:
```python
VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
```
On Railway (Linux), .venv/Scripts/python.exe doesn't exist → falls back to
sys.executable correctly. No code changes needed for Railway.
**Status:** FIXED

### Bug 3 — New venv setup requirements (DOCUMENTED)
**Symptom:** Multiple bugs appear when setting up from requirements.txt alone
**Fix:** Follow Environment Setup Checklist (Section 9 below)
**Status:** DOCUMENTED

### Bug 11 — Railway port mismatch (FIXED)
**Symptom:** Railway Public Networking defaults to 8080, app runs on 8000
**Root cause:** Railway dashboard default port setting
**Fix:** Hardcoded PORT=8000 in Dockerfile CMD. Set PORT=8000 in Railway Variables.
**Status:** FIXED

### Bug 12 — Railway JSON credentials corruption (FIXED)
**Symptom:** Long JSON env vars corrupted when pasted normally
**Fix:** Generate via python -c "import json; print(json.dumps(...))" | clip
Then paste via Railway Raw Editor only.
**Status:** FIXED

### Bug 13 — $PORT not expanding in railway.toml (FIXED)
**Symptom:** Error: Invalid value for '--port': '$PORT' is not a valid integer
**Root cause:** railway.toml startCommand passes $PORT as literal string
**Fix:** Removed startCommand from railway.toml. Dockerfile CMD uses hardcoded 8000.
PORT=8000 set in Railway Variables.
**Status:** FIXED

### Bug 14 — YouTube bot detection on Railway (OPEN — tooling fixed, Railway IP refused)
**Symptom:** yt-dlp fails with "Sign in to confirm you're not a bot". Intermittent per video.

**What was actually broken in the image (FIXED Sep 19, 2026, commit b024af0):**
The production trace showed `JS runtimes: none` and every PO token provider unavailable.
- The image shipped Node 20. yt-dlp and bgutil 2.x both need Node >= 22, so both were
  silently disabled. The Apr 4 "fix" therefore never ran at all.
- The bgutil server was cloned at tag 1.2.2 while pip installed plugin 2.0.0.
- yt-dlp was installed without its `default` group, so the EJS solver scripts were missing.
- yt-dlp enables only Deno by default, so Node also has to be named with `--js-runtimes node`.
Now: Node 22, server and plugin pinned to one `BGUTIL_VERSION`, `yt-dlp[default]`, and the
build fails if Node < 22. Verified in the trace: `JS runtimes: node-22`, challenge provider
`node`, and "Retrieved a gvs PO Token for web client".

**What is still failing, with evidence (Sep 19, 2026):**
With that toolchain fully working, 7 of 8 production downloads still failed. A diagnostic run
asked for ten client types. YouTube answered LOGIN_REQUIRED to every one of them (web,
web_safari, web_embedded, mweb, ios, android_vr, tv, tv_downgraded, visionos) on all 8
requests. The identical command succeeds from a residential connection. Code, yt-dlp version,
flags, runtime, and tokens are all eliminated, so the remaining variable is the Railway
network address. One popular video still succeeds, and a fresh container briefly succeeded
3 of 3, which fits IP reputation that varies by egress address.

**Two wrong diagnoses were recorded here earlier on Sep 19 and are retracted:** "only a proxy
can fix it" (said before the broken toolchain was found) and "it was just a stale yt-dlp".

**Remaining options (owner decision, all already supported by downloader.py):**
1. `YTDLP_PROXY` = a residential proxy. Most reliable. Paid, roughly a few dollars per GB.
2. `YTDLP_COOKIES_FILE` = cookies from a logged-in account. Free, but the account can be
   banned and cookies expire.
3. Retire or hide the downloader. This also removes the AdSense policy conflict below.
Third-party "YouTube to MP3" APIs exist, but they solve the same block with proxies and add
cost, a dependency, and legal exposure.

**Diagnosing next time:** `railway logs -p b369b5d5-59a9-425b-96ea-511f00a17231 -s audionlabs
-e production -n 400`, then look for `[ytdlp]` lines. Set `YTDLP_PLAYER_CLIENTS=all` to log
the status YouTube returns for every client type.
**AdSense conflict:** Google publisher policy does not allow ads next to YouTube download
tools. pages.py never injects ads on /youtube-downloader. Approval may still hinge on it.
**Status:** OPEN — blocked on the owner choosing option 1, 2, or 3

---

## 8. Deployment Configuration

### Docker (Railway)
```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y ffmpeg git
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir soundfile
RUN python -c "import whisper; whisper.load_model('small')"  # Pre-download
COPY sitecustomize_backup.py /usr/local/lib/python3.11/site-packages/sitecustomize.py
COPY . .
RUN mkdir -p uploads downloads separated slowed_outputs transcripts
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### railway.toml
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
```

### Railway Environment Variables
| Variable | Value | Notes |
|----------|-------|-------|
| PORT | 8000 | Must match Dockerfile CMD |
| ANTHROPIC_API_KEY | sk-ant-... | Set in Railway Variables tab |
| ADSENSE_CLIENT | ca-pub-XXXXXXXXXXXXXXXX | Optional. Turns on the AdSense head tag, meta tag, and /ads.txt |
| ADSENSE_SLOT | digits | Optional. Turns on the in-page ad unit. Without it only Auto ads work |
| YTDLP_PROXY | http://user:pass@host:port | Optional. Residential proxy. The Bug 14 fix |
| YTDLP_COOKIES_FILE | /path/cookies.txt | Optional fallback for Bug 14. Fragile |
| YTDLP_JS_RUNTIME | node | Optional. JS runtime yt-dlp uses. Default node |
| YTDLP_PLAYER_CLIENTS | all | Optional, diagnostics only. Logs YouTube's answer per client type |
| SITE_URL | https://audionlabs.ai | Optional. Used in robots.txt and sitemap.xml |

### DNS (Cloudflare)
- audionlabs.ai → CNAME → Railway (Proxied, orange cloud)
- www.audionlabs.ai → CNAME → Railway (Proxied)
- Nameservers: daniella.ns.cloudflare.com, jakub.ns.cloudflare.com
- SSL: Cloudflare handles HTTPS automatically

### Important Railway Notes
- Build time: ~200s first build (Whisper download), ~40s cached
- Files in uploads/downloads/separated/ are EPHEMERAL — deleted on redeploy
- Persistent storage needed before heavy production use (Railway Volumes or S3)
- Auto-deploys on every push to master branch

---

## 9. Environment Setup Checklist (New Machine)

```
1.  python -m venv .venv
2.  .venv\Scripts\pip install -r requirements.txt
3.  .venv\Scripts\pip install soundfile
4.  Copy sitecustomize_backup.py → .venv\Lib\site-packages\sitecustomize.py
5.  Verify FFmpeg: ffmpeg -version
6.  Verify yt-dlp: .venv\Scripts\python -m yt_dlp --version
7.  Test imports: .venv\Scripts\python -c "import fastapi, demucs, torchaudio, torch, yt_dlp; print('ALL OK')"
8.  Start: python -m uvicorn backend.main:app --port 8000
9.  Health: curl http://localhost:8000/health
```
**Critical:** Steps 3 and 4 are mandatory. Without them Demucs fails at file-save.
**Critical:** Never use --reload on Windows (zombie processes hold the port).

---

## 10. Key Design Decisions

**Lazy imports in main.py:** Heavy imports (torch, demucs, whisper) are NOT at
module level. They are imported inside each endpoint function. This ensures FastAPI
starts in <1 second and passes Railway's health check immediately.

**Subprocess isolation:** Demucs, FFmpeg, and yt-dlp all run as CLI subprocesses.
This avoids memory leaks, model loading issues, and allows clean load/unload.

**Single app architecture:** Replaces previous two-server setup (port 8000 + 8001).
Eliminates CORS issues, 502 errors, and deployment complexity.

**Python 3.11 in Docker, 3.14 local:** Docker uses 3.11-slim (stable torch wheels).
Local dev uses 3.14. requirements.txt targets Docker (torch==2.5.1+cpu).
Local venv uses torch==2.10.0+cpu manually after pip install.

**Cloudflare for custom domain:** Atom registrar blocks CNAME on root domain (@).
Cloudflare CNAME flattening solves this — audionlabs.ai works without www.

---

## 11. What's Shelved & Why

| Feature | Status | Reason |
|---------|--------|--------|
| LoFi mix engine | Shelved | Scope creep — ship core first. Code in MVAT_stem_webapp/lofi_engine.py |
| AI LoFi cover module | Shelved | R&D, not production-ready. In MVAT_stem_webapp/mvat_lofi_cover/ |
| Auth system | Not started | Ship tool first, add accounts after real users exist |
| Two-server architecture | Abandoned | Replaced by unified app |
| SVG aurora background | Abandoned | Broke z-index layering — div-based aurora blobs used instead |

---

## 12. Go-To-Market Plan

**Revenue model:**
- Free tier: 5 uses/day per tool, ads (AdSense after 1K visitors)
- Pro: $9.99/month or $79/year — unlimited + AI features + no ads
- Future: API access ($29/mo), enterprise/white label

**Acquisition channels (priority order):**
1. TikTok/Reels — 30s demo videos (YouTube → stems = viral hook)
2. Product Hunt — Tuesday 12:01am PST launch
3. SEO — Google Search Console, JSON-LD, blog content
4. Twitter/X — founder story thread
5. Directories — Futurepedia, AlternativeTo, AI Tool Hunt, BetaList
6. Reddit — r/WeAreTheMusicMakers, r/beatmakers, r/edmproduction

**Before public marketing (must complete first):**
- Bug 14 fix (YouTube downloader broken)
- Rate limiting
- File size/type validation
- Google Analytics 4
- Email capture
- Stripe + Pro tier

---

## 13. Session Log

| Session | Date | What Was Built | Commit |
|---------|------|----------------|--------|
| MVAT S1 | Mar 9 | Stem webapp v1 — Demucs, slowed+reverb, lofi, UI | — |
| MVAT S2 | Mar 10 | Audio tuning (6kHz locked), UI v5 redesign | — |
| MVAT S3 | Mar 13 | UI unification, downloader aesthetic port | — |
| Downloader S1-S3 | Mar 13 | yt-dlp downloader, two-step download flow, Send-to-AudionLabs | — |
| Unified S1 | Mar 13 | Merged app — single backend, unified UI | — |
| Unified S2 | Mar 14 | Transcribe backend (Whisper + Claude API) | 62d7134 |
| Unified S3 | Mar 14 | Transcribe frontend (upload/YouTube tabs, results) | d1f6427 |
| Unified S4 | Mar 14 | Session save — docs update | ec6081a |
| Deploy S1 | Mar 16 | Dockerfile, railway.toml, deployment config | — |
| Deploy S2 | Mar 16 | Lazy imports fix (startup crash) | af160e3 |
| Deploy S3 | Mar 16 | PORT fix (hardcoded 8000) | 4a06420 |
| Deploy S4 | Mar 16 | LIVE — health check passed, audionlabs.ai connected | — |
| Docs | Apr 4 | Full BLUEPRINT + CLAUDE.md cleanup and status update | — |
| Bug 14 try | Apr 4 | PO Token provider (bgutil). Did not fix the IP block | 6e21f93 |
| Revamp v2 | Sep 19 | Light pill UI on all pages, live Slowed+Reverb studio, live stem mixer, AdSense plumbing, privacy/terms, tests. Rebuild also fixed Bug 14 | see git log |

## 14. Next Session Goals
1. AdSense: owner creates the account, then sets ADSENSE_CLIENT (and ADSENSE_SLOT) in Railway
   Variables. The site already serves the tag, the meta tag, /ads.txt, /privacy, and /terms
2. Bug 14: owner picks a residential proxy (YTDLP_PROXY), cookies, or retiring the downloader
3. Create the hello@audionlabs.ai mailbox (Cloudflare Email Routing). Privacy and Terms cite it
4. Rate limiting on all endpoints (slowapi or custom middleware)
5. File size limit — 100MB max enforced in backend
6. Google Analytics 4
7. Studio extras: MP3 export, trim, independent pitch, saved presets (Pro candidates)
8. Update BLUEPRINT.md + commit at session close

---

## 15. v2 Revamp (Sep 19, 2026)

### What changed
- **Design:** dark aurora theme replaced by a white, Apple-style, pill-based UI on every page.
  Mockup kept at renditions/v2-light.html.
- **Live Slowed + Reverb studio** (`studio.js`): decodes the file in the browser, plays it through
  bass shelf, low-pass, dry plus convolver reverb, then a limiter, and updates every node live as
  sliders move. Speed uses playbackRate, so pitch follows speed exactly like the FFmpeg asetrate
  method. Export renders the same graph in an OfflineAudioContext to a 16-bit WAV. Presets:
  Signature slowed (0.90x, 6 kHz, 30% reverb), Deep slowed, Nightcore, Sped up, Original.
- **Live stem mixer** (`mixer.js`): after Demucs finishes, the four stems load into AudioBuffers
  and start on one shared clock, so they stay sample-aligned. Per-stem mute, solo, and volume
  (0 to 150%), Full mix / Instrumental / Acapella shortcuts, export of the current balance, and
  "Open mix in Slowed + Reverb", which hands the rendered mix to the studio through IndexedDB.
  Exports are scaled down only when the stems would sum past full scale.
- **`audio-core.js`:** shared helpers (decode, peaks, waveform drawing, impulse response, WAV
  encoder, handoff storage).
- **`backend/pages.py`:** assembles pages from `static/partials/` (head, sprite, nav, footer),
  stamps asset URLs with a version for Cloudflare cache-busting, and injects AdSense when the
  env vars are set. Ads never load on /youtube-downloader, /privacy, or /terms.
- **New routes:** /privacy, /terms, /ads.txt, /robots.txt, /sitemap.xml.
- **Stale-page guard:** pre-v2 pages had no cache headers, so browsers can serve old HTML from
  cache. app.js (always fetched fresh) detects the old markup and refetches the page once.
- **Fixed:** empty file bar showing before upload (an id rule beat the `hidden` attribute),
  unstyled Browse button on Transcribe, dead Sign In / Join links (removed until auth exists).

### Rules for the v2 frontend
- Pages contain comment placeholders (`<!-- NAV -->`, `<!-- HEAD_COMMON -->`, `<!-- AD_SLOT -->`,
  `__V__`). Always load pages through the app, never by opening the HTML file directly.
- Never rename an element id that app.js or studio.js looks up. `tests/test_site.py` fails if a
  page is missing one.
- The locked audio settings in Section 5 still govern the SERVER render. The live studio is a
  separate, user-adjustable path whose default preset mirrors them.

### Testing
```
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests -q
```
Browser checks done for this release: studio playback rate, presets, seek, loop, export length
and peak level, low-pass and bass measurements; full upload to Demucs to mixer flow; mute, solo,
shortcuts, mix export peak, studio handoff; transcription; local YouTube download; no horizontal
overflow at 375px on all seven pages.
