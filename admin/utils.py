# determine file path based on DEBUG setting
import json

from bot.config import DEBUG

API_KEYS_FILE = 'api_keys.json' if DEBUG else '/data/api_keys.json'


def load_keys() -> dict:
    """Load API keys from the JSON file."""
    with open(API_KEYS_FILE, 'r') as f:
        return json.load(f)


def save_keys(data: dict) -> None:
    """Save API keys to the JSON file with indentation."""
    with open(API_KEYS_FILE, 'w') as f:
        json.dump(data, f, indent=2)