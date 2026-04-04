from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {

    # Python
    "fastapi": {
        "name": "FastAPI",
        "description": "Python FastAPI with uvicorn",
        "dockerfile": """\
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
    },

    "flask": {
        "name": "Flask",
        "description": "Python Flask with gunicorn",
        "dockerfile": """\
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
""",
    },

    "django": {
        "name": "Django",
        "description": "Python Django with gunicorn",
        "dockerfile": """\
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
""",
    },

    # JavaScript / Node.js
    "node": {
        "name": "Node.js",
        "description": "Node.js (Express / generic)",
        "dockerfile": """\
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

EXPOSE 3000

CMD ["node", "index.js"]
""",
    },

    "nextjs": {
        "name": "Next.js",
        "description": "Next.js with standalone output",
        "dockerfile": """\
FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
""",
    },

    "react": {
        "name": "React",
        "description": "React (Vite/CRA) with nginx",
        "dockerfile": """\
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
""",
    },

    "vue": {
        "name": "Vue.js",
        "description": "Vue.js with nginx",
        "dockerfile": """\
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
""",
    },

    "angular": {
        "name": "Angular",
        "description": "Angular with nginx",
        "dockerfile": """\
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build --configuration=production

FROM nginx:alpine
COPY --from=build /app/dist/*/browser /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
""",
    },

    # TypeScript runtimes
    "bun": {
        "name": "Bun",
        "description": "Bun runtime",
        "dockerfile": """\
FROM oven/bun:1-alpine

WORKDIR /app

COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile --production

COPY . .

EXPOSE 3000

CMD ["bun", "run", "index.ts"]
""",
    },

    "deno": {
        "name": "Deno",
        "description": "Deno runtime",
        "dockerfile": """\
FROM denoland/deno:latest

WORKDIR /app

COPY . .

RUN deno cache main.ts

EXPOSE 8000

CMD ["deno", "run", "--allow-net", "--allow-read", "--allow-env", "main.ts"]
""",
    },

    # Go
    "go": {
        "name": "Go",
        "description": "Go with multi-stage build",
        "dockerfile": """\
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server .

FROM alpine:3.20
RUN apk --no-cache add ca-certificates
COPY --from=builder /server /server

EXPOSE 8080

CMD ["/server"]
""",
    },

    # Rust
    "rust": {
        "name": "Rust",
        "description": "Rust with multi-stage build",
        "dockerfile": """\
FROM rust:1.80-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -rf src
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/app /usr/local/bin/app

EXPOSE 8080

CMD ["app"]
""",
    },

    # Java
    "spring": {
        "name": "Spring Boot",
        "description": "Spring Boot (Maven)",
        "dockerfile": """\
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY pom.xml mvnw ./
COPY .mvn .mvn
RUN ./mvnw dependency:resolve
COPY src src
RUN ./mvnw package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]
""",
    },

    "gradle": {
        "name": "Java (Gradle)",
        "description": "Java app with Gradle",
        "dockerfile": """\
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY build.gradle settings.gradle gradlew ./
COPY gradle gradle
RUN ./gradlew dependencies
COPY src src
RUN ./gradlew bootJar

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]
""",
    },

    # Ruby
    "rails": {
        "name": "Ruby on Rails",
        "description": "Rails with Puma",
        "dockerfile": """\
FROM ruby:3.3-slim

RUN apt-get update -qq && \\
    apt-get install -y --no-install-recommends build-essential libpq-dev nodejs && \\
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Gemfile Gemfile.lock ./
RUN bundle install --without development test

COPY . .

RUN bundle exec rake assets:precompile

EXPOSE 3000

CMD ["bundle", "exec", "puma", "-C", "config/puma.rb"]
""",
    },

    # PHP
    "laravel": {
        "name": "Laravel",
        "description": "PHP Laravel with Apache",
        "dockerfile": """\
FROM php:8.3-apache

RUN a2enmod rewrite && \\
    apt-get update && apt-get install -y --no-install-recommends \\
    libpng-dev libzip-dev unzip && \\
    docker-php-ext-install pdo_mysql gd zip && \\
    rm -rf /var/lib/apt/lists/*

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

COPY . .
RUN composer install --no-dev --optimize-autoloader

RUN chown -R www-data:www-data storage bootstrap/cache

ENV APACHE_DOCUMENT_ROOT=/var/www/html/public
RUN sed -ri 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/000-default.conf

EXPOSE 80

CMD ["apache2-foreground"]
""",
    },

    # .NET
    "dotnet": {
        "name": ".NET",
        "description": "ASP.NET Core",
        "dockerfile": """\
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY *.csproj ./
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app/publish .

EXPOSE 8080

CMD ["dotnet", "App.dll"]
""",
    },

    # Elixir
    "phoenix": {
        "name": "Elixir Phoenix",
        "description": "Phoenix Framework",
        "dockerfile": """\
FROM elixir:1.16-alpine AS builder
RUN apk add --no-cache build-base git
WORKDIR /app

ENV MIX_ENV=prod
RUN mix local.hex --force && mix local.rebar --force

COPY mix.exs mix.lock ./
RUN mix deps.get --only prod && mix deps.compile

COPY . .
RUN mix assets.deploy && mix release

FROM alpine:3.20
RUN apk add --no-cache libstdc++ openssl ncurses-libs
WORKDIR /app
COPY --from=builder /app/_build/prod/rel/app ./

EXPOSE 4000

CMD ["bin/app", "start"]
""",
    },

    # Static / Nginx
    "static": {
        "name": "Static Site",
        "description": "Static HTML/CSS/JS with nginx",
        "dockerfile": """\
FROM nginx:alpine

COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
""",
    },

    # Python ML
    "python-ml": {
        "name": "Python ML",
        "description": "Python ML/Data Science with Jupyter",
        "dockerfile": """\
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8888

CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
""",
    },

    # SvelteKit
    "sveltekit": {
        "name": "SvelteKit",
        "description": "SvelteKit with Node adapter",
        "dockerfile": """\
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json ./
RUN npm ci --omit=dev

EXPOSE 3000

CMD ["node", "build"]
""",
    },

    # Nuxt.js
    "nuxtjs": {
        "name": "Nuxt.js",
        "description": "Nuxt.js with SSR output",
        "dockerfile": """\
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/.output ./

EXPOSE 3000

CMD ["node", "server/index.mjs"]
""",
    },

    # Astro
    "astro": {
        "name": "Astro",
        "description": "Astro static site with nginx",
        "dockerfile": """\
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
""",
    },

    # Streamlit
    "streamlit": {
        "name": "Streamlit",
        "description": "Python Streamlit data app",
        "dockerfile": """\
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
""",
    },

    # NestJS
    "nestjs": {
        "name": "NestJS",
        "description": "NestJS backend with multi-stage build",
        "dockerfile": """\
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./
RUN npm ci --omit=dev

EXPOSE 3000

CMD ["node", "dist/main"]
""",
    },

}

def get_template_names() -> list[str]:
    """Return sorted list of template keys."""
    return sorted(TEMPLATES.keys())


def get_template(name: str) -> dict[str, str] | None:
    """Return template dict by key, or None."""
    return TEMPLATES.get(name.lower())
