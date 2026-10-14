package com.ildarrash.teamtasks.api

import com.ildarrash.teamtasks.domain.InvalidRequestException
import com.ildarrash.teamtasks.domain.TaskNotFoundException
import com.ildarrash.teamtasks.domain.TransientDatabaseException
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.http.converter.HttpMessageNotReadableException
import org.springframework.web.bind.MethodArgumentNotValidException
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException
import org.springframework.web.HttpMediaTypeNotSupportedException
import org.springframework.web.HttpRequestMethodNotSupportedException
import org.springframework.web.servlet.resource.NoResourceFoundException
import org.slf4j.LoggerFactory
import java.util.HashMap

@RestControllerAdvice
class ApiExceptionHandler {
    private val logger = LoggerFactory.getLogger(javaClass)

    @ExceptionHandler(InvalidRequestException::class)
    fun invalid(exception: InvalidRequestException) = error(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", exception.message ?: "Request validation failed", exception.fieldErrors)

    @ExceptionHandler(TaskNotFoundException::class)
    fun notFound(exception: TaskNotFoundException) = error(HttpStatus.NOT_FOUND, "TASK_NOT_FOUND", exception.message ?: "Task was not found")

    @ExceptionHandler(TransientDatabaseException::class)
    fun unavailable(exception: TransientDatabaseException) = error(HttpStatus.SERVICE_UNAVAILABLE, "TRANSIENT_DATABASE_ERROR", exception.message ?: "The database is busy. Please retry the request.")

    @ExceptionHandler(HttpMessageNotReadableException::class)
    fun malformedJson() = error(HttpStatus.BAD_REQUEST, "MALFORMED_JSON", "Request body must contain valid JSON")

    @ExceptionHandler(MethodArgumentTypeMismatchException::class)
    fun typeMismatch(exception: MethodArgumentTypeMismatchException) = error(
        HttpStatus.BAD_REQUEST,
        "VALIDATION_ERROR",
        "Request validation failed",
        mapOf(exception.name to "has an invalid value"),
    )

    @ExceptionHandler(MethodArgumentNotValidException::class)
    fun methodValidation(exception: MethodArgumentNotValidException) = error(
        HttpStatus.BAD_REQUEST,
        "VALIDATION_ERROR",
        "Request validation failed",
        exception.bindingResult.fieldErrors.associate { it.field to (it.defaultMessage ?: "is invalid") },
    )

    @ExceptionHandler(HttpRequestMethodNotSupportedException::class)
    fun methodNotAllowed() = error(HttpStatus.METHOD_NOT_ALLOWED, "METHOD_NOT_ALLOWED", "The HTTP method is not supported for this resource")

    @ExceptionHandler(HttpMediaTypeNotSupportedException::class)
    fun unsupportedMediaType() = error(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json")

    @ExceptionHandler(NoResourceFoundException::class)
    fun noResource() = error(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "The requested resource was not found")

    @ExceptionHandler(Exception::class)
    fun unexpected(exception: Exception): ResponseEntity<ApiError> {
        logger.error("Unhandled API exception", exception)
        return error(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "An unexpected server error occurred")
    }

    private fun error(status: HttpStatus, code: String, message: String, fieldErrors: Map<String, String> = emptyMap()): ResponseEntity<ApiError> =
        ResponseEntity.status(status).body(ApiError(status.value(), code, message, HashMap(fieldErrors)))
}

data class ApiError(
    val status: Int,
    val code: String,
    val message: String,
    val fieldErrors: Map<String, String>,
)
