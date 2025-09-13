from . import texts

# Иконки для разных типов статистики
STATS_ICONS = {
    'chatgpt_4': '👽', 'chatgpt_4_mini': '🔹', 'chatgpt_o1': '🤖',
    'claude': '🤖', 'dalle': '🌇', 'elevenlabs': '🗣',
    'faceswap': '👥', 'flux': '🌩', 'kling': '🔗',
    'luma': '💡', 'minimax': '📈', 'mj': '📷',
    'remove_bg': '🎨', 'runway': '🎬', 'suno_v3': '🎶',
    'suno_v4': '🎶', 'udio': '🔊', 'image_gpt': '🌠',
    'neurocoin': '💰', 'income': '💵'
}


def format_statistics_report(stats_data: dict, users: list) -> str:
    """
    Формирует большой текстовый отчет по статистике.
    """
    users_stats = stats_data.get('users', {})
    refs = 0
    for user in users:
        if user.ref_id:
            refs += 1

    stats_blocks = []
    for name, data in stats_data.items():
        if name == 'users':
            continue

        icon = STATS_ICONS.get(name, '⚙️')
        # Безопасно получаем значения с дефолтом 0
        block = texts.STATS_BLOCK_TEMPLATE.format(
            icon=icon,
            name=name.replace('_', ' ').capitalize(),
            all_time=data.get('all_time', 0),
            now_month=data.get('now_month', 0),
            past_month=data.get('past_month', 0)
        )
        stats_blocks.append(block)

    final_report = texts.STATISTICS_REPORT_TEMPLATE.format(
        total_users=len(users),
        users_now_month=users_stats.get('now_month', 0),
        users_past_month=users_stats.get('past_month', 0),
        refs=refs,
        stats_block="\n".join(stats_blocks)
    )

    return final_report
