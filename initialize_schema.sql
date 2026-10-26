-- Copyright 2026 Allan Brand
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://apache.org
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific permissions and
-- limitations under the License.

-- Ensure clean execution environments by wrapping structures into an atomic transaction block
BEGIN;

CREATE TABLE IF NOT EXISTS job_executions (
    id VARCHAR(255) PRIMARY KEY,
    job_type VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    filters JSONB NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(50) DEFAULT 'viewer'
);

CREATE TABLE IF NOT EXISTS groups (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR(255) PRIMARY KEY,
    object_type VARCHAR(100) NOT NULL,
    object_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_stream (
    id VARCHAR(255) PRIMARY KEY,
    actor_username VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    object_id VARCHAR(255) NOT NULL,
    changes_json JSONB,
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS job_history_summaries (
    id VARCHAR(255) PRIMARY KEY,
    job_id VARCHAR(255) NOT NULL,
    executed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    success BOOLEAN DEFAULT TRUE,
    summary_data JSONB NOT NULL,
    raw_console_output TEXT NOT NULL
);

-- Establish Many-to-Many Relational Constraint Bridge Triggers
CREATE TABLE IF NOT EXISTS user_group_association (
    user_id VARCHAR(255) REFERENCES users(id) ON DELETE CASCADE,
    group_id VARCHAR(255) REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS group_permission_association (
    group_id VARCHAR(255) REFERENCES groups(id) ON DELETE CASCADE,
    permission_id VARCHAR(255) REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, permission_id)
);

-- Construct Performance Enhancing Search Query Indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_activity_stream_actor ON activity_stream(actor_username);
CREATE INDEX IF NOT EXISTS idx_activity_stream_timestamp ON activity_stream(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_job_id ON job_history_summaries(job_id);

COMMIT;
