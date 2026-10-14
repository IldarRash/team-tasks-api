package com.ildarrash.teamtasks.service

import com.ildarrash.teamtasks.domain.InvalidRequestException
import com.ildarrash.teamtasks.domain.NewTask
import com.ildarrash.teamtasks.domain.Task
import com.ildarrash.teamtasks.domain.TaskNotFoundException
import com.ildarrash.teamtasks.domain.TaskPatch
import com.ildarrash.teamtasks.domain.TransientDatabaseException
import com.ildarrash.teamtasks.repository.TaskRepository
import org.springframework.stereotype.Service
import org.springframework.transaction.PlatformTransactionManager
import org.springframework.transaction.TransactionDefinition
import org.springframework.transaction.support.DefaultTransactionDefinition
import org.springframework.transaction.support.TransactionTemplate
import java.sql.SQLException
import java.util.UUID

@Service
class TaskService(
    private val repository: TaskRepository,
    transactionManager: PlatformTransactionManager,
) {
    private val transactions = TransactionTemplate(transactionManager, DefaultTransactionDefinition(TransactionDefinition.PROPAGATION_REQUIRED))

    fun create(request: NewTask): Task {
        validateNewTask(request)
        return write {
            repository.ensureAndLockTeam(request.teamId)
            val task = Task(UUID.randomUUID(), request.teamId, request.name, request.description, repository.nextPriority(request.teamId))
            repository.insert(task)
            task
        }
    }

    fun get(id: UUID): Task = repository.findById(id) ?: throw TaskNotFoundException(id)

    fun list(teamId: Long?): List<Task> {
        if (teamId != null && teamId <= 0) invalid("teamId", "must be a positive integer")
        return repository.findAll(teamId)
    }

    fun patch(id: UUID, patch: TaskPatch): Task {
        validatePatch(patch)
        return writeForTask(id) { current ->
            val updated = current.copy(name = patch.name ?: current.name, description = patch.description ?: current.description)
            repository.updateContent(updated.id, updated.name, updated.description)
            updated
        }
    }

    fun delete(id: UUID) {
        writeForTask(id) { current ->
            repository.delete(id)
            repository.compactAfterDelete(current.teamId, current.priority)
            Unit
        }
    }

    private fun <T> writeForTask(id: UUID, action: (Task) -> T): T = write {
        // The team is read first only to locate its durable cross-instance lock. It is read again after locking.
        val initial = repository.findById(id) ?: throw TaskNotFoundException(id)
        repository.ensureAndLockTeam(initial.teamId)
        val current = repository.findById(id) ?: throw TaskNotFoundException(id)
        action(current)
    }

    private fun <T> write(action: () -> T): T {
        repeat(MAX_ATTEMPTS - 1) {
            try {
                return transactions.execute { action() }!!
            } catch (exception: RuntimeException) {
                if (!isRetryableRollback(exception)) throw exception
            }
        }
        try {
            return transactions.execute { action() }!!
        } catch (exception: RuntimeException) {
            if (isRetryableRollback(exception)) throw TransientDatabaseException()
            throw exception
        }
    }

    private fun validateNewTask(request: NewTask) {
        if (request.teamId <= 0) invalid("teamId", "must be a positive integer")
        validateText("name", request.name, 200)
        validateText("description", request.description, 10_000)
    }

    private fun validatePatch(patch: TaskPatch) {
        if (patch.name == null && patch.description == null) invalid("body", "at least one of name or description is required")
        patch.name?.let { validateText("name", it, 200) }
        patch.description?.let { validateText("description", it, 10_000) }
    }

    private fun validateText(field: String, value: String, maxLength: Int) {
        if (value.isBlank()) invalid(field, "must not be blank")
        if (value.length > maxLength) invalid(field, "must be at most $maxLength characters")
    }

    private fun invalid(field: String, message: String): Nothing = throw InvalidRequestException("Request validation failed", mapOf(field to message))

    private fun isRetryableRollback(exception: Throwable): Boolean {
        var current: Throwable? = exception
        while (current != null) {
            if (current is SQLException && current.sqlState in RETRYABLE_SQL_STATES) return true
            current = current.cause
        }
        return false
    }

    private companion object {
        const val MAX_ATTEMPTS = 3
        val RETRYABLE_SQL_STATES = setOf("40P01", "40001")
    }
}
