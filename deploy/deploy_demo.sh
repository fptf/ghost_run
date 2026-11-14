#!/usr/bin/env bash
# Выкладка демо-стенда на сервер по SSH.
#   SSH_KEY=~/.ssh/demo_key [WEB_PORT=8088] deploy/deploy_demo.sh root@<demo-host>
# Копирует код (без node_modules, .venv, исходных треков ./tracks) в /opt/runners, при первом
# запуске создаёт deploy/demo.env со случайными секретами и поднимает стенд.
set -euo pipefail
HOST="${1:?укажите user@host}"
KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
DIR=/opt/runners
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST")
cd "$(dirname "$0")/.."

rsync -az --delete -e "ssh -i $KEY" \
  --exclude .git --exclude node_modules --exclude .venv --exclude dist \
  --exclude '__pycache__' --exclude .pytest_cache --exclude .mypy_cache --exclude .ruff_cache \
  --exclude /tracks --exclude /tracks-dump --exclude /deploy/demo.env --exclude .DS_Store \
  ./ "$HOST:$DIR/"

"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
cd $DIR
if [ ! -f deploy/demo.env ]; then
  umask 077
  printf 'POSTGRES_PASSWORD=%s\nJWT_SECRET=%s\nWEB_PORT=%s\n' "\$(openssl rand -hex 16)" "\$(openssl rand -hex 32)" "${WEB_PORT:-8088}" > deploy/demo.env
fi
docker compose -f docker-compose.demo.yml --env-file deploy/demo.env up -d --build --wait
docker compose -f docker-compose.demo.yml --env-file deploy/demo.env ps
REMOTE
