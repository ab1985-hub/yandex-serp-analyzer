# Yandex Search API — Справочник

Источник: официальная документация Yandex Cloud (сохранено из .docx, загруженного пользователем).

---

## О сервисе

Yandex Search API позволяет автоматически отправлять запросы к поисковой базе Яндекса и получать результаты поиска в форматах **XML** или **HTML**.

Дополнительно предоставляет инструмент **Wordstat** — статистика поисковых запросов (топ популярных запросов, динамика частоты, распределение по регионам).

---

## Режимы работы

| Режим | Описание |
|---|---|
| **Синхронный** | Ответ сразу после обработки. Подходит для небольшого числа запросов. |
| **Асинхронный (отложенный)** | Возвращает `Operation` с ID, по которому можно получить результат. Подходит для пакетной обработки. |

### Типы поиска

| Тип | Режимы |
|---|---|
| Текстовый поиск (XML/HTML) | Синхронный + асинхронный |
| Поиск изображений | Только синхронный |
| Генеративный ответ (YandexGPT) | Только синхронный |

---

## Эндпоинты

### Синхронный текстовый поиск (REST)

```
POST https://searchapi.api.cloud.yandex.net/v2/web/search
Authorization: Api-Key <API-ключ>
Content-Type: application/json
```

### Тело запроса

```json
{
  "query": {
    "searchType": "SEARCH_TYPE_RU",
    "queryText": "кофемашина",
    "region": 213,
    "groupsOnPage": 10
  },
  "folderId": "<folder_id>",
  "responseFormat": "FORMAT_XML"
}
```

**Параметры `query`:**

| Поле | Описание |
|---|---|
| `searchType` | `SEARCH_TYPE_RU` — рунет, `SEARCH_TYPE_TR` — Турция, `SEARCH_TYPE_COM` — мировой |
| `queryText` | Текст запроса |
| `region` | lr-код региона Яндекса (213 = Москва, 2 = СПб, 225 = Россия) |
| `groupsOnPage` | Количество результатов (1–100) |

**Параметры верхнего уровня:**

| Поле | Описание |
|---|---|
| `folderId` | ID каталога в Yandex Cloud (env: `YANDEX_FOLDER_ID`) |
| `responseFormat` | `FORMAT_XML` или `FORMAT_HTML` |

### Ответ

```json
{
  "rawData": "<base64-encoded XML или HTML>"
}
```

Декодировать: `base64.b64decode(rawData)`

---

## XML-структура ответа (FORMAT_XML)

```xml
<yandexsearch version="1.0">
  <request>...</request>
  <response>
    <results>
      <grouping>
        <group>
          <doc>
            <title>Заголовок страницы</title>
            <url>https://example.com/page</url>
            <domain>example.com</domain>
            <passages>
              <passage>Сниппет текста...</passage>
            </passages>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>
```

Один `<group>` = одна позиция в выдаче. В каждом может быть несколько `<doc>` (если включена группировка по домену), обычно берётся первый.

---

## Wordstat API

```
Хост: wordstat.api.cloud.yandex.net
```

> **Внимание:** DNS не резолвится с внешних серверов (только из Yandex Cloud). В Replit — используется fallback-список регионов.

### Реальные REST-пути (из официального proto cloudapi)

| gRPC метод | REST path | Описание |
|---|---|---|
| `GetTop` | `POST /v2/wordstat/topRequests` | Топ запросов за 30 дней |
| `GetDynamics` | `POST /v2/wordstat/dynamics` | Динамика частоты |
| `GetRegionsDistribution` | `POST /v2/wordstat/regions` | Распределение по регионам |
| `GetRegionsTree` | `POST /v2/wordstat/getRegionsTree` | Дерево регионов |

> **Важно:** документация называет методы `GetTop`, `GetDynamics` и т.д., но реальные REST-пути отличаются от очевидных `/getTop` → они `/topRequests`, `/dynamics`, `/regions`. Путь получен из официального [cloudapi proto](https://github.com/yandex-cloud/cloudapi/blob/master/yandex/cloud/searchapi/v2/wordstat_service.proto).

### GetTop — параметры запроса

```json
POST /v2/wordstat/topRequests
{
  "folderId": "<folder_id>",
  "phrase": "купить квартиру",
  "numPhrases": 100,
  "regions": ["213"],
  "devices": []
}
```

### GetTop — ответ

```json
{
  "totalCount": 1094188,
  "results": [
    {"phrase": "купить квартиру", "count": "1094188"},
    {"phrase": "купить квартиру в москве", "count": "180874"}
  ],
  "associations": [
    {"phrase": "продажа автомобилей", "count": "54468"}
  ]
}
```

> **Внимание:** `count` в ответе приходит как строка, а не число — нужно явно конвертировать `int(count)`.

### GetRegionsTree — ответ

```json
{
  "regions": [
    {
      "id": "225",
      "label": "Россия",
      "children": [...]
    }
  ]
}
```

> **Поле:** имя региона — `label` (не `name`), id — строка (нужно конвертировать в int).

---

## Аутентификация

Заголовок: `Authorization: Api-Key <ключ>`

- `YANDEX_API_KEY` — API-ключ AI Studio (env-переменная)
- `YANDEX_FOLDER_ID` — ID каталога (env-переменная)

API-ключ AI Studio автоматически имеет нужные роли для Search API + Wordstat.

---

## lr-коды основных регионов

| Регион | lr-код |
|---|---|
| Москва | 213 |
| Санкт-Петербург | 2 |
| Новосибирск | 65 |
| Екатеринбург | 54 |
| Казань | 43 |
| Нижний Новгород | 47 |
| Краснодар | 35 |
| Россия (вся) | 225 |

---

## Квоты (примерные)

- Синхронный поиск: лимит RPM зависит от тарифа
- Асинхронный: подходит для пакетной обработки >100 запросов

---

## Ссылки

- Официальная документация: https://yandex.cloud/ru/docs/search-api/
- AI Studio: https://studio.yandex.cloud/
- GitHub SDK: https://github.com/yandex-cloud/yandex-cloud-ml-sdk
