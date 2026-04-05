#!/bin/bash
# Запуск OmniVoice Telegram Bot с токенами из SOPS

set -e

# Загрузить токены из SOPS
export TELEGRAM_BOT_TOKEN=$(age -d -i ~/.config/openclaw/secrets/age.key ~/.config/openclaw/secrets/tg_token.enc | grep -o '8516401012:[A-Za-z0-9_-]*')
export HF_TOKEN=$(age -d -i ~/.config/openclaw/secrets/age.key ~/.config/openclaw/secrets/hf_token.enc | grep -o 'hf_[A-Za-z0-9]*')

echo "✅ Токены загружены из SOPS"
echo "🤖 Бот: @omni_voice_bot"
echo "🚀 Запуск..."

# Запуск бота
cd "$(dirname "$0")"
python3 examples/telegram_bot.py --token "$TELEGRAM_BOT_TOKEN"
