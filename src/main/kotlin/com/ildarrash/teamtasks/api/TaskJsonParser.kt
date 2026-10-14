package com.ildarrash.teamtasks.api

import com.fasterxml.jackson.databind.JsonNode
import com.ildarrash.teamtasks.domain.InvalidRequestException
import com.ildarrash.teamtasks.domain.NewTask
import com.ildarrash.teamtasks.domain.TaskPatch

/** Keeps PATCH presence/null semantics at the HTTP boundary, before domain validation. */
object TaskJsonParser {
    fun create(body: JsonNode): NewTask {
        objectBody(body, setOf("teamId", "name", "description"))
        return NewTask(
            teamId = requiredPositiveLong(body, "teamId"),
            name = requiredText(body, "name"),
            description = requiredText(body, "description"),
        )
    }

    fun patch(body: JsonNode): TaskPatch {
        objectBody(body, setOf("name", "description"))
        if (body.size() == 0) invalid("body", "at least one of name or description is required")
        return TaskPatch(
            name = optionalText(body, "name"),
            description = optionalText(body, "description"),
        )
    }

    fun priority(body: JsonNode): Int {
        objectBody(body, setOf("priority"))
        val node = body.get("priority") ?: invalid("priority", "is required")
        if (!node.isIntegralNumber || !node.canConvertToInt()) invalid("priority", "must be an integer")
        return node.intValue()
    }

    fun optionalPositiveLong(field: String, raw: String?): Long? {
        if (raw == null) return null
        val value = raw.toLongOrNull() ?: invalid(field, "must be a positive integer")
        if (value <= 0) invalid(field, "must be a positive integer")
        return value
    }

    private fun objectBody(body: JsonNode, allowedFields: Set<String>) {
        if (!body.isObject) invalid("body", "must be a JSON object")
        body.fieldNames().forEachRemaining { field ->
            if (field !in allowedFields) invalid(field, "is not allowed")
        }
    }

    private fun requiredPositiveLong(body: JsonNode, field: String): Long {
        val node = body.get(field) ?: invalid(field, "is required")
        if (!node.isIntegralNumber || !node.canConvertToLong() || node.longValue() <= 0) invalid(field, "must be a positive integer")
        return node.longValue()
    }

    private fun requiredText(body: JsonNode, field: String): String = optionalText(body, field, true)!!

    private fun optionalText(body: JsonNode, field: String, required: Boolean = false): String? {
        val node = body.get(field)
        if (node == null) {
            if (required) invalid(field, "is required")
            return null
        }
        if (!node.isTextual) invalid(field, "must be a string")
        return node.textValue()
    }

    private fun invalid(field: String, message: String): Nothing =
        throw InvalidRequestException("Request validation failed", mapOf(field to message))
}
