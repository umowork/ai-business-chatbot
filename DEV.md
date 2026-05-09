# DEV.md

## Обзор

AI Business Chatbot — AI-чат-бот для бизнеса с поддержкой документов (RAG),
классификацией запросов и интеграцией с CRM (Битрикс24 / AmoCRM).

## Архитектура

```
main.py                      # Точка входа (Telegram bot / Web API)
├── config.py                # Конфигурация из env
├── models/                  # Модели БД (SQLAlchemy async)
│   ├── base.py              #  User, Dialog, Lead + Database
│   ├── user.py
│   ├── dialog.py
│   └── lead.py
├── crm/                       # CRM интеграция (Bitrix24, AmoCRM, Mock)
│   ├── base.py                #  CRMResult, BaseCRMProvider, CRMFactory
│   ├── bitrix24.py            # Bitrix24 REST API
│   ├── amocrm.py              # AmoCRM API v4
│   └── mock.py                # Mock CRM для dev/tests
├── services/                  # Бизнес-логика
│   ├── llm.py                 #  LLM gateway (OpenAI, GigaChat, YandexGPT)
│   ├── llm_gigachat.py        # GigaChat provider
│   ├── llm_yandex.py          # YandexGPT provider
│   ├── classifier.py          # Классификация запросов (LLM + keywords)
│   └── rag.py                 # RAG (PDF → embeddings → search)
├── bot/                       # Telegram bot (aiogram 3)
│   ├── handlers.py            # Обработчики сообщений и callback'ов
│   └── keyboards.py           # Inline-клавиатуры
└── api/                       # Web API (FastAPI)
    └── web.py                 # REST endpoints
```

## Установка

```bash
# 1. Клонировать репозиторий
git clone ...
cd 05-ai-business-chatbot

# 2. Настроить окружение
cp .env.example .env
# отредактировать .env (BOT_TOKEN обязателен)

# 3. Установить зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt  # для разработки

# 4. Запуск
make run          # Telegram bot (mock mode)
make run-api      # Web API только
make run-all      # Telegram + Web API
```

## Тестирование

```bash
make test             # Все тесты
make test-coverage    # С coverage отчётом
make test-quick       # Быстрый прогон
```

### Тестовые файлы

| Файл | Описание | Тестов |
|------|----------|--------|
| tests/test_models.py | CRUD операции с БД | 12 |
| tests/test_services_llm.py | LLM провайдеры, factory | 8 |
| tests/test_services_crm.py | CRM провайдеры, factory | 8 |
| tests/test_services_classifier.py | Классификация запросов | 12 |
| tests/test_services_rag.py | RAG: chunking, vector store | 12 |
| tests/test_bot_handlers.py | Telegram handler helpers | 8 |

**Всего: 60+ тестов**

## Режимы работы

### MOCK_MODE=true (по умолчанию для разработки)
- LLM: MockLLMProvider (возвращает заглушки)
- CRM: MockCRMProvider (создаёт виртуальные сделки)
- RAG: рандомные эмбеддинги
- Никаких внешних API не требуется

### MOCK_MODE=false (продакшен)
- LLM: реальные провайдеры (OpenAI, GigaChat, YandexGPT)
- CRM: Bitrix24 REST / AmoCRM API
- RAG: реальные эмбеддинги (OpenAI / sentence-transformers)

## Переменные окружения

См. [.env.example](./.env.example) — все переменные с описанием.

## Self-check

```bash
make check
```
Запускает: подсчёт строк, поиск моков/TODO (исключая тесты), прогон тестов.

## Docker

```bash
make docker-build
make docker-up
```
