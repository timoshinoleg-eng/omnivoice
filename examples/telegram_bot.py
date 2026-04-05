"""
Telegram Bot Integration Example
================================
Пример интеграции VoiceCraft Bot с Telegram

Установка:
    pip install python-telegram-bot>=20.0

Запуск:
    python telegram_bot.py --token YOUR_BOT_TOKEN
"""

import os
import sys
import argparse
import logging
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from voicecraft_bot import voicecraft_bot, process_message, get_message

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    result = process_message("/start", user_id)
    
    await update.message.reply_text(
        result['response'],
        parse_mode='Markdown'
    )


async def limits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /limits"""
    user_id = str(update.effective_user.id)
    result = process_message("/limits", user_id)
    
    await update.message.reply_text(
        result['response'],
        parse_mode='Markdown'
    )


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /voice (сброс профиля)"""
    user_id = str(update.effective_user.id)
    result = process_message("/voice", user_id)
    
    await update.message.reply_text(result['response'])


async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /demo"""
    user_id = str(update.effective_user.id)
    result = process_message("/demo", user_id)
    
    await update.message.reply_text(result['response'])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = str(update.effective_user.id)
    result = process_message("/help", user_id)
    
    await update.message.reply_text(
        result['response'],
        parse_mode='Markdown'
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    
    result = process_message(text, user_id)
    
    # Send response
    if result['response']:
        await update.message.reply_text(result['response'])
    
    # If there's audio data, send it
    if result.get('data') and result['data'].get('audio_data'):
        audio_data = result['data']['audio_data']
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            # Send audio
            with open(temp_path, 'rb') as audio_file:
                await update.message.reply_voice(audio_file)
        finally:
            # Cleanup
            try:
                os.remove(temp_path)
            except:
                pass


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    user_id = str(update.effective_user.id)
    
    # Show uploading indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='upload_voice'
    )
    
    try:
        # Download voice message
        voice_file = await update.message.voice.get_file()
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, f"{user_id}_voice.ogg")
        
        await voice_file.download_to_drive(audio_path)
        logger.info(f"Downloaded voice from {user_id}: {audio_path}")
        
        # Process
        result = process_message(
            "",
            user_id,
            has_audio=True,
            audio_path=audio_path
        )
        
        # Send response
        await update.message.reply_text(result['response'])
        
        # Cleanup
        try:
            os.remove(audio_path)
            os.rmdir(temp_dir)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await update.message.reply_text(
            "❌ Ошибка обработки голосового сообщения. Попробуйте снова."
        )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик аудио файлов"""
    user_id = str(update.effective_user.id)
    
    # Show uploading indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='upload_document'
    )
    
    try:
        # Get audio file
        if update.message.audio:
            audio_file = await update.message.audio.get_file()
            file_name = update.message.audio.file_name or f"{user_id}_audio.mp3"
        elif update.message.document:
            audio_file = await update.message.document.get_file()
            file_name = update.message.document.file_name
        else:
            await update.message.reply_text("❌ Неподдерживаемый формат файла")
            return
        
        # Download
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, file_name)
        
        await audio_file.download_to_drive(audio_path)
        logger.info(f"Downloaded audio from {user_id}: {audio_path}")
        
        # Process
        result = process_message(
            "",
            user_id,
            has_audio=True,
            audio_path=audio_path
        )
        
        # Send response
        await update.message.reply_text(result['response'])
        
        # Cleanup
        try:
            os.remove(audio_path)
            os.rmdir(temp_dir)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error handling audio: {e}")
        await update.message.reply_text(
            "❌ Ошибка обработки аудио файла. Попробуйте снова."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова позже."
        )


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='VoiceCraft Telegram Bot')
    parser.add_argument(
        '--token',
        required=True,
        help='Telegram Bot Token'
    )
    
    args = parser.parse_args()
    
    # Create application
    application = Application.builder().token(args.token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("limits", limits_command))
    application.add_handler(CommandHandler("voice", voice_command))
    application.add_handler(CommandHandler("demo", demo_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.AUDIO | filters.Document.AUDIO, handle_audio))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Run bot
    logger.info("Starting VoiceCraft Telegram Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
