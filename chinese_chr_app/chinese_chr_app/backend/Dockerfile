FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
# Build context is chinese_chr_app/, so backend files are at chinese_chr_app/backend/
COPY chinese_chr_app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code. When adding a new module imported by app.py, add it here.
# Current app.py local imports: auth, database, pinyin_search, pinyin_recall
COPY chinese_chr_app/backend/app.py .
COPY chinese_chr_app/backend/auth.py .
COPY chinese_chr_app/backend/database.py .
COPY chinese_chr_app/backend/pinyin_search.py .
COPY chinese_chr_app/backend/pinyin_recall.py .

# Copy data files (JSON only) - maintain directory structure
# Build context is chinese_chr_app/, so data/ is at data/
# Exclude PNG files - they're served from GCS, not bundled in container
# Create data directory first
RUN mkdir -p ./data/backups
COPY data/characters.json ./data/
COPY data/extracted_characters_hwxnet.json ./data/
COPY data/radical_stroke_counts.json ./data/
# Note: characters_by_radicals.json is generated dynamically, so we don't need to copy it

# Fail the build if app cannot be imported (e.g. missing local module). Prevents 503 in prod.
RUN python -c "import app"

# Expose port (Cloud Run will set PORT env var)
ENV PORT=8080
EXPOSE 8080

# Run with gunicorn (Cloud Run compatible)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
