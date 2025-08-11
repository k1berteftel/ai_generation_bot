# data/constants.py

MODELS = {
    #'Sora - Генерация изображений': 'gpt-4o-image',
    "Veo3 - видео сценарию": "veo3_quality",
    #"Veo3 (Качественный)": "veo3_quality",
    #"Veo3 (Бюджетный)": "veo3_fast",
    # "Pixverse v4.5": "pixverse/pixverse-v4.5",
    "Kling v2.1 — видео текст+фото": "kling-v2.1-master",
    "Seedance 1 Lite — видео по тексту": "seedance-1-lite",
    # "Luma Ray-2": "luma/ray-2-720p",
}

VEO_MODELS = {
    "Veo3 (Качественный)": "veo3_quality",
    "Veo3 (Бюджетный)": "veo3_fast",
}

MODELS_EXAMPLE_OBJECT = {
    "Veo3 - видео сценарию": {
        'name': '<b>Veo3</b>',
        'description': 'Делает видео и звук по тексту. Может работать с фото.',
        'examples':  [
            {
                'name': 'Ведущий и бабушка\n',
                'media': 'medias/veo/veo_ex_1.mp4',
                'content_type': 'video',
                'prompt': '<blockquote expandable><b>Ведущий с микрофоном спрашивает у бабушки на улицах на русском языке. '
                          '(оператор) - вы понимаете, что вы нейросеть? (бабушка) - да, внучок, ты ведь тоже '
                          'нейронка, ахаха (смеётся). Бабушка прыгает вверх и улетает.</b></blockquote>'
            },
        ],
        'manual': 'https://t.me/veo3_2025'
    },
    "Kling v2.1 — видео текст+фото": {
        'name': '<b>kling-v2.1-master</b>',
        'description': 'Генерирует видео по тексту или фото.',
        'examples': [
            {
                'name': '',
                'media': 'medias/kling/kling_ex_2.MP4',
                'content_type': 'video',
                'prompt': '<blockquote expandable><b>Create a realistic vertical video (9:16), as if recorded '
                          'with an iPhone at an outdoor seasons as summer. The setting has warm lighting from '
                          'streetlights or soft party lights. A little boy around 2 to 3 years old, with light '
                          'skin tone, broun hair, and big green expressive eyes, runs joyfully toward a young '
                          'couple sitting close together. The couple must look exactly like the people in the '
                          'attached photo — no changes to their facial features, skin tone, hairstyle, or clothing. '
                          'They both have medium skin, man have dark hair, women have broun hair and are man '
                          'wearing summer outfits. The child should clearly look like the boy, with features that '
                          'naturally combine both parents. He hugs them lovingly, wrapping her arms around them, '
                          'smiling and laughing. The couple smiles and embraces he warmly. The video should feel '
                          'authentic, as if casually filmed by a friend or family member on a phone — slightly '
                          'shaky, casually composed, and emotionally genuine</b></blockquote>'
            },
        ],
        'manual': 'https://t.me/kling_promt2025'
    },
    "Seedance 1 Lite — видео по тексту": {
        'name': "<b>seedance-1-lite</b>",
        'description': 'Быстрое видео по тексту.',
        'examples':  [
            {
                'name': '',
                'media': 'medias/seedance/seedance_ex.mp4',
                'content_type': 'gif',
                'prompt': '<blockquote expandable><b>Оживи фотографию</b></blockquote>'
            },
        ],
        'manual': 'https://t.me/seedance25'
    },
    "Minimax - Видео по фото": {
        'name': '<b>minimax-video-01</b>',
        'description': 'Простое видео по тексту. Может работать с фото.',
        'examples': [
            {
                'name': '',
                'media': 'medias/minimax/minimax.mp4',
                'content_type': 'gif',
                'prompt': '<blockquote><b>Черный кот переходит дорогу</b></blockquote>'
            },
        ],
        'manual': 'https://t.me/minimax2025'
    },
    'Sora - Генерация изображений': {
        'name': '<b>gpt-4o-image</b>',
        'description': 'Генерация изображений',
        'examples': [
            {
                'name': '',
                'media': 'medias/sora/sora_ex_2.jpg',
                'content_type': 'photo',
                'prompt': '<blockquote expandable><b>Сделай Фотографию в стиле urban night aesthetic. '
                          'Человек (молодая девушка) висит в центре тёмной улицы ночью, позирует, повиснув '
                          'спиной на дорожном знаке как будто распятый(знак немного прикрыт спиной молодой девушки), '
                          'девушка висит над землей руки в стороны.  сам знак немного подсвечен и отражает '
                          'свет.</b></blockquote>'
            },
        ],
        'manual': 'https://t.me/sora_2026'
    },
    'Sora - Генерация изображений|text': {
        'name': '<b>gpt-4o-image</b>',
        'description': 'Генерация изображений',
        'examples': [
            {
                'name': '',
                'media': 'medias/sora/sora_text.jpg',
                'content_type': 'photo',
                'prompt': '<blockquote expandable><b>Город на Луне, где дома построены из прозрачного стекла и '
                          'управляются мыслями</b></blockquote>'
            },
        ],
        'manual': 'https://t.me/generation_text'
    }
}


