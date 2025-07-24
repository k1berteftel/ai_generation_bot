import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Any, List, Sequence, Type, Dict

from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import User, StartMessage, AdUrl, SubscriptionCheck, Statistic


class UserRepository:

    def __init__(self, session_factory):
        self.session_factory = session_factory


    async def get_or_create_user(self, user_id: int, username: str | None, ad_url: str | None = None, ref_id: str | None = None) -> \
            tuple[Type[User], bool] | tuple[User, bool]:

        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                return user, False # Пользователь уже существует

            # Пользователя нет, создаем нового
            new_user = User(
                id=user_id,
                username=username,
                ad_url=ad_url,
                ref_id=ref_id
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user, True


    async def create_user(self, user_id: int, username: str, ref_id: Optional[int] = None, ad_url: Optional[str] = None) -> bool:

        stmt = insert(User).values(
            id=user_id,
            username=username,
            ref_id=ref_id,
            ad_url=ad_url
        ).on_duplicate_key_update(id=User.id)

        async with self.session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def get_user(self, user_id: int) -> Optional[User]:

        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            return user

    async def get_users(self, **kwargs) -> Sequence[User]:
        async with self.session_factory() as session:
            users = await session.scalars(select(User).where(*kwargs))
        return users.fetchall()

    async def update_user(self, user_id: int, **kwargs: Any) -> None:

        stmt = update(User).where(User.id == user_id).values(**kwargs)
        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def increase_value(self, user_id: int, column: str, amount: int = 1) -> None:

        if not hasattr(User, column):
            raise ValueError(f"Колонка '{column}' не найдена в модели User.")


        stmt = update(User).where(User.id == user_id).values({
            column: getattr(User, column) + amount
        })
        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def grant_unlim_access(self, user_id: int) -> None:
        await self.update_user(user_id, is_unlim=True, unlim_time=datetime.now())


    async def export_user_ids_to_file(self) -> str:

        async with self.session_factory() as session:
            stmt = select(User.id)
            result = await session.execute(stmt)

            user_ids = result.scalars().all()

        # 2. Создаем папку для экспорта, если ее нет
        export_dir = "exports"
        os.makedirs(export_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = os.path.join(export_dir, f"users_{timestamp}.txt")


        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for user_id in user_ids:
                    f.write(f"{user_id}\n")

            logging.info(f"Успешно экспортировано {len(user_ids)} ID пользователей в файл: {file_path}")

        except IOError as e:
            logging.error(f"Ошибка при записи файла {file_path}: {e}")
            # В случае ошибки можно вернуть пустую строку или вызвать исключение
            return ""

        # 5. Возвращаем путь к созданному файлу
        return file_path


    async def get_user_value(self, user_id: int, column_name: str) -> Any:

        async with self.session_factory() as session:
            query = select(getattr(User, column_name)).where(User.id == user_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def process_generation(self, user_id: int, cost: int) -> bool:
        async with self.session_factory() as session:
            user = await session.get(User, user_id)


            if not user or user.generations < cost:
                return False


            user.generations -= cost
            user.completed += 1
            await session.commit()
            return True

    async def check_unlim_status(self, user_id: int) -> bool:
        async with self.session_factory() as session:
            user = await session.get(User, user_id)

            if not (user and user.is_unlim and user.unlim_time):
                return False


            if datetime.now() <= user.unlim_time + timedelta(weeks=1):
                return True
            else:

                logging.info(f"Срок безлимитного доступа для пользователя {user_id} истек.")
                user.is_unlim = False
                user.unlim_time = None

                user.generations = max(0, user.generations - 500)
                await session.commit()
                return False

    async def get_total_user_count(self) -> int:
        """Возвращает общее количество пользователей."""
        async with self.session_factory() as session:
            stmt = select(func.count(User.id))
            result = await session.execute(stmt)
            return result.scalar_one()

    async def is_user_unlim(self, user_id: int) -> bool:

        async with self.session_factory() as session:

            query = select(User.is_unlim).where(User.id == user_id)
            result = await session.execute(query)
            is_unlim_flag = result.scalar_one_or_none()
            return bool(is_unlim_flag)


class AdUrlRepository:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def get_or_create(self, name: str) -> AdUrl:
        """Находит рекламную ссылку по имени или создает новую."""
        async with self.session_factory() as session:
            ad_url = await session.get(AdUrl, name)
            if ad_url:
                return ad_url

            new_ad_url = AdUrl(name=name)
            session.add(new_ad_url)
            await session.commit()
            return new_ad_url

    async def get_all(self) -> List[AdUrl]:
        """Возвращает все рекламные ссылки."""
        async with self.session_factory() as session:
            stmt = select(AdUrl)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_name(self, name: str) -> AdUrl | None:
        """
        Находит рекламную ссылку по её имени (primary key).
        """
        async with self.session_factory() as session:
            return await session.get(AdUrl, name)

    async def delete_by_name(self, name: str):
        """Удаляет рекламную ссылку по имени."""
        async with self.session_factory() as session:
            stmt = delete(AdUrl).where(AdUrl.name == name)
            await session.execute(stmt)
            await session.commit()

    async def increment_counters(self, name: str, **counters_to_add):
        """
        Увеличивает любые счетчики для рекламной ссылки.
        Пример: await db.ad_url.increment_counters('tg_ad', all_users=1, income=500)
        """
        async with self.session_factory() as session:
            await self.get_or_create(name)  # Гарантируем, что запись существует

            values_to_increment = {}
            for key, value in counters_to_add.items():
                if hasattr(AdUrl, key):
                    values_to_increment[key] = getattr(AdUrl, key) + value

            if values_to_increment:
                stmt = update(AdUrl).where(AdUrl.name == name).values(**values_to_increment)
                await session.execute(stmt)
                await session.commit()


class SubscriptionRepository:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def get_all_channels(self) -> List[SubscriptionCheck] | Sequence[SubscriptionCheck]:
        """Возвращает список всех каналов для обязательной подписки."""
        async with self.session_factory() as session:
            stmt = select(SubscriptionCheck)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_channel_by_id(self, channel_id: int) -> Type[SubscriptionCheck] | None:
        async with self.session_factory() as session:
            return await session.get(SubscriptionCheck, channel_id)


    async def add_channel(self, chat_id: str, link_channel: str | None = None) -> SubscriptionCheck:
        """Добавляет новый канал в список для проверки подписки."""
        async with self.session_factory() as session:
            new_channel = SubscriptionCheck(chat_id=chat_id, link_channel=link_channel)
            session.add(new_channel)
            await session.commit()
            await session.refresh(new_channel)  # Получаем ID после создания
            logging.info(f"Added new channel for subscription check: ID={new_channel.id}, ChatID={chat_id}")
            return new_channel

    async def update_channel(self, channel_id: int, **kwargs: Any):
        """
        Обновляет данные для конкретного канала по его ID.
        Пример: await db.subscription.update_channel(1, link_channel='new_link')
        """
        if not kwargs:
            return
        async with self.session_factory() as session:
            stmt = update(SubscriptionCheck).where(SubscriptionCheck.id == channel_id).values(**kwargs)
            await session.execute(stmt)
            await session.commit()
            logging.info(f"Updated subscription check channel ID={channel_id} with data: {kwargs}")

    async def delete_channel(self, channel_id: int):
        """Удаляет канал из списка проверки по его ID."""
        async with self.session_factory() as session:
            stmt = delete(SubscriptionCheck).where(SubscriptionCheck.id == channel_id)
            await session.execute(stmt)
            await session.commit()
            logging.info(f"Deleted subscription check channel ID={channel_id}")

    async def increment_subs_count(self, channel_id: int, amount: int = 1):
        """
        Атомарно увеличивает счетчик подписчиков для канала.
        """
        async with self.session_factory() as session:
            stmt = update(SubscriptionCheck).where(SubscriptionCheck.id == channel_id).values(
                count_subs=SubscriptionCheck.count_subs + amount
            )
            await session.execute(stmt)
            await session.commit()
            logging.info(f"Incremented subs_count for channel ID={channel_id} by {amount}")


class StatisticsRepository:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def get_or_create(self, name: str) -> Statistic:
        """Находит строку статистики по имени или создает новую."""
        async with self.session_factory() as session:
            stat_row = await session.get(Statistic, name)
            if stat_row:
                return stat_row

            new_stat_row = Statistic(name=name)
            session.add(new_stat_row)
            await session.commit()
            return new_stat_row

    async def increment_counters(self, name: str, **counters_to_add):
        """
        Увеличивает любые счетчики в таблице статистики.
        Это именно тот метод, который вам нужен для поля `gpt` и других.
        Пример: await db.statistic.increment_counters('global', gpt=1, now_day=1)
        """
        async with self.session_factory() as session:
            await self.get_or_create(name)  # Гарантируем, что запись существует

            values_to_increment = {}
            for key, value in counters_to_add.items():
                if hasattr(Statistic, key):
                    values_to_increment[key] = getattr(Statistic, key) + value

            if values_to_increment:
                stmt = update(Statistic).where(Statistic.name == name).values(**values_to_increment)
                await session.execute(stmt)
                await session.commit()

    async def get_multiple_stats(self, names: List[str]) -> Dict[str, dict]:
        """Возвращает данные для нескольких строк статистики."""
        async with self.session_factory() as session:
            stmt = select(Statistic).where(Statistic.name.in_(names))
            result = await session.execute(stmt)
            stats_rows = result.scalars().all()
            return {
                row.name: {
                    'all_time': row.all_time,
                    'now_month': row.now_month,
                    'past_month': row.past_month,
                } for row in stats_rows
            }


class StartMessageRepository:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def get_message(self) -> StartMessage | None:
        """Получает единственную запись о стартовом сообщении из таблицы."""
        async with self.session_factory() as session:
            # Просто выбираем первую (и единственную) запись
            stmt = select(StartMessage)
            result = await session.execute(stmt)
            return result.scalars().first()

    async def set_message(self, message_id: int, chat_id: int, reply_markup: str | None = None):
        """
        Полностью очищает таблицу и сохраняет информацию о новом стартовом сообщении.
        Гарантирует, что в таблице всегда будет только одна строка.
        """
        async with self.session_factory() as session:
            # Используем транзакцию, чтобы обе операции были атомарными
            async with session.begin():
                # 1. Удаляем все старые записи из таблицы
                await session.execute(delete(StartMessage))

                # 2. Создаем и добавляем новую запись
                new_message = StartMessage(
                    message_id=message_id,
                    chat_id=chat_id,
                    reply_markup=reply_markup
                )
                session.add(new_message)

    async def clear_message(self):
        """Полностью очищает таблицу стартовых сообщений."""
        async with self.session_factory() as session:
            await session.execute(delete(StartMessage))
            await session.commit()
            logging.info("Start message has been cleared from the database.")


    async def update_delay(self, new_delay: int):
        """Обновляет только задержку для стартового сообщения."""
        async with self.session_factory() as session:
            stmt = update(StartMessage).values(delay_seconds=new_delay)
            await session.execute(stmt)
            await session.commit()
            logging.info(f"Start message delay updated to {new_delay} seconds.")
