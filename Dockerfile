FROM node:alpine AS build

# RUN npm install -g npm@11.8.0 tsc@latest
RUN npm install -g tsc@latest

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY src ./src
COPY tsconfig.json ./

RUN npm run build

FROM node:alpine AS runtime

ARG UID=1000
ARG GID=1002

# RUN npm install -g npm@11.8.0 tsc@latest
RUN npm install -g tsc@latest

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=build /app/dist ./dist

RUN mkdir -p /app/data

RUN addgroup -g $GID app && adduser node app && chown -R node:app /app
USER node

EXPOSE 8002

CMD ["node", "dist/filler.js"]
