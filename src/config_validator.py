import os
import json
from typing import Tuple
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates configuration at startup"""

    @staticmethod
    def validate_ai_hub_key(api_key_path: str, base_url: str) -> Tuple[bool, str]:
        """Validate AI Hub API key format and connectivity"""
        try:
            with open(api_key_path, 'r') as f:
                api_key = f.read().strip()

            if not api_key or len(api_key) < 20:
                return False, "API key too short or empty"

            # Test connectivity with minimal request
            client = OpenAI(api_key=api_key, base_url=base_url)
            try:
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1,
                    timeout=10
                )
                return True, "Valid"
            except Exception as e:
                return False, f"Connection failed: {str(e)}"
        except FileNotFoundError:
            return False, f"API key file not found: {api_key_path}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def validate_telegram_token(token_path: str) -> Tuple[bool, str]:
        """Validate Telegram bot token"""
        try:
            with open(token_path, 'r') as f:
                token = f.read().strip()

            if ':' not in token:
                return False, "Invalid token format"

            parts = token.split(':')
            if len(parts) != 2:
                return False, "Invalid token structure"

            token_id, token_hash = parts
            if not token_id.isdigit() or len(token_hash) < 30:
                return False, "Token components invalid"

            return True, "Valid"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def validate_kraken_api(api_path: str) -> Tuple[bool, str]:
        """Validate Kraken API credentials"""
        try:
            with open(api_path, 'r') as f:
                api_data = json.load(f)

            if 'key' not in api_data or 'secret' not in api_data:
                return False, "Missing key or secret in API data"

            if not api_data['key'] or not api_data['secret']:
                return False, "API key or secret is empty"

            return True, "Valid"
        except FileNotFoundError:
            return False, f"API file not found: {api_path}"
        except json.JSONDecodeError:
            return False, f"Invalid JSON in API file: {api_path}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def validate_all_configurations() -> Tuple[bool, str]:
        """Validate all configurations at startup"""
        from config import (
            AI_HUB_KEY_PATH, TELEGRAM_TOKEN_PATH, KRAKEN_API_PATH,
            AI_BASE_URL
        )

        # Validate AI Hub key
        valid, message = ConfigValidator.validate_ai_hub_key(AI_HUB_KEY_PATH, AI_BASE_URL)
        if not valid:
            return False, f"AI Hub validation failed: {message}"

        # Validate Telegram token
        valid, message = ConfigValidator.validate_telegram_token(TELEGRAM_TOKEN_PATH)
        if not valid:
            return False, f"Telegram validation failed: {message}"

        # Validate Kraken API
        valid, message = ConfigValidator.validate_kraken_api(KRAKEN_API_PATH)
        if not valid:
            return False, f"Kraken API validation failed: {message}"

        return True, "All configurations valid"

    @staticmethod
    def print_validation_report():
        """Print detailed validation report"""
        from config import (
            AI_HUB_KEY_PATH, TELEGRAM_TOKEN_PATH, KRAKEN_API_PATH,
            AI_BASE_URL
        )

        print("🔍 SlopCoin Configuration Validation Report")
        print("=" * 50)

        # AI Hub validation
        print("\n🤖 AI Hub Configuration:")
        valid, message = ConfigValidator.validate_ai_hub_key(AI_HUB_KEY_PATH, AI_BASE_URL)
        print(f"  ✅ Valid: {valid}")
        print(f"  📋 Message: {message}")

        # Telegram validation
        print("\n💬 Telegram Configuration:")
        valid, message = ConfigValidator.validate_telegram_token(TELEGRAM_TOKEN_PATH)
        print(f"  ✅ Valid: {valid}")
        print(f"  📋 Message: {message}")

        # Kraken API validation
        print("\n🚀 Kraken API Configuration:")
        valid, message = ConfigValidator.validate_kraken_api(KRAKEN_API_PATH)
        print(f"  ✅ Valid: {valid}")
        print(f"  📋 Message: {message}")

        print("\n" + "=" * 50)
        print("🎉 Validation completed!")
