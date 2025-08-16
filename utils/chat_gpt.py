import os
import asyncio

import httpx
import base64
import random
import string

from openai import AsyncOpenAI
import replicate

from utils.helpers import upload_image_to_imgbb

import config


client = AsyncOpenAI(
    api_key=config.openai_api_token,
    http_client=httpx.AsyncClient(proxy='http://eAzEJHXk:6WL4egih@46.232.31.88:62560')
)


app = replicate.Client(api_token=config.replicate_api_token)


async def get_assistant_and_thread(model: str = 'gpt-4.1-mini'):
    """
    :param model: модель чата гпт
    :return: Две str переменной по факту являющиеся уникальными для каждого юзера, чтобы обрабатывать их
        диалог отдельно от других юзеров
    """
    assistant = await client.beta.assistants.create(
        model=model,
        temperature=1.0,
        name="Яна"
    )

    thread = await client.beta.threads.create()
    return assistant.id, thread.id


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
        #print(messages)

        async for message in messages:
            print(message.content[0].text.value)
            return message.content[0].text.value


async def generate_image(prompt: str, photos: list[str]) -> list[str] | None:
    data = {
        "prompt": prompt,
        "openai_api_key": config.openai_api_token
    }
    #'https://i.ibb.co/JFzb41y9/7f3a359df8e1.jpg'
    if photos:
        data["input_images"] = photos
    output = await app.predictions.async_create(
        model="openai/gpt-image-1",
        input=data
    )
    prediction_id = output.id
    prediction = await app.predictions.async_get(prediction_id)
    while True:
        if prediction.status == 'failed':
            return None
        if prediction.status == 'succeeded':
            return prediction.output
        await asyncio.sleep(4)
        prediction = await app.predictions.async_get(prediction_id)


#print(asyncio.run(generate_image('Сделай фото природы в горах', [])))
