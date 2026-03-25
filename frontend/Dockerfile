# ── Build stage ───────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Install deps first (layer caching)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
ENV VITE_API_URL=""
RUN npm run build

# ── Serve stage ───────────────────────────────────────────────
FROM nginxinc/nginx-unprivileged:alpine

# Copy built assets and config (runs as nginx user, uid 101)
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
