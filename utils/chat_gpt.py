import asyncio
import re
import logging
import io
from math import isclose
from pathlib import Path
from typing import Literal, List, Tuple, Optional

from PIL import Image

import httpx
import aiohttp

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from aiogram import Bot
from aiogram.types import Message, PhotoSize

from utils.helpers import upload_image_to_imgbb, save_image, download_and_upload_images, save_bot_files, photo_to_base64

import config


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


client = AsyncAnthropic(
    api_key=config.apimart_api_key,
    base_url="https://api.apimart.ai",
)

http_client = httpx.AsyncClient(proxy='http://6L4YePzU:Mrnd5Tsy@212.193.143.10:63196')
gpt_client = AsyncOpenAI(
    api_key=config.openai_api_token,
    http_client=http_client
)


FORMATS_API = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "4:5", "5:4", "9:16", "16:9", "21:9"
]

# Массив 2 (расширенный - описательные форматы)
FORMATS_DESCRIPTIVE = [
    "1:1", "2:3", "3:2", "4:3", "3:4",
    "16:9", "9:16", "5:4", "4:5", "21:9",
    "1:4", "4:1", "1:8", "8:1"
]

# Словарь с описанием форматов для справки (опционально)
FORMAT_DESCRIPTIONS = {
    "1:1": "Square, avatars, social media",
    "3:2 / 2:3": "Standard photos",
    "4:3 / 3:4": "Traditional display ratio",
    "16:9 / 9:16": "Widescreen / vertical video covers",
    "5:4 / 4:5": "Instagram images",
    "21:9": "Ultra-wide banner",
    "1:4 / 4:1": "Long poster / banner",
    "1:8 / 8:1": "Extreme long images / banner ads"
}

# Тип для выбора массива форматов
FormatSetType = Literal["api", "descriptive", "both"]


def parse_ratio(ratio_str: str) -> float:
    """Преобразует строку формата в число (отношение ширины к высоте)"""
    w, h = map(int, ratio_str.split(':'))
    return w / h


def get_all_formats(format_set: FormatSetType = "api") -> List[str]:
    """
    Возвращает список форматов в зависимости от выбранного набора
    """
    if format_set == "api":
        return FORMATS_API
    elif format_set == "descriptive":
        return FORMATS_DESCRIPTIVE
    elif format_set == "both":
        # Объединяем оба массива, убирая дубликаты (сохраняем порядок)
        combined = FORMATS_API.copy()
        for fmt in FORMATS_DESCRIPTIVE:
            if fmt not in combined:
                combined.append(fmt)
        return combined
    else:
        return FORMATS_API  # По умолчанию


def find_closest_ratio(target_ratio: float, format_set: FormatSetType = "api",
                       tolerance: float = 0.1, return_all_info: bool = False):
    """
    Находит ближайший поддерживаемый формат к целевому соотношению сторон

    Args:
        target_ratio: Целевое соотношение сторон (width/height)
        format_set: Какой набор форматов использовать ("api", "descriptive", "both")
        tolerance: Допустимое отклонение для точного совпадения
        return_all_info: Вернуть дополнительную информацию о найденном формате

    Returns:
        Если return_all_info=False: строка с форматом
        Если return_all_info=True: словарь с информацией о формате
    """
    # Получаем нужный набор форматов
    formats = get_all_formats(format_set)

    # Создаем список кортежей (формат, числовое значение)
    ratios = [(fmt, parse_ratio(fmt)) for fmt in formats]

    # Сначала ищем точное совпадение с учетом погрешности
    for fmt_str, fmt_value in ratios:
        if isclose(fmt_value, target_ratio, rel_tol=tolerance):
            if return_all_info:
                return {
                    "format": fmt_str,
                    "ratio": fmt_value,
                    "match_type": "exact",
                    "description": get_format_description(fmt_str)
                }
            return fmt_str

    # Если точного совпадения нет, находим ближайшее
    closest = min(ratios, key=lambda x: abs(x[1] - target_ratio))

    if return_all_info:
        return {
            "format": closest[0],
            "ratio": closest[1],
            "match_type": "closest",
            "difference": abs(closest[1] - target_ratio),
            "description": get_format_description(closest[0])
        }

    return closest[0]


def get_format_description(format_str: str) -> str:
    """Возвращает описание формата, если оно существует"""
    # Проверяем прямое совпадение
    if format_str in FORMAT_DESCRIPTIONS:
        return FORMAT_DESCRIPTIONS[format_str]

    # Проверяем обратное соотношение (например, для "2:3" ищем "3:2 / 2:3")
    w, h = map(int, format_str.split(':'))
    reversed_str = f"{h}:{w}"

    for key, desc in FORMAT_DESCRIPTIONS.items():
        if format_str in key or reversed_str in key:
            return desc

    return "No description available"


