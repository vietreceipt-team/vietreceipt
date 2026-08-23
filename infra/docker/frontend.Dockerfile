# Runs the dependency-free vanilla frontend server for local Compose use.
FROM node:22.13.0-bookworm-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci

COPY frontend /app

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
