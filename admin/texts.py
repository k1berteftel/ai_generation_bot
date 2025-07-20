ADMIN_PANEL_GREETING = "Админ панель:"
SUBSCRIPTION_CHECK_MENU = "Обязательная подписка:"
AD_URLS_MENU = "Рекламные ссылки:"
KEYS_MENU_HEADER = "Ключи:"

# --- Statistics Template ---
STATISTICS_REPORT_TEMPLATE = """
🚻<b>Пользователи:</b>
Всего пользователей: {total_users}
Пришло в этом месяце: {users_now_month}
Пришло в прошлом месяце: {users_past_month}

{stats_block}
"""

STATS_BLOCK_TEMPLATE = """
{icon}<b>{name}:</b>
Всего использовано: {all_time}
Использовано в этом месяце: {now_month}
Использовано в прошлом месяце: {past_month}
"""


AD_URL_STATS_TEMPLATE = """
Реферальная ссылка: <b>{name}</b>

Всего перешло по ссылке: {all_users}
Новые пользователи: {unique_users}
Старые пользователи: {not_unique_users}

Всего запросов: {requests}
Куплено на: {income} руб

Ссылка: https://t.me/{bot_name}?start=ad_url_start_{name}
"""

# --- Other Messages ---
PROMPT_FOR_NEW_LINK = "Отправьте новую ссылку:"
PROMPT_FOR_CHANNEL_ID = "Отправьте id канала:"
PROMPT_FOR_CHANNEL_LINK = "Отправьте ссылку для канала:"
PROMPT_FOR_AD_URL_NAME = "Отправьте название для ссылки:"
PROMPT_FOR_API_KEY = "Отправьте ключ для {service_name}"
PROMPT_FOR_KEYS_WITH_OWNER = "Пример: /addkey ключ1:владелец1 ключ2:владелец2"
PROMPT_FOR_DELETE_KEYS = "Пример: /delkey ключ1 ключ2"
PROMPT_FOR_PROMOTE = "Пример: /promote 12345 30"

# --- Statuses ---
SUCCESSFULLY_DELETED = "✅ Успешно удалено."
SUCCESSFULLY_ADDED = "✅ Успешно добавлено."
SUCCESSFULLY_UPDATED = "✅ Успешно обновлено."
SUCCESSFULLY_PROMOTED = "✅ Премиум успешно выдан!"
ACTION_CANCELED = "Отменено."
KEYS_UPDATED = "✅ Ключи обновлены."
LOGS_NOT_FOUND = "Файл с логами не найден."
KEYS_LIST_EMPTY = "🔍 Список ключей пуст."


# --- Errors ---
ERROR_GENERIC = "Произошла ошибка."
ERROR_INVALID_INPUT = "Некорректный ввод."
ERROR_NO_ADMIN_RIGHTS = "У вас нет прав для выполнения этой команды."