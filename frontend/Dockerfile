FROM node:22-alpine AS base

WORKDIR /app
COPY package.json ./
RUN npm install

FROM base AS dev
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM base AS build
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM alpine:3.20 AS export
COPY --from=build /app/dist /usr/share/originlabs-frontend
