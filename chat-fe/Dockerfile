# ============================================
# Build stage
# ============================================
FROM node:22-alpine AS builder

WORKDIR /build

# Install deps first for better layer caching
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the JS bundle at build time (Vite requirement for static SPAs).
# Override at build time: --build-arg VITE_API_URL=https://api.yourdomain.com
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


# ============================================
# Runtime stage - serve static build with Nginx
# ============================================
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=5s \
    --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
