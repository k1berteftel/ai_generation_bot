# handlers/user_handlers.py
import datetime
import html
import os
import asyncio
import logging
import json
from typing import Callable, Any, Awaitable

from aiogram import Router, F, types, Bot, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Message, InputMediaPhoto, \
    LabeledPrice, SuccessfulPayment, PreCheckoutQuery
from yookassa import Payment

# Импорты из вашего проекта
import config
from database.database import Database
from data.constants import *
from keyboards.inline import (
    get_main_menu_keyboard, get_account_keyboard, aspect_menu, balance_rubles_menu, balance_choose_menu,
    balance_stars_menu,
    url_button, json_to_keyboard, model_menu, get_prompt_keyboard, duration_menu,
    subscribe_button_keyboard, get_exemple_keyboard, get_student_menu,
    get_photo_menu,
    USER_MODELS, USER_DURATIONS, USER_PIXVERSE_MODE, USER_ASPECT_RATIO
)
from services.nexus_api import generate_on_nexus
from services.replicate_api import generate_replicate_async
from services.payment_service import check_payment
from utils.helpers import calculate_generation_cost, get_crystal_price_str, download_video, check_user_op, \
    download_and_upload_images, check_user_op_single
from utils.chat_gpt import get_text_answer, get_assistant_and_thread, generate_image
from APIKeyManager.apikeymanager import APIKeyManager

user_router = Router()


