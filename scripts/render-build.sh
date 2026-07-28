#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

python -m pip install -r requirements.txt
python manage.py collectstatic --noinput

python manage.py validate_neon_connection_pair

# Migrações e tarefas administrativas não devem passar pelo pool transacional.
export DATABASE_URL="${DIRECT_DATABASE_URL}"
export DJANGO_DATABASE_EXPECT_POOLED="False"
python manage.py migrate --noinput
python manage.py ensure_network_admin --from-environment
python manage.py check --deploy
