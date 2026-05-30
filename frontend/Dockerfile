FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source files
COPY . .

# Expose Next.js port
EXPOSE 3001

# Run the dev server on port 3001
CMD ["npm", "run", "dev", "--", "-p", "3001"]
