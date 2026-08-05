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
