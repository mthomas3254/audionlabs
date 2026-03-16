FROM python:3.11-slim

# Ensure logs appear in Railway in real time
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (cache layer)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir soundfile

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

# Start command — Railway sets $PORT dynamically
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
