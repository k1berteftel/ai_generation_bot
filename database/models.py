from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, Boolean, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from typing import Optional


class Base(DeclarativeBase):
    pass


class User(Base):
    """
    Декларативная модель SQLAlchemy для таблицы 'users'.
    """
    __tablename__ = 'users'

    # Колонки таблицы
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    generations: Mapped[int] = mapped_column(Integer, default=20, server_default="0")
    completed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ref_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ref_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="0")
    ad_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_generation: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, server_default=None)
    is_unlim: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    unlim_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"



class AdUrl(Base):
    __tablename__ = 'ad_urls'

    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    all_users: Mapped[int] = mapped_column(Integer, server_default='0')
    unique_users: Mapped[int] = mapped_column(Integer, server_default='0')
    not_unique_users: Mapped[int] = mapped_column(Integer, server_default='0')
    income: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    requests: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default='0')

    completed_op: Mapped[int] = mapped_column(Integer, server_default='0')

    def __repr__(self):
        return f"<AdUrl(name='{self.name}')>"


class SubscriptionCheck(Base):
    __tablename__ = 'op'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(255), nullable=False)
    link_channel: Mapped[str | None] = mapped_column(String(255))
    count_subs: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')

    def __repr__(self):
        return f"<SubscriptionCheck(id={self.id}, chat_id='{self.chat_id}')>"


class Statistic(Base):
    __tablename__ = 'statistics'

    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    all_time: Mapped[int] = mapped_column(BigInteger, server_default='0')
    now_month: Mapped[int] = mapped_column(BigInteger, server_default='0')
    now_week: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    now_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    past_month: Mapped[int] = mapped_column(BigInteger, server_default='0')
    chat_usage: Mapped[int] = mapped_column(BigInteger, server_default='0')

    def __repr__(self):
        return f"<Statistic(name='{self.name}')>"


class StartMessage(Base):
    __tablename__ = 'start_message'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    reply_markup: Mapped[str | None] = mapped_column(Text)

    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')

    def __repr__(self):
        return f"<StartMessage(id={self.id}, chat_id={self.chat_id}, message_id={self.message_id})>"

