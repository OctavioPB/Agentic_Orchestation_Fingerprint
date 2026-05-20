-- Runs once on first postgres container init (docker-entrypoint-initdb.d).
-- Creates the orchid user and database used by services/api.
-- The airflow database is created separately by the POSTGRES_DB env var.

CREATE USER orchid WITH PASSWORD 'orchid';
CREATE DATABASE orchid OWNER orchid;
