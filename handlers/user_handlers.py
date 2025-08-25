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
    get_photo_menu, choose_veo_keyboard, choose_seedance_keyboard, choose_hailuo_keyboard,
    USER_MODELS, USER_DURATIONS, USER_PIXVERSE_MODE, USER_ASPECT_RATIO
)
from services.nexus_api import generate_on_nexus, generate_on_api
from services.replicate_api import generate_replicate_async
from services.payment_service import check_payment
from utils.helpers import calculate_generation_cost, get_crystal_price_str, download_video, check_user_op, \
    download_and_upload_images, check_user_op_single
from utils.chat_gpt import get_text_answer, generate_image, get_assistant_and_thread
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
    durations = MODEL_DURATIONS.get(selected_model)
    current_duration = USER_DURATIONS.get(user_id, durations[0]) if durations else None
    aspect = USER_ASPECT_RATIO.get(user_id, "16:9")

    if selected_model in VEO_MODELS.keys():
        prompt_lines = [
            "💬 Напиши промпт для генерации видео.",
            "Вы можете прикрепить фото для референса.",
            "",
            f"Стоимость: <b>{get_crystal_price_str(VEO_COST.get(selected_model))}</b>"
        ]
        text = "\n".join(prompt_lines)
        keyboard = get_prompt_keyboard(user_id, selected_model)
        return text, keyboard

    if selected_model == 'Sora - Генерация изображений':
        user = await db.user.get_user(user_id)
        if user.generations >= 40:
            prompt_lines = [
                "💬 Напиши промпт для генерации изображения.",
                "Вы также можете прикрепить фото для референса (необязательно).",
                "",
                f"Стоимость: <b>{get_crystal_price_str(IMAGE_GPT_COST)}</b>"
            ]
            text = "\n".join(prompt_lines)
            keyboard = get_prompt_keyboard(user_id, selected_model)
            return text, keyboard
        else:
            text = (f'⚡️Цена генерации: 40💎\nТвой баланс составляет: {user.generations} 💎\n\n'
                    f'🎁Получайте 10 💎 за каждого приглашённого пользователя\n💸 Зарабатывайте 10% от всех его пополнений'
                    f'\n\n<code>https://t.me/{config.BOT_NAME}?start={user_id}</code>\nИспользуйте реферальную систему '
                    f'и получайте вознаграждение за активность!\n\n👇Или пополняй баланс по кнопке ниже')
            keyboard = balance_choose_menu()
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
    if selected_model in HAILUO_MODELS.keys():
        prompt_lines = [
            "💬 Напиши сценарий для видео или отправь фото с подписью:", "",
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


async def example_menu(selected_model: str, mode: str | None = None) -> tuple:
    """Формирование текста с примером, примера генерации и клавиатуры для меню выбранной модели"""
    if mode:
        model = MODELS_EXAMPLE_OBJECT[selected_model if mode == 'photo' else selected_model + '|text']
    else:
        model = MODELS_EXAMPLE_OBJECT[selected_model]
    url = model.get("manual")
    example = model.get("examples")[0]
    text = (f'{model.get("name")}\n<b>Описание:</b> {model.get("description")}\n\n'
            f'<u>{example.get("name") if example.get("name") else ""}</u>'
            f'{example.get("prompt")}\n\n🔗Инструкция: {url}')
    media = FSInputFile(path=example.get('media'))
    if selected_model.startswith('Sora - Генерация изображений'):
        keyboard = get_exemple_keyboard(url, True)
    else:
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
            "🤖 Здесь вы можете создавать уникальные тексты, генерировать изображения и видео с помощью нейросетей!\n\n"
            f"Ваш баланс: <b>{user.generations if not is_unlim else '∞'}</b> 💎\n"
            f'{free_generation}\n\n'
            f"<b>📌 Совет:</b> Закрепляй бота и используй промты, которые мы оставили в каждой генеративной модели."
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
    is_unlim = await db.user.check_unlim_status(user_id)
    if not user.last_generation or (user.last_generation.day != datetime.datetime.now().day):
        free_generation = '🎁Вам доступна одна бесплатная генерация'
    else:
        next_generation = user.last_generation + datetime.timedelta(days=1)
        free_generation = f'Следующая бесплатная генерация будет доступна <em>{next_generation.strftime("%Y-%m-%d %H:%M")}</em>🕜'
    text = (
        "<b>👋 Добро пожаловать в Super GPT!</b>\n\n"
        "🤖 Здесь вы можете создавать уникальные тексты, генерировать изображения и видео с помощью нейросетей!\n\n"
        f"Ваш баланс: <b>{user.generations if not is_unlim else '∞'}</b> 💎\n"
        f'{free_generation}\n\n'
        f"<b>📌 Совет:</b> Закрепляй бота и используй промты, которые мы оставили в каждой генеративной модели."
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
async def cb_model_selected(callback: types.CallbackQuery, db: Database, state: FSMContext):
    model = callback.data.replace("model_", "")
    USER_MODELS[callback.from_user.id] = model
    await callback.message.delete()
    if model == 'Veo3 - видео сценарию':
        text = ('🔹 Veo 3\n\nVeo 3 — делает реально красивые, «кинематографичные» видео. Качество 🔝.\n\n'
                'Veo 3 Fast — то же самое, но работает быстрее и дешевле, качество попроще (идеально для TikTok/Reels).'
                '\n\n☝️Для серьёзного и «вау-эффекта» - Veo3. Для быстрых роликов в соцсети - Veo3 Fast.')
        await callback.message.answer(
            text=text,
            reply_markup=choose_veo_keyboard()
        )
        return
    if model == 'Seedance 1 — видео по тексту':
        text = ('🔹 Hailuo 02\n\nHailuo 02 — картинка суперчёткая, реалистичная, прям как в фильме.\n\n'
                'Hailuo 02 Fast — версия «на скорость»: делает видео быстрее, но качество чуть ниже.\n\n'
                '☝️Если нужен «вау-визуал» - бери Hailuo. Если важнее быстро и удобно — Fast.')
        await callback.message.answer(
            text=text,
            reply_markup=choose_seedance_keyboard()
        )
        return
    if model == 'Haiuo v0.2 — видео текст+фото':
        text = ('🔹 Seedance\n\nLite — это как «лайт-версия» приложения: самое простое, чтобы попробовать.\n\n'
                'Pro — это как «премиум»: больше функций, настроек и возможностей для крутого результата.\n\n'
                '☝️Если хочешь быстро и просто - бери Lite. Если любишь «по максимуму» - тогда Pro.')
        await callback.message.answer(
            text=text,
            reply_markup=choose_hailuo_keyboard()
        )
        return
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


@user_router.callback_query(F.data.startswith('sub_model_choose'))
async def start_veo_gen(callback: types.CallbackQuery, state: FSMContext, db: Database):
    sub_model = callback.data.split('|')[-1]
    user_id = callback.from_user.id
    model = USER_MODELS.get(user_id)
    await state.update_data(sub_model=sub_model)
    text, media_data, keyboard = await example_menu(model)
    await callback.message.delete()
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
    await state.set_state(DialogStates.waiting_for_prompt)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Закончить диалог ✖️', callback_data='back_main')]])
    text = ('🤖 SUPER GPT активен!\n\nЯ готов ответить на любые вопросы и помочь с идеями'
            '\nСпроси что-нибудь прямо сейчас!')
    assistant_id, thread_id = await get_assistant_and_thread()
    await state.update_data(assistant_id=assistant_id, thread_id=thread_id)
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
    if not answer:
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
    text = ('✅ У вас есть 1 бесплатная попытка в сутки на генерацию с текстом. \n\n<b>▶️ Генерация фото по тексту</b> '
            '– это когда ты пишешь, что хочешь увидеть (например, "кот в очках на пляже"), а ИИ сам «придумывает» '
            'и рисует такую картинку. (1 бесплатно)\n\n<b>📸Генерация фото по тексту и фото (с референсом)</b> – ИИ '
            'использует твою фотографию как образец — он сохраняет стиль, позу, цвета, но уже с новым содержанием '
            'по твоему описанию. <b>(Только платные)</b>')
    keyboard = get_photo_menu()
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=FSInputFile(path='medias/photo_menu.jpg'), caption=text,
        reply_markup=keyboard, parse_mode='HTML'
    )


@user_router.callback_query(F.data.startswith("choose_photo"))
async def open_sora_menu(callback: types.CallbackQuery, db: Database, state: FSMContext):
    mode = callback.data.split('|')[1]
    user_id = callback.from_user.id
    await callback.message.delete()
    await state.clear()
    USER_MODELS[callback.from_user.id] = 'Sora - Генерация изображений'
    model = USER_MODELS.get(callback.from_user.id)
    if mode == 'photo':
        text, media_data, keyboard = await example_menu(model, 'photo')
        if media_data:
            await callback.message.answer_photo(
                photo=media_data[0],
                caption=text,
                reply_markup=keyboard
            )
        else:
            await callback.message.answer(
                text=text, reply_markup=keyboard
            )
    else:
        await state.update_data(mode='text')
        text, media_data, keyboard = await example_menu(model, 'text')
        await callback.message.answer_photo(
            photo=media_data[0],
            caption=text,
            reply_markup=keyboard
        )


@user_router.callback_query(F.data == "start_gen")  # функция начала генерации
async def cb_start_gen(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    data = await state.get_data()
    model = USER_MODELS.get(user_id) if not data.get('sub_model') else data.get('sub_model')
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
    data = await state.get_data()
    aspect = callback.data.replace("aspect_", "")
    user_id = callback.from_user.id
    USER_ASPECT_RATIO[user_id] = aspect
    selected_model = USER_MODELS.get(user_id) if not data.get('sub_model') else data.get('sub_model')
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
    data = await state.get_data()
    selected_model = USER_MODELS.get(user_id) if not data.get('sub_model') else data.get('sub_model')
    if not selected_model: return

    d = callback.data.replace("set_duration_", "")
    USER_DURATIONS[user_id] = d

    prompt_text, prompt_kb = await prompt_menu(user_id, selected_model, db)
    await callback.message.edit_text(prompt_text, reply_markup=prompt_kb, parse_mode='HTML')


@user_router.callback_query(F.data == "back_to_prompt")
async def cb_back_to_prompt(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    data = await state.get_data()
    selected_model = USER_MODELS.get(user_id) if not data.get('sub_model') else data.get('sub_model')
    if not selected_model: return

    prompt_text, prompt_kb = await prompt_menu(user_id, selected_model, db)
    await callback.message.edit_text(prompt_text, reply_markup=prompt_kb, parse_mode='HTML')
    await state.set_state(GenStates.waiting_for_prompt)


@user_router.callback_query(F.data == "toggle_pixverse_mode", GenStates.waiting_for_prompt)
async def cb_toggle_pixverse_mode(callback: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    data = await state.get_data()
    selected_model = USER_MODELS.get(user_id) if not data.get('sub_model') else data.get('sub_model')

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
        image_urls = await download_and_upload_images(bot, album)
    if model_key == 'Sora - Генерация изображений' and mode is None:
        cost = IMAGE_GPT_COST
        if image_urls:
            params["image_urls"] = image_urls

    elif model_key == 'Sora - Генерация изображений':
        if not user.last_generation or (user.last_generation.day != datetime.datetime.now().day):
            await db.user.update_user(user_id, last_generation=datetime.datetime.now())
            cost = 0
        else:
            cost = TEXT_GPT_COST

    elif model_key == 'Veo3 - видео сценарию':
        cost = VEO_COST.get(data.get('sub_model'))
        veo_model = VEO_MODELS.get(data.get('sub_model'))

        params["model_name"] = veo_model
        if image_urls:
            params["image_urls"] = image_urls

    else:
        if image_urls:
            params["image_urls"] = image_urls
        aspect_ratio = USER_ASPECT_RATIO.get(user_id, "16:9")
        params["model_name"] = MODELS.get(model_key)

        if model_key == 'Seedance 1 — видео по тексту':
            params["model_name"] = SEEDANCE_MODELS.get(data.get('sub_model'))
        if model_key == 'Haiuo v0.2 — видео текст+фото':
            params["model_name"] = HAILUO_MODELS.get(data.get('sub_model'))

        if model_key in MODEL_DURATIONS:
            duration_str = USER_DURATIONS.get(user_id, MODEL_DURATIONS[model_key][0])
            if model_key in ['Haiuo v0.2 — видео текст+фото', 'Seedance 1 — видео по тексту']:
                sub_model = data.get('sub_model')
                cost = calculate_generation_cost(sub_model, duration_str)
            else:
                cost = calculate_generation_cost(model_key, duration_str)
            params["duration"] = int(duration_str.replace(" сек", ""))
            params["aspect_ratio"] = aspect_ratio

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
            result_urls = await generate_image(prompt, image_urls)
        else:
            #result_urls = await generate_on_nexus(params)
            result_urls = await generate_on_api(params)

        if not result_urls:
            raise RuntimeError("API не вернул результат.")

        await msg.delete()
        safe_prompt = html.escape(params["prompt"])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='⬅️ На главное меню', callback_data='back_main')]])
        if model_key == 'Sora - Генерация изображений':
            media_group = [InputMediaPhoto(media=url) for url in result_urls]
            if media_group:
                media_group[0].caption = (f"🖼️ <b>Готово!</b>\n<b>Промпт:</b> <code>{safe_prompt}</code>\n\n"
                                          f"<a href='https://t.me/ai_generation_robot'>Бот для генерации</a>")
                media_group[0].parse_mode = 'HTML'
                message_to_copy = await bot.send_media_group(chat_id=user_id, media=media_group)
                await bot.copy_messages(
                    chat_id=-1002858090617,
                    from_chat_id=message.chat.id,
                    message_ids=[msg.message_id for msg in message_to_copy]
                )
        else:  # Для всех видеомоделей, включая Veo
            video = result_urls
            caption = (f"🎬 <b>Видео готово!</b>\n<b>Промпт:</b> <code>{safe_prompt}</code>\n"
                       f"<b>Модель:</b> {model_key}\n\n"
                       f"<a href='https://t.me/ai_generation_robot'>Бот для генерации</a>")
            msg = await message.answer_video(video, caption=caption, parse_mode='HTML')
            await bot.copy_message(
                chat_id=-1002744087198,
                from_chat_id=msg.chat.id,
                message_id=msg.message_id
            )

        await message.answer('Вы можете вернуться на главное меню', reply_markup=keyboard)
        await db.statistic.increment_counters(model_key, all_time=1, now_month=1)

    except Exception as e:
        logging.error(f"Ошибка генерации для модели {model_key}: {e}", exc_info=True)
        await db.user.increase_value(user_id, 'generations', cost)
        await db.user.increase_value(user_id, 'completed', -1)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⬅️ Назад', callback_data='back_main')]])
        try:
            await msg.edit_text(f"❌ <b>Ошибка:</b>\n<code>{html.escape(str(e))}</code>\n\nВаши 💎 возвращены на баланс.", reply_markup=keyboard,
                                parse_mode='HTML')
        except Exception:
            await msg.answer(f"❌ <b>Ошибка:</b>\n<code>{html.escape(str(e))}</code>\n\nВаши 💎 возвращены на баланс.", reply_markup=keyboard,
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
        await db.payments.create_payment(user_id, message.from_user.username, int(amount), 'stars')

    await message.answer('✅ Оплата прошла успешно. Ваш баланс пополнен!')


@user_router.callback_query(F.data == 'check_op')
async def check_op_user_func(call: types.CallbackQuery, db: Database, state: FSMContext, bot: Bot):
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
