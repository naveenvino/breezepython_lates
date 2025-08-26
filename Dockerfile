# Production Dockerfile for Trading System
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-prod.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY src/ ./src/
COPY unified_api_correct.py .
COPY static/ ./static/
COPY *.html ./

# Create necessary directories
RUN mkdir -p logs data backups

# Create non-root user for security
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app

# Switch to non-root user
USER trader

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/monitoring/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "unified_api_correct:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]