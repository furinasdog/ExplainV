# ExplainV WebUI (Backend + Frontend)
FROM node:22-slim

WORKDIR /app

# Copy backend
COPY backend/package.json backend/package-lock.json ./backend/
RUN cd backend && npm ci --omit=dev

# Copy frontend dist (pre-built)
COPY frontend/dist ./frontend/dist

# Copy backend source
COPY backend/ ./backend/

EXPOSE 3000

CMD ["node", "backend/server.js"]