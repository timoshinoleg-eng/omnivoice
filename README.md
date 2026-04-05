# 🎙️ VoiceCraft Bot

**Бот для клонирования голоса и генерации речи через Hugging Face Spaces**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 Описание

VoiceCraft Bot — это multi-agent система для клонирования голоса и генерации речи с использованием модели OmniVoice через Hugging Face Spaces.

### Основные возможности

- 🎤 **Клонирование голоса** — загрузите 3-10 секунд аудио для создания голосового профиля
- 🔊 **Генерация речи** — озвучивайте любой текст клонированным голосом
- 📊 **Лимиты** — 3 генерации в день на пользователя (сброс в 00:00 UTC)
- ⏱️ **Длительность** — до 59 секунд аудио, до 1000 символов текста
- 🛡️ **Модерация** — автоматическая проверка контента
- 🔄 **Обработка ошибок** — retry-логика для timeout и rate limit

## 🏗️ Архитектура

```
VoiceCraft Bot (Multi-Agent System)
│
├── 🤖 Agents
│   ├── IntentClassifier      # Распознавание намерений
│   ├── QuotaManager          # Управление лимитами 3/3
│   ├── VoiceProfileSetup     # Настройка голосового профиля
│   ├── ContentModerator      # Проверка контента
│   ├── HFGenerator          # Интеграция с HF Space API
│   ├── ErrorHandler         # Обработка ошибок
│   └── VoiceCraftBot        # Главный координатор
│
├── 💾 Storage
│   └── StateManager         # Хранение состояний пользователей
│
├── 🛠️ Utils
│   ├── audio_utils          # Работа с аудио
│   ├── hf_api              # HF Space API клиент
│   └── content_moderator   # Модерация контента
│
└── ⚙️ Config
    └── settings            # Конфигурация и сообщения
```

## 🚀 Быстрый старт

### Установка

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/voicecraft_bot.git
cd voicecraft_bot

# Установка зависимостей
pip install requests

# Опционально: для работы с аудио
pip install ffmpeg-python
```

### Запуск

```bash
# Интерактивный режим
python -m voicecraft_bot.bot --mode interactive

# Демонстрация workflow
python -m voicecraft_bot.bot --mode demo
```

### Пример использования

```python
from voicecraft_bot import voicecraft_bot, process_message

# Обработка текстового сообщения
result = process_message("/start", user_id="user_001")
print(result['response'])

# Проверка лимитов
result = process_message("/limits", user_id="user_001")
print(result['response'])

# Генерация речи (требуется голосовой профиль)
result = process_message("Привет, мир!", user_id="user_001")
print(result['response'])
```

## 📚 Документация

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начало работы, приветственное сообщение |
| `/limits` | Проверка текущих лимитов |
| `/voice` | Сброс голосового профиля |
| `/demo` | Использование демо-голоса |
| `/help` | Справка по использованию |

### Workflow

#### 1. Первый запуск

```
Пользователь: /start
Бот: 🎙️ Добро пожаловать в VoiceCraft!
     ...
```

#### 2. Настройка голосового профиля

```
Пользователь: [отправляет аудио 3-10 сек]
Бот: ⚠️ Подтверждение прав
     Вы подтверждаете, что это ваш голос?

Пользователь: Да
Бот: 📝 Введите расшифровку текста в аудио:

Пользователь: Привет, это мой голос
Бот: ✅ Профиль создан!
```

#### 3. Генерация речи

```
Пользователь: Привет, как дела?
Бот: ⚡ Генерация началась...
     [отправляет аудио]
     ✅ Готово!
     ⏱️ Длительность: 2.5s
     📉 Осталось сегодня: 2/3
```

### Лимиты

| Параметр | Значение |
|----------|----------|
| Генераций в день | 3 |
| Макс. длительность аудио | 59 секунд |
| Макс. длина текста | 1000 символов |
| Длительность образца голоса | 3-10 секунд |
| Сброс лимитов | 00:00 UTC |

### Конфигурация

```python
from voicecraft_bot.config import config

# Настройка HF Space
config.HF_SPACE_URL = "https://k2-fsa-omnivoice.hf.space"

# Настройка лимитов
config.MAX_GENERATIONS_PER_DAY = 3
config.MAX_AUDIO_DURATION_SECONDS = 59
config.MAX_CHARACTERS_PER_REQUEST = 1000

