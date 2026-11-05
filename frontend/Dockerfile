# ==============================================================================
# Production Dockerfile for Resume Analyzer Frontend
# Builds React bundle and serves via lightweight Nginx web server
# ==============================================================================

# Stage 1: Build production bundle
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci --prefer-offline --no-audit

COPY . .
ARG REACT_APP_API_URL=""
ENV REACT_APP_API_URL=${REACT_APP_API_URL} \
    CI=false \
    GENERATE_SOURCEMAP=false

RUN npm run build

# Stage 2: Production Nginx runtime
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]

