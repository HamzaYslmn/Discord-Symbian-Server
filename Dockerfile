# Use an official Python runtime as a parent image
FROM python:3.11-slim as python-base

# Set the working directory for Python
WORKDIR /app/python

# Copy the Python application files
COPY WebSocket/ ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Use an official Node.js runtime as a parent image
FROM node:20 as node-base

# Set the working directory for Node.js
WORKDIR /app/node

# Copy the Node.js application files
COPY HttpProxy/ ./

# Install Node.js dependencies
RUN npm install

# Combine both images into a single image
FROM node:20-slim

# Install a process manager (e.g., PM2) to run both processes
RUN npm install -g pm2

# Copy the Node.js app from the node-base stage
COPY --from=node-base /app/node /app/node

# Copy the Python app from the python-base stage
COPY --from=python-base /app/python /app/python

# Expose the ports for both applications
EXPOSE 8080 8000

# Set the working directory
WORKDIR /app

# Start both the Node.js and Python applications using PM2
CMD ["pm2-runtime", "start", "node/app/index.js", "--name", "HttpProxy", "--", "&&", "python3", "python/main.py"]
