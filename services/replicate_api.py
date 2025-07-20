# services/replicate_api.py
import logging
import asyncio
import aiohttp
from APIKeyManager.apikeymanager import APIKeyManager
from data.constants import MODELS, ASPECT_INPUTS, MODEL_IMAGE_FIELD
from utils.helpers import _image_to_data_uri

async def generate_replicate_async(
        key_manager: APIKeyManager, model: str, prompt: str, aspect_ratio: str = "16:9",
        duration: str = '5 сек', pixverse_mode: str | None = None, image_path: str | None = None
) -> str:
    if model not in MODELS:
        raise ValueError(f"Модель '{model}' не найдена в списке поддерживаемых.")

    model_handle = MODELS[model]
    input_dict = {"prompt": prompt}

    if aspect_ratio in ASPECT_INPUTS:
        input_dict["aspect_ratio"] = ASPECT_INPUTS[aspect_ratio]
    try:
        input_dict["duration"] = int(duration.replace(" сек", ""))
    except (ValueError, AttributeError):
        pass
    if model == "Pixverse v4.5" and pixverse_mode:
        input_dict["mode"] = pixverse_mode
    if image_path and model in MODEL_IMAGE_FIELD:
        logging.info(f"Кодирование изображения {image_path} в Data URI...")
        input_dict[MODEL_IMAGE_FIELD[model]] = _image_to_data_uri(image_path)

    payload = {"version": model_handle, "input": input_dict}
    base_url = "https://api.replicate.com/v1/predictions"
    prediction_data = None
    working_headers = None

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:

        for attempt in range(2):
            current_key = await key_manager.get_key()
            headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}

            try:
                logging.info(f"Отправка запроса на генерацию с ключом {current_key[:8]}...")
                async with session.post(base_url, headers=headers, json=payload, timeout=60) as resp:
                    if resp.status == 402:
                        await key_manager.report_key_exhausted(current_key)
                        if attempt == 1:
                            raise RuntimeError("402: Все доступные ключи API исчерпали свою квоту.")
                        continue

                    resp.raise_for_status()
                    prediction_data = await resp.json()
                    working_headers = headers
                    logging.info(f"Задача успешно создана, ID: {prediction_data.get('id')}")
                    break

            except aiohttp.ClientError as e:
                logging.error(f"Сетевая ошибка при вызове Replicate API: {e}")
                raise RuntimeError(f"Сетевая ошибка при обращении к API: {e}")

        if not prediction_data or not working_headers:
            raise RuntimeError("Не удалось создать задачу генерации видео после всех попыток.")

        # Если результат уже есть в первом ответе
        if output := prediction_data.get("output"):
            return output[0] if isinstance(output, list) else output

        # Опрос статуса
        status_url = prediction_data['urls']['get']
        for _ in range(60):
            await asyncio.sleep(60)
            async with session.get(status_url, headers=working_headers, timeout=30) as st_resp:
                st_resp.raise_for_status()
                status_json = await st_resp.json()

            if status_json.get("status") == "succeeded":
                output = status_json.get("output")
                return output[0] if isinstance(output, list) else output

            if status_json.get("status") in ("failed", "canceled"):
                error_detail = status_json.get("error")
                raise RuntimeError(f"Генерация провалилась: {error_detail}")

        raise RuntimeError("Тайм-аут ожидания генерации видео.")