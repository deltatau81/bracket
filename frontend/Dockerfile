# Install dependencies only when needed
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json yarn.lock ./

RUN yarn --network-timeout 1000000

COPY . .

RUN NEXT_PUBLIC_API_BASE_URL=http://NEXT_PUBLIC_API_BASE_URL_PLACEHOLDER \
    NEXT_PUBLIC_HCAPTCHA_SITE_KEY=NEXT_PUBLIC_HCAPTCHA_SITE_KEY_PLACEHOLDER \
    yarn build


# Production image
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

RUN addgroup -g 1001 --system nodejs && \
    adduser --system nextjs -u 1001 -G nodejs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

COPY --from=builder --chmod=0755 /app/docker-entrypoint.sh ./entrypoint.sh

RUN apk add --no-cache bash

USER nextjs

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD wget --spider -q http://127.0.0.1:3000 || exit 1

CMD ["node", "server.js"]