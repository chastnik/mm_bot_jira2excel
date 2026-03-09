#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/install_prod.sh [repo_url] [install_dir] [branch]
# Example:
#   ./scripts/install_prod.sh https://github.com/chastnik/mm_bot_jira2excel /opt/jira2excel main
#   ./scripts/install_prod.sh /opt/jira2excel main  # uses default repo URL

DEFAULT_REPO_URL="https://github.com/chastnik/mm_bot_jira2excel"

# Backward-compatible argument parsing:
# - If 1st arg looks like URL, treat it as repo URL.
# - Otherwise treat args as [install_dir] [branch] and use default repo URL.
if [[ "${1:-}" =~ ^https?://|^git@ ]]; then
  REPO_URL="${1}"
  INSTALL_DIR="${2:-/opt/jira2excel}"
  BRANCH="${3:-main}"
else
  REPO_URL="${DEFAULT_REPO_URL}"
  INSTALL_DIR="${1:-/opt/jira2excel}"
  BRANCH="${2:-main}"
fi

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

if [[ -d "${INSTALL_DIR}/.git" ]]; then
  echo "Репозиторий уже установлен в ${INSTALL_DIR}"
else
  echo "Клонируем репозиторий в ${INSTALL_DIR}..."
  mkdir -p "${INSTALL_DIR}"
  git clone --branch "${BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"

if [[ ! -f ".env" ]]; then
  echo "Создаем .env из env.example"
  cp env.example .env
  echo "Заполните .env и запустите скрипт повторно:"
  echo "  ${INSTALL_DIR}/scripts/install_prod.sh ${REPO_URL} ${INSTALL_DIR} ${BRANCH}"
  exit 0
fi

mkdir -p state

echo "Запускаем контейнер бота..."
${COMPOSE_CMD} -f docker-compose.prod.yml up -d --build

echo "Установка завершена."
echo "Проверка логов:"
echo "  ${COMPOSE_CMD} -f docker-compose.prod.yml logs -f --tail=100"
