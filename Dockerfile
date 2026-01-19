# WatchVine WhatsApp Bot - Clean Production Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including SSL/TLS libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    ca-certificates \
    openssl \
    libssl-dev \
    python3-certifi \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install wheel before other packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel certifi

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Startup script - Complete flow then start main app
CMD python startup_flow.py && python main.py
