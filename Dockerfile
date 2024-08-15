# Use the official Python image as the base image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and set permissions
RUN useradd -m nonrootuser
USER nonrootuser

# Set the working directory in the container
WORKDIR /app

# Copy the project files to the working directory
COPY WebSocket/ .

# Create a virtual environment and activate it
RUN python -m venv venv
ENV PATH="/app/venv/bin:$PATH"

# Install the project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the necessary port
EXPOSE 8081

# Set the entrypoint command to run the application
CMD ["python", "main.py"]
