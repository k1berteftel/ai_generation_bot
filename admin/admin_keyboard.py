#admin
import logging
from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from database.models import SubscriptionCheck, AdUrl, Admins, Deeplinks


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
        ],
        [
            KeyboardButton(text='Партнеры'),
            KeyboardButton(text='Партнерские ссылки')
        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


def partner_panel_menu():
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Партнерские ссылки')]], resize_keyboard=True)
    return keyboard


async def get_partners_keyboard(admins: list[Admins]) -> InlineKeyboardMarkup:
    keyboards = []
    for admin in admins:
        keyboards.append([InlineKeyboardButton(text=admin.username if admin.username else str(admin.user_id),
                                              callback_data=f'partner_view_{admin.user_id}')])
    keyboards.append([InlineKeyboardButton(text='➕Добавить партнера', callback_data='add_partner_switcher')])
    return InlineKeyboardMarkup(inline_keyboard=keyboards)


def get_admins_button(user_id: int, ad_url_list: List[Deeplinks], page: int = 0):
    buttons = []
    for ad_url in ad_url_list:
        buttons.append([InlineKeyboardButton(text=ad_url.name, callback_data=f'admin:view:{ad_url.name}')])
    # [[], []]
    buttons = [buttons[i:i + 10] for i in range(0, len(buttons), 10)]
    # [[[], []], [[], []]]
    pager_buttons = []
    if page != 0:
        pager_buttons.append(InlineKeyboardButton(text='◀️', callback_data='admin_pager_back'))
    pager_buttons.append(InlineKeyboardButton(text=f'{page+1}/{len(buttons)}', callback_data='admin_show_pages'))
    if buttons and page != len(buttons) - 1:
        pager_buttons.append(InlineKeyboardButton(text='▶️', callback_data='admin_pager_next'))
    keyboard = buttons[page] if buttons else []
    # [[], []]
    keyboard.append(pager_buttons)
    keyboard.append([InlineKeyboardButton(text='Удалить партнера', callback_data=f'partner_del_{user_id}')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_deeplink_view_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='Назад', callback_data='close_admin_view')]]
    )
    return keyboard


def get_deeplinks_panel_button(ad_url_list: List[Deeplinks], page: int = 0):
    buttons = []
    for ad_url in ad_url_list:
        buttons.append([InlineKeyboardButton(text=ad_url.name, callback_data=f'deeplink:view:{ad_url.name}')])
    # [[], []]
    buttons = [buttons[i:i + 10] for i in range(0, len(buttons), 10)]
    # [[[], []], [[], []]]
    pager_buttons = []
    if page != 0:
        pager_buttons.append(InlineKeyboardButton(text='◀️', callback_data='partner_pager_back'))
    pager_buttons.append(InlineKeyboardButton(text=f'{page+1}/{len(buttons)}', callback_data='show_pages'))
    if buttons and page != len(buttons) - 1:
        pager_buttons.append(InlineKeyboardButton(text='▶️', callback_data='partner_pager_next'))
    keyboard = buttons[page] if buttons else []
    # [[], []]
    keyboard.append(pager_buttons)
    keyboard.append([InlineKeyboardButton(text='Создать рекламную ссылку', callback_data='create_deeplink_panel')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def deeplink_one_panel_button(name):
    buttons = [
        [
            InlineKeyboardButton(text='🔄 Обновить', callback_data=f'deeplink:update:{name}'),
            InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'deeplink:delete:{name}'),
        ],
        [
            InlineKeyboardButton(text='Назад', callback_data='deeplink:back')
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
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


def ad_urls_panel_button(ad_url_list: List[AdUrl], page: int = 0):
    buttons = []
    for ad_url in ad_url_list:
        buttons.append([InlineKeyboardButton(text=ad_url.name, callback_data=f'ad_url:view:{ad_url.name}')])
    # [[], []]
    buttons = [buttons[i:i + 10] for i in range(0, len(buttons), 10)]
    # [[[], []], [[], []]]
    pager_buttons = []
    if page != 0:
        pager_buttons.append(InlineKeyboardButton(text='◀️', callback_data='pager_back'))
    pager_buttons.append(InlineKeyboardButton(text=f'{page+1}/{len(buttons)}', callback_data='show_pages'))
    if page != len(buttons) - 1:
        pager_buttons.append(InlineKeyboardButton(text='▶️', callback_data='pager_next'))
    keyboard = buttons[page]
    # [[], []]
    keyboard.append([InlineKeyboardButton(text='Создать рекламную ссылку', callback_data='create_ad_url_panel')])
    keyboard.append(pager_buttons)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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


