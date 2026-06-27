FROM node:20-slim

WORKDIR /app

# Install deps before copying source so this layer is cached
COPY package*.json .
RUN npm install

# Source is mounted at run time in development (see docker-compose volumes).
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
