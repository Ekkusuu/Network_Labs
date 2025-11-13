FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY src/ ./src/
COPY boards/ ./boards/
COPY public/ ./public/
COPY tests/ ./tests/

# Expose port
EXPOSE 8080

# Set Python path
ENV PYTHONPATH=/app/src

# Run the server
CMD ["python", "src/server.py", "8080", "boards/perfect.txt"]
