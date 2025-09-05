import json
import asyncio
import re

import httpx
import aiohttp

from openai import AsyncOpenAI

from utils.helpers import upload_image_to_imgbb

import config

client = AsyncOpenAI(
    api_key=config.openai_api_token,
    http_client=httpx.AsyncClient(proxy='http://6L4YePzU:Mrnd5Tsy@212.193.143.10:63196')
)


async def solve_task(images: list[str]):
    images = [{'type': 'image_url', "image_url": {"url": photo}} for photo in images]
    response = await client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Реши задачу и представь решение в понятном, читаемом формате без "
                                             "использования LaTeX и боксов. Используй обычные математические "
                                             "символы и простым языком, пошагово объясняй каждое свое "
                                             "действие в решении данной тебе задачи. Сами математические действия "
                                             "возвращай строго в формате <code>действие</code>"},
                    *images
                ]
            }
        ],
    )
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


async def get_text_answer(text: str, assistant_id: str, thread_id: str) -> str | dict | None:
    """
        Обработка ИИшкой сообщения юзера, возвращает ответ ИИ
    """
    print(assistant_id, thread_id)
    message = await client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=text
    )
    print(message.__dict__)
    run = await client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
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


async def generate_image(prompt: str, photos: list[str]) -> list[str] | None:
    url = 'https://api.unifically.com/v1/chat/completions'
    #prompt = await translate_text(prompt)
    if not prompt:
        return None
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.unifically_api_token}'
    }
    images = [{'type': 'image_url', "image_url": {"url": photo}} for photo in photos]
    data = {
        "model": "gpt-4o-image-vip",
        "messages": [
            {
                "role": "user",
                'content': [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    *images
                ]
            }
        ],
        "stream": True
    }
    async with aiohttp.ClientSession() as client:
        async with client.post(url, headers=headers, json=data, ssl=False) as response:
            content = str(await response.content.read())
            links = find_image_links(content)
            return links


#print(asyncio.run(generate_image('Сделай девушку азиаткой', [])))