MODEL_DESCRIPTIONS = {
    "Veo3 - видео сценарию": "Инструкция:  https://t.me/veo3_2025         \nДелает видео и звук по тексту. Может работать с фото.",
    # "Pixverse v4.5": "Мощная модель Pixverse версии 4.5: создаёт 5–8-секундные ролики в 540p–1080p, с плавной анимацией, лучше отражает сложные действия и больше «понимает» запросы. Подходит для динамичных сторителлинговых клипов.",
    "Kling v2.1 — видео текст+фото": "Инструкция:   https://t.me/kling_promt2025 \nГенерирует видео по тексту или фото.",
    "Seedance 1 Lite — видео по тексту": "Инструкция:    https://t.me/seedance25 \n\nБыстрое видео по тексту.",
    "Minimax - Видео по фото": "Инструкция:  https://t.me/minimax2025 \n\nПростое видео по тексту. Может работать с фото.",
    "Sora - Генерация изображений": "Инструкция:  https://t.me/sora_2026 \n\n Генерация изображении"
}

MODEL_IMAGE_FIELD = {
    "Veo3 - видео сценарию": "image_url",
    # "Pixverse v4.5": "image",
    "Kling v2.1 — видео текст+фото": "start_image",
    "Seedance 1 Lite — видео по тексту": "image",
    'Sora - Генерация изображений': 'image_urls'
    # "Luma Ray-2": "image",
}

MODEL_DURATIONS = {
    # "Veo3": ["3 сек", "5 сек", "10 сек"],
    # "Pixverse v4.5": ["5 сек", "8 сек"],
    "Kling v2.1 — видео текст+фото": ["5 сек", "10 сек"],
    "Seedance 1 Lite — видео по тексту": ["5 сек", "10 сек"],
    # "Luma Ray-2": ["5 сек", "9 сек"]
}

DURATION_PRICES = {
    "Seedance 1 Lite — видео по тексту": {"5 сек": 80, "10 сек": 160},
    # "Luma Ray-2": {"5 сек": 7, "9 сек": 14},
    "Kling v2.1 — видео текст+фото": {"5 сек": 120, "10 сек": 240},
    # "Pixverse v4.5": {
    #     "720p_smooth_5 сек": 6,
    #     "720p_normal_5 сек": 3,
    #     "720p_normal_8 сек": 6,
    #     "1080p_normal_5 сек": 6,
    # },
}

RUB_PRICES = {
    99: 99,
    250: 250,
    400: 400,
    700: 700,
    1500: 1500
}

STARS_PRICES = {
    99: 76,
    250: 189,
    400: 299,
    700: 539,
    1500: 1149
}

ASPECT_INPUTS = {"16:9": "16:9", "9:16": "9:16"}
DEFAULT_GENERATIONS = 0

IMAGE_GPT_COST = 40
TEXT_GPT_COST = 5

VEO_COST = {
    'Veo3 (Качественный)': 150,
    'Veo3 (Бюджетный)': 90
}
