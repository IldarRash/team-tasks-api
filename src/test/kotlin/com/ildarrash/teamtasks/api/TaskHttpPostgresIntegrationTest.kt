package com.ildarrash.teamtasks.api

import com.fasterxml.jackson.databind.ObjectMapper
import com.ildarrash.teamtasks.domain.NewTask
import com.ildarrash.teamtasks.domain.TaskNotFoundException
import com.ildarrash.teamtasks.repository.TaskRepository
import com.ildarrash.teamtasks.service.TaskService
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.http.MediaType
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import org.springframework.transaction.PlatformTransactionManager
import java.util.Collections
import java.util.concurrent.Callable
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.ThreadLocalRandom
import java.util.concurrent.TimeUnit
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * These checks use a real PostgreSQL transaction and are enabled explicitly with
 * RUN_POSTGRES_INTEGRATION=true. TEST_DATABASE_URL/USER/PASSWORD select an isolated database.
 */
@SpringBootTest
@AutoConfigureMockMvc
@EnabledIfEnvironmentVariable(named = "RUN_POSTGRES_INTEGRATION", matches = "true")
class TaskHttpPostgresIntegrationTest {
    @Autowired private lateinit var mockMvc: MockMvc
    @Autowired private lateinit var objectMapper: ObjectMapper
    @Autowired private lateinit var firstService: TaskService
    @Autowired private lateinit var repository: TaskRepository
    @Autowired private lateinit var transactionManager: PlatformTransactionManager
    @Autowired private lateinit var jdbc: NamedParameterJdbcTemplate

    private val createdTeams = Collections.synchronizedSet(mutableSetOf<Long>())

    @AfterEach
    fun cleanup() {
        val teams = synchronized(createdTeams) { createdTeams.toList() }
        if (teams.isNotEmpty()) {
            jdbc.update("delete from tasks where team_id in (:teams)", mapOf("teams" to teams))
            jdbc.update("delete from team_locks where team_id in (:teams)", mapOf("teams" to teams))
        }
    }

    @Test
    fun httpCrudAndPriorityAssignmentUseTheDocumentedContract() {
        val teamId = newTeamId()
        val first = createHttp(teamId, "first")
        val second = createHttp(teamId, "second")

        assertEquals(listOf(1, 2), listHttp(teamId).map { it.priority })
        assertEquals(first.teamId, second.teamId)
        val error = mockMvc.perform(
            post("/tasks").contentType(MediaType.APPLICATION_JSON)
                .content("""{"teamId":$teamId,"name":"a","description":"b","priority":1}"""),
        ).andExpect(status().isBadRequest).andReturn().response.contentAsString.let { objectMapper.readValue(it, ApiError::class.java) }
        assertEquals("VALIDATION_ERROR", error.code)
        assertEquals("is not allowed", error.fieldErrors["priority"])
    }

    @Test
    fun twoServiceInstancesSerializeParallelPostsAndReadersSeeDenseSnapshots() {
        val teamId = newTeamId()
        val secondService = TaskService(repository, transactionManager)
        val seed = (1..8).map { firstService.create(NewTask(teamId, "seed-$it", "seed task $it")) }
        val pool = Executors.newFixedThreadPool(20)
        try {
            val createTasks = (1..16).map { index ->
                Callable {
                    firstService.takeIf { index % 2 == 0 }?.create(NewTask(teamId, "parallel-$index", "parallel task $index"))
                        ?: secondService.create(NewTask(teamId, "parallel-$index", "parallel task $index"))
                }
            }
            submitAtBarrier(pool, createTasks).forEach { it.get(20, TimeUnit.SECONDS) }
            assertDense(teamId)

            val start = CountDownLatch(1)
            val writersDone = CountDownLatch(10)
            val reader = pool.submit(Callable {
                start.await(10, TimeUnit.SECONDS)
                while (writersDone.count > 0) {
                    val snapshot = secondService.list(teamId)
                    assertEquals((1..snapshot.size).toList(), snapshot.map { it.priority })
                }
            })
            val writers: List<Future<*>> = (0 until 10).map { index ->
                pool.submit(Callable {
                    start.await(10, TimeUnit.SECONDS)
                    try {
                        when (index % 3) {
                            0 -> firstService.create(NewTask(teamId, "mixed-create-$index", "mixed create $index"))
                            1 -> secondService.changePriority(seed[index % seed.size].id, 1)
                            else -> firstService.delete(seed[index % seed.size].id)
                        }
                    } catch (_: TaskNotFoundException) {
                        // A competing delete may legitimately remove the selected seed first.
                    } finally {
                        writersDone.countDown()
                    }
                })
            }
            start.countDown()
            writers.forEach { it.get(20, TimeUnit.SECONDS) }
            reader.get(20, TimeUnit.SECONDS)
            assertDense(teamId)
        } finally {
            pool.shutdownNow()
            assertTrue(pool.awaitTermination(10, TimeUnit.SECONDS))
        }
    }

    private fun createHttp(teamId: Long, name: String): TaskResponse {
        val body = mockMvc.perform(
            post("/tasks").contentType(MediaType.APPLICATION_JSON)
                .content("""{"teamId":$teamId,"name":"$name","description":"$name description"}"""),
        ).andExpect(status().isCreated).andReturn().response.contentAsString
        return objectMapper.readValue(body, TaskResponse::class.java)
    }

    private fun listHttp(teamId: Long): List<TaskResponse> {
        val body = mockMvc.perform(get("/tasks").queryParam("teamId", teamId.toString()))
            .andExpect(status().isOk).andReturn().response.contentAsString
        return objectMapper.readValue(body, objectMapper.typeFactory.constructCollectionType(List::class.java, TaskResponse::class.java))
    }

    private fun assertDense(teamId: Long) {
        val tasks = firstService.list(teamId)
        assertEquals((1..tasks.size).toList(), tasks.map { it.priority })
        assertEquals(tasks.size, tasks.map { it.id }.toSet().size)
    }

    private fun newTeamId(): Long =
        ThreadLocalRandom.current().nextLong(1_000_000_000L, Long.MAX_VALUE).also { createdTeams += it }

    private fun <T> submitAtBarrier(pool: java.util.concurrent.ExecutorService, tasks: List<Callable<T>>): List<Future<T>> {
        val ready = CountDownLatch(tasks.size)
        val start = CountDownLatch(1)
        val futures = tasks.map { task -> pool.submit(Callable { ready.countDown(); start.await(10, TimeUnit.SECONDS); task.call() }) }
        if (!ready.await(10, TimeUnit.SECONDS)) {
            pool.shutdownNow()
            throw AssertionError("all writers must be ready before the concurrent start")
        }
        start.countDown()
        return futures
    }

    private companion object {
        @JvmStatic
        @DynamicPropertySource
        fun databaseProperties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url") { System.getenv("TEST_DATABASE_URL") ?: "jdbc:postgresql://localhost:55432/taskdb" }
            registry.add("spring.datasource.username") { System.getenv("TEST_DATABASE_USER") ?: "tasks" }
            registry.add("spring.datasource.password") { System.getenv("TEST_DATABASE_PASSWORD") ?: "tasks" }
        }
    }
}
