# utils/helpers.py
import asyncio
import base64
import mimetypes
import logging
import os
import string
import random
import tempfile
from pathlib import Path

import aiofiles
import aiohttp
import requests


from aiogram import Bot, types
from aiogram.types import PhotoSize
from aiogram.fsm.context import FSMContext

import config
from data.constants import DURATION_PRICES


def _get_random_id() -> str:
    string.ascii_letter = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    simvols = ''
    for i in range(0, 8):
        simvols += str(random.choice(string.ascii_letters))
    return simvols


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
    url = 'https://files.storagecdn.online/upload'

    data = aiohttp.FormData()
    data.add_field('file',
                   open(image_path, 'rb'),
                   filename=Path(image_path).name,
                   content_type='application/octet-stream')

    headers = {
        'Authorization': f'Bearer {config.unifically_api_token}'
    }

    async with aiohttp.ClientSession() as session:
        async with session.put(url, data=data, headers=headers, ssl=False) as response:
            if response.status not in [200, 201]:
                print(await response.text())
                return None
            data = await response.json()
            if data['success'] != True:
                print(data['message'])
                return None
    return data['file_url']


async def save_image(data: dict) -> str:
    """
    Сохраняет base64 изображение в файл
    :param data: словарь с данными изображения
    """
    try:
        filename = _get_random_id()
        base64_data = data.get("data", "")
        mime_type = data.get("mime_type", "image/png")

        if not base64_data:
            raise ValueError("Нет данных изображения")

        image_bytes = base64.b64decode(base64_data)

        extension = mime_type.split('/')[-1]
        if extension == "jpeg":
            extension = "jpg"

        if not filename.endswith(f".{extension}"):
            filename = f"download/{Path(filename).stem}.{extension}"

        async with aiofiles.open(filename, 'wb') as file:
            await file.write(image_bytes)

        return filename

    except Exception as e:
        print(f"❌ Ошибка при сохранении изображения: {e}")
        raise e


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


async def save_bot_files(msgs: list[types.Message], bot: Bot):
    if not os.path.exists('download'):
        os.mkdir('download')
    files = []
    for msg in msgs:
        photo = msg.photo[-1]
        temp_photo_path = f"download/temp_{photo.file_unique_id}.jpg"
        try:
            await bot.download(file=photo.file_id, destination=temp_photo_path)

            files.append(temp_photo_path)
        except Exception as err:
            logging.warning(f"Не удалось загрузить на ImgBB файл: {temp_photo_path}\n{err}")
    return files


async def clear_context(state: FSMContext, period: int):
    await asyncio.sleep(period)
    await state.update_data(messages=None)


async def photo_to_base64(photo: PhotoSize, bot: Bot) -> tuple[str, str] | None:
    """
    Конвертирует PhotoSize из Telegram в base64 и автоматически удаляет файл.

    Args:
        photo: Объект PhotoSize от aiogram
        bot: Экземпляр бота для скачивания файла

    Returns:
        Tuple[str, str] - (base64_data, media_type) или None в случае ошибки
        media_type всегда 'image/jpeg' для фото Telegram
    """
    # Создаем временный файл с уникальным именем
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
        temp_path = tmp_file.name

    try:
        # Скачиваем файл через бота
        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, destination=temp_path)

        # Читаем и кодируем в base64
        async with aiofiles.open(temp_path, 'rb') as f:
            file_content = await f.read()
            base64_data = base64.b64encode(file_content).decode('utf-8')

        # Для фото Telegram всегда JPEG
        return (base64_data, 'image/jpeg')

    except Exception as e:
        print(f"Ошибка при обработке фото: {e}")
        return None

    finally:
        # Гарантированно удаляем временный файл
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            ...