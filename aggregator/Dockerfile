# Multi-stage build for Python aggregator service
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Create non-root user for security
RUN useradd -m -u 1000 aggregator && \
    mkdir -p /app && \
    chown -R aggregator:aggregator /app

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder --chown=aggregator:aggregator /root/.local /home/aggregator/.local

# Copy application code
COPY --chown=aggregator:aggregator ./app ./app

# Set environment variables
ENV PATH=/home/aggregator/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Switch to non-root user
USER aggregator

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
