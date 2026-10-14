package com.ildarrash.teamtasks.performance;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.gatling.javaapi.core.ChainBuilder;
import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;
import io.gatling.javaapi.http.HttpProtocolBuilder;

import java.time.Duration;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

import static io.gatling.javaapi.core.CoreDsl.constantConcurrentUsers;
import static io.gatling.javaapi.core.CoreDsl.details;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.global;
import static io.gatling.javaapi.core.CoreDsl.group;
import static io.gatling.javaapi.core.CoreDsl.scenario;
import static io.gatling.javaapi.core.CoreDsl.StringBody;
import static io.gatling.javaapi.core.CoreDsl.bodyString;
import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

/**
 * One closed-model virtual user performs one complete task lifecycle per iteration.
 * Fixtures must seed a contiguous [teamBaseId, teamBaseId + teams) range before a run.
 */
public final class TaskLifecycleSimulation extends Simulation {
  private static final String BASE_URL = System.getProperty("baseUrl", "http://127.0.0.1:8081");
  private static final int TEAMS = positiveIntProperty("teams", 1);
  private static final int USERS = positiveIntProperty("users", 20);
  private static final int DURATION_SECONDS = positiveIntProperty("durationSeconds", 60);
  private static final long TEAM_BASE_ID = positiveLongProperty("teamBaseId", 7_000_000_000_000L);
  private static final AtomicLong NEXT_TEAM = new AtomicLong();
  private static final ObjectMapper JSON = new ObjectMapper();

  private final HttpProtocolBuilder httpProtocol = http
      .baseUrl(BASE_URL)
      .acceptHeader("application/json")
      .contentTypeHeader("application/json")
      .disableFollowRedirect();

  private final ChainBuilder lifecycle = group("Task lifecycle").on(
      exec(session -> session.set("teamId", TEAM_BASE_ID + Math.floorMod(NEXT_TEAM.getAndIncrement(), TEAMS)))
          .exec(http("Create task")
              .post("/tasks")
              .body(StringBody("{\"teamId\":#{teamId},\"name\":\"load task\",\"description\":\"benchmark lifecycle\"}"))
              .asJson()
              .check(
                  status().is(201),
                  jsonPath("$.id").saveAs("taskId"),
                  jsonPath("$.teamId").is(session -> Long.toString(session.getLong("teamId"))),
                  jsonPath("$.priority").exists()))
          .exitHereIfFailed()
          .exec(http("Move task to first priority")
              .patch("/tasks/#{taskId}/priority")
              .body(StringBody("{\"priority\":1}"))
              .asJson()
              .check(
                  status().is(200),
                  jsonPath("$.id").is(session -> session.getString("taskId")),
                  jsonPath("$.teamId").is(session -> Long.toString(session.getLong("teamId"))),
                  jsonPath("$.priority").is("1")))
          .exitHereIfFailed()
          .exec(http("List team tasks")
              .get("/tasks")
              .queryParam("teamId", "#{teamId}")
              .check(
                  status().is(200),
                  jsonPath("$[0].teamId").is(session -> Long.toString(session.getLong("teamId"))),
                  bodyString().transform(TaskLifecycleSimulation::snapshotValidity).is("valid")))
          .exitHereIfFailed()
          .exec(http("Delete created task")
              .delete("/tasks/#{taskId}")
              .check(status().is(204)))
          .exitHereIfFailed());

  private final ScenarioBuilder taskLifecycle = scenario("Task lifecycle").exec(lifecycle);

  public TaskLifecycleSimulation() {
    setUp(taskLifecycle.injectClosed(constantConcurrentUsers(USERS).during(Duration.ofSeconds(DURATION_SECONDS)))
        .protocols(httpProtocol))
        .assertions(
            global().failedRequests().count().is(0L),
            details("Task lifecycle").failedRequests().count().is(0L));
  }

  private static String snapshotValidity(String responseBody) {
    try {
      JsonNode tasks = JSON.readTree(responseBody);
      if (!tasks.isArray() || tasks.isEmpty()) {
        return "invalid";
      }

      long teamId = -1;
      Set<Integer> priorities = new HashSet<>();
      for (JsonNode task : tasks) {
        UUID.fromString(requiredText(task, "id"));
        long currentTeamId = requiredPositiveLong(task, "teamId");
        int priority = requiredPositiveInt(task, "priority");
        if (teamId == -1) {
          teamId = currentTeamId;
        } else if (teamId != currentTeamId) {
          return "invalid";
        }
        if (!priorities.add(priority)) {
          return "invalid";
        }
      }

      for (int expected = 1; expected <= priorities.size(); expected++) {
        if (!priorities.contains(expected)) {
          return "invalid";
        }
      }
      return "valid";
    } catch (RuntimeException | java.io.IOException ignored) {
      return "invalid";
    }
  }

  private static String requiredText(JsonNode task, String field) {
    JsonNode value = task.get(field);
    if (value == null || !value.isTextual() || value.textValue().isBlank()) {
      throw new IllegalArgumentException("Missing " + field);
    }
    return value.textValue();
  }

  private static long requiredPositiveLong(JsonNode task, String field) {
    JsonNode value = task.get(field);
    if (value == null || !value.canConvertToLong() || value.longValue() < 1) {
      throw new IllegalArgumentException("Invalid " + field);
    }
    return value.longValue();
  }

  private static int requiredPositiveInt(JsonNode task, String field) {
    JsonNode value = task.get(field);
    if (value == null || !value.canConvertToInt() || value.intValue() < 1) {
      throw new IllegalArgumentException("Invalid " + field);
    }
    return value.intValue();
  }

  private static int positiveIntProperty(String name, int defaultValue) {
    String value = System.getProperty(name, Integer.toString(defaultValue));
    try {
      int parsed = Integer.parseInt(value);
      if (parsed < 1) {
        throw new IllegalArgumentException(name + " must be positive");
      }
      return parsed;
    } catch (NumberFormatException exception) {
      throw new IllegalArgumentException(name + " must be a positive integer", exception);
    }
  }

  private static long positiveLongProperty(String name, long defaultValue) {
    String value = System.getProperty(name, Long.toString(defaultValue));
    try {
      long parsed = Long.parseLong(value);
      if (parsed < 1) {
        throw new IllegalArgumentException(name + " must be positive");
      }
      return parsed;
    } catch (NumberFormatException exception) {
      throw new IllegalArgumentException(name + " must be a positive long", exception);
    }
  }
}
