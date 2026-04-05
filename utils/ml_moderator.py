"""
ML Content Moderation (OpenAI)
===============================
Замена keyword-based модерации на ML-модель OpenAI
"""

import os
import requests
from typing import Tuple, List


class MLModerator:
    """
    ML модератор контента через OpenAI Moderation API
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY') or os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://api.openai.com/v1"
        
        # If using OpenRouter
        if os.getenv('OPENROUTER_API_KEY'):
            self.base_url = "https://openrouter.ai/api/v1"
    
    def moderate_text(self, text: str) -> Tuple[bool, List[str]]:
        """
        Проверить текст через ML модерацию
        
        Args:
            text: Текст для проверки
            
        Returns:
            (is_safe: bool, categories: list of flagged categories)
        """
        if not self.api_key:
            # Fallback: skip ML moderation
            return True, []
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            if 'openrouter' in self.base_url:
                # OpenRouter doesn't have moderation endpoint, use completion
                return self._moderate_via_openrouter(text)
            
            # OpenAI Moderation API
            response = requests.post(
                f"{self.base_url}/moderations",
                headers=headers,
                json={'input': text},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'results' in result and len(result['results']) > 0:
                    moderation = result['results'][0]
                    flagged = moderation.get('flagged', False)
                    categories = moderation.get('categories', {})
                    
                    # Get list of flagged categories
                    flagged_categories = [
                        cat for cat, is_flagged in categories.items() 
                        if is_flagged
                    ]
                    
                    # Block if flagged for severe categories
                    severe_categories = [
                        'sexual', 'hate', 'violence', 'self-harm',
                        'sexual/minors', 'hate/threatening', 'violence/graphic'
                    ]
                    
                    is_safe = not any(cat in flagged_categories for cat in severe_categories)
                    
                    return is_safe, flagged_categories
                
                return True, []
            else:
                print(f"[MLModerator] API error: {response.status_code}")
                # Fail open - allow if API fails
                return True, []
                
        except Exception as e:
            print(f"[MLModerator] Error: {e}")
            # Fail open
            return True, []
    
    def _moderate_via_openrouter(self, text: str) -> Tuple[bool, List[str]]:
        """
        Fallback модерация через OpenRouter completion API
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://voicecraft.bot',
                'X-Title': 'VoiceCraft Bot'
            }
            
            prompt = f"""Analyze this text for inappropriate content. Respond with ONLY a JSON object:
{{
  "flagged": true/false,
  "categories": ["category1", "category2"]
}}

Categories to check: hate, sexual, violence, self-harm, harassment

Text to analyze: \"{text[:500]}\"

Response:"""
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    'model': 'openai/gpt-3.5-turbo',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.1,
                    'max_tokens': 100
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse JSON response
                import json
                try:
                    moderation = json.loads(content)
                    flagged = moderation.get('flagged', False)
                    categories = moderation.get('categories', [])
                    return not flagged, categories
                except:
                    return True, []
            
            return True, []
            
        except Exception as e:
            print(f"[MLModerator] OpenRouter error: {e}")
            return True, []


# Global instance
_ml_moderator = None

def get_ml_moderator() -> MLModerator:
    """Получить глобальный экземпляр MLModerator"""
    global _ml_moderator
    if _ml_moderator is None:
        _ml_moderator = MLModerator()
    return _ml_moderator