class AlbumMiddleware(BaseMiddleware):
    album_data: dict[str, list[Message]] = {}

    def __init__(self, latency: int | float = 0.1):
        self.latency = latency

    async def __call__(
            self,
            handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            data["album"] = [event]
            return await handler(event, data)

        group_id = event.media_group_id
        if group_id not in self.album_data:
            self.album_data[group_id] = [event]
            await asyncio.sleep(self.latency)
            data["album"] = self.album_data.pop(group_id)
            return await handler(event, data)

        self.album_data[group_id].append(event)
        return


user_router.message.middleware(AlbumMiddleware())


class GenStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_aspect = State()


class DialogStates(StatesGroup):
    waiting_for_prompt = State()


async def prompt_menu(user_id, selected_model, db: Database):
    """Формирует текст и клавиатуру для меню ввода промпта."""
    durations = MODEL_DURATIONS.get(selected_model, ["5 сек"])
    current_duration = USER_DURATIONS.get(user_id, durations[0])
    aspect = USER_ASPECT_RATIO.get(user_id, "16:9")

    if selected_model == 'Veo3 - видео сценарию':
        prompt_lines = [
            "💬 Напиши промпт для генерации видео.",
            "Вы можете прикрепить фото для референса.",
            "",
            f"Стоимость: <b>{get_crystal_price_str(VEO_COST)}</b>"
        ]
        text = "\n".join(prompt_lines)
        keyboard = get_prompt_keyboard(user_id, selected_model)
        return text, keyboard

    if selected_model == 'Sora - Генерация изображений':
        user = await db.user.get_user(user_id)
        prompt_lines = [
            "💬 Напиши промпт для генерации изображения.",
            "Вы также можете прикрепить фото для референса (необязательно).",
            "",
            f"Стоимость: <b>{get_crystal_price_str(IMAGE_GPT_COST)}</b>"
        ]
        text = "\n".join(prompt_lines)
        keyboard = get_prompt_keyboard(user_id, selected_model)
        return text, keyboard

    if selected_model == 'Sora - Генерация изображений|text':
        user = await db.user.get_user(user_id)
        free = False
        if not user.last_generation or (user.last_generation.day != datetime.datetime.now().day):
            free = True
        prompt_lines = [
            "💬 Напиши промпт для генерации изображения.",
            f"Стоимость: <b>{get_crystal_price_str(TEXT_GPT_COST if not free else 0)}</b>"
        ]
        text = "\n".join(prompt_lines)
        keyboard = get_prompt_keyboard(user_id, selected_model.replace('|text', ''))
        return text, keyboard

    prompt_lines = [
        "💬 Напиши сценарий для видео или отправь фото с подписью:", "",
        f"Соотношение сторон: <b>{aspect}</b>",
        f"Длительность: <b>{current_duration}</b>",
    ]

    pixverse_mode = None
    resolution = "720p"  # Установлено по умолчанию, можно сделать настраиваемым
    if selected_model == "Pixverse v4.5":
        pixverse_mode = USER_PIXVERSE_MODE.get(user_id, "smooth")
        prompt_lines.append(f"Режим: <b>{'Smooth' if pixverse_mode == 'smooth' else 'Normal'}</b>")

    cost = calculate_generation_cost(selected_model, current_duration, pixverse_mode, resolution)
    prompt_lines.append(f"Стоимость: <b>{get_crystal_price_str(cost)}</b>")

    text = "\n".join(prompt_lines)
    keyboard = get_prompt_keyboard(user_id, selected_model)
    return text, keyboard


async def example_menu(selected_model: str, text: bool = False) -> tuple:
    """Формирование текста с примером, примера генерации и клавиатуры для меню выбранной модели"""
    model = MODELS_EXAMPLE_OBJECT[selected_model if not text else selected_model + '|text']
    url = model.get("manual")
    example = model.get("examples")[0]
    text = (f'{model.get("name")}\n<b>Описание:</b> <em>{model.get("description")}</em>\n\n'
            f'<u>{example.get("name") if example.get("name") else ""}</u>'
            f'{example.get("prompt")}\n\n🔗Инструкция: {url}')
    media = FSInputFile(path=example.get('media'))
    keyboard = get_exemple_keyboard(url)
    return text, [media, example.get("content_type")], keyboard


async def message_start(message: types.Message, db: Database, bot: Bot):
    """Отправляет кастомное стартовое сообщение, если оно настроено в админке."""
    copy_message = await db.start_message.get_message()
    if copy_message:
        keyboard = None
        if copy_message.reply_markup:
            try:
                keyboard_data = json.loads(copy_message.reply_markup)
                keyboard = await json_to_keyboard(keyboard_data)
            except (json.JSONDecodeError, TypeError) as e:
                logging.error(f"Ошибка при декодировании клавиатуры из JSON: {e}")

        await asyncio.sleep(copy_message.delay_seconds)

        await bot.copy_message(
            message_id=copy_message.message_id,
            chat_id=message.chat.id,
            from_chat_id=copy_message.chat_id,
            reply_markup=keyboard
        )


# --- Хендлеры ---

@user_router.message(Command("start"))
async def cmd_start(message: types.Message, db: Database, state: FSMContext, bot: Bot):
    await state.clear()

    parts = message.text.split(' ', 1)
    param = parts[1] if len(parts) > 1 else ""

    url_name = ""
    ref_id = None

    if param.startswith('ad_url_start_'):
        url_name = param.replace('ad_url_start_', '')
    elif param:
        try:
            ref_id = int(param)
        except Exception:
            ...


    user, is_new = await db.user.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        ad_url=url_name or None,
        ref_id=ref_id or None
    )

    if is_new and ref_id:
        try:
            ref_id = int(ref_id)
            await state.update_data(ref_id=ref_id)
        except Exception:
            ...

    if url_name:
        if is_new:
            logging.info(f"User {user.id} is new, ad_url: {url_name}. Updating unique stats.")
            await db.ad_url.increment_counters(name=url_name, all_users=1, unique_users=1)
            await db.statistic.increment_counters(name='users', now_month=1)
        else:
            logging.info(f"User {user.id} is existing, ad_url: {url_name}. Updating non-unique stats.")
            await db.ad_url.increment_counters(name=url_name, all_users=1, not_unique_users=1)

    op_answer = await check_user_op(db, bot, message.from_user.id)
    if op_answer is not None:
        await message.answer(
            '📢 Чтобы продолжить пользоваться ботом, подпишитесь на наши каналы!\n\n'
            'Это обязательное условие — подписка помогает нам оставлять генерации бесплатными. \n\n'
            '👇 После подписки нажмите «Подписался»',
            reply_markup=subscribe_button_keyboard(op_answer)
        )
        await state.update_data(not_passed=[channel[0] for channel in op_answer])
        return

    user_id = message.from_user.id
    chosen_model = USER_MODELS.get(user_id)
    model_text = f"<b>{chosen_model}</b>" if chosen_model else "<i>не выбрана</i>"
    is_unlim = await db.user.check_unlim_status(message.from_user.id)

    markup = get_main_menu_keyboard()

    if not is_new:
        if not user.last_generation or (user.last_generation.day != datetime.datetime.now().day):
            free_generation = '🎁Вам доступна одна бесплатная генерация'
        else:
            next_generation = user.last_generation + datetime.timedelta(days=1)
            free_generation = f'Следующая бесплатная генерация будет доступна <em>{next_generation.strftime("%Y-%m-%d %H:%M")}</em>🕜'
        text = (
            "<b>👋 Добро пожаловать в Super GPT!</b>\n\n"
            "🤖 Здесь вы можете создавать уникальные тексты, генерировать изображения и видео с помощью нейросетей "
            "и экспериментировать с искусственным интеллектом!\n\n"
            f"Ваш баланс: <b>{user.generations if not is_unlim else '∞'}</b> 💎\n"
            f'{free_generation}\n\n'
            f"<b>📌 Совет:</b> Чтобы всегда иметь к нам быстрый доступ — закрепите бота в верхней части списка чатов. "
            f"Так вы не упустите ни одной возможности творить с помощью AI!"
            "Что хочешь сгенерировать сегодня?"
        )
        await message.answer_video(
            video=FSInputFile(path='medias/menu_video.MP4'),
            caption=text, reply_markup=markup, parse_mode='HTML')
    else:
        text = ('<b>👋 Добро пожаловать в SUPER GPT!</b>\n<b>Ты попал в мир нейросетей нового поколения!</b>'
                '\n\nНа твой баланс зачислено 20 💎, используй их! \n\nНаш бот — твой личный ассистент с '
                'искусственным интеллектом, который умеет:\n\n🎬 Создавать видео с аудио-дорожкой и по сценарию\n'
                '📢 Делать рекламные ролики и баннеры\n🖼 Генерировать изображения по твоим запросам\n'
                '📥 Импортировать фото и текст для работы\n⚡️ Работает на мощных ИИ: Veo3, Kling v2.1, '
                'Seedance 1 Lite, Minimax, Sora\n\n<b>Чтобы начать:</b>\n\n- Получи 20 алмазов на баланс в подарок!\n'
                '- Пригласи друзей — за каждого получаешь бонус, а также шанс 1 раз бесплатно использовать Sora.\n'
                '-Или пополни баланс Рублями или STARS\n\n<b>Готов создавать крутой контент с нейросетями? </b>'
                '\nЖми на кнопки ниже и погнали! 🚀')
        await message.answer(
            text=text,
            reply_markup=markup
        )

    await message_start(message, db, bot)


