FROM gcc:14 AS builder

WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y cmake && rm -rf /var/lib/apt/lists/*

COPY . .
RUN mkdir build && cd build && cmake .. && make

FROM debian:bookworm-slim
WORKDIR /app
# Copy the compiled binary (replace 'app_binary' with your target name)
COPY --from=builder /usr/src/app/build/app_binary .

CMD ["./app_binary"]
