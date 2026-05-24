#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Starting TradeBot backend with Docker Compose..."
if docker compose version >/dev/null 2>&1; then
  docker compose up --build --remove-orphans
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up --build --remove-orphans
else
  echo "Error: Neither 'docker compose' nor 'docker-compose' is installed."
  exit 1
fi
