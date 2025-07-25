# keyboards/inline.py
import json
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from data.constants import MODELS, MODEL_DURATIONS, ASPECT_INPUTS

USER_MODELS = {}
USER_DURATIONS = {}
USER_PIXVERSE_MODE = {}
USER_ASPECT_RATIO = {}


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😀 Начать диалог", callback_data="start_chat")],
        [InlineKeyboardButton(text="🧠 Выбрать модель", callback_data="choose_model")],
        [InlineKeyboardButton(text="🎁Студентам и школьникам", callback_data="for_students")],
        [
            InlineKeyboardButton(text="👤 Мой аккаунт", callback_data="account"),
            InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")
        ]
        # [InlineKeyboardButton(text="🎬 Инструкция", url="https://teletype.in/@visvist/FN93qwX9c24")],
    ])


def get_account_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="↗️ Поделиться", url=f"http://t.me/share/url?url=https://t.me/ai_generation_robot?start={user_id}"),
            #InlineKeyboardButton(text="🎁 Подарить Veo3", callback_data="gift"),
        ],
        #[InlineKeyboardButton(text="🎬 Бесплатные генерации", callback_data="free_gens")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])


def get_student_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Решальник задач (скоро)', callback_data='pass')],
            [InlineKeyboardButton(text='Генерация презентаций (скоро)', callback_data='pass')],
            [InlineKeyboardButton(text='Создание рефератов (скоро)', callback_data='pass')],
            [InlineKeyboardButton(text='Ответы на вопросы (скоро)', callback_data='pass')],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ]
    )


def balance_rubles_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 250 кристалов — 250₽", callback_data="buy_rub_250")],
        [InlineKeyboardButton(text="💎 400 кристалов — 400₽", callback_data="buy_rub_400")],
        [InlineKeyboardButton(text="💎 700 кристалов — 700₽", callback_data="buy_rub_700")],
        [InlineKeyboardButton(text="💎 1500 кристалов — 1500₽", callback_data="buy_rub_1500")],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='balance')]
    ])


def balance_stars_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 250 кристалов — 189 ⭐️", callback_data="buy_stars_250")],
        [InlineKeyboardButton(text="💎 400 кристалов — 299 ⭐️", callback_data="buy_stars_400")],
        [InlineKeyboardButton(text="💎 700 кристалов — 539 ⭐️", callback_data="buy_stars_700")],
        [InlineKeyboardButton(text="💎 1500 кристалов — 1149 ⭐️", callback_data="buy_stars_1500")],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='balance')]
    ])


def balance_choose_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⭐️ Telegram Stars', callback_data='telegram_stars_callback')],
        [InlineKeyboardButton(text='💳Банковская карта', callback_data='bank_card_callback')],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])


def aspect_menu(selected="16:9") -> InlineKeyboardMarkup:
    buttons = []

    aspect_ratios = list(ASPECT_INPUTS.keys())

    for i in range(0, len(aspect_ratios), 3):
        row = []
        for ar in aspect_ratios[i:i + 3]:
            text = f"{ar} ✅" if selected == ar else ar
            row.append(InlineKeyboardButton(text=text, callback_data=f"aspect_{ar}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_prompt")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def url_button(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Оплатить', url=link)]])


async def json_to_keyboard(keyboard_data: dict) -> InlineKeyboardMarkup:
    inline_keyboard = []

    for row in keyboard_data['inline_keyboard']:
        buttons = [
            InlineKeyboardButton(
                text=btn['text'],
                url=btn.get('url'),
                callback_data=btn.get('callback_data'),
                web_app=btn.get('web_app'),
                login_url=btn.get('login_url'),
                switch_inline_query=btn.get('switch_inline_query'),
                switch_inline_query_current_chat=btn.get('switch_inline_query_current_chat'),
                switch_inline_query_chosen_chat=btn.get('switch_inline_query_chosen_chat'),
                copy_text=btn.get('copy_text'),
                callback_game=btn.get('callback_game'),
                pay=btn.get('pay')
            ) for btn in row
        ]
        inline_keyboard.append(buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def model_menu() -> InlineKeyboardMarkup:
    model_names = list(MODELS.keys())
    buttons = []
    for name in model_names:
            # --- Ключевое изменение здесь ---
        button = [InlineKeyboardButton(text=name, callback_data=f"model_{name}")]

        buttons.append(button)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def duration_menu(selected_model: str, user_id: int) -> InlineKeyboardMarkup:
    durations = MODEL_DURATIONS.get(selected_model, ["5 сек"])
    current_duration = USER_DURATIONS.get(user_id, durations[0])
    kb = []
    for d in durations:
        text = f"{d} ✅" if d == current_duration else d
        kb.append([InlineKeyboardButton(text=text, callback_data=f"set_duration_{d}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_prompt")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_prompt_keyboard(user_id: int, selected_model: str) -> InlineKeyboardMarkup:
    back = f'model_{selected_model}'
    if selected_model == 'Veo3 - видео сценарию':
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="ℹ️ Инструкция", url="https://t.me/veo3guide")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=back)],
            ]
        )

    if selected_model == 'Sora - Генерация изображений':
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="ℹ️ Инструкция", url="https://t.me/veo3guide")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=back)],
            ]
        )

    current_duration = USER_DURATIONS.get(user_id, MODEL_DURATIONS.get(selected_model, ["5 сек"])[0])
    row1 = [
        InlineKeyboardButton(text=f"⏱ Длительность: {current_duration}", callback_data="choose_duration"),
        InlineKeyboardButton(text="📐 Соотношение сторон", callback_data="choose_aspect"),
    ]
    row2 = []
    if selected_model == "Pixverse v4.5":
        pixverse_mode = USER_PIXVERSE_MODE.get(user_id, "smooth")
        row2 = [InlineKeyboardButton(text="🟢 Smooth" if pixverse_mode == "smooth" else "⚪️ Normal",
                                     callback_data="toggle_pixverse_mode")]
    return InlineKeyboardMarkup(
        inline_keyboard=[row1] + ([row2] if row2 else []) + [
            [InlineKeyboardButton(text="ℹ️ Инструкция", url="https://t.me/veo3guide")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back)],
        ]
    )


def get_exemple_keyboard(url: str):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='😀 Начать генерацию', callback_data='start_gen')],
            [InlineKeyboardButton(text='ℹ️ Инструкция', url=url)],
            [InlineKeyboardButton(text='⬅️ Назад', callback_data='choose_model')]
        ]
    )
    return keyboard


def subscribe_button_keyboard(channels: list[list]) -> InlineKeyboardMarkup:
    buttons = []
    for channel in channels:
        buttons.append(
            [InlineKeyboardButton(text='Подписаться', url=channel[1])]
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        *buttons,
        [InlineKeyboardButton(text='Подписался ✔️', callback_data=f'check_op')]
    ])