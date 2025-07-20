# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from yookassa import Configuration

import config
from APIKeyManager.apikeymanager import APIKeyManager
from admin.admin_handlers import admin_router
from database.database import Database
from database.engine import engine, async_session_factory
from database.models import Base
from handlers.user_handlers import user_router

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")


async def on_startup(bot: Bot):
    """Выполняется при старте бота."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) # Раскомментировать для полной очистки БД
        await conn.run_sync(Base.metadata.create_all)
    logging.info("База данных готова к работе.")
    # Тут можно добавить отправку сообщения админу о запуске бота

async def main():
    """Основная функция для запуска бота."""
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Инициализация менеджера ключей API
    if config.DEBUG:
        key_manager = APIKeyManager(bot, file_path='api_replicate_keys.json')
    else:
        key_manager = APIKeyManager(bot)
    await key_manager.init()

    # Настройка YooKassa
    if config.yookassa_shop_id and config.yookassa_api_token:
        Configuration.account_id = config.yookassa_shop_id
        Configuration.secret_key = config.yookassa_api_token
        logging.info("YooKassa сконфигурирована.")
    else:
        logging.warning("YooKassa не сконфигурирована. Платежные функции могут быть недоступны.")

    # Внедрение зависимостей (dependency injection) в хендлеры
    # Теперь db, key_manager и bot будут доступны в каждом хендлере
    db_instance = Database(async_session_factory)
    dp['db'] = db_instance
    dp['key_manager'] = key_manager
    dp['bot'] = bot

    # Регистрация роутеров
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Выполнение задач при старте
    await on_startup(bot)

    logging.info("Запуск бота...")
    try:
        # Удаляем вебхук перед запуском, если он был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")