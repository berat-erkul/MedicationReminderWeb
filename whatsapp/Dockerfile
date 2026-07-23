FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY src ./src

ENV PORT=3001
ENV AUTH_DIR=/data/auth_info

VOLUME ["/data"]
EXPOSE 3001

CMD ["npm", "start"]
