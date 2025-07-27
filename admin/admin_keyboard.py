#admin
import logging
from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from database.models import SubscriptionCheck, AdUrl


def admin_panel_menu():
    buttons = [
        [
            KeyboardButton(text="Статистика"),
            KeyboardButton(text="ОП"),
        ],
        [
            KeyboardButton(text='Рекламные ссылки'),
            KeyboardButton(text='Рассылки')
        ],
        [
            KeyboardButton(text='Ключи для апи'),
            KeyboardButton(text='Юзеры Бд')
        ],
        [
            KeyboardButton(text='Покупки'),
            KeyboardButton(text='Логи')
        ],
        [
            KeyboardButton(text='Стартовое сообщение')
        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


def op_panel_button(subscription_list: List[SubscriptionCheck]):
    buttons = []
    for subscription in subscription_list:
        buttons.append([InlineKeyboardButton(text=subscription.chat_id, callback_data=f'op:view:{subscription.id}')])
    buttons.append([InlineKeyboardButton(text='Создать обязательную подписку', callback_data='create_op_panel')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard




def op_url_one_bottom_panel(channel_id: int):
    buttons = [
        [
            InlineKeyboardButton(text='🔄 Обновить ссылку', callback_data=f'op:update_link:{channel_id}'),
            InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'op:delete:{channel_id}'),
        ],
        [
            InlineKeyboardButton(text='Назад', callback_data=f'admin_panel_op')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard



def cancel_op_panel_button():
    buttons = [
        [
            InlineKeyboardButton(text='Отмена', callback_data='admin_panel_op')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def cancel_urls_panel_button():
    buttons = [
        [
            InlineKeyboardButton(text='Отмена', callback_data='back_urls_panel')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def ad_url_one_panel_button(name):
    buttons = [
        [
            InlineKeyboardButton(text='🔄 Обновить', callback_data=f'ad_url:update:{name}'),
            InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'ad_url:delete:{name}'),
        ],
        [
            InlineKeyboardButton(text='Назад', callback_data='ad_url:back')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def cancel_key_panel_button():
    buttons = [
        [
            InlineKeyboardButton(text='Отмена', callback_data='back_keys_panel')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def ad_urls_panel_button(ad_url_list: List[AdUrl]):
    buttons = []
    for ad_url in ad_url_list:
        buttons.append([InlineKeyboardButton(text=ad_url.name, callback_data=f'ad_url:view:{ad_url.name}')])
    buttons.append([InlineKeyboardButton(text='Создать рекламную ссылку', callback_data='create_ad_url_panel')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def api_keys_panel_button():
    buttons = [
        [
            InlineKeyboardButton(text='ChatGPT', callback_data='key:set:chatgpt'),
            InlineKeyboardButton(text='ChatGPT o1', callback_data='key:set:claude_o1')
        ],
        [
            InlineKeyboardButton(text='Claude', callback_data='key:set:claude'),
            InlineKeyboardButton(text='ElevenLabs', callback_data='key:set:elevenlabs')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard



def start_message_menu_keyboard(is_set: bool) -> InlineKeyboardMarkup:
    """
    Генерирует меню управления стартовым сообщением.
    """
    buttons = []
    if is_set:
        buttons.extend([
            [InlineKeyboardButton(text="🔄 Установить/Изменить пост", callback_data="admin:start_msg:set")],
            [InlineKeyboardButton(text="🕒 Установить задержку", callback_data="admin:start_msg:delay")],
            [InlineKeyboardButton(text="🗑️ Удалить сообщение", callback_data="admin:start_msg:delete")],
        ])
    else:
        buttons.append(
            [InlineKeyboardButton(text="➕ Установить пост", callback_data="admin:start_msg:set")]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_copy_message() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой отмены для процесса установки стартового сообщения.
    """
    buttons = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:start_msg:cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_malling_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Начать рассылку', callback_data='confirm_malling')],
            [InlineKeyboardButton(text='Отмена', callback_data='cancel_malling')]
        ]
    )