@user_router.callback_query(F.data == "back_main")
async def cb_back_main(callback: types.CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    user = await db.user.get_user(user_id)
    if not user:
        await callback.answer("Произошла ошибка, попробуйте перезапустить бота /start", show_alert=True)
        return

    chosen_model = USER_MODELS.get(user_id)
    model_text = f"<b>{chosen_model}</b>" if chosen_model else "<i>не выбрана</i>"
    is_unlim = await db.user.check_unlim_status(user_id)
    text = (
        "<b>👋 Добро пожаловать в Super GPT!</b>\n\n"
        "🤖 Здесь вы можете создавать уникальные тексты, генерировать изображения и видео с помощью нейросетей "
        "и экспериментировать с искусственным интеллектом!\n\n"
        f"Ваш баланс: <b>{user.generations if not is_unlim else '∞'}</b> 💎\n\n"
        f"<b>📌 Совет:</b> Чтобы всегда иметь к нам быстрый доступ — закрепите бота в верхней части списка чатов. "
        f"Так вы не упустите ни одной возможности творить с помощью AI!"
        "Что хочешь сгенерировать сегодня?"
    )
    markup = get_main_menu_keyboard()
    try:
        await callback.message.delete()
        await callback.message.answer_video(
            video=FSInputFile(path='medias/menu_video.MP4'), caption=text, reply_markup=markup)
    except Exception:
        await callback.answer()


@user_router.callback_query(F.data == "choose_model")
async def cb_choose_model(callback: types.CallbackQuery):
    text = f"Выбери модель для генерации:"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=model_menu(), parse_mode='HTML')


