"""
ML Content Moderation
=====================
Модерация контента через OpenAI Moderation API
Заменяет keyword-based на нейросетевую классификацию
"""

import os
import requests
from typing import Tuple, List, Dict, Any


class MLContentModerator:
    """
    ML-based модератор контента через OpenAI API
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY') or os.getenv('KIMI_API_KEY')
        self.endpoint = "https://api.openai.com/v1/moderations"
        
        # Fallback to Kimi if no OpenAI key
        if not self.api_key and os.getenv('KIMI_API_KEY'):
            self.endpoint = "https://api.moonshot.cn/v1/moderations"
            self.api_key = os.getenv('KIMI_API_KEY')
    
    def check_text(self, text: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Проверить текст через ML модерацию
        
        Args:
            text: Текст для проверки
            
        Returns:
            (is_safe: bool, violations: list, details: dict)
        """
        if not self.api_key:
            # Fallback to keyword-based if no API key
            return self._keyword_fallback(text)
        
        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={"input": text},
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"[ML Moderation] API error: {response.status_code}")
                return self._keyword_fallback(text)
            
            data = response.json()
            
            # Check results
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]
                
                # Check if flagged
                if result.get('flagged', False):
                    # Get categories
                    categories = result.get('categories', {})
                    scores = result.get('category_scores', {})
                    
                    violations = []
                    details = {'scores': scores, 'categories': categories}
                    
                    # Map OpenAI categories to our violations
                    category_map = {
                        'sexual': 'NSFW/сексуальный контент',
                        'hate': 'разжигание ненависти',
                        'harassment': 'домогательства',
                        'self-harm': 'самоповреждение',
                        'sexual/minors': 'контент с участием несовершеннолетних',
                        'hate/threatening': 'угрозы',
                        'violence': 'насилие',
                        'violence/graphic': 'графическое насилие'
                    }
                    
                    for cat, flagged in categories.items():
                        if flagged:
                            violations.append(category_map.get(cat, cat))
                    
                    return False, violations, details
                
                # Check scores even if not flagged (high confidence)
                scores = result.get('category_scores', {})
                high_risk = []
                
                for cat, score in scores.items():
                    if score > 0.8:  # High confidence threshold
                        high_risk.append(cat)
                
                if high_risk:
                    violations = [f"{cat} (score: {scores[cat]:.2f})" for cat in high_risk]
                    return False, violations, {'scores': scores}
                
                return True, [], {'scores': scores}
            
            return True, [], {}
            
        except Exception as e:
            print(f"[ML Moderation] Error: {e}")
            return self._keyword_fallback(text)
    
    def _keyword_fallback(self, text: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Fallback на keyword-based модерацию"""
        from ..utils.content_moderator import content_moderator
        is_safe, violations = content_moderator.check_text(text)
        return is_safe, violations, {'fallback': True}


# Global instance
ml_moderator = MLContentModerator()