# Настройка таймаутов
config.HF_REQUEST_TIMEOUT = 55
```

## 🔧 Интеграция с Telegram

```python
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from voicecraft_bot import voicecraft_bot, process_message

async def start(update: Update, context):
    result = process_message("/start", str(update.effective_user.id))
    await update.message.reply_text(result['response'])

async def handle_text(update: Update, context):
    result = process_message(
        update.message.text,
        str(update.effective_user.id)
    )
    await update.message.reply_text(result['response'])

async def handle_voice(update: Update, context):
    # Скачать голосовое сообщение
    voice_file = await update.message.voice.get_file()
    audio_path = f"temp/{update.effective_user.id}_voice.ogg"
    await voice_file.download_to_drive(audio_path)
    
    result = process_message(
        "",
        str(update.effective_user.id),
        has_audio=True,
        audio_path=audio_path
    )
    await update.message.reply_text(result['response'])

# Запуск бота
app = Application.builder().token("YOUR_BOT_TOKEN").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))
app.run_polling()
```

## 🛡️ Безопасность

### Модерация контента

Бот автоматически проверяет текст на:
- Запрещенные ключевые слова (насилие, ненависть, NSFW)
- Подозрительные паттерны
- Превышение лимита символов

### Подтверждение прав

Перед клонированием голоса требуется явное подтверждение:
- Пользователь должен подтвердить, что это его голос
- Или что у него есть разрешение на использование записи

### Watermarking

Все сгенерированные аудио содержат пометку:
```
_Сгенерировано ИИ_
```

## 🐛 Обработка ошибок

### Типы ошибок и стратегии

| Ошибка | Стратегия |
|--------|-----------|
| Timeout (>59s) | Retry с увеличенной задержкой |
| Rate Limit (429) | Подождать 2-3 минуты |
| Service Unavailable (503) | Повторить через 5 минут |
| Voice Profile Expired | Запросить новый образец |
| Quota Exceeded | Предложить Pro-тариф |

### Retry логика

```python
from voicecraft_bot.agents import error_handler, ErrorType

# Автоматическая классификация ошибки
error_type = error_handler.classify_error(error_message)

# Получение стратегии
result = error_handler.process(
    error_message,
    user_id,
    error_type=error_type,
    can_retry=True
)
```

## 📊 Мониторинг

### Статистика бота

```python
from voicecraft_bot import voicecraft_bot

stats = voicecraft_bot.get_stats()
print(stats)
# {
#     'active_sessions': 42,
#     'storage_stats': {
#         'total_users': 150,
#         'total_generations': 423,
#         'active_today': 23
#     }
# }
```

### Логирование ошибок

```python
from voicecraft_bot.agents import error_handler

# Получить статистику ошибок
error_stats = error_handler.get_error_stats(user_id)
print(error_stats)
# {
#     'total_errors': 5,
#     'error_types': {'timeout': 3, 'rate_limit': 2}
# }
```

## 🔌 API Reference

### VoiceCraftBot

```python
class VoiceCraftBot:
    def process(user_input, user_id, **kwargs) -> AgentResult
    def get_stats() -> dict
    def stop()
```

### StateManager

```python
class StateManager:
    def get_user_state(user_id: str) -> UserState
    def check_quota(user_id: str, max_daily: int) -> tuple
    def increment_generation_count(user_id: str) -> bool
    def set_voice_profile(user_id: str, profile: VoiceProfile) -> bool
```

### HFSpaceAPI

```python
class HFSpaceAPI:
    def upload_audio(file_path: str) -> tuple
    def generate_speech(text, ref_audio_url, ref_text, **kwargs) -> tuple
    def warmup() -> bool
    def check_health() -> tuple
```

## 🧪 Тестирование

```bash
# Запуск тестов
python -m pytest tests/

# Покрытие кода
python -m pytest --cov=voicecraft_bot tests/
```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Распространяется под лицензией MIT. См. [LICENSE](LICENSE) для подробностей.

## 🙏 Благодарности

- [OmniVoice](https://github.com/k2-fsa/omnivoice) — модель для клонирования голоса
- [Hugging Face](https://huggingface.co/) — хостинг моделей

## 📞 Поддержка

- GitHub Issues: [github.com/yourusername/voicecraft_bot/issues](https://github.com/yourusername/voicecraft_bot/issues)
- Telegram: [@voicecraft_support](https://t.me/voicecraft_support)

---

<p align="center">
  Made with ❤️ by VoiceCraft Team
</p>
