FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
# Build context is chinese_chr_app/, so backend files are at chinese_chr_app/backend/
COPY chinese_chr_app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (app.py imports auth and database)
COPY chinese_chr_app/backend/app.py .
COPY chinese_chr_app/backend/auth.py .
COPY chinese_chr_app/backend/database.py .

# Copy data files (JSON only) - maintain directory structure
# Build context is chinese_chr_app/, so data/ is at data/
# Exclude PNG files - they're served from GCS, not bundled in container
# Create data directory first
RUN mkdir -p ./data/backups
COPY data/characters.json ./data/
COPY data/extracted_characters_hwxnet.json ./data/
# Note: characters_by_radicals.json is generated dynamically, so we don't need to copy it

# Expose port (Cloud Run will set PORT env var)
ENV PORT=8080
EXPOSE 8080

# Run with gunicorn (Cloud Run compatible)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
