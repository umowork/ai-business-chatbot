FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: install RAG dependencies
RUN pip install --no-cache-dir numpy PyMuPDF 2>/dev/null || true

# Copy application code
COPY . .

# Create documents directory
RUN mkdir -p documents

RUN useradd --create-home appuser
USER appuser

# Default: run Telegram bot
CMD ["python", "main.py"]