@user_router.callback_query(F.data.startswith("model_"))
async def cb_model_selected(callback: types.CallbackQuery, state: FSMContext):
    model = callback.data.replace("model_", "")
    USER_MODELS[callback.from_user.id] = model
    await callback.message.delete()
    text, media_data, keyboard = await example_menu(model)
    if media_data[1] == 'photo':
        await callback.message.answer_photo(
            photo=media_data[0],
            caption=text,
            reply_markup=keyboard
        )
    if media_data[1] == 'video':
        await callback.message.answer_video(
            video=media_data[0],
            caption=text,
            reply_markup=keyboard
        )
    if media_data[1] == 'gif':
        await callback.message.answer_animation(
            animation=media_data[0],
            caption=text,
            reply_markup=keyboard
        )


@user_router.callback_query(F.data == 'start_chat')
async def start_gpt_chat(callback: types.CallbackQuery, state: FSMContext):
    assistant_id, thread_id = await get_assistant_and_thread()
    await state.update_data(assistant_id=assistant_id, thread_id=thread_id)
    await state.set_state(DialogStates.waiting_for_prompt)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Закончить диалог ✖️', callback_data='back_main')]])
    text = ('🤖 SUPER GPT активен!\n\nЯ готов ответить на любые вопросы и помочь с идеями'
            '\nСпроси что-нибудь прямо сейчас!')
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=FSInputFile(path='medias/start_gpt.jpg'),
        caption=text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@user_router.message(DialogStates.waiting_for_prompt)
async def answer_gpt(message: types.Message, state: FSMContext):
    try:
        await message.bot.edit_message_reply_markup(
            chat_id=message.from_user.id,
            message_id=message.message_id - 1
        )
    except Exception:
        ...
    msg_to_del = await message.answer('✍️')
    state_data = await state.get_data()
    assistant_id, thread_id = state_data.get('assistant_id'), state_data.get('thread_id')
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='Закончить диалог ✖️', callback_data='back_main')]])
    prompt = message.text if message.text else message.caption
    answer = await get_text_answer(prompt, assistant_id, thread_id)
    if answer is None:
        answer = '❗️Во время операции произошла какая-то ошибка, пожалуйста попробуйте снова'
    await msg_to_del.delete()
    await message.answer(answer, reply_markup=keyboard)


@user_router.callback_query(F.data == 'for_students')
async def open_students_menu(callback: types.CallbackQuery):
    text = 'В данном меню собраны нейронные сети, которые могут помочь вам с учебой:'  # сгенерировать текст в qwen
    keyboard = get_student_menu()
    await callback.message.delete()
    await callback.message.answer(text=text, reply_markup=keyboard, parse_mode='HTML')


@user_router.callback_query(F.data == 'photo_menu')
async def open_photo_menu(callback: types.CallbackQuery):
    text = ('✅ У вас есть 1 бесплатная попытка в сутки на генерацию с текстом. \n\n▶️ Генерация фото по тексту – '
            'это когда ты пишешь, что хочешь увидеть (например, "кот в очках на пляже"), а компьютер с помощью '
            'искусственного интеллекта сам «придумывает» и рисует такую картинку. Он не берёт фото из интернета, '
            'а создаёт новое изображение, опираясь на то, что знает о котах, очках и пляже.  (1 бесплатно)\n\n'
            '📸Генерация фото по тексту и фото (с референсом) – это когда ты не только пишешь, что хочешь (например, '
            '"сделай в этом же стиле собаку в очках"), но ещё и показываешь пример (например, картинку кота в очках). '
            'Тогда ИИ использует твою фотографию как образец — он сохраняет стиль, позу, цвета и рисует что-то '
            'похожее, но уже с новым содержанием по твоему описанию. <b>(Только платные)</b>')
    keyboard = get_photo_menu()
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=FSInputFile(path='medias/photo_menu.jpg'), caption=text,
        reply_markup=keyboard, parse_mode='HTML'
    )


