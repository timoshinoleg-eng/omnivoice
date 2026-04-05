"""
VoiceCraft Bot - Entry Point
============================
Точка входа для запуска бота
"""

import os
import sys
import argparse
import json
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voicecraft_bot import voicecraft_bot, get_message, config
from voicecraft_bot.agents import UserIntent, AgentStatus


def process_message(text: str, user_id: str, has_audio: bool = False, audio_path: Optional[str] = None) -> dict:
    """
    Обработать сообщение от пользователя
    
    Args:
        text: Текст сообщения
        user_id: ID пользователя
        has_audio: Есть ли аудио
        audio_path: Путь к аудио файлу
    
    Returns:
        dict с ответом для пользователя
    """
    user_input = {
        'text': text,
        'has_audio': has_audio
    }
    
    result = voicecraft_bot.process(
        user_input,
        user_id,
        has_audio=has_audio,
        audio_path=audio_path
    )
    
    return {
        'status': result.status.value,
        'message': result.message,
        'response': result.response_to_user,
        'data': result.data,
        'next_action': result.next_action
    }


def interactive_mode():
    """Интерактивный режим для тестирования"""
    print("=" * 60)
    print("🎙️ VoiceCraft Bot - Interactive Mode")
    print("=" * 60)
    print("\nКоманды:")
    print("  /start - Начать")
    print("  /limits - Проверить лимиты")
    print("  /voice - Сбросить голос")
    print("  /demo - Демо режим")
    print("  /help - Помощь")
    print("  /quit - Выход")
    print("=" * 60)
    
    user_id = "test_user_001"
    
    while True:
        try:
            print()
            user_input = input("👤 Вы: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['/quit', '/exit', 'quit', 'exit']:
                print("\n👋 До свидания!")
                break
            
            result = process_message(user_input, user_id)
            
            print(f"\n🤖 Бот: {result['response']}")
            
            if result['data']:
                print(f"   [Debug] {json.dumps(result['data'], ensure_ascii=False, indent=2)}")
        
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")


def demo_workflow():
    """Демонстрация полного workflow"""
    print("=" * 60)
    print("🎙️ VoiceCraft Bot - Demo Workflow")
    print("=" * 60)
    
    user_id = "demo_user_001"
    
    # Step 1: Start
    print("\n📌 Step 1: /start")
    result = process_message("/start", user_id)
    print(f"Bot: {result['response'][:200]}...")
    
    # Step 2: Check limits
    print("\n📌 Step 2: /limits")
    result = process_message("/limits", user_id)
    print(f"Bot: {result['response']}")
    
    # Step 3: Try to generate without voice profile
    print("\n📌 Step 3: Generate without voice profile")
    result = process_message("Привет, это тестовое сообщение", user_id)
    print(f"Bot: {result['response']}")
    
    # Step 4: Start voice setup
    print("\n📌 Step 4: Start voice setup")
    result = process_message("clone my voice", user_id)
    print(f"Bot: {result['response'][:100]}...")
    
    # Step 5: Help
    print("\n📌 Step 5: /help")
    result = process_message("/help", user_id)
    print(f"Bot: {result['response'][:200]}...")
    
    print("\n" + "=" * 60)
    print("✅ Demo completed!")
    print("=" * 60)


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='VoiceCraft Bot')
    parser.add_argument(
        '--mode',
        choices=['interactive', 'demo', 'server'],
        default='interactive',
        help='Режим работы'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'interactive':
        interactive_mode()
    elif args.mode == 'demo':
        demo_workflow()
    elif args.mode == 'server':
        print("Server mode not implemented yet. Use interactive mode for testing.")
    
    # Cleanup
    voicecraft_bot.stop()


if __name__ == '__main__':
    main()
