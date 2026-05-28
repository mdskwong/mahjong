# Use a lightweight Python base image
FROM python:3.11-slim

WORKDIR /app

# Copy backend and frontend source directories
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Start the application
CMD ["python", "backend/main.py"]