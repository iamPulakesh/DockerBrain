FROM ruby:3.3-slim

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends build-essential libpq-dev nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Gemfile Gemfile.lock ./
RUN bundle install --without development test

COPY . .

RUN bundle exec rake assets:precompile

EXPOSE 3000

CMD ["bundle", "exec", "puma", "-C", "config/puma.rb"]
