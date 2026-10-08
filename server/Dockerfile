FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn -B package
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/target/learning-gateway-0.2.0.jar /app/app.jar
USER 10001:10001
EXPOSE 8081
ENTRYPOINT ["java","-jar","/app/app.jar"]
