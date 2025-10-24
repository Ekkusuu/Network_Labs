FROM python:3.11-slim
WORKDIR /app
COPY . /app
EXPOSE 8080 8081
CMD ["python", "server.py", "content", "--host", "0.0.0.0", "--port", "8080"]
