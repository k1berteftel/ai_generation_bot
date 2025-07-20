from sqlalchemy.ext.asyncio import async_sessionmaker

from .repository import UserRepository,AdUrlRepository, SubscriptionRepository, StatisticsRepository, StartMessageRepository

class Database:
    """
    Главный класс-агрегатор для всех репозиториев.
    Предоставляет единую точку доступа к данным: db.user, db.promocode и т.д.
    """
    def __init__(self, session_factory: async_sessionmaker):
        # Создаем экземпляры всех наших репозиториев
        self.user = UserRepository(session_factory)
        self.ad_url = AdUrlRepository(session_factory)
        self.subscription = SubscriptionRepository(session_factory)
        self.statistic = StatisticsRepository(session_factory)
        self.start_message = StartMessageRepository(session_factory)