# Kio Frontend — Vite build served by nginx
#
# Build from the repo root:
#   docker build -t kio-web \
#     --build-arg VITE_API_BASE_URL=https://api.example.com \
#     --build-arg VITE_GOOGLE_CLIENT_ID=... .
#
# IMPORTANT: Vite inlines VITE_* values at BUILD time. They are baked into the
# JS bundle, so they are build args, not runtime env vars — pointing this image
# at a different API means rebuilding it, not restarting it. Corollary: never
# pass a secret as a VITE_* value; everything here ships to the browser.

# ===================================================================
# Stage 1 — build
# ===================================================================
FROM node:20.18-bookworm-slim AS builder

WORKDIR /app

# Copy manifests first so `npm ci` is cached until dependencies actually change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

# Fail loudly at build time rather than shipping a bundle that silently falls
# back to http://localhost:8000 and breaks for every real user.
RUN if [ -z "$VITE_API_BASE_URL" ]; then \
        echo "ERROR: --build-arg VITE_API_BASE_URL is required." >&2; \
        exit 1; \
    fi

RUN npx tsc --noEmit && npm run build


# ===================================================================
# Stage 2 — serve
# ===================================================================
FROM nginx:1.27-alpine AS runtime

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
