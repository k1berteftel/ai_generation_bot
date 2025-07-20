from typing import Any

import asyncio
import logging
import aiohttp
import config

async def generate_on_nexus(params: dict[str, Any]) -> list[str]:
    """
    Универсальная функция для запуска задач на NexusAPI и получения результата.
    Принимает готовый словарь `params`.
    Возвращает список URL-ов результата (видео или картинки).
    """
    if not config.NEXUS_API_TOKEN:
        raise ValueError("Отсутствует NEXUS_API_TOKEN в конфигурации.")

    gen_url = "https://nexusapi.dev/generate"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {config.NEXUS_API_TOKEN}"
    }
    payload = {"params": params}

    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. Запускаем задачу
        try:
            model_name = params.get('model_name', 'unknown_model')
            logging.info(f"Запускаем задачу для модели {model_name} с параметрами: {params}")
            async with session.post(gen_url, json=payload, ssl=False) as resp:
                resp.raise_for_status()
                task_data = await resp.json()
                task_id = task_data.get("task_id")
                if not task_id:
                    raise RuntimeError(f"API не вернул task_id. Ответ: {task_data}")
        except aiohttp.ClientError as e:
            logging.error(f"Сетевая ошибка при запуске задачи: {e}")
            raise RuntimeError(f"Ошибка сети при обращении к API: {e}")

        # 2. Ожидаем результат
        task_url = f"https://nexusapi.dev/tasks/{task_id}"
        logging.info(f"Ожидаем результат для задачи {task_id}")
        for _ in range(60):
            await asyncio.sleep(20)
            try:
                async with session.get(task_url, ssl=False) as resp:
                    resp.raise_for_status()
                    status_data = await resp.json()

                status = status_data.get("status")
                if status == "completed":
                    logging.info(f"Задача {task_id} успешно выполнена.")
                    result = status_data.get("result", {})
                    # Возвращаем любой из возможных ключей с URL'ами
                    return result.get("image_urls") or result.get("video_urls") or [result.get("video_url")]
                elif status == "failed":
                    error_msg = status_data.get("error", "Неизвестная ошибка")
                    raise RuntimeError(f"Генерация провалилась: {error_msg}")

            except aiohttp.ClientError as e:
                logging.error(f"Сетевая ошибка при проверке статуса задачи {task_id}: {e}")

        raise RuntimeError("Тайм-аут ожидания генерации.")