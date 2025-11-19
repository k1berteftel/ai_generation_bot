import os
import sys
import time
from typing import Callable, Any, Awaitable

from aiogram import Router, types, F, Bot, BaseMiddleware
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Update, User

import config
from APIKeyManager.apikeymanager import APIKeyManager
from admin import texts
from admin.admin_keyboard import (admin_panel_menu, op_panel_button, cancel_op_panel_button, ad_urls_panel_button,
    cancel_urls_panel_button, ad_url_one_panel_button, op_url_one_bottom_panel, cancel_key_panel_button,
    api_keys_panel_button, cancel_copy_message, start_message_menu_keyboard, confirm_malling_keyboard,
    get_partners_keyboard, partner_panel_menu, get_deeplinks_panel_button, deeplink_one_panel_button)
from admin.admin_states import (OpState, NameUrl, StartMessage,
    UpdateLinkOp, ApiKeyStates, SetStartMessageDelay, Malling, Partners, Deeplink)
from admin.services import format_statistics_report

from utils.tables import get_table
from config import list_admins
from database.database import Database


admin_router = Router()


class AdminsMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
            event: Update,
            data: dict[str, Any],
    ) -> Any:
        event_from_user: User = data.get('event_from_user')
        db: Database = data.get('db')
        if event_from_user.id not in list_admins:
            return
        if event_from_user.id not in [admin.user_id for admin in await db.admins.get_all()]:
            return
        return await handler(event, data)


admin_router.message(AdminsMiddleware())
admin_router.callback_query(AdminsMiddleware())


