FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS. yt-dlp needs a JavaScript runtime to solve YouTube's challenges, and
# both yt-dlp and the bgutil PO token script require Node >= 22. Node 20 silently
# disabled both, which was the real cause of Bug 14. Fail the build if this regresses.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node -e "process.exit(+process.versions.node.split('.')[0] >= 22 ? 0 : 1)"

# bgutil PO token generation script (default path: ~/bgutil-ytdlp-pot-provider/).
# BGUTIL_VERSION must match the pip plugin version installed below.
ARG BGUTIL_VERSION=2.0.0
RUN cd /root \
    && git clone --single-branch --branch ${BGUTIL_VERSION} https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    && cd bgutil-ytdlp-pot-provider/server \
    && npm ci --no-audit --no-fund \
    && npx tsc \
    && test -f build/generate_once.js

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir soundfile

# Latest yt-dlp with its "default" group, which includes yt-dlp-ejs, the challenge
# solver scripts the JS runtime runs. The plugin version matches BGUTIL_VERSION above.
RUN pip install --no-cache-dir -U "yt-dlp[default]"
RUN pip install --no-cache-dir "bgutil-ytdlp-pot-provider==${BGUTIL_VERSION}"

RUN python -c "import whisper; whisper.load_model('small')"

COPY sitecustomize_backup.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

COPY . .

RUN mkdir -p uploads downloads separated slowed_outputs transcripts

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
