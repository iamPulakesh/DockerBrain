FROM swift:5.10-jammy AS build

WORKDIR /build

COPY ./Package.* ./
RUN swift package resolve

COPY . .
RUN swift build -c release --static-swift-stdlib

FROM ubuntu:jammy
WORKDIR /app
# Copy the compiled executable (replace 'App' with your executable name)
COPY --from=build /build/.build/release/App /app/
EXPOSE 8080

CMD ["./App"]
