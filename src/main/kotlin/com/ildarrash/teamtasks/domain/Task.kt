package com.ildarrash.teamtasks.domain

import java.util.UUID

data class Task(
    val id: UUID,
    val teamId: Long,
    val name: String,
    val description: String,
    val priority: Int,
)

data class NewTask(val teamId: Long, val name: String, val description: String)
data class TaskPatch(val name: String? = null, val description: String? = null)
