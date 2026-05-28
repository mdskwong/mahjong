# Use a lightweight Python base image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for OpenCV and Ultralytics
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend and frontend source directories
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY model/ /app/model/
COPY weights/ /app/weights/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Start the application
CMD ["python", "backend/main.py"]