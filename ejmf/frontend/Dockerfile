FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG EJMF_API_INTERNA=http://api:8000
ENV EJMF_API_INTERNA=$EJMF_API_INTERNA
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npx next build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN adduser -D -u 10001 ejmf
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER ejmf
EXPOSE 3000
CMD ["node", "server.js"]
