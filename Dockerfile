FROM python:3.11-slim

# Ensure logs appear in Railway in real time
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS (required for bgutil POT server)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (cache layer)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir soundfile

# Upgrade yt-dlp to latest + install POT provider plugin (Bug 14 fix)
RUN pip install --no-cache-dir -U yt-dlp
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider

# Pre-download Whisper small model so first user
# doesn't wait for download
RUN python -c "import whisper; whisper.load_model('small')"

# Copy sitecustomize patch
COPY sitecustomize_backup.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p uploads downloads separated slowed_outputs transcripts

# Expose port
EXPOSE 8000

# Start POT server, poll until ready, then start uvicorn
CMD bash -c "bgutil-provider &>/dev/null & \
  echo 'Waiting for POT server...' && \
  until curl -s http://localhost:4416 > /dev/null 2>&1; do \
    sleep 1; \
  done && \
  echo 'POT server ready.' && \
  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
