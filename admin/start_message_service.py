import asyncio
import json
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.database.database import Database


async def send_start_message_to_user(bot: Bot, db: Database, user_id: int):
    """
    Проверяет, есть ли стартовое сообщение, и отправляет его пользователю
    с учетом установленной задержки.
    """
    start_msg_info = await db.start_message.get_message()

    if not start_msg_info:
        # Если стартового сообщения не установлено, ничего не делаем.
        return

    delay = start_msg_info.delay_seconds
    logging.info(f"Start message found. Sending to user {user_id} with a delay of {delay} seconds.")

    # Ждем указанную задержку
    if delay > 0:
        await asyncio.sleep(delay)

    try:
        # Восстанавливаем клавиатуру из JSON, если она есть
        reply_markup = None
        if start_msg_info.reply_markup:
            keyboard_data = json.loads(start_msg_info.reply_markup)
            reply_markup = InlineKeyboardMarkup.model_validate(keyboard_data)

        # Используем copy_message для точного копирования поста
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=start_msg_info.chat_id,
            message_id=start_msg_info.message_id,
            reply_markup=reply_markup
        )
        logging.info(f"Successfully sent start message to user {user_id}")
    except Exception as e:
        logging.error(f"Failed to send start message to user {user_id}: {e}")