@user_router.callback_query(F.data.startswith("choose_photo"))
async def open_sora_menu(callback: types.CallbackQuery, state: FSMContext):
    mode = callback.data.split('|')[1]
    user_id = callback.from_user.id
    await callback.message.delete()
    await state.clear()
    USER_MODELS[callback.from_user.id] = 'Sora - Генерация изображений'
    model = USER_MODELS.get(callback.from_user.id)
    if mode == 'photo':
        text, media_data, keyboard = await example_menu(model)
        await callback.message.answer_photo(
            photo=media_data[0],
            caption=text,
            reply_markup=keyboard
        )
    else:
        await state.update_data(mode='text')
        text, media_data, keyboard = await example_menu(model, True)
        await callback.message.answer_photo(
            photo=media_data[0],
            caption=text,
            reply_markup=keyboard
        )


@user_router.callback_query(F.data == "start_gen")  # функция начала генерации
async def cb_start_gen(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    model = USER_MODELS.get(user_id)
    data = await state.get_data()
    USER_MODELS[callback.from_user.id] = model
    if data.get('mode'):
        model += '|text'
    text, keyboard = await prompt_menu(callback.from_user.id, model, db)
    await state.set_state(GenStates.waiting_for_prompt)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@user_router.callback_query(F.data == "choose_aspect", GenStates.waiting_for_prompt)
async def cb_choose_aspect(callback: types.CallbackQuery, state: FSMContext):
    aspect = USER_ASPECT_RATIO.get(callback.from_user.id, "16:9")
    await callback.message.edit_text(
        "Выберите подходящее соотношение сторон для вашего видео:",
        reply_markup=aspect_menu(aspect)
    )
    await state.set_state(GenStates.waiting_for_aspect)


@user_router.callback_query(F.data.startswith("aspect_"), GenStates.waiting_for_aspect)
async def cb_aspect_selected(callback: types.CallbackQuery, state: FSMContext, db: Database):
    aspect = callback.data.replace("aspect_", "")
    user_id = callback.from_user.id
    USER_ASPECT_RATIO[user_id] = aspect
    selected_model = USER_MODELS.get(user_id)
    if not selected_model:
        await cb_back_main(callback, state)  # Возврат в главное меню, если модель не выбрана
        return

    prompt_text, prompt_kb = await prompt_menu(user_id, selected_model, db)
    await callback.message.edit_text(prompt_text, reply_markup=prompt_kb, parse_mode='HTML')
    await state.set_state(GenStates.waiting_for_prompt)


@user_router.callback_query(F.data == "choose_duration", GenStates.waiting_for_prompt)
async def cb_choose_duration(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    selected_model = USER_MODELS.get(user_id)
    if not selected_model: return
    await callback.message.edit_reply_markup(reply_markup=duration_menu(selected_model, user_id))


@user_router.callback_query(F.data.startswith("set_duration_"), GenStates.waiting_for_prompt)
async def cb_set_duration(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    selected_model = USER_MODELS.get(user_id)
    if not selected_model: return

    d = callback.data.replace("set_duration_", "")
    USER_DURATIONS[user_id] = d

    prompt_text, prompt_kb = await prompt_menu(user_id, selected_model, db)
    await callback.message.edit_text(prompt_text, reply_markup=prompt_kb, parse_mode='HTML')


@user_router.callback_query(F.data == "back_to_prompt")
async def cb_back_to_prompt(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    selected_model = USER_MODELS.get(user_id)
    if not selected_model: return

    prompt_text, prompt_kb = await prompt_menu(user_id, selected_model, db)
    await callback.message.edit_text(prompt_text, reply_markup=prompt_kb, parse_mode='HTML')
    await state.set_state(GenStates.waiting_for_prompt)


@user_router.callback_query(F.data == "toggle_pixverse_mode", GenStates.waiting_for_prompt)
async def cb_toggle_pixverse_mode(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    selected_model = USER_MODELS.get(user_id)
    if not selected_model: return

    current = USER_PIXVERSE_MODE.get(user_id, "smooth")
    USER_PIXVERSE_MODE[user_id] = "normal" if current == "smooth" else "smooth"

    prompt_text, prompt_kb = await prompt_menu(user_id, selected_model, db)
    await callback.message.edit_text(prompt_text, reply_markup=prompt_kb, parse_mode='HTML')


@user_router.callback_query(F.data == "telegram_stars_callback")
async def balance_method_choose_payment_func(call: types.CallbackQuery):
    await call.message.edit_text('Выберите пакет для пополнения баланса:', reply_markup=balance_stars_menu())


@user_router.callback_query(F.data == "bank_card_callback")
async def balance_method_choose_payment_func(call: types.CallbackQuery):
    await call.message.edit_text('Выберите пакет для пополнения баланса:', reply_markup=balance_rubles_menu())


@user_router.callback_query(F.data == "balance")
async def cb_balance(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Выберите способ для пополнения баланса:", reply_markup=balance_choose_menu())


@user_router.callback_query(F.data.startswith("buy_rub_"))
async def buy_generations_rubles_menu(callback: types.CallbackQuery, db: Database):
    amount_str = callback.data.replace("buy_rub_", "")
    amount = 'unlim' if amount_str == 'unlim' else int(amount_str)
    price = RUB_PRICES[amount]

    payment = Payment.create({
        "amount": {
            "value": price,
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://web.telegram.org"
        },
        "capture": True,
        "description": f'Покупка {amount} Генераций ID: {callback.from_user.id}',
        'receipt': {"customer": {
            "email": 'danila.timonin12@mail.ru',
        },
            'items': [{
                "description": f'Покупка {amount} Нейро-коинов',
                "quantity": 1.00,
                "amount": {
                    "value": str(price),
                    "currency": "RUB"
                },
                "vat_code": 1,
                "payment_mode": "full_prepayment",
                "payment_subject": "another"
            }]}
    })

    payment_data = json.loads(payment.json())
    payment_id = payment_data['id']
    payment_url = (payment_data['confirmation'])['confirmation_url']

    await callback.message.answer(
        f"<b>{price}₽ СЧЁТ</b>\nПокупка {amount} генераций\n"
        f"{'Активно только в течении недели' if amount == 'unlim' else ''}\n"
        "<i>Данная ссылка действительна в течении 10 минут</i>",
        reply_markup=url_button(payment_url),
        parse_mode='HTML'
    )

    # Запускаем проверку платежа в фоне
    asyncio.create_task(process_successful_payment(payment_id, callback, db, amount, price))
    await callback.answer()


@user_router.callback_query(F.data.startswith('buy_stars_'))
async def buy_generations_stars_menu(call: types.CallbackQuery):
    amount_str = call.data.replace("buy_stars_", "")
    amount = 'unlim' if amount_str == 'unlim' else int(amount_str)

    prices = [LabeledPrice(label="XTR", amount=STARS_PRICES[amount])]

    payload = str(amount)
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=f'Пополнение {"♾️" if amount == "unlim" else amount}',
        description=f'Пополнение {"♾️" if amount == "unlim" else amount}',
        prices=prices,
        provider_token="",
        payload=payload,
        currency="XTR"
    )


async def process_successful_payment(payment_id, callback, db: Database, amount, price):
    """Обрабатывает успешный платеж после проверки."""
    is_paid, _ = await check_payment(payment_id)
    if is_paid:
        user_id = callback.from_user.id
        if amount == 'unlim':
            await db.user.grant_unlim_access(user_id)
            await db.user.increase_value(user_id, 'generations', 50)
        else:
            user = await db.user.get_user(user_id)
            if user.ref_id:
                await db.user.increase_value(user.ref_id, 'generations', round(amount * 0.1))
            await db.user.increase_value(user_id, 'generations', amount)
            await db.payments.create_payment(user_id, callback.from_user.username, price, 'card')

        await db.statistic.increment_counters('income', all_time=price, now_month=price)
        ad_url = await db.user.get_user_value(user_id, 'ad_url')
        if ad_url:
            await db.ad_url.increment_counters(ad_url, income=int(price))

        await callback.message.answer('✅ Оплата прошла успешно. Ваш баланс пополнен!')


@user_router.callback_query(F.data == "account")
async def cb_account(callback: types.CallbackQuery, db: Database):
    user_id = callback.from_user.id
    is_unlim = await db.user.check_unlim_status(user_id)
    user = await db.user.get_user(user_id)
    if not user:
        await callback.answer("Произошла ошибка, попробуйте перезапустить бота /start", show_alert=True)
        return
    text = (
        "<b>Мой аккаунт</b>\n\n"
        f"<b>Осталось генераций:</b> {user.generations if not is_unlim else '∞'} 💎\n"
        f"<b>Выполнено генераций:</b> {user.completed}\n\n"
        f"👥<b>Реферальная программа</b>\nПриглашайте друзей и зарабатывайте бонусы!\n"
        f"⚡️ Получайте 10 💎 за каждого приглашённого пользователя\n⚡️ Зарабатывайте 10% от всех его пополнений\n"
        f"Используйте реферальную систему и получайте вознаграждение за активность!🔥\n\n<b>• Приглашённых:</b> {user.ref_count}\n"
        f"• Ссылка: `<code>https://t.me/{config.BOT_NAME}?start={user_id}</code>`\n\n"
        "<b>Поддержка:</b> @supergptsupportbot"
    )
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=get_account_keyboard(user_id), parse_mode="HTML")


@user_router.message(GenStates.waiting_for_prompt, F.content_type.in_({'text', 'photo'}))
async def handle_prompt(
        message: types.Message,
        state: FSMContext,
        db: Database,
        bot: Bot,
        album: list[types.Message]
):
    user_id = message.from_user.id
    user = await db.user.get_user(user_id)
    model_key = USER_MODELS.get(user_id)
    data = await state.get_data()
    mode = data.get('mode')
    if not model_key:
        await message.answer("Сначала выбери модель через главное меню.")
        await state.clear()
        return

    if mode and message.photo:
        await message.answer('Промпт должен быть быть только текстовым, пожалуйста попробуйте снова')
        return

    # 1. Находим сообщение с текстом (промптом)
    prompt_message = next((msg for msg in album if msg.caption or msg.text), None)
    prompt = prompt_message.caption if prompt_message and prompt_message.caption else prompt_message.text if prompt_message else None

    if not prompt:
        await message.answer("Пожалуйста, добавьте текстовое описание (промпт).")
        return

    # 2. Определяем параметры и стоимость для каждой модели
    params = {"prompt": prompt}
    cost = 0
    image_urls = []  # Инициализируем заранее

    # Загружаем изображения один раз, если они есть
    if any(msg.photo for msg in album):
        print('pass photo')
        image_urls = await download_and_upload_images(bot, album)
    if model_key == 'Sora - Генерация изображений' and mode is None:
        cost = IMAGE_GPT_COST
        params["model_name"] = MODELS[model_key]
        if image_urls:
            params["image_urls"] = image_urls

    elif model_key == 'Sora - Генерация изображений':
        if not user.last_generation or (user.last_generation.day != datetime.datetime.now().day):
            await db.user.update_user(user_id, last_generation=datetime.datetime.now())
            cost = 0
        else:
            cost = TEXT_GPT_COST

    elif model_key == 'Veo3 - видео сценарию':
        cost = VEO_COST
        params["model_name"] = MODELS[model_key]
        params["translate"] = True
        if image_urls:
            params["image_url"] = image_urls[0]

    else:
        aspect_ratio = USER_ASPECT_RATIO.get(user_id, "16:9")
        if model_key in MODEL_DURATIONS:
            duration_str = USER_DURATIONS.get(user_id, MODEL_DURATIONS[model_key][0])
            cost = calculate_generation_cost(model_key, duration_str)
            params["duration"] = int(duration_str.replace(" сек", ""))
        else:  # Если у модели нет выбора длительности (как у Minimax)
            cost = 999

        params["model_name"] = MODELS[model_key]
        if model_key != 'Minimax - Видео по фото':
            params["aspect_ratio"] = aspect_ratio

        if image_urls:

            image_field = MODEL_IMAGE_FIELD.get(model_key)
            if image_field:
                params[image_field] = image_urls[0]
    # 3. Списываем баланс

    await state.clear()

    status_message = "⏳ Принял. Отправляю запрос..."
    if image_urls:
        status_message = "⏳ Принял. Загрузил фото и отправляю на обработку..."

    if not await db.user.process_generation(user_id, cost):
        await message.answer("У вас закончились генерации или произошла ошибка списания. Пополните баланс!",
                             reply_markup=balance_choose_menu())
        return
    msg = await message.answer(f"{status_message} Это будет стоить {cost} 💎")
    try:
        # 4. Отправляем запрос в API
        if model_key == 'Sora - Генерация изображений':
            print('sora generate')
            result_urls = await generate_image(image_urls, prompt)
        else:
            result_urls = await generate_on_nexus(params)

        if not result_urls:
            raise RuntimeError("API не вернул результат.")

        await msg.delete()
        safe_prompt = html.escape(params["prompt"])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='⬅️ На главное меню', callback_data='back_main')]])
        if model_key == 'Sora - Генерация изображений':
            media_group = [InputMediaPhoto(media=url) for url in result_urls]
            if media_group:
                media_group[0].caption = f"🖼️ <b>Готово!</b>\n<b>Промпт:</b> <code>{safe_prompt}</code>"
                media_group[0].parse_mode = 'HTML'
                message_to_copy = await bot.send_media_group(chat_id=user_id, media=media_group)
                await bot.copy_messages(
                    chat_id=-1002858090617,
                    from_chat_id=message.chat.id,
                    message_ids=[msg.message_id for msg in message_to_copy]
                )
        else:  # Для всех видеомоделей, включая Veo
            video_url = result_urls[0]
            caption = f"🎬 <b>Видео готово!</b>\n<b>Промпт:</b> <code>{safe_prompt}</code>\n<b>Модель:</b> {model_key}"
            await message.answer_video(video_url, caption=caption, parse_mode='HTML')

        await message.answer('Вы можете вернуться на главное меню', reply_markup=keyboard)
        await db.statistic.increment_counters(model_key, all_time=1, now_month=1)

    except Exception as e:
        logging.error(f"Ошибка генерации для модели {model_key}: {e}", exc_info=True)
        await db.user.increase_value(user_id, 'generations', cost)
        await db.user.increase_value(user_id, 'completed', -1)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⬅️ Назад', callback_data='back_main')]])
        await msg.edit_text(f"❌ <b>Ошибка:</b>\n<code>{html.escape(str(e))}</code>\n\nВаши 💎 возвращены на баланс.", reply_markup=keyboard,
                            parse_mode='HTML')


