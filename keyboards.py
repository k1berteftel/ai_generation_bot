from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="😀 Начать диалог", callback_data="start_chat")],
            [InlineKeyboardButton(text="🎞 Создать видео", callback_data="choose_model")],
            [InlineKeyboardButton(text="🖼Генерация фото как в Тик-ток", callback_data="photo_menu")],
            [InlineKeyboardButton(text="🎁Студентам и школьникам", callback_data="for_students")],
            [
                InlineKeyboardButton(text="👤 Мой аккаунт", callback_data="account"),
                InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")
            ],
            #[InlineKeyboardButton(text="🎬 Инструкция", url="https://teletype.in/@visvist/FN93qwX9c24")],
        ]
    )


def get_account_keyboard(user_id: int) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                # switch_inline_query='' позволяет открыть список чатов для пересылки
                InlineKeyboardButton(text="↗️ Поделиться", switch_inline_query=f"start={user_id}"),
                InlineKeyboardButton(text="🎁 Подарить Veo3", callback_data="gift"),
            ],
            [InlineKeyboardButton(text="🎬 Бесплатные генерации", callback_data="free_gens")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ]
    )



def balance_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 50 кристалов — 500₽", callback_data="buy_50")],
            [InlineKeyboardButton(text="💎 100 кристалов — 1000₽", callback_data="buy_100")],
            [InlineKeyboardButton(text="💎 250 кристалов — 2500₽", callback_data="buy_250")],
            [InlineKeyboardButton(text="💎 ∞ кристалов — 6999₽", callback_data="buy_unlim")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ]
    )


def aspect_menu(selected="16:9"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="16:9 ✅" if selected == "16:9" else "16:9", callback_data="aspect_16:9"),
                InlineKeyboardButton(text="9:16 ✅" if selected == "9:16" else "9:16", callback_data="aspect_9:16"),
            ],
            [InlineKeyboardButton(text="1:1 ✅" if selected == "1:1" else "1:1", callback_data="aspect_1:1")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_prompt")]
        ]
    )


def url_button(link):
    buttons = [
        [
            InlineKeyboardButton(text='Оплатить', url=link)
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard



async def json_to_keyboard(keyboard_data):
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
