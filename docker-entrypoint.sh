#!/usr/bin/env sh
set -eu

mkdir -p /app/state
touch /app/state/bot.log
touch /app/state/user_sessions.json

ln -sf /app/state/bot.log /app/bot.log
ln -sf /app/state/user_sessions.json /app/user_sessions.json

exec python3 main.py
