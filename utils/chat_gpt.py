import os

import httpx
import base64
import random
import string

from openai import AsyncOpenAI

from utils.helpers import upload_image_to_imgbb

import config


def get_random_id() -> str:
    string.ascii_letter = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    simvols = ''
    for i in range(0, 8):
        simvols += str(random.choice(string.ascii_letters))
    return simvols


client = AsyncOpenAI(
    api_key=config.openai_api_token,
    http_client=httpx.AsyncClient(proxy='http://eAzEJHXk:6WL4egih@109.205.62.47:64856')   # замена прокси на пользовательское
)


async def get_assistant_and_thread(model: str = 'gpt-4.1-mini', role: str = None):
    """
    :param role: Роль которую будет отыгрывать ИИ.
    :param model: модель чата гпт
    :return: Две str переменной по факту являющиеся уникальными для каждого юзера, чтобы обрабатывать их
        диалог отдельно от других юзеров
    """
    assistant = await client.beta.assistants.create(
        model=model,
        instructions=role if role else None,
        temperature=1.0,
        name="Яна"
    )

    thread = await client.beta.threads.create()
    return assistant.id, thread.id


async def get_text_answer(text: str, assistant_id: str, thread_id: str) -> str | None:
    """
        Обработка ИИшкой сообщения юзера, возвращает ответ ИИ
    """
    message = await client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=text
    )
    run = await client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    info = (f'Стоимость запроса: {run.usage.completion_tokens}\nСтоимость промпта: {run.usage.prompt_tokens}'
            f'\nОбщая стоимость: {run.usage.total_tokens}')
    with open('upload.txt', 'a', encoding='utf-8') as file:
        file.write('Запрос на диалог: ' + info + '\n\n')
    print(info)
    print(run)
    print(run.status)
    if run.status == "completed":
        messages = await client.beta.threads.messages.list(thread_id=thread_id)
        #print(messages)

        async for message in messages:
            print(message.content[0].text.value)
            return message.content[0].text.value
    else:
        return None


async def generate_image(photos: list[str], prompt: str) -> list[str]:
    photos_data = []
    for photo in photos:
        photos_data.append(
            {
                "type": "input_image",
                "image_url": photo,
            }
        )
    try:

        response = await client.responses.create(
            model="gpt-4.1-mini",
            input=[
                    {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        *photos_data
                    ]
                }
            ],
            tools=[{"type": "image_generation", "input_fidelity": "low"}],
        )
        info = f'Общая стоимость: {response.usage.total_tokens}'
        with open('upload.txt', 'a', encoding='utf-8') as file:
            file.write('Запрос на генерацию: ' + info + '\n\n')
        image_data = [
            output.result
            for output in response.output
            if output.type == "image_generation_call"
        ]
        photos = []
        for image in image_data:
            image_base64 = image
            file_path = f"{get_random_id()}.png"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(image_base64))
            try:
                photo_url = await upload_image_to_imgbb(file_path)
            except Exception:
                continue
            if photo_url:
                photos.append(photo_url)
            try:
                os.remove(file_path)
            except Exception:
                ...
        return photos

    except Exception as e:
        raise Exception(f"Ошибка при генерации изображения: {str(e)}")