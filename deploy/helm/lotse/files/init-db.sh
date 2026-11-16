#!/bin/sh
# First-start bootstrap for the Postgres container. Mounted by compose.yaml and by the
# Helm chart, so both create the same roles. Passwords come from the environment and
# are never written into a migration.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v db="$POSTGRES_DB" \
  -v app_password="$LOTSE_APP_DB_PASSWORD" \
  -v platform_password="$LOTSE_PLATFORM_DB_PASSWORD" \
  -v keycloak_password="$KEYCLOAK_DB_PASSWORD" <<'SQL'
CREATE ROLE lotse_owner NOLOGIN;
CREATE ROLE lotse_app LOGIN NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE lotse_platform LOGIN NOBYPASSRLS PASSWORD :'platform_password';
REVOKE CONNECT ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO lotse_app, lotse_platform;

-- Keycloak keeps its own database on the same server.
CREATE ROLE keycloak LOGIN PASSWORD :'keycloak_password';
CREATE DATABASE keycloak OWNER keycloak;
REVOKE CONNECT ON DATABASE keycloak FROM PUBLIC;
SQL
