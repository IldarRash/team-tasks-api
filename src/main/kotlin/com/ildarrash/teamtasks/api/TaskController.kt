package com.ildarrash.teamtasks.api

import com.fasterxml.jackson.databind.JsonNode
import com.ildarrash.teamtasks.domain.NewTask
import com.ildarrash.teamtasks.domain.Task
import com.ildarrash.teamtasks.domain.TaskPatch
import com.ildarrash.teamtasks.service.TaskService
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PatchMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController
import java.net.URI
import java.util.UUID

@RestController
@RequestMapping("/tasks")
class TaskController(private val service: TaskService) {
    @PostMapping
    fun create(@RequestBody body: JsonNode): ResponseEntity<TaskResponse> {
        val request = TaskJsonParser.create(body)
        val task = service.create(request)
        return ResponseEntity.created(URI.create("/tasks/${task.id}")).body(task.toResponse())
    }

    @GetMapping("/{id}")
    fun get(@PathVariable id: UUID): TaskResponse = service.get(id).toResponse()

    @GetMapping
    fun list(@RequestParam(required = false) teamId: String?): List<TaskResponse> =
        service.list(TaskJsonParser.optionalPositiveLong("teamId", teamId)).map { it.toResponse() }

    @PatchMapping("/{id}")
    fun patch(@PathVariable id: UUID, @RequestBody body: JsonNode): TaskResponse =
        service.patch(id, TaskJsonParser.patch(body)).toResponse()

    @PatchMapping("/{id}/priority")
    fun changePriority(@PathVariable id: UUID, @RequestBody body: JsonNode): TaskResponse =
        service.changePriority(id, TaskJsonParser.priority(body)).toResponse()

    @DeleteMapping("/{id}")
    fun delete(@PathVariable id: UUID): ResponseEntity<Void> {
        service.delete(id)
        return ResponseEntity.status(HttpStatus.NO_CONTENT).build()
    }
}

data class TaskResponse(
    val id: UUID,
    val teamId: Long,
    val name: String,
    val description: String,
    val priority: Int,
)

private fun Task.toResponse() = TaskResponse(id, teamId, name, description, priority)
