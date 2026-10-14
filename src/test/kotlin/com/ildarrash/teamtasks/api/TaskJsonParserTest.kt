package com.ildarrash.teamtasks.api

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.ildarrash.teamtasks.domain.InvalidRequestException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class TaskJsonParserTest {
    private val json = jacksonObjectMapper()

    @Test
    fun `create accepts only server-assigned task fields`() {
        val task = TaskJsonParser.create(json.readTree("""{"teamId":7,"name":"A","description":"B"}"""))

        assertEquals(7, task.teamId)
        assertEquals("A", task.name)
    }

    @Test
    fun `create rejects client supplied priority and missing fields`() {
        val priorityError = assertFailsWith<InvalidRequestException> {
            TaskJsonParser.create(json.readTree("""{"teamId":7,"name":"A","description":"B","priority":1}"""))
        }
        val missingError = assertFailsWith<InvalidRequestException> {
            TaskJsonParser.create(json.readTree("""{"teamId":7,"name":"A"}"""))
        }

        assertEquals("is not allowed", priorityError.fieldErrors["priority"])
        assertEquals("is required", missingError.fieldErrors["description"])
    }

    @Test
    fun `patch distinguishes absent field from explicit null`() {
        val patch = TaskJsonParser.patch(json.readTree("""{"name":"renamed"}"""))
        assertEquals("renamed", patch.name)
        assertEquals(null, patch.description)

        val nullError = assertFailsWith<InvalidRequestException> {
            TaskJsonParser.patch(json.readTree("""{"name":null}"""))
        }
        assertEquals("must be a string", nullError.fieldErrors["name"])
    }

    @Test
    fun `priority requires an integer`() {
        val error = assertFailsWith<InvalidRequestException> {
            TaskJsonParser.priority(json.readTree("""{"priority":1.5}"""))
        }
        assertEquals("must be an integer", error.fieldErrors["priority"])
    }
}
