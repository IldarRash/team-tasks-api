package com.ildarrash.teamtasks.service

import com.ildarrash.teamtasks.domain.NewTask
import com.ildarrash.teamtasks.domain.Task
import com.ildarrash.teamtasks.domain.TaskNotFoundException
import com.ildarrash.teamtasks.domain.TransientDatabaseException
import com.ildarrash.teamtasks.repository.TaskRepository
import org.junit.jupiter.api.Test
import org.springframework.dao.DataAccessResourceFailureException
import org.springframework.transaction.PlatformTransactionManager
import org.springframework.transaction.TransactionDefinition
import org.springframework.transaction.TransactionStatus
import org.springframework.transaction.support.SimpleTransactionStatus
import java.sql.SQLException
import java.util.UUID
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class TaskServiceTest {
    @Test
    fun `moving a task upward shifts only its preceding range`() {
        val repository = InMemoryRepository(teamTasks("a", "b", "c", "d"))
        val service = TaskService(repository, RecordingTransactionManager())

        val result = service.changePriority(repository.tasks[3].id, 2)

        assertEquals(2, result.priority)
        assertEquals(listOf("a", "d", "b", "c"), repository.orderedNames())
        assertDense(repository.tasks)
    }

    @Test
    fun `moving a task downward and a no-op preserve dense priorities`() {
        val repository = InMemoryRepository(teamTasks("a", "b", "c", "d"))
        val service = TaskService(repository, RecordingTransactionManager())

        service.changePriority(repository.tasks[0].id, 4)
        val noOp = service.changePriority(repository.tasks[2].id, repository.tasks[2].priority)

        assertEquals(listOf("b", "c", "d", "a"), repository.orderedNames())
        assertEquals(2, noOp.priority)
        assertDense(repository.tasks)
    }

    @Test
    fun `deleting a middle task compacts remaining priorities under the team lock`() {
        val repository = InMemoryRepository(teamTasks("a", "b", "c"))
        val service = TaskService(repository, RecordingTransactionManager())

        service.delete(repository.tasks[1].id)

        assertEquals(listOf("a", "c"), repository.orderedNames())
        assertDense(repository.tasks)
        assertEquals(1, repository.lockCalls)
    }

    @Test
    fun `deadlock and serialization rollback retry at most three attempts then map to transient error`() {
        listOf("40P01", "40001").forEach { sqlState ->
            val repository = FailingLockRepository(sqlState)
            val transactions = RecordingTransactionManager()
            val service = TaskService(repository, transactions)

            assertFailsWith<TransientDatabaseException> { service.create(NewTask(1, "task", "description")) }
            assertEquals(3, repository.lockCalls, "SQLSTATE $sqlState")
            assertEquals(3, transactions.rollbacks, "SQLSTATE $sqlState")
            assertEquals(0, transactions.commits, "SQLSTATE $sqlState")
        }
    }

    @Test
    fun unknownCommitOutcomeIsNotRetried() {
        val repository = InMemoryRepository(mutableListOf())
        val transactions = CommitFailureTransactionManager()
        val service = TaskService(repository, transactions)

        assertFailsWith<DataAccessResourceFailureException> { service.create(NewTask(1, "task", "description")) }
        assertEquals(1, repository.lockCalls)
        assertEquals(1, transactions.commits)
    }

    private fun teamTasks(vararg names: String): MutableList<Task> = names.mapIndexed { index, name ->
        Task(UUID.randomUUID(), 1, name, "$name description", index + 1)
    }.toMutableList()

    private fun assertDense(tasks: List<Task>) = assertEquals((1..tasks.size).toList(), tasks.sortedBy { it.priority }.map { it.priority })

    private open class RecordingTransactionManager : PlatformTransactionManager {
        var commits = 0
        var rollbacks = 0
        override fun getTransaction(definition: TransactionDefinition?): TransactionStatus = SimpleTransactionStatus()
        open override fun commit(status: TransactionStatus) { commits++ }
        override fun rollback(status: TransactionStatus) { rollbacks++ }
    }

    private class CommitFailureTransactionManager : RecordingTransactionManager() {
        override fun commit(status: TransactionStatus) {
            super.commit(status)
            throw DataAccessResourceFailureException("commit outcome is unknown", SQLException("connection lost during commit", "08006"))
        }
    }

    private open class InMemoryRepository(val tasks: MutableList<Task>) : TaskRepository {
        var lockCalls = 0
        override fun ensureAndLockTeam(teamId: Long) { lockCalls++ }
        override fun findById(id: UUID): Task? = tasks.firstOrNull { it.id == id }
        override fun findAll(teamId: Long?): List<Task> = tasks.filter { teamId == null || it.teamId == teamId }.sortedWith(compareBy<Task> { it.teamId }.thenBy { it.priority })
        override fun nextPriority(teamId: Long): Int = tasks.filter { it.teamId == teamId }.size + 1
        override fun insert(task: Task) { tasks += task }
        override fun updateContent(id: UUID, name: String, description: String) { replace(id) { it.copy(name = name, description = description) } }
        override fun delete(id: UUID) { tasks.removeAll { it.id == id } }
        override fun compactAfterDelete(teamId: Long, deletedPriority: Int) = rewrite { if (it.teamId == teamId && it.priority > deletedPriority) it.copy(priority = it.priority - 1) else it }
        override fun shiftPrioritiesUp(teamId: Long, fromInclusive: Int, toExclusive: Int) = rewrite { if (it.teamId == teamId && it.priority in fromInclusive until toExclusive) it.copy(priority = it.priority + 1) else it }
        override fun shiftPrioritiesDown(teamId: Long, fromExclusive: Int, toInclusive: Int) = rewrite { if (it.teamId == teamId && it.priority in (fromExclusive + 1)..toInclusive) it.copy(priority = it.priority - 1) else it }
        override fun setPriority(id: UUID, priority: Int) { replace(id) { it.copy(priority = priority) } }
        fun orderedNames() = tasks.sortedBy { it.priority }.map { it.name }
        private fun replace(id: UUID, mapper: (Task) -> Task) {
            val index = tasks.indexOfFirst { it.id == id }
            if (index < 0) throw TaskNotFoundException(id)
            tasks[index] = mapper(tasks[index])
        }
        private fun rewrite(mapper: (Task) -> Task) {
            tasks.indices.forEach { index -> tasks[index] = mapper(tasks[index]) }
        }
    }

    private class FailingLockRepository(private val sqlState: String) : InMemoryRepository(mutableListOf()) {
        override fun ensureAndLockTeam(teamId: Long) {
            lockCalls++
            throw DataAccessResourceFailureException("database write failed", SQLException("failure", sqlState))
        }
    }
}
