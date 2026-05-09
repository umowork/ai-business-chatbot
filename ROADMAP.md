# ROADMAP — 05 ai-business-chatbot

## Шаг 1 — Скелет + диалог

- [ ] aiogram 3 + PostgreSQL + Redis структура
- [ ] YAML-конфиг бизнеса (`config.yml`)
- [ ] Handler любого сообщения → LLM ответ по конфигу
- [ ] Сохранение диалогов в БД

## Шаг 2 — LLM Gateway (РФ-приоритет)

- [ ] GigaChat integration (Sber)
- [ ] YandexGPT integration (Yandex Cloud)
- [ ] OpenAI fallback
- [ ] Выбор провайдера в YAML
- [ ] Прозрачное логирование cost / latency

## Шаг 3 — Lead qualification

- [ ] Pydantic схема Lead (поля по конфигу клиента)
- [ ] Extraction через `instructor`
- [ ] Сценарий: «собрать имя, телефон, услугу, бюджет»
- [ ] Lead Score (горячий / тёплый / холодный)

## Шаг 4 — Битрикс24 / AmoCRM

- [ ] Bitrix24 REST: создание контакта + сделки
- [ ] AmoCRM API: создание lead'а
- [ ] Webhook валидация
- [ ] Retry с backoff при failure CRM

## Шаг 5 — Push менеджеру + календарь

- [ ] При горячем лиде → форвард в TG-чат менеджеров
- [ ] Резюме лида (auto-summarize диалога)
- [ ] Google Calendar: запись на услугу
- [ ] Inline-keyboard для подтверждения времени

## Шаг 6 — Веб-виджет

- [ ] FastAPI endpoint для веб-чата
- [ ] Vanilla JS виджет (можно переиспользовать из проекта 06)
- [ ] Тот же backend, разные frontend

## Шаг 7 — Polish + деплой

- [ ] Multi-bot deployment (один процесс → несколько клиентов через конфиги)
- [ ] Админ-команды: stats, recent leads, broadcast
- [ ] Тесты: dialog flow, CRM integration (с моками)
- [ ] Docker compose
- [ ] Deploy на Yandex Cloud
- [ ] README с реальными метриками
- [ ] Loom-демка
- [ ] Tag `v1.0.0`
