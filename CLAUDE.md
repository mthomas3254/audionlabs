# AudionLabs — Claude Code Context

## READ THIS FIRST
Read BLUEPRINT.md completely before touching any code.
BLUEPRINT.md is the single source of truth.

## Quick Reference
- **Owner:** Malik Thomas
- **Path:** C:\Users\User\PycharmProjects\audionlabs\
- **GitHub:** mthomas3254/audionlabs (private)
- **Live URL:** https://audionlabs.ai
- **Railway URL:** audionlabs-production.up.railway.app
- **Run locally:** python -m uvicorn backend.main:app --port 8000
- **Stack:** Python 3.14 + FastAPI + Demucs + Whisper + Claude API
- **Status:** LIVE IN PRODUCTION (v2 revamp shipped Sep 19, 2026)
- **Tests:** .venv\Scripts\python -m pytest tests -q

## What This Does
AudionLabs is a professional audio processing SaaS for YouTube creators,
DJs, remix artists, and producers. Four tools, one platform:
1. Stem Splitter (Demucs AI) + LIVE in-browser stem mixer (mute, solo, rebalance, export)
2. Slowed + Reverb LIVE studio (Web Audio in the browser: speed, reverb, warmth, bass, WAV export)
3. YouTube Downloader (yt-dlp — MP3/MP4)
4. AI Transcription (Whisper + Claude Sonnet — free + Pro features)

## Pages & Endpoints
| Route | File | Status |
|-------|------|--------|
| / | index.html | LIVE |
| /stems | stems.html | LIVE |
| /slowed-reverb | slowed-reverb.html | LIVE |
| /youtube-downloader | youtube-downloader.html | LIVE |
| /transcribe | transcribe.html | LIVE |
| /privacy, /terms | privacy.html, terms.html | LIVE |
| /ads.txt, /robots.txt, /sitemap.xml | backend/pages.py | LIVE (ads.txt only when ADSENSE_CLIENT is set) |
| POST /process_audio | queues stems + slowed, returns 202 job_id | WORKING |
| GET /jobs/{id} | job status / result | WORKING |
| POST /download | YouTube yt-dlp | MOSTLY FAILING on Railway (Bug 14, YouTube refuses the IP) |
| POST /transcribe | queues Whisper + Claude, returns 202 job_id | WORKING |
| GET /health | health check | WORKING |

## Current Status — Feature Checklist
- [x] Landing page
- [x] Stems page + backend (Demucs)
- [x] Slowed+reverb page + backend (FFmpeg)
- [x] YouTube downloader page + backend (yt-dlp)
- [x] Transcribe page + backend (Whisper + Claude API)
- [x] Railway deployment
- [x] Custom domain (audionlabs.ai via Cloudflare)
- [x] SSL/HTTPS (Cloudflare)
- [x] v2 light pill UI on all pages (Sep 19, 2026)
- [x] Live Slowed + Reverb studio (studio.js)
- [x] Live stem mixer (mixer.js)
- [x] AdSense plumbing, privacy, terms, ads.txt (waiting on publisher id)
- [x] pytest suite (tests/)
- [x] Modal GPU backend for stems, built and tested, OFF until DEMUCS_BACKEND=modal + Modal tokens are set
- [ ] **YouTube bot detection (Bug 14 — toolchain fixed Sep 19, but YouTube refuses the Railway IP)**
- [ ] Rate limiting
- [ ] File size limits (100MB)
- [ ] File type validation
- [ ] Google Analytics 4
- [ ] Email capture (Mailchimp)
- [ ] Stripe + Pro tier
- [ ] Auth system
- [ ] Persistent file storage

## Audio Settings (LOCKED — NEVER CHANGE)
- Slowed+reverb: 0.9x speed, 6kHz lowpass, loudnorm I=-16 TP=-1.5 LRA=11
- Demucs model: htdemucs

## Next Session Priorities (in order)
0a. **Modal GPU** — owner signs up at modal.com and runs `pip install modal && modal setup`. Then:
    `modal deploy modal_app/demucs_gpu.py`, `modal token new`, set DEMUCS_BACKEND=modal and both
    MODAL_TOKEN_* in Railway. Splits drop from ~2 minutes to ~20 seconds
0. **AdSense** — owner creates the account, then set ADSENSE_CLIENT and ADSENSE_SLOT in Railway
1. **Bug 14** — owner decision: YTDLP_PROXY (residential proxy), YTDLP_COOKIES_FILE, or retire the downloader
2. **Security hardening** — rate limiting, file size limits, file type validation, Cloudflare WAF
3. **Analytics** — Google Analytics 4 on all pages
4. **Email capture** — Mailchimp signup on landing page
5. **Stripe + Pro tier** — $9.99/month, usage limits on free tier
6. **Persistent storage** — Railway Volumes or S3 (files deleted on redeploy)

## Deployment Info
- Platform: Railway (Dockerfile — python:3.11-slim)
- Region: asia-southeast1
- Port: 8000 (hardcoded — no $PORT expansion issue)
- Cloudflare proxy: active (orange cloud)
- Auto-deploys on every git push to master
- ANTHROPIC_API_KEY set in Railway Variables
- Whisper small model (~462MB) baked into Docker image

## Known Active Bugs
See BLUEPRINT.md → Known Bugs section for full detail.
- **Bug 15 (FIXED Sep 21):** Cloudflare 524 on splits and a frozen site during a split. Long work now runs
  as background jobs (backend/jobs.py). Never call Demucs or Whisper from a request handler again
- **Bug 14 (OPEN):** image toolchain was broken (Node 20, mismatched bgutil, no EJS) and is now fixed.
  YouTube still returns LOGIN_REQUIRED to all ten client types from the Railway IP. See BLUEPRINT.md.
  Read `[ytdlp]` lines in Railway logs before theorizing
- **Bug 1 (FIXED):** torchaudio torchcodec save error — sitecustomize.py patch
- **Bug 2 (FIXED):** sys.executable wrong Python on Windows — VENV_PYTHON fix
- **Bug 11 (FIXED):** Railway port mismatch — hardcoded 8000
- **Bug 12 (FIXED):** JSON credentials corruption — Raw Editor paste
- **Bug 13 (FIXED):** $PORT not expanding in railway.toml startCommand

## Critical Rules
- NEVER use --reload flag on Windows (zombie processes)
- NEVER commit .env
- NEVER change audio settings (6kHz, 0.9x, loudnorm values)
- NEVER use sys.executable in subprocess — always use VENV_PYTHON
- Always lazy-load heavy imports (torch, demucs, whisper) inside endpoints
- NEVER run Demucs, Whisper, or anything slower than ~10s inside a request handler. Queue it
  through backend/jobs.py. Cloudflare drops requests at 100s and async handlers block the loop
- sitecustomize.py patch must be in Docker image AND local venv
- NEVER rename an element id that app.js or studio.js looks up (tests/test_site.py enforces this)
- Pages use placeholders filled by backend/pages.py. Load them through the app, not as files
- Ads load on every page by owner decision. /youtube-downloader is the policy risk. The off switch
  is ADSENSE_EXCLUDE in Railway Variables, not a code change
- Run the tests before every push. Master auto-deploys

## Go-To-Market (parallel to dev)
- TikTok/Reels: demo videos (YouTube → stems pipeline)
- Product Hunt: launch Tuesday 12:01am PST
- SEO: Google Search Console + JSON-LD structured data
- Twitter/X: founder story + build thread
- Directories: Futurepedia, AlternativeTo, AI Tool Hunt
- Revenue model: Free (5/day) → Pro $9.99/mo → Ads (AdSense)
