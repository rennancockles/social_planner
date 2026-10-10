FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines import.meta.env.* at build time, so this has to be a build arg, not a
# runtime environment variable — baking in "http://localhost:8000" is correct for this
# app's single-machine, personal-use deployment (browser and backend share the host).
ARG PLANNER_API_URL=http://localhost:8000
ENV PLANNER_API_URL=$PLANNER_API_URL

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
