-- Creates the isolated test database alongside the main `bidstanza` database.
-- Postgres runs every script in /docker-entrypoint-initdb.d only once, when the
-- data volume is first initialised. If the volume already exists, run
-- `docker compose down -v` to re-trigger it.
CREATE DATABASE bidstanza_test OWNER bidstanza;
