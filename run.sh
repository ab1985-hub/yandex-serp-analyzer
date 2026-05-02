#!/bin/bash
set -e

fuser -k 8000/tcp 2>/dev/null || true
sleep 1

echo "Устанавливаем Python зависимости..."
pip install -r requirements.txt --quiet

echo "Запускаем backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000
