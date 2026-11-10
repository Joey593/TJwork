-- Initial schema generated from SQLAlchemy models; MySQL 8.4
CREATE DATABASE IF NOT EXISTS aurora CHARACTER SET utf8mb4;
USE aurora;

CREATE TABLE audit_logs (
	actor_id VARCHAR(32),
	action VARCHAR(80) NOT NULL,
	entity_id VARCHAR(64) NOT NULL,
	detail JSON NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id)
)

;


CREATE TABLE users (
	username VARCHAR(64) NOT NULL,
	password_hash VARCHAR(256) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (username)
)

;


CREATE TABLE projects (
	name VARCHAR(120) NOT NULL,
	description TEXT NOT NULL,
	base_url VARCHAR(500) NOT NULL,
	owner_id VARCHAR(32) NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(owner_id) REFERENCES users (id)
)

;


CREATE TABLE experiments (
	project_id VARCHAR(32) NOT NULL,
	name VARCHAR(160) NOT NULL,
	method VARCHAR(32) NOT NULL,
	observations JSON NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES projects (id)
)

;


CREATE TABLE requirements (
	project_id VARCHAR(32) NOT NULL,
	title VARCHAR(200) NOT NULL,
	content TEXT NOT NULL,
	points JSON NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES projects (id)
)

;


CREATE TABLE runs (
	project_id VARCHAR(32) NOT NULL,
	actor_id VARCHAR(32) NOT NULL,
	name VARCHAR(160) NOT NULL,
	status VARCHAR(20) NOT NULL,
	browser VARCHAR(20) NOT NULL,
	`repeat` INTEGER NOT NULL,
	snapshot JSON NOT NULL,
	summary JSON NOT NULL,
	started_at VARCHAR(40),
	finished_at VARCHAR(40),
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES projects (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;


CREATE TABLE generations (
	project_id VARCHAR(32) NOT NULL,
	requirement_id VARCHAR(32) NOT NULL,
	method VARCHAR(32) NOT NULL,
	model VARCHAR(100) NOT NULL,
	prompt_version VARCHAR(40) NOT NULL,
	input_hash VARCHAR(64) NOT NULL,
	duration_ms INTEGER NOT NULL,
	payload JSON NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES projects (id),
	FOREIGN KEY(requirement_id) REFERENCES requirements (id)
)

;


CREATE TABLE cases (
	project_id VARCHAR(32) NOT NULL,
	requirement_id VARCHAR(32) NOT NULL,
	generation_id VARCHAR(32),
	status VARCHAR(20) NOT NULL,
	version INTEGER NOT NULL,
	body JSON NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES projects (id),
	FOREIGN KEY(requirement_id) REFERENCES requirements (id),
	FOREIGN KEY(generation_id) REFERENCES generations (id)
)

;


CREATE TABLE case_revisions (
	case_id VARCHAR(32) NOT NULL,
	actor_id VARCHAR(32) NOT NULL,
	version INTEGER NOT NULL,
	action VARCHAR(32) NOT NULL,
	body JSON NOT NULL,
	note TEXT NOT NULL,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(case_id) REFERENCES cases (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;


CREATE TABLE results (
	run_id VARCHAR(32) NOT NULL,
	case_id VARCHAR(32) NOT NULL,
	ordinal INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	duration_ms INTEGER NOT NULL,
	evidence JSON NOT NULL,
	analysis JSON,
	id VARCHAR(32) NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(run_id) REFERENCES runs (id),
	FOREIGN KEY(case_id) REFERENCES cases (id)
)

;
