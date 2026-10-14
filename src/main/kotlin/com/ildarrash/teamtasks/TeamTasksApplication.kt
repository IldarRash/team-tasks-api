package com.ildarrash.teamtasks

import com.ildarrash.teamtasks.api.ApiError
import com.ildarrash.teamtasks.api.TaskResponse
import com.ildarrash.teamtasks.nativeimage.TeamTasksRuntimeHints
import org.springframework.aot.hint.annotation.RegisterReflectionForBinding
import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication
import org.springframework.context.annotation.ImportRuntimeHints

@SpringBootApplication
@ImportRuntimeHints(TeamTasksRuntimeHints::class)
@RegisterReflectionForBinding(TaskResponse::class, ApiError::class)
class TeamTasksApplication

fun main(args: Array<String>) {
    runApplication<TeamTasksApplication>(*args)
}
