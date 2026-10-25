FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /build
COPY services/keyple/pom.xml .
RUN mvn -q dependency:go-offline
COPY services/keyple/src src
RUN mvn -q package
FROM eclipse-temurin:21.0.8_9-jre
WORKDIR /app
COPY --from=build /build/target/classes /app/classes
COPY --from=build /build/target/dependency /app/lib
CMD ["java", "-cp", "classes:lib/*", "org.alize.demo.CardServer"]
