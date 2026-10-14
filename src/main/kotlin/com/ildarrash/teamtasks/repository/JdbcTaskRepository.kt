package com.ildarrash.teamtasks.repository

import com.ildarrash.teamtasks.domain.Task
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate
import org.springframework.stereotype.Repository
import java.sql.ResultSet
import java.util.UUID

@Repository
class JdbcTaskRepository(private val jdbc: NamedParameterJdbcTemplate) : TaskRepository {
    private val mapper = { rs: ResultSet, _: Int ->
        Task(
            id = rs.getObject("id", UUID::class.java),
            teamId = rs.getLong("team_id"),
            name = rs.getString("name"),
            description = rs.getString("description"),
            priority = rs.getInt("priority"),
        )
    }

    override fun ensureAndLockTeam(teamId: Long) {
        val params = mapOf("teamId" to teamId)
        jdbc.update("insert into team_locks (team_id) values (:teamId) on conflict do nothing", params)
        jdbc.queryForObject("select team_id from team_locks where team_id = :teamId for update", params, Long::class.java)
    }

    override fun findById(id: UUID): Task? = jdbc.query(
        "select id, team_id, name, description, priority from tasks where id = :id",
        mapOf("id" to id), mapper,
    ).firstOrNull()

    override fun findAll(teamId: Long?): List<Task> {
        val sql = if (teamId == null) {
            "select id, team_id, name, description, priority from tasks order by team_id, priority"
        } else {
            "select id, team_id, name, description, priority from tasks where team_id = :teamId order by priority"
        }
        return jdbc.query(sql, if (teamId == null) emptyMap<String, Any>() else mapOf("teamId" to teamId), mapper)
    }

    override fun nextPriority(teamId: Long): Int = jdbc.queryForObject(
        "select coalesce(max(priority), 0) + 1 from tasks where team_id = :teamId",
        mapOf("teamId" to teamId), Int::class.java,
    )!!

    override fun insert(task: Task) {
        jdbc.update(
            "insert into tasks (id, team_id, name, description, priority) values (:id, :teamId, :name, :description, :priority)",
            taskParams(task),
        )
    }

    override fun updateContent(id: UUID, name: String, description: String) {
        jdbc.update("update tasks set name = :name, description = :description where id = :id", mapOf("id" to id, "name" to name, "description" to description))
    }

    override fun delete(id: UUID) {
        jdbc.update("delete from tasks where id = :id", mapOf("id" to id))
    }

    override fun compactAfterDelete(teamId: Long, deletedPriority: Int) {
        jdbc.update("update tasks set priority = priority - 1 where team_id = :teamId and priority > :priority", mapOf("teamId" to teamId, "priority" to deletedPriority))
    }

    override fun shiftPrioritiesUp(teamId: Long, fromInclusive: Int, toExclusive: Int) {
        jdbc.update("update tasks set priority = priority + 1 where team_id = :teamId and priority >= :from and priority < :to", mapOf("teamId" to teamId, "from" to fromInclusive, "to" to toExclusive))
    }

    override fun shiftPrioritiesDown(teamId: Long, fromExclusive: Int, toInclusive: Int) {
        jdbc.update("update tasks set priority = priority - 1 where team_id = :teamId and priority > :from and priority <= :to", mapOf("teamId" to teamId, "from" to fromExclusive, "to" to toInclusive))
    }

    override fun setPriority(id: UUID, priority: Int) {
        jdbc.update("update tasks set priority = :priority where id = :id", mapOf("id" to id, "priority" to priority))
    }

    private fun taskParams(task: Task) = MapSqlParameterSource()
        .addValue("id", task.id)
        .addValue("teamId", task.teamId)
        .addValue("name", task.name)
        .addValue("description", task.description)
        .addValue("priority", task.priority)
}
