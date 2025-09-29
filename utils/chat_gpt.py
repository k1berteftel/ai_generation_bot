import json
import asyncio
import re

import httpx
import aiohttp

from openai import AsyncOpenAI
from openai.types.beta.threads.message_content_part_param import MessageContentPartParam

from utils.helpers import upload_image_to_imgbb

import config

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


def find_image_links(text):
    # Регулярное выражение для поиска строк, начинающихся с ![gen и содержащих ссылку
    pattern = r'!\[gen[^\]]+\]\((https?://[^\s)]+)\)'

    # Поиск всех совпадений в тексте
    matches = re.findall(pattern, text)

    return matches


async def generate_image(prompt: str, photos: list[str]) -> list[str] | dict:
    url = 'https://api.unifically.com/nano-bana/generate'
    #prompt = await translate_text(prompt)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.unifically_api_token}'
    }
    data = {
      "prompt": prompt,
    }
    if photos:
        data["image_urls"] = photos
    async with aiohttp.ClientSession() as client:
        async with client.post(url, headers=headers, json=data, ssl=False) as response:
            print(response.status)
            if response.status not in [200, 201]:
                data = await response.json()
                return {'error': data['data']['error']['message']}
            data = await response.json()
            print(data)
            if data['data']['status'] != 'completed':
                return {'error': data['data']['error']['message']}
    return [data['data']['output']['image_url']]


#print(asyncio.run(generate_image('Сделай девушку азиатку', [])))
