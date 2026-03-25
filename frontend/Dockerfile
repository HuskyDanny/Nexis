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
FROM nginx:alpine

# Security: non-root (nginx user already exists in nginx:alpine, uid 101)
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# nginx:alpine runs as root by default but worker processes run as nginx user
# For K8s, we'll handle non-root via securityContext

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
