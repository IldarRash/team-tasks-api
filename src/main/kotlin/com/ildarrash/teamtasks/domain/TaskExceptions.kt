package com.ildarrash.teamtasks.domain

class InvalidRequestException(
    override val message: String,
    val fieldErrors: Map<String, String> = emptyMap(),
) : RuntimeException(message)

class TaskNotFoundException(id: Any) : RuntimeException("Task $id was not found")

class TransientDatabaseException : RuntimeException("The database is busy. Please retry the request.")
