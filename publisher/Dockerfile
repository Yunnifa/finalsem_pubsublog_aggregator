# Multi-stage build for Python publisher service
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 publisher && \
    mkdir -p /app && \
    chown -R publisher:publisher /app

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=publisher:publisher publisher.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER publisher

# Run publisher
CMD ["python", "publisher.py"]
