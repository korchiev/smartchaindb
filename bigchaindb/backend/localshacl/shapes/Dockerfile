FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --production

# Copy application files (not mounted volumes)
COPY index.js ./

EXPOSE 3000

CMD [ "npm", "start" ]