@user_router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_q: PreCheckoutQuery):
    """Подтверждает любой предварительный запрос на оплату."""
    await pre_checkout_q.answer(ok=True)


@user_router.message(F.successful_payment)
async def successful_payment_handler(message: Message, db: Database):
    """
    Обрабатывает успешную оплату через Telegram Stars.
    """
    user_id = message.from_user.id
    logging.info(f"Successful payment from {user_id}: {message.successful_payment.invoice_payload}")

    amount = message.successful_payment.invoice_payload

    if amount == 'unlim':
        await db.user.grant_unlim_access(user_id)
        await db.user.increase_value(user_id, 'generations', 50)
    else:
        user = await db.user.get_user(user_id)
        if user.ref_id:
            await db.user.increase_value(user.ref_id, 'generations', round(int(amount) * 0.1))
        await db.user.increase_value(user_id, 'generations', int(amount))
        await db.payments.create_payment(user_id, message.from_user.username, amount, 'stars')

    await message.answer('✅ Оплата прошла успешно. Ваш баланс пополнен!')


@user_router.callback_query(F.data == 'check_op')
async def check_op_user_func(call: types.CallbackQuery, db: Database, state: FSMContext, bot: Bot):
    channels = await db.subscription.get_all_channels()
    answer = await check_user_op(db, bot, call.from_user.id)
    if answer is None:
        data = await state.get_data()
        ref_id = data.get('ref_id')
        if ref_id:
            await db.user.increase_value(ref_id, 'generations', 10)
            await db.user.increase_value(ref_id, 'ref_count', 1)
        await db.user.update_user(call.from_user.id, passed=True)
        op_ids = data.get('not_passed')
        for op_id in op_ids:
            await db.subscription.increment_subs_count(op_id)
        await call.message.edit_text('Вы можете пользоваться ботом! ✅')
    else:
        await call.answer('Вы не подписались на каналы!', show_alert=True)
