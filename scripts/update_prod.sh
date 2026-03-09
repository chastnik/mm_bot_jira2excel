#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/update_prod.sh [install_dir] [branch]
# Example:
#   ./scripts/update_prod.sh /opt/jira2excel main

INSTALL_DIR="${1:-/opt/jira2excel}"
BRANCH="${2:-main}"

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

BACKUP_DIR="${INSTALL_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

if [[ -f ".env" ]]; then
  cp ".env" "${BACKUP_DIR}/.env.${TIMESTAMP}.bak"
fi

if [[ -f "state/user_sessions.json" ]]; then
  cp "state/user_sessions.json" "${BACKUP_DIR}/user_sessions.json.${TIMESTAMP}.bak"
fi

echo "Обновляем код из Git (${BRANCH})..."
git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

mkdir -p state

echo "Пересобираем и перезапускаем контейнер..."
${COMPOSE_CMD} -f docker-compose.prod.yml up -d --build

echo "Обновление завершено."
echo "Проверка логов:"
echo "  ${COMPOSE_CMD} -f docker-compose.prod.yml logs -f --tail=100"
