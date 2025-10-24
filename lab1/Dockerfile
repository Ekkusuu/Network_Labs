# Multi-stage not necessary; simple Python slim image
FROM python:3.12-slim
WORKDIR /app
# Copy server code
COPY server/server.py /app/server.py
# Copy content into image (can also be mounted)
COPY content /app/content
EXPOSE 8080
ENTRYPOINT ["python", "server.py", "content", "--host", "0.0.0.0", "--port", "8080"]
