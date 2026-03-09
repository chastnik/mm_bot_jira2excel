#!/usr/bin/env sh
set -eu

mkdir -p /app/state
touch /app/state/bot.log

# Инициализируем файл сессий валидным JSON, если он отсутствует или пустой.
if [ ! -s /app/state/user_sessions.json ]; then
  printf "{}\n" > /app/state/user_sessions.json
fi

ln -sf /app/state/bot.log /app/bot.log
ln -sf /app/state/user_sessions.json /app/user_sessions.json

exec python3 main.py
