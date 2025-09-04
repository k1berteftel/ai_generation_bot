# utils/helpers.py
import base64
import mimetypes
import logging
import os

import aiohttp
import requests
from aiogram import Bot, types

import config
from data.constants import DURATION_PRICES


def calculate_generation_cost(model: str, duration: str, pixverse_mode: str = None,
                              resolution: str = None) -> int | None:
    if model == 'Sora - Генерация изображений':
        from data.constants import IMAGE_GPT_COST
        return IMAGE_GPT_COST

    if model == "Pixverse v4.5":
        res = resolution if resolution else "720p"
        mode = pixverse_mode if pixverse_mode else "smooth"
        key = f"{res}_{mode}_{duration}"
        return DURATION_PRICES[model].get(key)

    print(model)
    return DURATION_PRICES.get(model, {}).get(duration)

def get_crystal_price_str(cost: int | None) -> str:
    if cost is None:
        return "Недоступно"
    return f"{cost} 💎"

def download_video(url: str, filename: str) -> str:
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return filename

def _image_to_data_uri(file_path: str) -> str:
    """Кодирует изображение из файла в формат Data URI (base64)."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith('image'):
        raise ValueError("Не удалось определить MIME-тип изображения или файл не является изображением.")
    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_string}"

async def check_user_op_single(bot: Bot, target_chat_id: str, user_id: int) -> bool:
    async with aiohttp.ClientSession() as session:
        if ':' in target_chat_id:

            api_url = f"https://api.telegram.org/bot{target_chat_id}/getChatMember"
            payload = {
                "chat_id": user_id,
                "user_id": user_id
            }
            async with session.post(api_url, data=payload, ssl=False) as resp:
                data = await resp.json()

            status = data["ok"]
            if not status:
                return False

        else:

            member = await bot.get_chat_member(target_chat_id, user_id)
            if member.status == 'left':
                return False

    return True

async def check_user_op(db, bot: Bot, user_id: int):
    all_op = await db.subscription.get_all_channels()
    if not all_op:
        return None
    channels = []
    async with aiohttp.ClientSession() as session:
        for pare in all_op:
            if ':' in pare.chat_id:
                api_url = f"https://api.telegram.org/bot{pare.chat_id}/getChatMember"
                payload = {
                    "chat_id": user_id,
                    "user_id": user_id
                }
                async with session.post(api_url, data=payload, ssl=False) as resp:
                    data = await resp.json()

                status = data["ok"]
                if not status:
                    channels.append([pare.id, pare.link_channel])

            else:

                member = await bot.get_chat_member(pare.chat_id, user_id)
                if member.status == 'left':
                    channels.append([pare.id, pare.link_channel])
    if channels:
        return channels

    return None


async def upload_image_to_imgbb(image_path: str) -> str | None:
    """Загружает локальный файл на ImgBB и возвращает URL."""
    if not config.IMGBB_API_KEY:
        logging.error("Ключ API для ImgBB не найден в конфигурации.")
        return None

    with open(image_path, 'rb') as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    data = {
        'key': config.IMGBB_API_KEY,
        'image': encoded_image,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.imgbb.com/1/upload", data=data, ssl=False) as response:
            if response.status == 200:
                response_data = await response.json()
                image_url = response_data['data']['url']
                logging.info(f"Изображение успешно загружено на ImgBB: {image_url}")
                return image_url
            else:
                try:
                    response_data = await response.json()
                    logging.error(f"Ошибка загрузки на ImgBB: {response_data}")
                except aiohttp.ContentTypeError:
                    logging.error(f"Ошибка загрузки на ImgBB: {response.status} {await response.text()}")
                return None


async def download_and_upload_images(
        bot: Bot,
        album: list[types.Message]
) -> list[str]:
    """
    Скачивает фото из Telegram, загружает их на ImgBB и возвращает список URL.
    Работает только со списком сообщений (album).
    """
    urls = []

    # Убираем лишнюю логику, работаем только с album
    messages_to_process = album

    if len(messages_to_process) > 10:
        raise ValueError("Можно отправить не более 10 фотографий в одном запросе.")

    for msg in messages_to_process:
        # Пропускаем сообщения без фото (например, если в альбоме был текст)
        if not msg.photo:
            continue

        photo_obj = msg.photo[-1]
        temp_photo_path = f"temp_{photo_obj.file_unique_id}.jpg"

        try:
            await bot.download(file=photo_obj.file_id, destination=temp_photo_path)

            image_url = await upload_image_to_imgbb(temp_photo_path)
            if image_url:
                urls.append(image_url)
            else:
                logging.warning(f"Не удалось загрузить на ImgBB файл: {temp_photo_path}")

        finally:
            if os.path.exists(temp_photo_path):
                os.remove(temp_photo_path)

    # Если в итоге ни одной картинки не загрузилось, вернется пустой список
    return urls