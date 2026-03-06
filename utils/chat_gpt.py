import os
import json
import asyncio
import re
import logging
from pathlib import Path

import httpx
import aiohttp

from openai import AsyncOpenAI
from aiogram import Bot
from aiogram.types import Message

from utils.helpers import upload_image_to_imgbb, save_image, download_and_upload_images, save_bot_files

import config


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


client = AsyncOpenAI(
    api_key=config.openai_api_token,
    http_client=httpx.AsyncClient(proxy='http://6L4YePzU:Mrnd5Tsy@212.193.143.10:63196')
)


async def solve_task(images: list[str], prompt: str | None = None):
    images = [{'type': 'image_url', "image_url": {"url": photo}} for photo in images]
    system_prompt = ("Реши задачу и представь решение в понятном, читаемом формате без "
                     "использования LaTeX и боксов. Используй обычные математические "
                     "символы и простым языком, пошагово объясняй каждое свое "
                     "действие в решении данной тебе задачи. Сами математические действия "
                     "возвращай строго в формате <code>действие</code>")
    prompt = system_prompt if not prompt else system_prompt + (f'\nВот пользовательский промпт к '
                                                               f'решению задачи: "{prompt}"')
    response = await client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *images
                ]
            }
        ],
    )
    print(response.usage.total_tokens, response.usage.prompt_tokens, response.usage.completion_tokens)
    print(response.choices[0].message.content)
    return response.choices[0].message.content


async def get_assistant_and_thread(model: str = 'gpt-4.1-mini', role: str | None = None):
    """
    :param model: модель чата гпт
    :return: Две str переменной по факту являющиеся уникальными для каждого юзера, чтобы обрабатывать их
        диалог отдельно от других юзеров
    """
    assistant = await client.beta.assistants.create(
        model=model,
        instructions=role,
        temperature=1.0,
        name="Яна"
    )

    thread = await client.beta.threads.create()
    return assistant.id, thread.id


#print(asyncio.run(get_assistant_and_thread()))


async def get_text_answer(prompt: str, assistant_id: str, thread_id: str, images: list[str] = None) -> str | dict | None:
    """
        Обработка ИИшкой сообщения юзера, возвращает ответ ИИ
    """
    images = [{'type': 'image_url', "image_url": {"url": photo}} for photo in images]
    print(assistant_id, thread_id)
    content = []
    if prompt:
        content.append({"type": "text", "text": prompt})
    if images:
        content.extend(images)
    message = await client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content
    )
    print(message.__dict__)
    run = await client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    print(run.status)
    print(run.last_error)
    info = (f'Стоимость запроса: {run.usage.completion_tokens}\nСтоимость промпта: {run.usage.prompt_tokens}'
            f'\nОбщая стоимость: {run.usage.total_tokens}')
    print(info)
    if run.status == "completed":
        messages = await client.beta.threads.messages.list(thread_id=thread_id)
        # print(messages)

        async for message in messages:
            print(message.content[0].text.value)
            return message.content[0].text.value


#assistant_id, thread_id = asyncio.run(get_assistant_and_thread())
#asyncio.run(get_text_answer('Привет', assistant_id, thread_id))


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
    images = []
    if photos:
        images = await download_and_upload_images(bot, photos)
    try:
        result = await generate_image_by_apimart(prompt, images)
    except Exception as err:
        logging.error(f'unifically generate error: {err}')
        result = None
    if isinstance(result, dict) or result is None:
        result = await generate_image_by_unifically(prompt, images)
    return result


async def generate_image_by_unifically(prompt: str, photos: list[str]) -> list[str] | dict:
    url = f'https://api.unifically.com/v1/tasks'
    #prompt = await translate_text(prompt)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.unifically_api_token}'
    }
    data = {
        "model": 'google/nano-banana',
        "input": {
            "prompt": prompt,
            "aspect_ratio": '16:9'
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
                    return {'error': await response.text()}
                data = await response.json()
                print(data)
                if data['data'].get('status') == 'failed':
                    return {'error': data['data']['error'].get('message')}
                if data['data'].get('status') == 'completed':
                    return data['data']['result']['images'][0].get('url')[0]
                await asyncio.sleep(3)


async def generate_image_by_apimart(prompt: str, photos: list[str]):
    url = 'https://api.apimart.ai/v1/images/generations'
    headers = {
        "Authorization": f"Bearer {config.apimart_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gemini-2.5-flash-image-preview",
        "prompt": prompt,
        "size": "16:9",
        "resolution": "1K",
    }
    if photos:
        data['image_urls'] = photos
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers, ssl=False) as response:
            if response.status != 200:
                return {'error': await response.text()}
            data = await response.json()
            task_id = data['data'][0].get('task_id')
    return await _polling_apimart_generate(task_id)


#print(asyncio.run(generate_image_by_veo('Сделай фото мультяшного леопарда', [])))
