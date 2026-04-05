#!/bin/bash
# Запуск OmniVoice Telegram Bot с токенами из SOPS

set -e

# Загрузить токены из SOPS
export TELEGRAM_BOT_TOKEN=$(age -d -i ~/.config/openclaw/secrets/age.key ~/.config/openclaw/secrets/tg_token.enc | grep -o '8516401012:[A-Za-z0-9_-]*')
export HF_TOKEN=$(age -d -i ~/.config/openclaw/secrets/age.key ~/.config/openclaw/secrets/hf_token.enc | grep -o 'hf_[A-Za-z0-9]*')

# S3 Configuration (Yandex Object Storage)
export S3_BUCKET="${S3_BUCKET:-voicecraft-profiles}"
export S3_ENDPOINT="${S3_ENDPOINT:-https://storage.yandexcloud.net}"
export S3_REGION="${S3_REGION:-ru-central1}"

# Try to load S3 credentials from SOPS if available
if [ -f ~/.config/openclaw/secrets/yandex_s3.enc ]; then
    eval $(age -d -i ~/.config/openclaw/secrets/age.key ~/.config/openclaw/secrets/yandex_s3.enc 2>/dev/null | grep -E '^(S3_ACCESS_KEY|S3_SECRET_KEY)=')
fi

echo "✅ Токены загружены из SOPS"
echo "🤖 Бот: @omni_voice_bot"
echo "💾 S3 Bucket: $S3_BUCKET"
echo "🚀 Запуск..."

# Запуск бота
cd "$(dirname "$0")"
python3 examples/telegram_bot.py --token "$TELEGRAM_BOT_TOKEN"
