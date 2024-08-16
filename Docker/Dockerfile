FROM node:alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy the rest of the files
COPY . .

# Build the project
RUN npm run build

# Install PM2 globally
RUN npm install pm2 -g

# Expose ports
EXPOSE 8080
EXPOSE 8081

# Start both apps with PM2
CMD ["pm2-runtime", "pm2.config.js"]
