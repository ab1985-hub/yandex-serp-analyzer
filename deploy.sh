#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Скрипт деплоя на Timeweb VPS (Ubuntu 22.04 / Debian 12)
#  Запускать от root или через sudo:
#    chmod +x deploy.sh && sudo ./deploy.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/ab1985-hub/yandex-serp-analyzer.git"
APP_DIR="/opt/serp-analyzer"
COMPOSE_FILE="$APP_DIR/docker-compose.yml"

echo "═══════════════════════════════════════════════"
echo "  Yandex SERP Analyzer — деплой на сервер"
echo "═══════════════════════════════════════════════"

# 1. Установить Docker если не установлен
if ! command -v docker &>/dev/null; then
  echo "[1/5] Устанавливаю Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
else
  echo "[1/5] Docker уже установлен."
fi

# 2. Установить Docker Compose plugin если нет
if ! docker compose version &>/dev/null; then
  echo "[2/5] Устанавливаю Docker Compose plugin..."
  apt-get install -y docker-compose-plugin
else
  echo "[2/5] Docker Compose уже установлен."
fi

# 3. Клонировать / обновить репозиторий
if [ -d "$APP_DIR/.git" ]; then
  echo "[3/5] Обновляю код..."
  git -C "$APP_DIR" pull --ff-only
else
  echo "[3/5] Клонирую репозиторий..."
  git clone "$REPO_URL" "$APP_DIR"
fi

# 4. Создать .env если его нет
if [ ! -f "$APP_DIR/.env" ]; then
  echo ""
  echo "[4/5] Файл .env не найден. Создаю из шаблона..."
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo ""
  echo "  ⚠️  Отредактируйте файл $APP_DIR/.env:"
  echo "      YANDEX_API_KEY=..."
  echo "      YANDEX_FOLDER_ID=..."
  echo "      SERP_PROXY_URL=..."
  echo ""
  read -rp "  Нажмите Enter после того, как заполните .env..."
else
  echo "[4/5] Файл .env уже существует."
fi

# 5. Собрать и запустить контейнеры
echo "[5/5] Сборка и запуск контейнеров..."
docker compose -f "$COMPOSE_FILE" pull 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans

echo ""
echo "✅ Готово! Сервис запущен на порту 80."
echo "   Проверить статус: docker compose -f $COMPOSE_FILE ps"
echo "   Логи:            docker compose -f $COMPOSE_FILE logs -f app"
echo ""

# Показать IP сервера
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo "   Откройте в браузере: http://$SERVER_IP"
echo "═══════════════════════════════════════════════"
