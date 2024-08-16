FROM node:alpine

WORKDIR /app

# Copy only the necessary files
COPY package*.json ./
COPY tsconfig.json ./
COPY .dockerignore ./
COPY .gitignore ./
COPY proxy/package*.json ./proxy/
COPY src/package*.json ./src/

# Install dependencies
RUN npm ci

# Copy the remaining files
COPY . .

# Install PM2 globally
RUN npm install pm2 -g

# Build the project
RUN npm run build

# Expose the necessary ports
EXPOSE 8080
EXPOSE 8081

# Use PM2 to run both the proxy and gateway apps
CMD ["pm2-runtime", "pm2.config.js"]
