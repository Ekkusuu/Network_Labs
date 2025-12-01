FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY src/ ./src/

# Expose port
EXPOSE 5000

# Set Python path
ENV PYTHONPATH=/app/src

# Default command (can be overridden in docker-compose)
CMD ["python", "src/leader.py"]
