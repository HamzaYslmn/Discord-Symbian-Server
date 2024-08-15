# Use the official Python 3.11-slim image as the base image
FROM python:3.11-slim

# Install Node.js 20
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory for the HttpProxy app
WORKDIR /app/HttpProxy

# Copy the HttpProxy app files
COPY HttpProxy/package*.json ./
COPY HttpProxy/index.js ./

# Install Node.js dependencies
RUN npm install

# Set the working directory for the WebSocket app
WORKDIR /app/WebSocket

# Copy the WebSocket app files
COPY WebSocket/main.py ./

# Expose the ports
EXPOSE 8080 8081

# Create a script to run both applications
WORKDIR /app
COPY . .

RUN echo '#!/bin/sh\n\
node /app/HttpProxy/index.js &\n\
python3 /app/WebSocket/main.py' > start.sh
RUN chmod +x start.sh

# Start both applications
CMD ["./start.sh"]
