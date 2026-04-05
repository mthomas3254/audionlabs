FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS (required for bgutil POT script)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Build bgutil POT generation script (default path: ~/bgutil-ytdlp-pot-provider/)
RUN cd /root \
    && git clone --single-branch --branch 1.2.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    && cd bgutil-ytdlp-pot-provider/server \
    && npm install \
    && npx tsc

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir soundfile

# Upgrade yt-dlp to latest + install POT provider plugin (Bug 14 fix)
RUN pip install --no-cache-dir -U yt-dlp
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider

RUN python -c "import whisper; whisper.load_model('small')"

COPY sitecustomize_backup.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

COPY . .

RUN mkdir -p uploads downloads separated slowed_outputs transcripts

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
