# STITCHIQ frontend — Vite build served by nginx (CTO B1).
#
# The primary target is Vercel / Cloudflare Pages, which build from source and
# need no container. This image exists for the two cases those don't cover:
# `docker compose up` giving a reviewer the whole product on one machine, and
# self-hosting behind the customer's own ingress.

FROM node:22-alpine AS build
WORKDIR /repo

# The frontend is an npm WORKSPACE, so the root manifests come first and
# `npm ci` runs at the root — installing from within apps/frontend would
# resolve a different (unlocked) tree.
COPY package.json package-lock.json ./
COPY apps/frontend/package.json apps/frontend/
RUN npm ci

COPY apps/frontend apps/frontend
# VITE_* is compiled INTO the bundle, so the API origin is a build argument,
# not a runtime env var. Empty default = same-origin (what the compose file and
# any reverse-proxy deployment want).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build --workspace apps/frontend


FROM nginx:1.27-alpine AS runtime
COPY --from=build /repo/apps/frontend/dist /usr/share/nginx/html
COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
