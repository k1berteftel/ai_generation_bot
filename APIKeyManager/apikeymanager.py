import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union

import aiogram
import aiofiles

import config


class APIKeyManager:
    """
    Асинхронный менеджер API-ключей с ротацией при исчерпании лимитов.
    """

    def __init__(
        self,
        bot: aiogram.Bot,
        file_path: Union[str, Path] = "api_replicate_keys.json"
    ):
        self.bot = bot
        self.file_path = Path(file_path)
        self._keys: List[Dict[str, str]] = []
        self._lock = asyncio.Lock()
        self._current_index: int = 0

    async def init(self) -> None:
        """
        Загрузить ключи из файла и подготовить менеджер.
        """
        await self._load_keys()

    async def _load_keys(self) -> None:
        """
        Асинхронно считать JSON-файл с ключами.
        """
        if not self.file_path.exists():
            await self._save_keys()
            return

        async with aiofiles.open(self.file_path, 'r') as f:
            data = await f.read()
        obj = json.loads(data)
        self._keys = obj.get('keys', [])
        logging.info("Loaded %d API keys", len(self._keys))

    async def _save_keys(self) -> None:
        """
        Асинхронно сохранить текущее состояние ключей в файл.
        """
        payload = json.dumps({'keys': self._keys}, ensure_ascii=False)
        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(payload)
        logging.debug("Saved %d API keys", len(self._keys))

    async def get_key(self) -> Optional[str]:
        """
        Получить текущий активный ключ.
        Если список пуст, возвращает None.
        """
        async with self._lock:
            if not self._keys:
                logging.error("No API keys available")
                return None
            # Циклическая ротация
            key = self._keys[self._current_index]['key']
            return key

    async def report_key_exhausted(self, exhausted_key: str) -> None:
        """
        Пометить ключ исчерпанным и уведомить админов, затем перейти к следующему.
        """
        async with self._lock:
            if not self._keys:
                return
            current = self._keys[self._current_index]
            if current['key'] != exhausted_key:
                return

            # Удаляем или перемещаем исчерпанный ключ
            removed = self._keys.pop(self._current_index)
            logging.warning("API key exhausted and removed: %s", removed)

            # Уведомляем администраторов
            for user_id in config.list_admins:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=f"[!] Ключ исчерпан и удалён: {removed['owner']}"
                    )
                except Exception as e:
                    logging.error(
                        "Failed to notify admin %s: %s", user_id, e
                    )

            # Корректируем индекс на случай конца списка
            if self._current_index >= len(self._keys):
                self._current_index = 0

            await self._save_keys()

    async def add_key(self, key: str, owner: str) -> None:
        """
        Добавить новый ключ и сразу сохранить его.
        """
        async with self._lock:
            self._keys.append({'key': key, 'owner': owner})
            logging.info("Added new API key for owner: %s", owner)
            await self._save_keys()

    async def delete_key(self, key_to_delete: str) -> bool:
        """
        Удалить ключ по значению. Возвращает True, если удалено.
        """
        async with self._lock:
            initial = len(self._keys)
            self._keys = [k for k in self._keys if k['key'] != key_to_delete]
            if len(self._keys) < initial:
                logging.info("Deleted API key: %s", key_to_delete)
                # Сброс индекса, если вышли за границы
                if self._current_index >= len(self._keys):
                    self._current_index = 0
                await self._save_keys()
                return True
            logging.warning("API key not found: %s", key_to_delete)
            return False

    async def list_keys(self) -> List[Dict[str, str]]:
        """
        Получить копию списка ключей с владельцами.
        """
        async with self._lock:
            return [k.copy() for k in self._keys]
