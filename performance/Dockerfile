FROM eclipse-temurin:17-jdk
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
COPY build/libs/team-tasks-api.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
