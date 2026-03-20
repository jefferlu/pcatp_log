# ATP Log Analyzer — Docker Image
FROM python:3.11-slim

WORKDIR /app

# System dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Runtime data directory (DuckDB lives here, mounted as volume)
RUN mkdir -p /data
ENV ATP_DATA_DIR=/data

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
