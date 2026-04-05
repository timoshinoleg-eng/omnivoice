"""
Unit Tests for VoiceCraft Bot Agents
====================================
Тесты для агентов бота
"""

import sys
import os
import unittest
import tempfile
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voicecraft_bot.agents import (
    IntentClassifier, UserIntent,
    QuotaManager,
    ContentModeratorAgent,
    ErrorHandler, ErrorType,
    AgentStatus
)
from voicecraft_bot.storage import StateManager, VoiceProfile
from voicecraft_bot.config import config


class TestIntentClassifier(unittest.TestCase):
    """Тесты для классификатора намерений"""
    
    def setUp(self):
        self.classifier = IntentClassifier()
    
    def test_classify_start(self):
        """Тест распознавания /start"""
        result = self.classifier.process("/start", "test_user")
        self.assertEqual(result.data['intent'], UserIntent.START)
    
    def test_classify_help(self):
        """Тест распознавания help"""
        result = self.classifier.process("помощь", "test_user")
        self.assertEqual(result.data['intent'], UserIntent.HELP)
    
    def test_classify_limits(self):
        """Тест распознавания limits"""
        result = self.classifier.process("/limits", "test_user")
        self.assertEqual(result.data['intent'], UserIntent.STATUS)
    
    def test_classify_clone(self):
        """Тест распознавания clone"""
        result = self.classifier.process("клонировать голос", "test_user")
        self.assertEqual(result.data['intent'], UserIntent.CLONE)
    
    def test_classify_with_voice_profile(self):
        """Тест генерации с существующим профилем"""
        result = self.classifier.process(
            "Привет, мир!",
            "test_user",
            has_voice_profile=True
        )
        self.assertEqual(result.data['intent'], UserIntent.GENERATE)


class TestQuotaManager(unittest.TestCase):
    """Тесты для менеджера квот"""
    
    def setUp(self):
        self.quota_manager = QuotaManager()
        self.test_user = f"test_user_{datetime.now().timestamp()}"
    
    def test_check_quota_new_user(self):
        """Тест проверки квоты для нового пользователя"""
        result = self.quota_manager.process(None, self.test_user, action='check')
        self.assertEqual(result.status, AgentStatus.SUCCESS)
        self.assertTrue(result.data['can_generate'])
        self.assertEqual(result.data['used'], 0)
    
    def test_increment_quota(self):
        """Тест увеличения квоты"""
        # Increment
        result = self.quota_manager.process(None, self.test_user, action='increment')
        self.assertEqual(result.status, AgentStatus.SUCCESS)
        
        # Check
        result = self.quota_manager.process(None, self.test_user, action='check')
        self.assertEqual(result.data['used'], 1)
    
    def test_quota_exceeded(self):
        """Тест превышения квоты"""
        # Use all quotas
        for _ in range(config.MAX_GENERATIONS_PER_DAY):
            self.quota_manager.process(None, self.test_user, action='increment')
        
        # Try to use one more
        result = self.quota_manager.process(None, self.test_user, action='check')
        self.assertEqual(result.status, AgentStatus.REJECTED)
        self.assertFalse(result.data['can_generate'])


class TestContentModerator(unittest.TestCase):
    """Тесты для модератора контента"""
    
    def setUp(self):
        self.moderator = ContentModeratorAgent()
    
    def test_safe_text(self):
        """Тест безопасного текста"""
        result = self.moderator.process("Привет, как дела?", "test_user")
        self.assertEqual(result.status, AgentStatus.SUCCESS)
        self.assertTrue(result.data['is_safe'])
    
    def test_blocked_keyword(self):
        """Тест текста с запрещенным словом"""
        result = self.moderator.process("Это текст с насилием", "test_user")
        self.assertEqual(result.status, AgentStatus.REJECTED)
    
    def test_text_too_long(self):
        """Тест слишком длинного текста"""
        long_text = "A" * 1001
        result = self.moderator.process(long_text, "test_user")
        self.assertEqual(result.status, AgentStatus.REJECTED)
    
    def test_length_only_check(self):
        """Тест проверки только длины"""
        result = self.moderator.process(
            "Короткий текст",
            "test_user",
            check_type='length_only'
        )
        self.assertEqual(result.status, AgentStatus.SUCCESS)


class TestErrorHandler(unittest.TestCase):
    """Тесты для обработчика ошибок"""
    
    def setUp(self):
        self.handler = ErrorHandler()
    
    def test_classify_timeout(self):
        """Тест классификации timeout"""
        error_type = self.handler.classify_error("Request timeout")
        self.assertEqual(error_type, ErrorType.TIMEOUT)
    
    def test_classify_rate_limit(self):
        """Тест классификации rate limit"""
        error_type = self.handler.classify_error("HTTP 429 Too many requests")
        self.assertEqual(error_type, ErrorType.RATE_LIMIT)
    
    def test_retry_strategy(self):
        """Тест стратегии повторных попыток"""
        result = self.handler.process(
            "timeout",
            "test_user",
            error_type=ErrorType.TIMEOUT,
            can_retry=True
        )
        self.assertEqual(result.status, AgentStatus.NEED_MORE_INFO)
        self.assertEqual(result.data['next_action'], 'retry')


class TestStateManager(unittest.TestCase):
    """Тесты для менеджера состояний"""
    
    def setUp(self):
        # Use temp directory for tests
        self.temp_dir = tempfile.mkdtemp()
        self.manager = StateManager(self.temp_dir)
        self.test_user = f"test_user_{datetime.now().timestamp()}"
    
    def test_get_user_state_new(self):
        """Тест получения состояния нового пользователя"""
        state = self.manager.get_user_state(self.test_user)
        self.assertEqual(state.user_id, self.test_user)
        self.assertEqual(state.daily_generations_used, 0)
    
    def test_increment_generation(self):
        """Тест увеличения счетчика генераций"""
        self.manager.increment_generation_count(self.test_user)
        state = self.manager.get_user_state(self.test_user)
        self.assertEqual(state.daily_generations_used, 1)
        self.assertEqual(state.total_generations_all_time, 1)
    
    def test_voice_profile(self):
        """Тест установки голосового профиля"""
        profile = VoiceProfile(
            ref_audio_url="https://example.com/audio.wav",
            ref_text="Привет",
            created_at=datetime.now().isoformat()
        )
        
        self.manager.set_voice_profile(self.test_user, profile)
        state = self.manager.get_user_state(self.test_user)
        
        self.assertIsNotNone(state.voice_profile)
        self.assertEqual(state.voice_profile.ref_audio_url, "https://example.com/audio.wav")
    
    def test_check_quota(self):
        """Тест проверки квоты"""
        can_generate, remaining, used = self.manager.check_quota(self.test_user, max_daily=3)
        self.assertTrue(can_generate)
        self.assertEqual(remaining, 3)
        self.assertEqual(used, 0)


class TestConfig(unittest.TestCase):
    """Тесты для конфигурации"""
    
    def test_config_values(self):
        """Тест значений конфигурации"""
        self.assertEqual(config.MAX_GENERATIONS_PER_DAY, 3)
        self.assertEqual(config.MAX_AUDIO_DURATION_SECONDS, 59)
        self.assertEqual(config.MAX_CHARACTERS_PER_REQUEST, 1000)
    
    def test_get_message(self):
        """Тест получения сообщений"""
        from voicecraft_bot.config import get_message
        msg = get_message('welcome')
        self.assertIn('VoiceCraft', msg)


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestIntentClassifier))
    suite.addTests(loader.loadTestsFromTestCase(TestQuotaManager))
    suite.addTests(loader.loadTestsFromTestCase(TestContentModerator))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestStateManager))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
