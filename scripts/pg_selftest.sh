#!/bin/sh
# Runs the full automated test-suite against a PostgreSQL database.
# WARNING: it DROPS ALL TABLES in the target. Use a NEW empty database (e.g. a second Railway Postgres), never production.
#   TEST_DATABASE_URL='postgresql://user:pass@host:port/db' sh scripts/pg_selftest.sh
set -e
[ -n "$TEST_DATABASE_URL" ] || { echo "Set TEST_DATABASE_URL first"; exit 1; }
CONFIRM_WIPE_TEST_DB=yes python -W ignore -m unittest discover -s tests -t . -v