async def get_image_dimensions(image_url: str) -> Optional[Tuple[int, int]]:
    """Получает размеры изображения по URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    img = Image.open(io.BytesIO(image_data))
                    return img.size  # (width, height)
    except Exception as e:
        print(f"Error getting image dimensions: {e}")
    return None


async def determine_best_format(
        image_urls: List[str],
        format_set: FormatSetType = "api",
        tolerance: float = 0.1,
        return_details: bool = False
):
    """
    Главная функция для определения наилучшего формата изображения

    Args:
        image_urls: Список URL изображений
        format_set: Какой набор форматов использовать
        tolerance: Допустимое отклонение для поиска
        return_details: Вернуть детальную информацию о найденном формате

    Returns:
        Если return_details=False: строка с форматом (например, "16:9")
        Если return_details=True: словарь с полной информацией
    """
    if not image_urls:
        default_format = "16:9" if format_set == "api" else "16:9"
        if return_details:
            return {
                "format": default_format,
                "ratio": parse_ratio(default_format),
                "match_type": "default",
                "description": get_format_description(default_format),
                "note": "No images provided, using default format"
            }
        return default_format

    try:
        # Получаем размеры первого изображения
        dimensions = await get_image_dimensions(image_urls[0])
        if dimensions:
            width, height = dimensions
            target_ratio = width / height

            # Находим лучший формат
            result = find_closest_ratio(
                target_ratio,
                format_set=format_set,
                tolerance=tolerance,
                return_all_info=return_details
            )

            if return_details:
                result["original_dimensions"] = f"{width}x{height}"
                result["original_ratio"] = target_ratio
                return result

            return result

    except Exception as e:
        print(f"Error determining image format: {e}")

    # В случае ошибки возвращаем формат по умолчанию
    default_format = "16:9"
    if return_details:
        return {
            "format": default_format,
            "ratio": parse_ratio(default_format),
            "match_type": "default",
            "description": get_format_description(default_format),
            "error": str(e) if 'e' in locals() else "Unknown error"
        }
    return default_format


async def solve_task(image: PhotoSize, bot: Bot, prompt: str | None = None):
    system_prompt = ("Реши задачу и представь решение в понятном, читаемом формате без "
                     "использования LaTeX и боксов. Используй обычные математические "
                     "символы и простым языком, пошагово объясняй каждое свое "
                     "действие в решении данной тебе задачи. Сами математические действия "
                     "возвращай строго в формате <code>действие</code>")
    prompt = system_prompt if not prompt else system_prompt + (f'\nВот пользовательский промпт к '
                                                               f'решению задачи: "{prompt}"')
    messages = []
    if image:
        data, media_type = await photo_to_base64(image, bot)
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    },
                    {"type": "text", "text": prompt} if prompt else ...
                ],
            }
        )
    else:
        messages.append({"role": "user", "content": prompt})
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=prompt,
        messages=messages
    )
    answer = message.content[0].text
    return answer


async def get_assistant_and_thread(model: str = 'gpt-4.1-mini', role: str | None = None):
    """
    :param model: модель чата гпт
    :return: Две str переменной по факту являющиеся уникальными для каждого юзера, чтобы обрабатывать их
        диалог отдельно от других юзеров
    """
    assistant = await gpt_client.beta.assistants.create(
        model=model,
        instructions=role,
        temperature=1.0,
        name="Яна"
    )

    thread = await gpt_client.beta.threads.create()
    return assistant.id, thread.id


#print(asyncio.run(get_assistant_and_thread()))


async def get_ai_answer(prompt: str, assistant_id: str, thread_id: str, images: list[str] = None) -> str | dict | None:
    """
        Обработка ИИшкой сообщения юзера, возвращает ответ ИИ
    """
    if images:
        images = [{'type': 'image_url', "image_url": {"url": photo}} for photo in images]
    content = []
    if prompt:
        content.append({"type": "text", "text": prompt})
    if images:
        content.extend(images)
    message = await gpt_client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content
    )
    print(message.__dict__)
    run = await gpt_client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    logger.info(run.status)
    logger.info(run.last_error)
    info = (f'Стоимость запроса: {run.usage.completion_tokens}\nСтоимость промпта: {run.usage.prompt_tokens}'
            f'\nОбщая стоимость: {run.usage.total_tokens}')
    logger.info(info)
    if run.status == "completed":
        messages = await gpt_client.beta.threads.messages.list(thread_id=thread_id)
        logger.info(messages)

        async for message in messages:
            logger.info(message.content[0].text.value)
            return message.content[0].text.value
    # if not messages:
    #     messages = []
    #
    # if image:
    #     data, media_type = await photo_to_base64(image, bot)
    #     messages.append(
    #         {
    #             "role": "user",
    #             "content": [
    #                 {
    #                     "type": "image",
    #                     "source": {
    #                         "type": "base64",
    #                         "media_type": media_type,
    #                         "data": data,
    #                     },
    #                 },
    #                 {"type": "text", "text": prompt} if prompt else ...
    #             ],
    #         }
    #     )
    # else:
    #     messages.append({"role": "user", "content": prompt})
    # message = await client.messages.create(
    #     model="claude-haiku-4-5-20251001",
    #     max_tokens=1024,
    #     system=system_prompt,
    #     messages=messages
    # )
    # answer = message.content[0].text
    # messages.append({"role": "assistant", "content": answer})
    # return answer, messages


def find_image_links(text):
    # Регулярное выражение для поиска строк, начинающихся с ![gen и содержащих ссылку
    pattern = r'!\[gen[^\]]+\]\((https?://[^\s)]+)\)'

    # Поиск всех совпадений в тексте
    matches = re.findall(pattern, text)

    return matches


async def _polling_unifically_generate(task_id: str) -> list[str] | dict:
    url = f'https://api.unifically.com/v1/tasks/{task_id}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.unifically_api_token}'
    }
    async with aiohttp.ClientSession() as client:
        while True:
            async with client.get(url, headers=headers, ssl=False) as response:
                if response.status not in [200, 201]:
                    print(await response.text())
                    data = await response.json()
                    return {'error': data['data']['error']['message']}
                data = await response.json()
                print(data)
            if data['data']['status'] == 'failed':
                return {'error': data['data']['error']['message']}
            if data['data']['status'] == 'completed':
                return [data['data']['output']['image_url']]
            await asyncio.sleep(4)


counter = 1


async def generate_division(prompt: str, bot: Bot, photos: list[Message]):
    logger.info('Start generate division')
    images = []
    if photos:
        logger.info('Download and upload images...')
        images = await download_and_upload_images(bot, photos)
    try:
        logger.info('Start first apimart try')
        result = await generate_image_by_apimart(prompt, images, '2.5')
    except Exception as err:
        logging.error(f'3.1 generate error: {err}')
        result = None

    if isinstance(result, dict) or result is None:
        try:
            logger.info('Start second apimart try')
            result = await generate_image_by_apimart(prompt, images, '2.5')
        except Exception as err:
            logging.error(f'2.5 generate error: {err}')
            result = None
    if isinstance(result, dict) or result is None:
        try:
            logger.info('Start 3rd inificcaly try')
            result = await generate_image_by_unifically(prompt, images)
        except Exception as err:
            logging.error(f'unificcaly generate error: {err}')
    return result


async def generate_image_by_unifically(prompt: str, photos: list[str]) -> list[str] | dict:
    url = f'https://api.unifically.com/v1/tasks'
    #prompt = await translate_text(prompt)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.unifically_api_token}'
    }
    size = await determine_best_format(
        image_urls=photos,
        format_set='api',
        tolerance=0.15
    ) if photos else "16:9"
    data = {
        "model": 'google/nano-banana',
        "input": {
            "prompt": prompt,
            "aspect_ratio": size
        }
    }
    if photos:
        data["input"]["image_urls"] = photos
    async with aiohttp.ClientSession() as client:
        async with client.post(url, headers=headers, json=data, ssl=False) as response:
            print(response.status)
            if response.status not in [200, 201]:
                print(await response.text())
                data = await response.json()
                return {'error': data['data']['error']['message']}
            data = await response.json()
            print(data)
        if data['code'] != 200:
            return {'error': data['data']['error']['message']}
        if data['data'].get('output'):
            return [data['data']['output']['image_url']]
        task_id = data['data'].get('task_id')
    return await _polling_unifically_generate(task_id)


async def _polling_apimart_generate(task_id: str):
    url = f'https://api.apimart.ai/v1/tasks/{task_id}'
    headers = {
        "Authorization": f"Bearer {config.apimart_api_key}",
    }
    while True:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                if response.status != 200:
                    try:
                        data = await response.json()
                        return {'error': f"{data['error'].get('code')}: {data['error'].get('message')}"}
                    except Exception:
                        ...
                    return {'error': await response.text()}
                data = await response.json()
                logger.info(f'Polling data: {data}')
                status = data['data'].get('status')
                if status and status == 'failed':
                    return {'error': data['data']['error'].get('message')}
                if status and status == 'completed':
                    return data['data']['result']['images'][0].get('url')
                await asyncio.sleep(3)


async def generate_image_by_apimart(prompt: str, photos: list[str], version: Literal['2.5', '3.1']):
    url = 'https://api.apimart.ai/v1/images/generations'
    headers = {
        "Authorization": f"Bearer {config.apimart_api_key}",
        "Content-Type": "application/json"
    }
    logger.info('start determine format')
    size = await determine_best_format(
        image_urls=photos,
        format_set='descriptive' if version == '3.1' else 'api',
        tolerance=0.15  # Можно настроить точность
    ) if photos else "16:9"
    data = {
        "model": "gemini-2.5-flash-image-preview" if version == '2.5' else "gemini-3.1-flash-image-preview",
        "prompt": prompt,
        "size": size,
        "resolution": "1K",
    }
    if photos:
        data['image_urls'] = photos
    logger.info('Send request')
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers, ssl=False) as response:
            if response.status != 200:
                try:
                    data = await response.json()
                    return {'error': f"{data['error'].get('code')}: {data['error'].get('message')}"}
                except Exception:
                    ...
                return {'error': await response.text()}
            data = await response.json()
            task_id = data['data'][0].get('task_id')
    return await _polling_apimart_generate(task_id)


#print(asyncio.run(generate_image_by_veo('Сделай фото мультяшного леопарда', [])))
