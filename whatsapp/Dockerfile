# libsignal (Baileys bağımlılığı) GitHub'dan çekilir ve native kod derler,
# bu yüzden kurulum için git + C/C++ toolchain gerekir. Bunları ayrı bir
# build stage'inde tutup runtime imajını ince bırakıyoruz.
FROM node:22-alpine AS build
WORKDIR /app
RUN apk add --no-cache git python3 make g++
COPY package.json ./
RUN npm install --omit=dev

FROM node:22-alpine AS runtime
WORKDIR /app
COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src

ENV PORT=3001
ENV AUTH_DIR=/data/auth_info

VOLUME ["/data"]
EXPOSE 3001

CMD ["npm", "start"]
