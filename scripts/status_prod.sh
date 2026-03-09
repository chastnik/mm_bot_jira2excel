#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/status_prod.sh [install_dir]
# Example:
#   ./scripts/status_prod.sh /opt/jira2excel

INSTALL_DIR="${1:-/opt/jira2excel}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Ошибка: команда '$1' не найдена"
    exit 1
  fi
}

ensure_docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    return
  fi

  echo "Ошибка: не найден docker compose (ни 'docker compose', ни 'docker-compose')"
  exit 1
}

require_cmd git
require_cmd docker
ensure_docker_compose

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  echo "Ошибка: директория '${INSTALL_DIR}' не содержит git-репозиторий"
  exit 1
fi

cd "${INSTALL_DIR}"

if [[ ! -f "docker-compose.prod.yml" ]]; then
  echo "Ошибка: не найден файл docker-compose.prod.yml в ${INSTALL_DIR}"
  exit 1
fi

echo "=== Git ==="
echo "Текущая ветка: $(git rev-parse --abbrev-ref HEAD)"
echo "Текущий коммит: $(git rev-parse --short HEAD)"
echo "Последний коммит:"
git log -1 --pretty=format:'%h %ad %an %s' --date=iso
echo
echo

echo "=== Containers ==="
${COMPOSE_CMD} -f docker-compose.prod.yml ps
echo

echo "=== Last logs (100 lines) ==="
${COMPOSE_CMD} -f docker-compose.prod.yml logs --tail=100
