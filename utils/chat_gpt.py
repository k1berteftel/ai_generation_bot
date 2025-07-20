import httpx

from openai import AsyncOpenAI

import config


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