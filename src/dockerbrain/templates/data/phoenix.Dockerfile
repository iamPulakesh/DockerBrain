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
