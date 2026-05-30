# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# The backend URL must be known at build time because Next.js bakes
# NEXT_PUBLIC_* variables into the client bundle during `next build`.
# Pass it in with: docker build --build-arg NEXT_PUBLIC_API_URL=https://...
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package*.json ./
RUN npm ci --prefer-offline

COPY . .
RUN npm run build
# Produces a static site in /app/out (next.config.ts sets output:"export")

# ── Stage 2: production static file server ─────────────────────────────────────
FROM node:18-alpine AS runner

WORKDIR /app

# `serve` is a lightweight static file server (no nginx config needed)
RUN npm install -g serve

COPY --from=builder /app/out .

EXPOSE 3000
CMD ["serve", "-s", ".", "-l", "3000"]
