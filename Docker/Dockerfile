# Use the official Node.js image from the Docker Hub, based on the Alpine Linux distribution.
FROM node:alpine

# Set the working directory for PM2 config and both apps.
WORKDIR /app

# Copy the PM2 config file and the package.json files for both apps.
COPY package*.json ./
COPY pm2.config.js ./
COPY gateway/package*.json ./gateway/
COPY proxy/package*.json ./proxy/

# Install global PM2
RUN npm install pm2 -g

# Install dependencies for both apps
RUN cd gateway && npm ci && cd ..
RUN cd proxy && npm ci && cd ..

# Copy the rest of the project files
COPY . .

# Build the gateway application (TypeScript compilation)
RUN cd gateway && npm run build && cd ..

# Expose ports for both gateway and proxy services
EXPOSE 8080
EXPOSE 8081

# Start the applications using PM2
CMD ["pm2-runtime", "start", "pm2.config.js"]
