import asyncio
import logging

import aiomysql

from bot import config

db_host = config.db_host
db_name = config.db_name
db_user = config.db_user
db_pass = config.db_pass
db_port = config.db_port


def cycle_func(result):
    names = [f'{row[0]}\n' for row in result]
    return names


async def return_all_names_db_op(db_pool):
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT id, chat_id FROM op")
                results = await cursor.fetchall()
                # results — это список кортежей вида [(id1, chat_id1), (id2, chat_id2), ...]
                return results
    except aiomysql.Error as error:
        logging.error(f"Произошла ошибка при работе с базой данных: {error}")
        return None


async def delete_value_db_op(id):
    conn = await aiomysql.connect(host=db_host, port=db_port,
                                  user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute(f"DELETE FROM op WHERE id = %s", (id,))
            await conn.commit()
            return True
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None


async def create_op_task_url(id, link) -> bool:
    conn = await aiomysql.connect(host=db_host, port=db_port, user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            logging.info(f"INSERT INTO op (chat_id, link_channel) VALUES ({id}, {link})")
            await cursor.execute(
                f"INSERT INTO op (chat_id, link_channel) VALUES (%s, %s)", (id, link))
            await conn.commit()
            result = True
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при записи в БД: {error}")
            result = False
        finally:
            await conn.ensure_closed()
    return result


async def db_count() -> int:
    conn = await aiomysql.connect(host=db_host, port=db_port, user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute("SELECT COUNT(*) FROM users")
            results = await cursor.fetchone()
            return results[0]
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None


async def get_all_statistics(names):
    query = """
    SELECT * FROM statistics WHERE name IN (%s)
    """ % ', '.join(['%s'] * len(names))

    conn = await aiomysql.connect(host=db_host, port=db_port,
                                  user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute(query, tuple(names))
            results = await cursor.fetchall()
            return {row[0]: row for row in results}  # Предполагается, что name - первый столбец
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None


async def return_all_names_db():
    conn = await aiomysql.connect(host=db_host, port=db_port,
                                  user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute(f"SELECT name FROM ad_urls")
            results = await cursor.fetchall()
            print(results)
            return results
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None


async def select_all():
    conn = await aiomysql.connect(host=db_host, port=db_port,
                                  user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute("SELECT id FROM users WHERE premium = 'No'")
            results = await cursor.fetchall()
            loop = asyncio.get_running_loop()
            names = await loop.run_in_executor(None, cycle_func, results)
            return names
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None
        finally:
            await conn.ensure_closed()


async def create_ad_url(url_name) -> bool:
    conn = await aiomysql.connect(host=db_host, port=db_port, user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            logging.info(f"INSERT INTO ad_urls (name) VALUES ({url_name})")
            await cursor.execute(
                f"INSERT INTO ad_urls (name) VALUES (%s)",
                (url_name))
            await conn.commit()
            result = True
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при записи в БД: {error}")
            result = False
        finally:
            await conn.ensure_closed()
    return result


async def delete_value_db(name):
    conn = await aiomysql.connect(host=db_host, port=db_port,
                                  user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute(f"DELETE FROM ad_urls WHERE name = %s", (name,))
            await conn.commit()
            return True
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None


async def return_values_all_db(name):
    conn = await aiomysql.connect(host=db_host, port=db_port,
                                  user=db_user, password=db_pass, db=db_name)
    async with conn.cursor() as cursor:
        try:
            await cursor.execute(f"SELECT * FROM ad_urls WHERE name = %s", (name,))
            results = await cursor.fetchone()
            print(results)
            return results
        except aiomysql.Error as error:
            logging.error(f"Произошла ошибка при работе с базой данных: {error}")
            return None
