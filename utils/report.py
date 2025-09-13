import asyncio

import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from openai import AsyncOpenAI

import config


class ReportCreator:
    def __init__(self, openai_api_key, google_credentials_path):
        self.openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            http_client=httpx.AsyncClient(proxy='http://6L4YePzU:Mrnd5Tsy@212.193.143.10:63196')
        )
        self.docs_service = self.setup_google_docs(google_credentials_path)
        self.drive_service = self.setup_google_drive(google_credentials_path)

    def setup_google_docs(self, credentials_path):
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/documents']
        )
        return build('docs', 'v1', credentials=credentials)

    def setup_google_drive(self, credentials_path):
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        return build('drive', 'v3', credentials=credentials)

    async def generate_referat_structure(self, topic, length="medium", style="academic"):
        """Генерирует структуру реферата"""
        length_map = {
            "short": "1500-2000 слов",
            "medium": "2500-3500 слов",
            "long": "4000-5000 слов"
        }

        prompt = f"""
        Создай детальную структуру реферата на тему: "{topic}"
        Объем: {length_map[length]}
        Стиль: {style}

        Верни строго в формате:
        ЗАГОЛОВОК: [Название раздела]
        ПОДЗАГОЛОВОК: [Подраздел]
        ОПИСАНИЕ: [2-3 предложения о содержании]
        КЛЮЧЕВЫЕ_ПУНКТЫ: [ключевые аспекты через запятую]
        """

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты эксперт по созданию академических структур рефератов."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )

        return response.choices[0].message.content

    async def generate_section_content(self, topic, section_info, previous_sections=""):
        """Генерирует содержание для конкретного раздела"""
        prompt = f"""
        Напиши раздел реферата на тему: "{topic}"

        Информация о разделе:
        {section_info}

        Предыдущие разделы (для контекста):
        {previous_sections}

        Требования:
        - Академический стиль
        - Используй научную терминологию
        - Приводи факты и данные
        - Соблюдай логическую связность
        - Объем: 300-500 слов
        - Добавь подзаголовки где уместно
        """

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты профессиональный академический писатель."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=1500
        )

        return response.choices[0].message.content

    def create_google_doc(self, title, content):
        """Создает Google Doc с содержимым"""
        # Создаем документ
        doc = self.docs_service.documents().create(body={'title': title}).execute()
        document_id = doc['documentId']

        # Форматируем контент для Google Docs
        requests = self.prepare_document_requests(content)

        # Добавляем контент
        self.docs_service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()

        return document_id

    def prepare_document_requests(self, content):
        """Подготавливает запросы для форматирования документа"""
        requests = []

        # Сначала вставляем весь текст целиком
        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': content
            }
        })

        # Теперь добавляем форматирование для заголовков
        # Находим позиции заголовков и применяем стили
        lines = content.split('\n')
        current_index = 1  # Начинаем с начала документа

        for line in lines:
            if line.startswith('# '):
                # Заголовок 1 уровня
                end_index = current_index + len(line)
                requests.append({
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': end_index
                        },
                        'paragraphStyle': {
                            'namedStyleType': 'HEADING_1'
                        },
                        'fields': 'namedStyleType'
                    }
                })
            elif line.startswith('## '):
                end_index = current_index + len(line)
                requests.append({
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': end_index
                        },
                        'paragraphStyle': {
                            'namedStyleType': 'HEADING_2'
                        },
                        'fields': 'namedStyleType'
                    }
                })

            current_index += len(line) + 1  # +1 для символа новой строки

        return requests


    def create_heading_request(self, text, index, level):
        return {
            'insertText': {
                'location': {'index': index},
                'text': text + '\n'
            }
        }

    def create_paragraph_request(self, text, index):
        return {
            'insertText': {
                'location': {'index': index},
                'text': text + '\n'
            }
        }

    def make_document_public(self, file_id):
        """Делает файл публичным и возвращает ссылку"""
        try:
            # Устанавливаем публичный доступ
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }

            self.drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()

            # Получаем публичную ссылку
            file_metadata = self.drive_service.files().get(
                fileId=file_id,
                fields='webViewLink'
            ).execute()

            return file_metadata.get('webViewLink')
        except Exception as e:
            print(f"Ошибка при установке публичного доступа: {e}")
            # Возвращаем обычную ссылку если не удалось сделать публичной
            return f"https://docs.google.com/document/d/{file_id}"

    async def create_complete_referat(self, topic, description="", length="medium", style="academic"):
        """Полный процесс создания реферата"""
        print("Генерирую структуру реферата...")
        structure = await self.generate_referat_structure(topic, length, style)

        print("Анализирую структуру...")
        sections = self.parse_structure(structure)

        full_content = f"# {topic}\n\n"
        if description:
            full_content += f"## Описание\n{description}\n\n"

        previous_sections = ""

        print("Генерирую содержание...")
        for i, section in enumerate(sections, 1):
            print(f"Обрабатываю раздел {i}/{len(sections)}: {section['title']}")

            section_content = await self.generate_section_content(
                topic,
                f"Раздел: {section['title']}\nОписание: {section.get('description', '')}",
                previous_sections
            )

            full_content += f"# {section['title']}\n\n{section_content}\n\n"
            previous_sections += f"\n{section['title']}: {section_content[:200]}..."

        print("Создаю Google Doc...")
        doc_id = self.create_google_doc(f"Реферат: {topic}", full_content)

        return doc_id, full_content

    def parse_structure(self, structure_text):
        """Парсит сгенерированную структуру"""
        sections = []
        current_section = {}

        for line in structure_text.split('\n'):
            line = line.strip()
            if line.startswith('ЗАГОЛОВОК:'):
                if current_section:
                    sections.append(current_section)
                current_section = {'title': line.replace('ЗАГОЛОВОК:', '').strip()}
            elif line.startswith('ОПИСАНИЕ:'):
                current_section['description'] = line.replace('ОПИСАНИЕ:', '').strip()
            elif line.startswith('КЛЮЧЕВЫЕ_ПУНКТЫ:'):
                current_section['key_points'] = line.replace('КЛЮЧЕВЫЕ_ПУНКТЫ:', '').strip()

        if current_section:
            sections.append(current_section)

        return sections


# Использование
async def main():
    # Инициализация
    creator = ReportCreator(
        openai_api_key=config.openai_api_token,
        google_credentials_path="/Users/kirill/Desktop/ai-generation-robot-master/data/users-447515-c4ca08bde40f.json"
    )

    # Создание реферата
    topic = "Искусственный интеллект в современном образовании"
    description = "Анализ применения AI технологий в учебном процессе, преимущества и challenges"

    doc_id, content = await creator.create_complete_referat(
        topic=topic,
        description=description,
        length="medium",
        style="academic"
    )
    url = creator.make_document_public(doc_id)

    print(f"Реферат создан! Ссылка: https://docs.google.com/document/d/{doc_id}")
    print(url)
    return url


if __name__ == "__main__":
    asyncio.run(main())