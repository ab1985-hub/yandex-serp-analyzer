# MVP веб-сервис анализа конкурентности ключевых слов (Яндекс SERP)

Готовый MVP-проект с backend на FastAPI и frontend на React + TypeScript.

## Возможности MVP

- Ввод списка ключевых слов вручную или загрузкой файла.
- Выбор страны, региона, города и режима геопривязки (`strict`, `region_only`).
- Анализ ТОП-10 Яндекс SERP по каждому ключу.
- Подсчет уровней совпадения (`STRONG`, `NEAR`, `PARTIAL`, `NONE`) по леммам (pymorphy2).
- Расчет `SEO score`, `Ads score`, `Итогового score`.
- Классификация конкуренции (`A`, `B`, `C`, `D`) и автоматическая рекомендация.
- Таблица результатов с поиском, фильтрами и сортировкой.
- Экспорт результатов в CSV и JSON.

## Структура проекта

- `app/main.py` — вход FastAPI
- `app/api/` — API роуты
- `app/services/` — бизнес-логика (`serp_collector`, `text_processor`, `matcher`, `scorer`, `classifier`, `reporter`)
- `app/models/` — pydantic модели
- `app/utils/` — логирование
- `client/src/pages/` — страницы frontend
- `client/src/components/` — React-компоненты
- `client/src/services/` — API-клиент
- `client/src/types/` — типы данных

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`
- `DATAFORSEO_BASE_URL` (по умолчанию уже указан)
- `VITE_API_BASE` (адрес backend)

Если логин/пароль DataForSEO не заданы, используется fallback-режим с тестовыми данными.

## Локальный запуск

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd client
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Откройте: `http://localhost:5173`

## Запуск в Replit

В репозитории добавлены:

- `.replit`
- `run.sh`

Достаточно нажать **Run** — скрипт поднимет backend и frontend.

## Пример API запроса

`POST /api/analyze`

```json
{
  "search_engine": "yandex",
  "country": "Россия",
  "region": "Москва",
  "city": "Москва",
  "geo_mode": "strict",
  "depth": 10,
  "keywords": [
    "купить квартиру с террасой москва",
    "квартира с мастер спальней москва"
  ]
}
```
