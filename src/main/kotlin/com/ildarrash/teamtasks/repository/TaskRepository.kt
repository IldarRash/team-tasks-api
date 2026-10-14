package com.ildarrash.teamtasks.repository

import com.ildarrash.teamtasks.domain.Task
import java.util.UUID

interface TaskRepository {
    fun ensureAndLockTeam(teamId: Long)
    fun findById(id: UUID): Task?
    fun findAll(teamId: Long?): List<Task>
    fun nextPriority(teamId: Long): Int
    fun insert(task: Task)
    fun updateContent(id: UUID, name: String, description: String)
    fun delete(id: UUID)
    fun compactAfterDelete(teamId: Long, deletedPriority: Int)
    fun shiftPrioritiesUp(teamId: Long, fromInclusive: Int, toExclusive: Int)
    fun shiftPrioritiesDown(teamId: Long, fromExclusive: Int, toInclusive: Int)
    fun setPriority(id: UUID, priority: Int)
}
