CREATE TABLE team_locks (
    team_id BIGINT PRIMARY KEY CHECK (team_id > 0)
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES team_locks(team_id),
    name VARCHAR(200) NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT NOT NULL CHECK (length(trim(description)) BETWEEN 1 AND 10000),
    priority INTEGER NOT NULL CHECK (priority > 0),
    CONSTRAINT tasks_team_priority_unique UNIQUE (team_id, priority)
        DEFERRABLE INITIALLY DEFERRED
);