@admin_router.message(Command('admin'))
async def admin_panel_entry(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in list_admins:
        await message.answer(texts.ADMIN_PANEL_GREETING, reply_markup=admin_panel_menu())
    else:
        await message.answer(texts.ADMIN_PANEL_GREETING, reply_markup=partner_panel_menu())


@admin_router.message(F.text == 'Партнерские ссылки')
async def deeplinks_handler(message: types.Message, db: Database, state: FSMContext):
    if message.from_user.id in list_admins:
        ad_urls = await db.deeplinks.get_all()
    else:
        ad_urls = await db.deeplinks.get_all_admin(message.from_user.id)
    data = await state.get_data()
    page = data.get('page', 0)
    await message.answer(texts.AD_URLS_MENU, reply_markup=get_deeplinks_panel_button(ad_urls, page))


@admin_router.callback_query(F.data.startswith('partner_pager'))
async def deeplinks_pager(call: types.CallbackQuery, db: Database, state: FSMContext):
    await call.message.delete()
    action = call.data.split('_')[-1]
    data = await state.get_data()
    page = data.get('page', 0)
    if action == 'next':
        page += 1
    else:
        page -= 1
    await state.update_data(page=page)
    if call.from_user.id in list_admins:
        ad_urls = await db.deeplinks.get_all()
    else:
        ad_urls = await db.deeplinks.get_all_admin(call.from_user.id)
    await call.message.answer(texts.AD_URLS_MENU, reply_markup=get_deeplinks_panel_button(ad_urls, page))


async def _show_single_deeplink_stats(call: types.CallbackQuery, db: Database, name: str, is_update: bool = False):
    """Отображает статистику для одной конкретной рекламной ссылки."""
    ad_url_data = await db.deeplinks.get_by_name(name)
    if not ad_url_data:
        await call.answer("Ссылка не найдена", show_alert=True)
        return

    users = await db.user.get_users(ad_url=ad_url_data.name, passed=True)
    active = 0
    not_passed = 0
    for user in users:
        if user.active:
            active += 1
        if not user.passed:
            not_passed += 1

    text = texts.AD_URL_STATS_TEMPLATE.format(
        name=ad_url_data.name,
        unique_users=ad_url_data.unique_users,
        requests=ad_url_data.requests,
        income=ad_url_data.income,
        active=active,
        not_active=len(users) - active,
        passed=len(users),
        not_passed=not_passed,
        bot_name=config.BOT_NAME
    )
    if is_update:
        text = "<i>ОБНОВЛЕНО</i>\n\n" + text

    keyboard = deeplink_one_panel_button(name)
    await call.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


async def _show_deeplink_menu(message: types.Message, db: Database, page: int = 0, is_edit: bool = False):
    """Внутренняя функция для отображения меню рекламных ссылок."""
    if message.from_user.id in list_admins:
        ad_urls = await db.deeplinks.get_all()
    else:
        ad_urls = await db.deeplinks.get_all_admin(message.from_user.id)
    keyboard = get_deeplinks_panel_button(ad_urls, page)
    if is_edit:
        await message.edit_text(texts.AD_URLS_MENU, reply_markup=keyboard)
    else:
        await message.answer(texts.AD_URLS_MENU, reply_markup=keyboard)


@admin_router.callback_query(F.data.startswith('deeplink:'))
async def deeplinks_action_handler(call: types.CallbackQuery, db: Database, state: FSMContext):

    await state.set_state()

    try:
        _, action, *params = call.data.split(':')
        name = params[0] if params else None
    except ValueError:
        return await call.answer("Ошибка данных.", show_alert=True)

    data = await state.get_data()
    page = data.get('page', 0)

    if action == 'view':
        await _show_single_deeplink_stats(call, db, name)
    elif action == 'update':
        await _show_single_deeplink_stats(call, db, name, is_update=True)
    elif action == 'delete':
        await db.deeplinks.delete_by_name(name)
        await call.answer(texts.SUCCESSFULLY_DELETED, show_alert=True)
        await _show_deeplink_menu(call.message, db, page, is_edit=True)
    elif action == 'create':
        await call.message.edit_text(texts.PROMPT_FOR_AD_URL_NAME)
        #await state.set_state(NameUrl.name)
    elif action == 'back':
        await _show_deeplink_menu(call.message, db, page, is_edit=True)


@admin_router.callback_query(F.data == 'create_deeplink_panel')
async def create_deeplink_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(texts.PROMPT_FOR_AD_URL_NAME)
    await state.set_state(Deeplink.name)


@admin_router.message(Deeplink.name)
async def set_deeplink_name_handler(message: types.Message, state: FSMContext, db: Database):
    await state.set_state()
    data = await state.get_data()
    page = data.get('page', 0)
    # Создаем запись через репозиторий
    await db.deeplinks.get_or_create(message.from_user.id, message.text.replace(' ', '_'))
    await message.answer(texts.SUCCESSFULLY_ADDED)
    await _show_deeplink_menu(message, db, page)


@admin_router.message(F.text == 'Рассылки')
async def get_mail(message: types.Message, state: FSMContext):
    await state.set_state(Malling.waiting_for_message)
    await message.answer('Пришлите сообщение которое вы хотели бы разослать')


@admin_router.message(Malling.waiting_for_message)
async def show_confirm_malling(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    await message.answer('Данное сообщение будет разослано всем пользователям бота, вы подтверждаете рассылку?',
                         reply_markup=confirm_malling_keyboard())


@admin_router.message(F.text == 'Покупки')
async def send_transactions(message: types.Message, db: Database):
    payments = list(await db.payments.get_payments())
    payments.reverse()
    columns = []
    for payment in payments:
        columns.append(
            [
                payment.user_id,
                payment.username,
                payment.sum,
                '💳Карта' if  payment.payment_type == 'card' else '⭐️Звезды',
                payment.paid.strftime("%Y-%m-%d | %H:%M")
            ]
        )

    columns.insert(0, ['User ID', 'Юзернейм', 'Сумма ₽', 'Способ оплаты', 'Дата оплаты'])
    table = get_table(columns, 'Транзакции')
    await message.answer_document(
        document=FSInputFile(table)
    )
    try:
        os.remove(table)
    except Exception:
        ...
    await message.answer(texts.ADMIN_PANEL_GREETING, reply_markup=admin_panel_menu())


@admin_router.callback_query(F.data == 'confirm_malling')
async def start_malling(clb: types.CallbackQuery, db: Database, state: FSMContext):
    users = await db.user.get_users()
    message = await clb.message.answer('Началась рассылка сообщения')
    state_data = await state.get_data()
    msg_id = state_data.get('msg_id')
    chat_id = state_data.get('chat_id')
    counter = 0
    for user in users:
        try:
            await clb.bot.copy_message(
                chat_id=user.id,
                message_id=msg_id,
                from_chat_id=chat_id
            )
            if not user.active:
                await db.user.update_user(user.id, active=True)
            counter += 1
        except Exception:
            await db.user.update_user(user.id, active=False)
    await message.delete()
    await clb.message.answer(f'Рассылка успешно завершена, сообщение получило {counter} пользователей из {len(users)}')
    await state.clear()
    await clb.message.answer(texts.ADMIN_PANEL_GREETING, reply_markup=admin_panel_menu())


async def cancel_malling(clb: types.CallbackQuery, state: FSMContext):
    await clb.answer('Рассылка была успешно отменена')
    await clb.message.answer(texts.ADMIN_PANEL_GREETING, reply_markup=admin_panel_menu())


async def _show_op_menu(message: types.Message, db: Database, is_edit: bool = False):
    """(Внутренняя) Отображает главное меню управления ОП."""
    channels = await db.subscription.get_all_channels()
    keyboard = op_panel_button(channels)
    text = texts.SUBSCRIPTION_CHECK_MENU
    if is_edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _show_op_channel_details(call: types.CallbackQuery, db: Database, channel_id: int):
    """(Внутренняя) Отображает детали конкретного канала ОП."""
    channel = await db.subscription.get_channel_by_id(channel_id)
    if not channel:
        await call.answer("Канал не найден.", show_alert=True)
        return

    text = f"Данные для канала {channel.chat_id}\n\n" \
           f"Ссылка для канала: {channel.link_channel}\n\n" \
           f"Подписчиков перешло: {channel.count_subs}"

    await call.message.edit_text(text, reply_markup=op_url_one_bottom_panel(channel.id))


@admin_router.message(F.text == 'ОП')
@admin_router.callback_query(F.data == 'admin_panel_op')
async def op_menu_handler(update: types.Update, db: Database, state: FSMContext):
    await state.set_state()
    """Точка входа в меню ОП."""
    message = update if isinstance(update, types.Message) else update.message
    is_edit = isinstance(update, types.CallbackQuery)
    await _show_op_menu(message, db, is_edit=is_edit)


@admin_router.callback_query(F.data.startswith('op:'))
async def op_action_handler(call: types.CallbackQuery, state: FSMContext, db: Database):

    await state.set_state()

    try:
        _, action, *params = call.data.split(':')
        channel_id = int(params[0]) if params else None
    except (ValueError, IndexError):
        return await call.answer("Ошибка данных.", show_alert=True)

    if action == 'view':
        await _show_op_channel_details(call, db, channel_id)
    elif action == 'delete':
        await db.subscription.delete_channel(channel_id)
        await call.answer(texts.SUCCESSFULLY_DELETED, show_alert=True)
        await _show_op_menu(call.message, db, is_edit=True)
    elif action == 'update_link':
        await call.message.edit_text(
            texts.PROMPT_FOR_NEW_LINK,
            reply_markup=cancel_op_panel_button()
        )
        await state.update_data(op_channel_id=channel_id)
        await state.set_state(UpdateLinkOp.new_link)
    elif action == 'back':
        await _show_op_menu(call.message, db, is_edit=True)


@admin_router.message(UpdateLinkOp.new_link)
async def set_op_link_handler(message: types.Message, state: FSMContext, db: Database):
    """Сохраняет новую ссылку для канала."""
    data = await state.get_data()
    channel_id = data.get('op_channel_id')
    await state.set_state()

    await db.subscription.update_channel(channel_id, link_channel=message.text)
    await message.answer(texts.SUCCESSFULLY_UPDATED)
    await _show_op_menu(message, db)


@admin_router.callback_query(F.data == 'create_op_panel')
async def create_op_handler(call: types.CallbackQuery, state: FSMContext):
    """Начинает процесс создания нового канала ОП."""
    await call.message.edit_text(texts.PROMPT_FOR_CHANNEL_ID, reply_markup=cancel_op_panel_button())
    await state.set_state(OpState.id)


@admin_router.message(OpState.id)
async def set_op_id_handler(message: types.Message, state: FSMContext):
    """Получает ID канала и запрашивает ссылку."""
    await state.update_data(op_channel_id_str=message.text)
    await message.answer(texts.PROMPT_FOR_CHANNEL_LINK, reply_markup=cancel_op_panel_button())
    await state.set_state(OpState.link)


@admin_router.message(OpState.link)
async def set_op_link_and_create_handler(message: types.Message, state: FSMContext, db: Database):
    """Получает ссылку, создает канал и отображает обновленное меню."""
    data = await state.get_data()
    await state.set_state()

    await db.subscription.add_channel(chat_id=data['op_channel_id_str'], link_channel=message.text)
    await message.answer(texts.SUCCESSFULLY_ADDED)
    await _show_op_menu(message, db)


@admin_router.message(F.text == 'Статистика')
async def statistics_handler(message: types.Message, db: Database):
    await message.answer("⏳ Собираю статистику...")

    stat_names = [
        'users', 'Kling v2.1 — видео текст+фото', 'Seedance 1 Lite — видео по тексту', 'Minimax - Видео по фото', 'Sora - Генерация изображений', 'Veo3 - видео сценарию', 'income',
        'Решение задач'
    ]
    stats_data = await db.statistic.get_multiple_stats(stat_names)
    users = await db.user.get_users()

    report_text = format_statistics_report(stats_data, users)

    await message.answer(report_text, parse_mode='HTML')


async def _show_ad_urls_menu(message: types.Message, db: Database, page: int = 0, is_edit: bool = False):
    """Внутренняя функция для отображения меню рекламных ссылок."""
    ad_urls = await db.ad_url.get_all()
    keyboard = ad_urls_panel_button(ad_urls, page)
    if is_edit:
        await message.edit_text(texts.AD_URLS_MENU, reply_markup=keyboard)
    else:
        await message.answer(texts.AD_URLS_MENU, reply_markup=keyboard)


async def _show_single_ad_url_stats(call: types.CallbackQuery, db: Database, name: str, is_update: bool = False):
    """Отображает статистику для одной конкретной рекламной ссылки."""
    ad_url_data = await db.ad_url.get_by_name(name)
    if not ad_url_data:
        await call.answer("Ссылка не найдена", show_alert=True)
        return

    users = await db.user.get_users(ad_url=ad_url_data.name, passed=True)
    active = 0
    not_passed = 0
    for user in users:
        if user.active:
            active += 1
        if not user.passed:
            not_passed += 1

    text = texts.AD_URL_STATS_TEMPLATE.format(
        name=ad_url_data.name,
        unique_users=ad_url_data.unique_users,
        requests=ad_url_data.requests,
        income=ad_url_data.income,
        active=active,
        not_active=len(users) - active,
        passed=len(users),
        not_passed=not_passed,
        bot_name=config.BOT_NAME
    )
    if is_update:
        text = "<i>ОБНОВЛЕНО</i>\n\n" + text

    keyboard = ad_url_one_panel_button(name)
    await call.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


@admin_router.message(F.text == 'Рекламные ссылки')
async def ad_urls_handler(message: types.Message, db: Database, state: FSMContext):
    ad_urls = await db.ad_url.get_all()
    data = await state.get_data()
    page = data.get('page', 0)
    await message.answer(texts.AD_URLS_MENU, reply_markup=ad_urls_panel_button(ad_urls, page))


@admin_router.callback_query(F.data == 'ad_urls_admin_panel')
async def ad_urls_func_call(call: types.CallbackQuery, db: Database, state: FSMContext):
    await call.message.delete()
    ad_urls = await db.ad_url.get_all()
    data = await state.get_data()
    page = data.get('page', 0)
    await call.message.answer(texts.AD_URLS_MENU, reply_markup=ad_urls_panel_button(ad_urls, page))


@admin_router.callback_query(F.data.startswith('pager'))
async def urls_pager(call: types.CallbackQuery, db: Database, state: FSMContext):
    await call.message.delete()
    action = call.data.split('_')[-1]
    data = await state.get_data()
    page = data.get('page', 0)
    if action == 'next':
        page += 1
    else:
        page -= 1
    await state.update_data(page=page)
    ad_urls = await db.ad_url.get_all()
    await call.message.answer(texts.AD_URLS_MENU, reply_markup=ad_urls_panel_button(ad_urls, page))


@admin_router.message(F.text == 'Юзеры Бд')
async def return_users_bd_func(message: types.Message, db: Database):
    file_path = await db.user.export_user_ids_to_file()

    await message.answer_document(document=FSInputFile(file_path))


#ad_url
@admin_router.callback_query(F.data == 'create_ad_url_panel')
async def create_ad_url_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(texts.PROMPT_FOR_AD_URL_NAME, reply_markup=cancel_urls_panel_button())
    await state.set_state(NameUrl.name)


@admin_router.message(NameUrl.name)
async def set_ad_url_name_handler(message: types.Message, state: FSMContext, db: Database):
    await state.set_state()
    data = await state.get_data()
    page = data.get('page', 0)
    # Создаем запись через репозиторий
    await db.ad_url.get_or_create(message.text.replace(' ', '_'))
    await message.answer(texts.SUCCESSFULLY_ADDED)
    await _show_ad_urls_menu(message, db, page)


@admin_router.callback_query(F.data.startswith('ad_url:'))
async def ad_urls_action_handler(call: types.CallbackQuery, db: Database, state: FSMContext):

    await state.set_state()

    try:
        _, action, *params = call.data.split(':')
        name = params[0] if params else None
    except ValueError:
        return await call.answer("Ошибка данных.", show_alert=True)

    data = await state.get_data()
    page = data.get('page', 0)

    if action == 'view':
        await _show_single_ad_url_stats(call, db, name)
    elif action == 'update':
        await _show_single_ad_url_stats(call, db, name, is_update=True)
    elif action == 'delete':
        await db.ad_url.delete_by_name(name)
        await call.answer(texts.SUCCESSFULLY_DELETED, show_alert=True)
        await _show_ad_urls_menu(call.message, db, page, is_edit=True)
    elif action == 'create':
        await call.message.edit_text(texts.PROMPT_FOR_AD_URL_NAME, reply_markup=cancel_urls_panel_button())
        await state.set_state(NameUrl.name)
    elif action == 'back':
        await _show_ad_urls_menu(call.message, db, page, is_edit=True)


@admin_router.message(F.text == 'Логи')
async def send_logs_bot_func(message: types.Message):
    MAX_FILE_SIZE = 50 * 1024 * 1024
    log_file_path = '/data/chatgpt.log'

    if os.path.exists(log_file_path):
        file_size = os.path.getsize(log_file_path)

        if file_size <= MAX_FILE_SIZE:
            await message.answer_document(document=FSInputFile(log_file_path))
        else:
            part_number = 1
            with open(log_file_path, 'r', encoding='utf-8') as log_file:
                while True:
                    # Читаем кусок файла
                    chunk = log_file.read(MAX_FILE_SIZE // 2)
                    if not chunk:
                        break
                    temp_file_path = f'/data/chatgpt_part_{part_number}.log'
                    with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
                        temp_file.write(chunk)

                    await message.answer_document(document=FSInputFile(temp_file_path))

                    os.remove(temp_file_path)
                    part_number += 1
    else:
        await message.answer("Файл с логами не найден.")


@admin_router.message(F.text == 'Партнеры')
async def handle_partner_data(message: types.Message, db: Database):
    admins = await db.admins.get_all()
    keyboard = await get_partners_keyboard(admins)
    await message.answer(
        text='Нажмите на партнера которого хотели бы удалить или добавьте нового по кнопке ниже',
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data == 'add_partner_switcher')
async def handle_add_partner(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Partners.get_partner)
    await call.message.delete()
    await call.message.answer('Отправьте Telegram ID для нового партнера или перешлите его сообщение боту')


@admin_router.message(F.text, Partners.get_partner)
async def get_partner(message: types.Message, db: Database, state: FSMContext):
    if message.forward_from:
        user_id = message.forward_from.id
        username = message.forward_from.username
    else:
        try:
            user_id = int(message.text)
            username = None
        except Exception:
            await message.answer('Telegram ID должен быть числом, пожалуйста попробуйте снова')
            return
    await db.admins.get_or_create(user_id, username)
    await state.clear()
    await message.answer('Партнер был успешно добавлен', reply_markup=admin_panel_menu())


@admin_router.callback_query(F.data.startswith('partner_del'))
async def del_partner(call: types.CallbackQuery, db: Database):
    user_id = int(call.data.split('_')[-1])
    await db.admins.delete(user_id)
    await call.answer('Партнер был успешно удален')
    await call.message.delete()

    admins = await db.admins.get_all()
    keyboard = await get_partners_keyboard(admins)
    await call.message.answer(
        text='Нажмите на партнера которого хотели бы удалить или добавьте нового по кнопке ниже',
        reply_markup=keyboard
    )


@admin_router.message(Command('restart'))
async def restart_bot(message: types.Message):
    if message.from_user.id in list_admins:
        os.execl(sys.executable, sys.executable, *sys.argv)


@admin_router.message(Command('promote'))
async def promote_handler(message: types.Message, command: CommandObject, db: Database):
    if not command.args:
        return await message.answer("Пример: /promote 12345 30")

    try:
        user_id_str, days_str = command.args.split()
        user_id, days = int(user_id_str), int(days_str)
        if days <= 0: raise ValueError
    except (ValueError, TypeError):
        return await message.answer(texts.ERROR_INVALID_INPUT)

    premium_end_time = int(time.time()) + (days * 86400)


    await db.user.update_user(
        user_id,
        premium='Yes',
        premium_time=premium_end_time
    )

    await message.answer(texts.SUCCESSFULLY_PROMOTED)


async def _show_start_message_menu(message: types.Message, db: Database, bot: Bot):
    """(Внутренняя) Отображает меню управления стартовым сообщением."""
    start_msg_info = await db.start_message.get_message()

    if not start_msg_info:
        await message.answer(
            "Стартовое сообщение не установлено.",
            reply_markup=start_message_menu_keyboard(is_set=False)
        )
        return

    # Показываем текущее сообщение и настройки
    text = f"Текущее стартовое сообщение (будет отправлено ниже).\n\n" \
           f"🕒 Задержка перед отправкой: {start_msg_info.delay_seconds} сек."

    await message.answer(text, reply_markup=start_message_menu_keyboard(is_set=True))
    # Пересылаем само сообщение для предпросмотра
    await bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=start_msg_info.chat_id,
        message_id=start_msg_info.message_id,
        reply_markup=None  # Клавиатуру не пересылаем, она может быть невалидной
    )


@admin_router.message(F.text == 'Стартовое сообщение')
async def start_message_entry_handler(message: types.Message, db: Database, bot: Bot):
    """Точка входа в меню управления стартовым сообщением."""
    await _show_start_message_menu(message, db, bot)


@admin_router.callback_query(F.data.startswith('admin:start_msg:'))
async def universal_handler_start_message_func(call: types.CallbackQuery, state: FSMContext, db: Database):
    action = call.data.split(':')[-1]

    if action == 'set':
        """Запрашивает новый пост для стартового сообщения."""
        await call.message.edit_text(
            'Отправьте пост, который будет использоваться как стартовое сообщение:',
            reply_markup=cancel_copy_message()
        )
        await state.set_state(StartMessage.mes)

    elif action == 'delay':
        """Запрашивает задержку."""
        await call.message.edit_text("Отправьте задержку в секундах (например, 5):", reply_markup=cancel_copy_message())
        await state.set_state(SetStartMessageDelay.delay)

    elif action == 'delete':
        await db.start_message.clear_message()
        await call.message.edit_text('✅ Стартовое сообщение успешно удалено!')


@admin_router.message(StartMessage.mes)
async def set_start_message_handler(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    await state.set_state()
    keyboard_json = message.reply_markup.model_dump_json() if message.reply_markup else None

    await db.start_message.set_message(
        message_id=message.message_id,
        chat_id=message.chat.id,
        reply_markup=keyboard_json
    )
    await message.answer(texts.SUCCESSFULLY_ADDED)
    await _show_start_message_menu(message, db, bot)


@admin_router.message(SetStartMessageDelay.delay)
async def set_delay_handler(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    """Сохраняет новую задержку."""
    try:
        delay = int(message.text)
        if delay < 0: raise ValueError
    except (ValueError, TypeError):
        return await message.answer("Ошибка: введите целое положительное число.")

    await state.set_state()
    await db.start_message.update_delay(delay)
    await message.answer(f"✅ Задержка установлена на {delay} сек.")
    await _show_start_message_menu(message, db, bot)


@admin_router.message(Command('delkey'))
async def delete_key(message: types.Message, command: CommandObject, key_manager: APIKeyManager):
    if message.from_user.id not in list_admins:
        return
    if not command.args:
        await message.answer(
            "⚠️ Пожалуйста, укажите один или несколько ключей для удаления.\n"
            "Например: `/delkey ключ1 ключ2`"
        )
        return

        # Получаем список ключей из аргументов
    keys_to_delete = command.args.split()

    deleted_keys = []
    not_found_keys = []

    for key in keys_to_delete:
        # Убираем возможные запятые в конце, если пользователь скопировал список
        cleaned_key = key.strip().strip(',')
        if not cleaned_key:
            continue

        success = await key_manager.delete_key(cleaned_key)
        if success:
            deleted_keys.append(f"✅ `{cleaned_key}`")
        else:
            not_found_keys.append(f"⚠️ `{cleaned_key}`")

    # Формируем красивый итоговый отчет
    response_parts = []
    if deleted_keys:
        response_parts.append("<b>Удаленные ключи:</b>\n" + "\n".join(deleted_keys))
    if not_found_keys:
        response_parts.append("<b>Ненайденные ключи:</b>\n" + "\n".join(not_found_keys))

    await message.answer("\n\n".join(response_parts), parse_mode='HTML')


@admin_router.message(Command('showkeys'))
async def show_keys(message: types.Message, key_manager: APIKeyManager):
    if message.from_user.id not in list_admins:
        return

    keys = await key_manager.list_keys()

    if not keys:
        await message.answer("🔍 Список ключей пуст.")
        return

    formatted_keys = "\n\n".join([f"🔑 {item['key']}\n👤 Владелец: {item['owner']}" for item in keys])

    await message.answer(f"🗂 Все ключи:\n\n{formatted_keys}")


@admin_router.message(Command('addkey'))
async def add_key(message: types.Message, command: CommandObject, key_manager: APIKeyManager):
    if message.from_user.id not in list_admins:
        return
    if not command.args:
        await message.answer("⚠️ Пожалуйста, укажите ключи после команды.\n"
                             "Например: `/addkey ключ1:владелец1 ключ2:владелец2`")
        return

        # Разделяем аргументы по пробелам или переносам строк
    lines = command.args.split()

    added_keys = []
    failed_lines = []

    for line in lines:
        try:
            # Разделяем строку на ключ и владельца, убирая лишние пробелы
            api_key, owner = map(str.strip, line.split(':', 1))
            if not api_key or not owner:  # Проверка на пустые значения
                raise ValueError("Ключ или владелец не могут быть пустыми.")

            await key_manager.add_key(api_key, owner)
            added_keys.append(f"✅ `{api_key}` : `{owner}`")
        except ValueError:
            # Если в строке нет ':' или одна из частей пуста
            failed_lines.append(f"❌ `{line}`")

    # Формируем итоговый ответ
    response_parts = []
    if added_keys:
        response_parts.append("<b>Добавленные ключи:</b>\n" + "\n".join(added_keys))
    if failed_lines:
        response_parts.append("<b>Не удалось обработать:</b>\n" + "\n".join(failed_lines))

    await message.answer("\n\n".join(response_parts), parse_mode='HTML')



@admin_router.message(Command('add_generations'))
async def add_tokens_func(message: types.Message, db: Database):
    text = message.text.replace('/add_generations ', '')
    user_id, count = text.split()
    try:
        user_id = int(user_id)
        count = int(count)
        await db.user.increase_value(user_id, 'generations', count)
        await message.answer('Успешно!')
    except Exception as e:
        await message.answer('Произошла ошибка')