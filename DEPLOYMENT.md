# AudionLabs — Railway Deployment Guide

## Prerequisites
- Railway account (railway.app)
- GitHub repo connected to Railway
- audionlabs.ai domain from Atom

## Environment Variables (set in Railway dashboard)
- ANTHROPIC_API_KEY = your key
- PORT = 8000 (Railway sets this automatically)

## Deploy Steps
1. Go to railway.app/new
2. Select "Deploy from GitHub repo"
3. Select mthomas3254/audionlabs
4. Railway auto-detects Dockerfile
5. Add environment variable: ANTHROPIC_API_KEY
6. Click Deploy
7. Wait ~10-15 mins (Whisper model download)
8. Check /health endpoint

## Custom Domain
1. In Railway project → Settings → Domains
2. Add custom domain: audionlabs.ai
3. Copy the CNAME value Railway gives you
4. Go to Atom DNS settings
5. Add CNAME record: @ → Railway CNAME
6. Wait 10-60 mins for DNS propagation

## Notes
- First deploy takes longer (Whisper model bakes into image)
- Railway auto-deploys on every git push to master
- Logs available in Railway dashboard

## Local Development (Python 3.14)
Local dev uses Python 3.14 with torch 2.10.0+cpu.
The Docker/Railway build uses Python 3.11 with torch 2.5.1+cpu.

To restore local requirements after editing for Docker:
```
pip install torch==2.10.0+cpu torchaudio==2.10.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
```

## Dockerfile Notes
- Python 3.11-slim (not 3.14) because torch 2.5.1 has 3.11 wheels
- FFmpeg installed via apt-get (no static build needed on Linux)
- Whisper small model pre-downloaded during build (~462MB)
- sitecustomize.py patch copied as backup (torchaudio torchcodec fix)
- VENV_PYTHON fallback works automatically — no .venv on Linux, so
  sys.executable is used (correct behavior in container)
