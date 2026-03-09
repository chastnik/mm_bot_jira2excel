from mattermostdriver import Driver
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict
from config import Config
from jira_client import JiraClient
from excel_generator import ExcelGenerator
from user_auth import UserAuthManager
from date_parser import DateParser
import time
import urllib3

# Отключаем SSL предупреждения для production среды
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class MattermostBot:
    """Бот для Mattermost с интеграцией Jira"""

    def __init__(self):
        """Инициализация бота"""
        # Правильная очистка URL от протокола
        clean_url = Config.MATTERMOST_URL if Config.MATTERMOST_URL else ""
        if clean_url.startswith("https://"):
            clean_url = clean_url[8:]  # Удаляем 'https://'
        elif clean_url.startswith("http://"):
            clean_url = clean_url[7:]  # Удаляем 'http://'

        self.driver = Driver(
            {
                "url": clean_url,
                "token": Config.MATTERMOST_TOKEN,
                "scheme": "https",
                "port": 443,
                "basepath": "/api/v4",
                "verify": Config.MATTERMOST_SSL_VERIFY,
                "request_timeout": 30,
                "websocket_kw_args": {
                    "sslopt": (
                        {"cert_reqs": None} if not Config.MATTERMOST_SSL_VERIFY else {}
                    )
                },
            }
        )

        self.excel_generator = ExcelGenerator()
        self.user_auth = (
            UserAuthManager()
        )  # Управление индивидуальными учетными данными
        self.date_parser = DateParser()  # Парсер дат в свободном формате
        self.loop = None  # Будет установлен в connect()

    async def connect(self):
        """Подключение к Mattermost"""
        try:
            # Сохраняем текущий event loop
            self.loop = asyncio.get_event_loop()

            self.driver.login()
            logger.info("Успешно подключились к Mattermost")

            # Получаем информацию о боте
            self.bot_user = self.driver.users.get_user_by_username(Config.BOT_NAME)
            if not self.bot_user:
                self.bot_user = self.driver.users.get_user("me")

            logger.info(f"Бот запущен как: {self.bot_user['username']}")

            # Проверяем доступность существующих DM каналов
            await self._verify_dm_channels()

        except Exception as e:
            logger.error(f"Ошибка подключения к Mattermost: {e}")
            raise

    def start_listening(self):
        """Запуск прослушивания сообщений"""
        if Config.MATTERMOST_USE_WEBSOCKET:
            try:
                logger.info("Запускаем WebSocket соединение...")
                # Запускаем WebSocket синхронно
                self.driver.init_websocket(event_handler=self.handle_event)
                logger.info("WebSocket соединение завершено")
            except Exception as e:
                logger.error(f"Ошибка в WebSocket соединении: {e}")
                logger.info("Переключаемся на HTTP polling режим...")
                self.start_http_polling()
        else:
            logger.info("Запускаем HTTP polling режим (WebSocket отключен)...")
            self.start_http_polling()

    def start_http_polling(self):
        """HTTP polling для получения сообщений"""
        logger.info("Начинаем HTTP polling для получения сообщений...")
        logger.info("🔍 Бот готов к поиску новых DM каналов и сообщений")

        last_check = int(time.time() * 1000)  # Миллисекунды
        dm_channels_cache = set()  # Кэш найденных DM каналов

        while True:
            try:
                current_time = int(time.time() * 1000)
                logger.debug(f"Проверка новых сообщений в {current_time}")

                # Получаем все DM каналы, где участвует бот
                try:
                    # Получаем все каналы бота через team_id
                    teams = self.driver.teams.get_user_teams(self.bot_user["id"])
                    all_channels = []

                    if teams:
                        # Используем первую команду для получения каналов
                        team_id = teams[0]["id"]
                        logger.debug(f"Используем team_id: {team_id}")
                        all_channels = self.driver.channels.get_channels_for_user(
                            self.bot_user["id"], team_id
                        )
                    else:
                        logger.warning("Не найдено команд для пользователя")

                    # Фильтруем только DM каналы (тип 'D')
                    dm_channels = [ch for ch in all_channels if ch.get("type") == "D"]

                    # Логируем найденные каналы
                    current_dm_ids = {ch["id"] for ch in dm_channels}
                    new_channels = current_dm_ids - dm_channels_cache

                    if new_channels:
                        logger.info(
                            f"🆕 Обнаружено новых DM каналов: {len(new_channels)}"
                        )
                        for channel_id in new_channels:
                            logger.info(f"   Новый DM канал: {channel_id}")
                        dm_channels_cache.update(new_channels)

                    logger.debug(f"Мониторим {len(dm_channels)} DM каналов...")

                    # Проверяем каждый DM канал на новые сообщения
                    for channel in dm_channels:
                        channel_id = channel["id"]

                        try:
                            # Получаем последние посты в канале
                            posts_response = self.driver.posts.get_posts_for_channel(
                                channel_id
                            )

                            if posts_response and "posts" in posts_response:
                                posts = posts_response["posts"]

                                for post_id, post in posts.items():
                                    post_time = int(post["create_at"])

                                    # Проверяем новые посты
                                    if post_time > last_check:
                                        user_id = post.get("user_id")
                                        message = post.get("message", "")

                                        # Игнорируем сообщения от бота
                                        if user_id != self.bot_user["id"]:
                                            logger.info(
                                                f"🔥 НОВОЕ СООБЩЕНИЕ! От пользователя {user_id} в канале {channel_id}: '{message[:100]}{'...' if len(message) > 100 else ''}'"
                                            )

                                            # Обрабатываем команду
                                            self.handle_message_sync(
                                                message, channel_id, user_id
                                            )

                        except Exception as e:
                            # Проверяем на ошибку авторизации
                            if (
                                "неверная или истекшая сессия" in str(e).lower()
                                or "unauthorized" in str(e).lower()
                            ):
                                logger.warning(
                                    "🔄 Переподключаемся из-за истекшей сессии..."
                                )
                                try:
                                    self.driver.login()
                                    logger.info("✅ Переподключение успешно")
                                except Exception as reconnect_error:
                                    logger.error(
                                        f"❌ Ошибка переподключения: {reconnect_error}"
                                    )
                            else:
                                logger.debug(
                                    f"Ошибка проверки канала {channel_id}: {e}"
                                )

                    # Проверяем подключение к боту
                    bot_info = self.driver.users.get_user(self.bot_user["id"])
                    logger.debug(
                        f"Статус бота: {bot_info.get('username', 'unknown')} - активен"
                    )

                except Exception as e:
                    # Проверяем на ошибку авторизации
                    if (
                        "неверная или истекшая сессия" in str(e).lower()
                        or "unauthorized" in str(e).lower()
                    ):
                        logger.warning("🔄 Переподключаемся из-за истекшей сессии...")
                        try:
                            self.driver.login()
                            logger.info("✅ Переподключение успешно")
                        except Exception as reconnect_error:
                            logger.error(
                                f"❌ Ошибка переподключения: {reconnect_error}"
                            )
                    else:
                        logger.error(f"Ошибка получения DM каналов: {e}")

                last_check = current_time

                # Пауза между проверками
                time.sleep(10)

            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки HTTP polling")
                break
            except Exception as e:
                logger.error(f"Ошибка в HTTP polling: {e}")
                time.sleep(15)  # Пауза при ошибке

    def handle_post_sync(self, post):
        """Синхронная обработка поста из HTTP polling"""
        try:
            logger.debug(f"Обрабатываем пост: {post.get('id', 'unknown')}")

            # Игнорируем сообщения от самого бота
            if post.get("user_id") == self.bot_user["id"]:
                logger.debug("Игнорируем сообщение от самого бота")
                return

            # Обрабатываем только прямые сообщения боту
            message = post.get("message", "").strip()
            channel_id = post.get("channel_id")
            user_id = post.get("user_id")

            logger.info(
                f"Пост от пользователя {user_id}: '{message[:50]}...' в канале {channel_id}"
            )

            # Проверяем что это прямое сообщение
            if self._is_direct_message(channel_id):
                logger.info(f"Обрабатываем DM сообщение от пользователя {user_id}")
                self.handle_message_sync(message, channel_id, user_id)
            else:
                logger.debug(f"Канал {channel_id} не является прямым сообщением")

        except Exception as e:
            logger.error(f"Ошибка обработки поста: {e}")

    def handle_event(self, event):
        """Обработка событий из Mattermost"""
        try:
            event_type = event.get("event")

            # Обрабатываем создание новых DM каналов
            if event_type == "channel_created":
                self._handle_channel_created_sync(event)

            # Обрабатываем сообщения
            elif event_type == "posted":
                post = json.loads(event["data"]["post"])

                # Игнорируем сообщения от самого бота
                if post.get("user_id") == self.bot_user["id"]:
                    return

                # Обрабатываем только прямые сообщения боту
                message = post.get("message", "").strip()
                channel_id = post.get("channel_id")
                user_id = post.get("user_id")

                # Проверяем что это прямое сообщение
                if self._is_direct_message(channel_id):
                    logger.info(
                        f"🔥 WEBSOCKET: Получено сообщение от пользователя {user_id} в канале {channel_id}"
                    )
                    self.handle_message_sync(message, channel_id, user_id)
                else:
                    # Логируем, что бот не отвечает в каналах
                    logger.debug(
                        f"Игнорируем сообщение в канале {channel_id}: бот работает только в прямых сообщениях"
                    )

            # Обрабатываем добавление пользователей в каналы (включая DM)
            elif event_type == "user_added":
                self._handle_user_added_sync(event)

            # Обрабатываем события пользователей (может помочь при создании новых DM)
            elif event_type == "hello":
                logger.info("🔄 WebSocket подключение установлено")

            elif event_type == "status_change":
                # Игнорируем изменения статуса
                pass

            else:
                logger.debug(f"Получено неизвестное событие: {event_type}")

        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}")

    def _handle_channel_created_sync(self, event):
        """Обработка создания нового канала"""
        try:
            channel_data = json.loads(event.get("data", "{}"))
            channel = channel_data.get("channel", {})

            if channel.get("type") == "D":  # Direct message
                logger.info(f"Создан новый DM канал: {channel.get('id')}")
                # Дополнительная логика при необходимости

        except Exception as e:
            logger.error(f"Ошибка обработки создания канала: {e}")

    def _handle_user_added_sync(self, event):
        """Обработка добавления пользователя в канал"""
        try:
            broadcast = event.get("broadcast", {})
            channel_id = broadcast.get("channel_id")
            user_id = event["data"].get("user_id")

            if channel_id and self._is_direct_message(channel_id):
                logger.info(f"Пользователь {user_id} добавлен в DM канал {channel_id}")

        except Exception as e:
            logger.error(f"Ошибка обработки добавления пользователя: {e}")

    def _is_direct_message(self, channel_id: str) -> bool:
        """Проверка, является ли канал приватным сообщением"""
        try:
            channel = self.driver.channels.get_channel(channel_id)
            is_dm = channel.get("type") == "D"

            # Логируем информацию о канале для отладки
            if is_dm:
                logger.debug(f"Канал {channel_id} является DM каналом")
            else:
                logger.debug(
                    f"Канал {channel_id} НЕ является DM каналом (тип: {channel.get('type')})"
                )

            return is_dm
        except Exception as e:
            logger.error(f"Ошибка проверки типа канала {channel_id}: {e}")
            return False

    def handle_message_sync(self, message: str, channel_id: str, user_id: str):
        """Обработка сообщения пользователя"""
        try:
            logger.info(
                f"📝 Обрабатываем сообщение от {user_id}: '{message[:50]}{'...' if len(message) > 50 else ''}'"
            )

            # Получаем информацию о пользователе для логирования
            try:
                user_info = self.driver.users.get_user(user_id)
                username = user_info.get("username", "unknown")
                logger.info(f"👤 Пользователь: {username} (ID: {user_id})")
            except Exception as e:
                logger.debug(
                    f"Не удалось получить информацию о пользователе {user_id}: {e}"
                )
                username = "unknown"

            # Проверяем, что это действительно DM канал
            if not self._is_direct_message(channel_id):
                logger.warning(
                    f"⚠️ Сообщение получено в не-DM канале {channel_id}, игнорируем"
                )
                return

            message_lower = message.lower().strip()

            # Команды бота
            if any(cmd in message_lower for cmd in ["помощь", "help", "команды"]):
                logger.info(f"🔍 Команда 'помощь' от пользователя {username}")
                self.send_help_sync(channel_id)

            elif any(
                cmd in message_lower
                for cmd in ["настройка", "подключение", "авторизация"]
            ):
                logger.info(f"🔐 Команда 'настройка' от пользователя {username}")
                self.start_jira_auth_sync(channel_id, user_id)

            elif any(cmd in message_lower for cmd in ["проекты", "список проектов"]):
                logger.info(f"📋 Команда 'проекты' от пользователя {username}")
                self.send_projects_list_sync(channel_id, user_id)

            elif "отчет" in message_lower or "трудозатраты" in message_lower:
                logger.info(f"📊 Команда 'отчет' от пользователя {username}")
                self.start_report_generation_sync(channel_id, user_id)

            elif "сброс" in message_lower or "очистить" in message_lower:
                logger.info(f"🗑️ Команда 'сброс' от пользователя {username}")
                self.reset_user_auth_sync(channel_id, user_id)

            elif self.user_auth.get_user_session(user_id):
                logger.info(f"📊 Обработка ввода сессии от пользователя {username}")
                self.handle_session_input_sync(message, channel_id, user_id)

            else:
                logger.info(
                    f"❓ Неизвестная команда от пользователя {username}: '{message[:30]}...'"
                )
                self.send_unknown_command_sync(channel_id)

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            self.send_error_message_sync(
                channel_id, "Произошла ошибка при обработке команды"
            )

    def send_help_sync(self, channel_id: str):
        """Отправка справки по командам"""
        help_text = """
**Бот для выгрузки трудозатрат из Jira** 📊

**Первый запуск:**
• `настройка` - подключение к вашему аккаунту Jira

**Доступные команды:**
• `проекты` - показать список доступных проектов
• `отчет` или `трудозатраты` - сгенерировать отчет по трудозатратам
• `сброс` - очистить сохраненные данные авторизации
• `помощь` - показать эту справку

**Для генерации отчета:**
1. Убедитесь, что вы подключены к Jira (`настройка`)
2. Введите команду `отчет`
3. Выберите один или несколько проектов:
   • Один проект: `PROJ`
   • Несколько проектов: `PROJ1, PROJ2, PROJ3`
4. Укажите период (начальную и конечную дату)
5. Получите Excel файл с трудозатратами

**📅 Указание периода (в свободном формате):**
• `прошлая неделя`, `эта неделя`
• `прошлый квартал`, `этот квартал`
• `2 квартал 2024`, `первый квартал`, `II квартал`
• `прошлый месяц`, `этот месяц` 
• `май`, `июнь 2024`
• `с мая по июнь`
• `с 15 мая по 20 июня`
• `последние 7 дней`, `последние 2 недели`
• `2024-01-01` (один день)
• `с 2024-01-01 по 2024-01-31`

**Безопасность:**
• Каждый пользователь подключается под своим аккаунтом Jira
• Доступны только те проекты, к которым у вас есть права
• Учетные данные хранятся в зашифрованном виде

**Дополнительные возможности:**
• При выборе нескольких проектов создается сводный отчет
• Данные сортируются по дате и включают статистику по каждому проекту
• Поддерживается неограниченное количество проектов в одном отчете

**📚 Полезные ссылки:**
• Инструкция по загрузке эксель файла в КСУП - https://confluence.1solution.ru/x/ZgwgGQ
        """
        self.send_message_sync(channel_id, help_text)

    def start_jira_auth_sync(self, channel_id: str, user_id: str):
        """Начало процесса аутентификации в Jira"""
        try:
            # Проверяем, есть ли уже аутентификация
            if self.user_auth.is_user_authenticated(user_id):
                username, _ = self.user_auth.get_user_credentials(user_id)
                message = f"""
✅ **Вы уже подключены к Jira**

**Текущий пользователь:** {username}

Чтобы изменить учетные данные, введите команду `сброс`, а затем `настройка` заново.
                """
                self.send_message_sync(channel_id, message)
                return

            # Запрашиваем имя пользователя
            message = """
🔐 **Настройка подключения к Jira**

**Шаг 1 из 2:** Введите ваше имя пользователя для подключения к Jira

**Пример:** john.doe или john_doe
            """
            self.send_message_sync(channel_id, message)

            # Сохраняем состояние ожидания имени пользователя
            self.user_auth.update_user_session(
                user_id, step="waiting_username", channel_id=channel_id
            )

        except Exception as e:
            logger.error(f"Ошибка начала аутентификации: {e}")
            self.send_error_message_sync(channel_id, "Ошибка инициализации настройки")

    def reset_user_auth_sync(self, channel_id: str, user_id: str):
        """Сброс аутентификации пользователя"""
        try:
            self.user_auth.remove_user_credentials(user_id)
            message = """
🗑️ **Данные авторизации очищены**

Ваши учетные данные Jira удалены из системы.

Для повторного подключения введите команду `настройка`.
            """
            self.send_message_sync(channel_id, message)

        except Exception as e:
            logger.error(f"Ошибка сброса аутентификации: {e}")
            self.send_error_message_sync(channel_id, "Ошибка сброса данных")

    def send_projects_list_sync(self, channel_id: str, user_id: str):
        """Отправка списка проектов"""
        try:
            # Проверяем аутентификацию пользователя
            if not self.user_auth.is_user_authenticated(user_id):
                self.send_message_sync(
                    channel_id,
                    "❌ **Требуется подключение к Jira**\n\n"
                    "Введите команду `настройка` для подключения к вашему аккаунту Jira.",
                )
                return

            # Получаем учетные данные пользователя
            username, password = self.user_auth.get_user_credentials(user_id)

            if not username or not password:
                self.send_message_sync(
                    channel_id,
                    "❌ Учетные данные не найдены. Выполните команду `настройка`",
                )
                return

            # Создаем Jira клиент для пользователя (после проверки выше username и password точно не None)
            jira_client = JiraClient(str(username), str(password))
            projects = jira_client.get_projects()

            if not projects:
                self.send_message_sync(
                    channel_id, "❌ Не удалось получить список проектов"
                )
                return

            projects_text = "**Доступные проекты:**\n\n"
            for project in projects[:20]:  # Ограничиваем до 20 проектов
                projects_text += f"• `{project['key']}` - {project['name']}\n"

            if len(projects) > 20:
                projects_text += f"\n... и еще {len(projects) - 20} проектов"

            self.send_message_sync(channel_id, projects_text)

        except Exception as e:
            logger.error(f"Ошибка получения списка проектов: {e}")
            self.send_error_message_sync(channel_id, "Ошибка получения списка проектов")

    def start_report_generation_sync(self, channel_id: str, user_id: str):
        """Начало процесса генерации отчета"""
        try:
            # Проверяем аутентификацию пользователя
            if not self.user_auth.is_user_authenticated(user_id):
                self.send_message_sync(
                    channel_id,
                    "❌ **Требуется подключение к Jira**\n\n"
                    "Введите команду `настройка` для подключения к вашему аккаунту Jira.",
                )
                return

            # Инициализируем сессию пользователя
            self.user_auth.update_user_session(
                user_id, step="project_selection", channel_id=channel_id
            )

            self.send_message_sync(
                channel_id,
                "📋 **Генерация отчета по трудозатратам**\n\n"
                "Введите ключ проекта или несколько ключей через запятую:\n"
                "• Один проект: `PROJ`\n"
                "• Несколько проектов: `PROJ1, PROJ2, PROJ3`\n"
                "• Введите `проекты` для просмотра списка доступных проектов",
            )
        except Exception as e:
            logger.error(f"Ошибка начала генерации отчета: {e}")
            self.send_error_message_sync(
                channel_id, "Ошибка инициализации генерации отчета"
            )

    def handle_session_input_sync(self, message: str, channel_id: str, user_id: str):
        """Обработка ввода в рамках сессии пользователя"""
        try:
            session = self.user_auth.get_user_session(user_id)
            step = session.get("step")

            # Обработка аутентификации
            if step == "waiting_username":
                self._handle_username_input_sync(message, channel_id, user_id)
                return
            elif step == "waiting_password":
                self._handle_password_input_sync(message, channel_id, user_id)
                return

            # Генерация отчета
            if step == "project_selection":
                if "проекты" in message:
                    self.send_projects_list_sync(channel_id, user_id)
                    return

                # Получаем учетные данные пользователя
                username, password = self.user_auth.get_user_credentials(user_id)

                if not username or not password:
                    self.send_message_sync(
                        channel_id,
                        "❌ Учетные данные не найдены. Выполните команду `настройка`",
                    )
                    return

                # После проверки выше username и password точно не None
                jira_client = JiraClient(str(username), str(password))

                # Обрабатываем несколько проектов через запятую
                project_keys = [key.strip().upper() for key in message.split(",")]
                projects = jira_client.get_projects()

                # Проверяем все указанные проекты
                selected_projects = []
                invalid_projects = []

                for project_key in project_keys:
                    project = next(
                        (p for p in projects if p["key"] == project_key), None
                    )
                    if project:
                        selected_projects.append(project)
                    else:
                        invalid_projects.append(project_key)

                # Если есть несуществующие проекты
                if invalid_projects:
                    self.send_message_sync(
                        channel_id,
                        f"❌ Проекты не найдены: `{', '.join(invalid_projects)}`\n"
                        f"Введите корректные ключи проектов или `проекты` для просмотра списка.",
                    )
                    return

                # Если не выбран ни один проект
                if not selected_projects:
                    self.send_message_sync(
                        channel_id,
                        "❌ Не указан ни один проект. Введите ключ проекта или `проекты` для просмотра списка.",
                    )
                    return

                self.user_auth.update_user_session(
                    user_id, projects=selected_projects, step="date_period"
                )

                # Формируем сообщение о выбранных проектах
                if len(selected_projects) == 1:
                    projects_text = f"**{selected_projects[0]['name']}** ({selected_projects[0]['key']})"
                else:
                    projects_list = [
                        f"• **{p['name']}** ({p['key']})" for p in selected_projects
                    ]
                    projects_text = f"{len(selected_projects)} проектов:\n" + "\n".join(
                        projects_list
                    )

                help_text = """
**Примеры периодов:**
• `прошлая неделя` или `эта неделя`
• `прошлый квартал` или `этот квартал`
• `2 квартал 2024` или `первый квартал`
• `прошлый месяц` или `этот месяц`  
• `май` или `июнь 2024`
• `с мая по июнь`
• `с 15 мая по 20 июня`
• `последние 7 дней`
• `последние 2 недели`
• `2024-01-01` (один день)
• `с 2024-01-01 по 2024-01-31`

**Или стандартный формат:** YYYY-MM-DD"""

                self.send_message_sync(
                    channel_id,
                    f"✅ Выбрано {projects_text}\n\n"
                    "📅 **Укажите период для отчета:**\n"
                    f"{help_text}",
                )

            elif step == "date_period":
                # Парсим период с помощью нового парсера
                start_date, end_date, explanation = self.date_parser.parse_period(
                    message
                )

                if not start_date or not end_date:
                    # Показываем ошибку и примеры
                    help_text = """
**Попробуйте один из примеров:**
• `прошлая неделя` - за прошлую неделю
• `этот месяц` - текущий месяц
• `май 2024` - май конкретного года  
• `с мая по июнь` - период между месяцами
• `последние 7 дней` - последняя неделя
• `2024-01-01` - конкретный день
• `с 2024-01-01 по 2024-01-31` - точный период"""

                    self.send_message_sync(channel_id, f"{explanation}\n\n{help_text}")
                    return

                # Сохраняем распознанные даты
                self.user_auth.update_user_session(
                    user_id, start_date=start_date, end_date=end_date
                )

                # Показываем что распознали и генерируем отчет
                self.send_message_sync(channel_id, explanation)

                session = self.user_auth.get_user_session(
                    user_id
                )  # Получаем обновленную сессию

                # Генерируем отчет
                self.generate_and_send_report_sync(session, user_id)

                # Очищаем сессию
                self.user_auth.update_user_session(
                    user_id,
                    step=None,
                    projects=None,
                    start_date=None,
                    end_date=None,
                    channel_id=None,
                )

        except Exception as e:
            logger.error(f"Ошибка обработки сессии: {e}")
            self.send_error_message_sync(channel_id, "Ошибка обработки команды")

    def _handle_username_input_sync(self, username: str, channel_id: str, user_id: str):
        """Обработка ввода имени пользователя для аутентификации"""
        try:
            username = username.strip()

            # Простая валидация имени пользователя
            if not username or len(username) < 2:
                self.send_message_sync(
                    channel_id,
                    "❌ Введите корректное имя пользователя (минимум 2 символа).",
                )
                return

            # Сохраняем имя пользователя и переходим к следующему шагу
            self.user_auth.update_user_session(
                user_id, temp_username=username, step="waiting_password"
            )

            message = """
✅ **Имя пользователя сохранено**

**Шаг 2 из 2:** Отправьте ваш пароль для Jira текстовым сообщением

**Важно:** 
- Используйте ваш обычный пароль от Jira
- Пароль будет сохранен в зашифрованном виде
- Никто не сможет увидеть ваш пароль в открытом виде
- Просто напишите пароль в ответном сообщении
            """
            self.send_message_sync(channel_id, message)

        except Exception as e:
            logger.error(f"Ошибка обработки имени пользователя: {e}")
            self.send_error_message_sync(
                channel_id, "Ошибка обработки имени пользователя"
            )

    def _handle_password_input_sync(self, password: str, channel_id: str, user_id: str):
        """Обработка ввода пароля"""
        try:
            password = password.strip()

            # Получаем временно сохраненное имя пользователя
            session = self.user_auth.get_user_session(user_id)
            username = session.get("temp_username")

            if not username:
                self.send_message_sync(
                    channel_id,
                    "❌ Ошибка: имя пользователя не найдено. Начните заново с команды `настройка`",
                )
                return

            if not password:
                self.send_message_sync(
                    channel_id, "❌ Пароль не может быть пустым. Введите ваш пароль."
                )
                return

            self.send_message_sync(channel_id, "🔄 Проверяю подключение к Jira...")

            # Тестируем подключение
            jira_client = JiraClient()
            success, message = jira_client.test_connection(username, password)

            if success:
                # Сохраняем учетные данные
                self.user_auth.save_user_credentials(user_id, username, password)

                # Очищаем временные данные
                self.user_auth.update_user_session(
                    user_id, temp_username=None, step=None
                )

                self.send_message_sync(
                    channel_id,
                    f"✅ **Подключение к Jira установлено!**\n\n"
                    f"{message}\n\n"
                    f"Теперь вы можете использовать:\n"
                    f"• `проекты` - список доступных проектов\n"
                    f"• `отчет` - генерация отчета по трудозатратам",
                )
            else:
                self.send_message_sync(
                    channel_id,
                    f"❌ **Ошибка подключения**\n\n"
                    f"{message}\n\n"
                    f"Проверьте правильность имени пользователя и пароля, затем попробуйте снова.",
                )

        except Exception as e:
            logger.error(f"Ошибка обработки пароля: {e}")
            self.send_error_message_sync(channel_id, "Ошибка обработки пароля")

    def _validate_date(self, date_str: str) -> bool:
        """Валидация формата даты"""
        try:
            datetime.strptime(date_str.strip(), "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def generate_and_send_report_sync(self, session: Dict, user_id: str):
        """Генерация и отправка отчета"""
        try:
            channel_id = session["channel_id"]
            projects = session["projects"]
            start_date = session["start_date"]
            end_date = session["end_date"]

            self.send_message_sync(
                channel_id, "⏳ Генерирую отчет... Это может занять некоторое время."
            )

            # Получаем учетные данные пользователя
            username, password = self.user_auth.get_user_credentials(user_id)

            if not username or not password:
                raise ValueError("Учетные данные пользователя не найдены")

            # После проверки выше username и password точно не None
            jira_client = JiraClient(str(username), str(password))

            # Получаем трудозатраты из Jira для всех проектов
            all_worklogs = []
            project_stats = []

            for project in projects:
                project_worklogs = jira_client.get_worklogs_for_project(
                    project["key"], start_date, end_date
                )

                if project_worklogs:
                    all_worklogs.extend(project_worklogs)
                    project_hours = sum(
                        float(w["hours"].replace(",", ".")) for w in project_worklogs
                    )
                    project_stats.append(
                        {
                            "name": project["name"],
                            "key": project["key"],
                            "records": len(project_worklogs),
                            "hours": project_hours,
                        }
                    )
                    logger.info(
                        f"Проект {project['key']}: {len(project_worklogs)} записей, {project_hours:.1f} ч"
                    )

            if not all_worklogs:
                projects_names = [p["name"] for p in projects]
                self.send_message_sync(
                    channel_id,
                    f"📭 Трудозатраты по проектам **{', '.join(projects_names)}** "
                    f"за период с {start_date} по {end_date} не найдены.",
                )
                return

            # Сортируем записи по дате
            all_worklogs.sort(key=lambda x: x["date"])

            # Генерируем название для отчета
            if len(projects) == 1:
                report_name = projects[0]["name"]
            else:
                report_name = f"Сводный отчет по {len(projects)} проектам"

            # Генерируем Excel файл
            excel_data = self.excel_generator.generate_timesheet_report(
                all_worklogs, report_name, start_date, end_date, projects
            )

            filename = self.excel_generator.generate_filename_for_multiple_projects(
                projects, start_date, end_date
            )

            # Формируем статистику для сообщения
            total_records = len(all_worklogs)
            total_hours = sum(float(w["hours"].replace(",", ".")) for w in all_worklogs)

            # Формируем детальную статистику по проектам
            stats_text = ""
            if len(projects) > 1:
                stats_text = "\n\n**Статистика по проектам:**\n"
                for stat in project_stats:
                    stats_text += f"• **{stat['name']}** ({stat['key']}): {stat['records']} записей, {stat['hours']:.1f} ч\n"

            # Отправляем файл
            self.send_file_sync(
                channel_id,
                excel_data,
                filename,
                f"📊 **Отчет по трудозатратам готов!**\n\n"
                f"**Проекты:** {', '.join([p['name'] for p in projects])}\n"
                f"**Период:** с {start_date} по {end_date}\n"
                f"**Всего записей:** {total_records}\n"
                f"**Общее время:** {total_hours:.1f} ч"
                f"{stats_text}",
            )

            # Отправляем подсказку о том, как сформировать новый отчёт
            help_message = """
🔄 **Хотите создать новый отчёт?**

**Быстрые команды:**
• `отчет` - создать новый отчёт
• `проекты` - посмотреть доступные проекты
• `помощь` - полная справка по командам

**💡 Совет:** Можете сразу написать `отчет` для быстрого создания нового отчёта!
            """
            self.send_message_sync(channel_id, help_message)

        except Exception as e:
            logger.error(f"Ошибка генерации отчета: {e}")
            self.send_error_message_sync(
                session["channel_id"], "Произошла ошибка при генерации отчета"
            )

    def send_message_sync(self, channel_id: str, message: str):
        """Отправка сообщения в канал"""
        try:
            # Ограничиваем длину сообщения (лимит Mattermost ~16384 символа)
            max_length = 15000
            if len(message) > max_length:
                # Обрезаем сообщение и добавляем предупреждение
                truncated_message = (
                    message[: max_length - 200]
                    + "\n\n⚠️ **Сообщение обрезано из-за ограничений длины**"
                )
                logger.warning(
                    f"Сообщение обрезано с {len(message)} до {len(truncated_message)} символов"
                )
                message = truncated_message

            self.driver.posts.create_post(
                {"channel_id": channel_id, "message": message}
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            # Попытка отправить короткое сообщение об ошибке
            try:
                error_msg = f"❌ Произошла ошибка при отправке сообщения.\n\nОшибка: {str(e)[:200]}..."
                self.driver.posts.create_post(
                    {"channel_id": channel_id, "message": error_msg}
                )
            except Exception:
                logger.error("Не удалось отправить даже сообщение об ошибке")

    def send_file_sync(
        self, channel_id: str, file_data: bytes, filename: str, message: str = ""
    ):
        """Отправка файла в канал"""
        try:
            # Загружаем файл
            file_response = self.driver.files.upload_file(
                channel_id=channel_id,
                files={
                    "files": (
                        filename,
                        file_data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

            file_id = file_response["file_infos"][0]["id"]

            # Отправляем сообщение с файлом
            self.driver.posts.create_post(
                {"channel_id": channel_id, "message": message, "file_ids": [file_id]}
            )

        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            self.send_error_message_sync(channel_id, "Ошибка отправки файла")

    def send_error_message_sync(self, channel_id: str, error_msg: str):
        """Отправка сообщения об ошибке"""
        self.send_message_sync(channel_id, f"❌ **Ошибка:** {error_msg}")

    def send_unknown_command_sync(self, channel_id: str):
        """Отправка сообщения о неизвестной команде"""
        message = """
❓ **Не понимаю команду**

**Попробуйте:**
• `помощь` - список всех команд
• `настройка` - подключение к Jira
• `отчет` - создать отчет по трудозатратам

**Для новых пользователей:** начните с команды `настройка`
        """
        self.send_message_sync(channel_id, message)

    def disconnect(self):
        """Отключение от Mattermost"""
        try:
            self.driver.logout()
            logger.info("Отключились от Mattermost")
        except Exception as e:
            logger.error(f"Ошибка отключения: {e}")

    async def _verify_dm_channels(self):
        """Проверка доступности DM каналов для аутентифицированных пользователей"""
        try:
            authenticated_count = self.user_auth.get_authenticated_users_count()
            if authenticated_count > 0:
                logger.info(
                    f"Найдено {authenticated_count} аутентифицированных пользователей"
                )
            else:
                logger.info("Нет аутентифицированных пользователей")

        except Exception as e:
            logger.error(f"Ошибка проверки пользователей: {e}")

    def _ensure_dm_channel_access(self, user_id: str, channel_id: str):
        """Обеспечение доступа к DM каналу"""
        try:
            # Получаем информацию о канале
            channel = self.driver.channels.get_channel(channel_id)

            if channel.get("type") != "D":
                logger.warning(f"Канал {channel_id} не является DM каналом")
                return False

            # Проверяем, что бот является участником канала
            members = self.driver.channels.get_channel_members(channel_id)
            bot_is_member = any(
                member["user_id"] == self.bot_user["id"] for member in members
            )

            if not bot_is_member:
                logger.warning(f"Бот не является участником DM канала {channel_id}")
                # В DM каналах бот автоматически становится участником при создании
                return False

            logger.debug(f"Доступ к DM каналу {channel_id} подтвержден")
            return True

        except Exception as e:
            logger.error(f"Ошибка проверки доступа к каналу {channel_id}: {e}")
            return False

    def create_or_get_dm_channel(self, user_id: str):
        """Создает или получает DM канал с пользователем"""
        try:
            logger.info(f"🔍 Ищем/создаем DM канал с пользователем {user_id}...")

            # Сначала проверяем, существует ли уже DM канал
            teams = self.driver.teams.get_user_teams(self.bot_user["id"])
            all_channels = []

            if teams:
                team_id = teams[0]["id"]
                all_channels = self.driver.channels.get_channels_for_user(
                    self.bot_user["id"], team_id
                )
            else:
                logger.warning(
                    "Не найдено команд для пользователя при создании DM канала"
                )
            dm_channels = [ch for ch in all_channels if ch.get("type") == "D"]

            # Ищем существующий канал с этим пользователем
            for channel in dm_channels:
                channel_id = channel["id"]
                try:
                    # Получаем участников канала
                    members = self.driver.channels.get_channel_members(channel_id)
                    member_ids = {member["user_id"] for member in members}

                    # Проверяем, что в канале только бот и указанный пользователь
                    if (
                        user_id in member_ids
                        and self.bot_user["id"] in member_ids
                        and len(member_ids) == 2
                    ):
                        logger.info(f"✅ Найден существующий DM канал: {channel_id}")
                        return channel_id

                except Exception as e:
                    logger.debug(f"Ошибка проверки канала {channel_id}: {e}")
                    continue

            # Если не найден, создаем новый DM канал
            logger.info(f"📱 Создаем новый DM канал с пользователем {user_id}...")

            dm_channel = self.driver.channels.create_direct_message_channel(
                [self.bot_user["id"], user_id]
            )
            channel_id = dm_channel["id"]

            logger.info(f"✅ Создан новый DM канал: {channel_id}")

            # Отправляем приветственное сообщение
            welcome_message = """
🤖 **Добро пожаловать!**

Я бот для выгрузки трудозатрат из Jira в Excel формат.

**Для начала работы введите:** `настройка`

**Или посмотрите справку:** `помощь`
            """
            self.send_message_sync(channel_id, welcome_message)

            return channel_id

        except Exception as e:
            logger.error(f"Ошибка создания DM канала с пользователем {user_id}: {e}")
            return None

    def connect_sync(self):
        """Подключение к Mattermost (синхронная версия)"""
        try:
            self.driver.login()
            logger.info("Успешно подключились к Mattermost")

            # Получаем информацию о боте
            self.bot_user = self.driver.users.get_user_by_username(Config.BOT_NAME)
            if not self.bot_user:
                self.bot_user = self.driver.users.get_user("me")

            logger.info(f"Бот запущен как: {self.bot_user['username']}")

            # Проверяем сохраненные пользователи
            authenticated_users = self.user_auth.get_authenticated_users_count()
            if authenticated_users > 0:
                logger.info(
                    f"Загружено {authenticated_users} аутентифицированных пользователей"
                )
            else:
                logger.info("Нет аутентифицированных пользователей")

        except Exception as e:
            logger.error(f"Ошибка подключения к Mattermost: {e}")
            raise

    def test_send_message(self, channel_id=None, message=None):
        """Тестовая функция для отправки сообщения"""
        try:
            if not channel_id:
                # Если канал не указан, попробуем найти любой доступный DM канал
                teams = self.driver.teams.get_user_teams(self.bot_user["id"])
                channels = []

                if teams:
                    team_id = teams[0]["id"]
                    channels = self.driver.channels.get_channels_for_user(
                        self.bot_user["id"], team_id
                    )
                else:
                    logger.error("Не найдено команд для тестирования")
                    return False

                dm_channels = [ch for ch in channels if ch.get("type") == "D"]
                if dm_channels:
                    channel_id = dm_channels[0]["id"]
                else:
                    logger.error("Не найдено DM каналов для тестирования")
                    return False

            if not message:
                message = (
                    "🤖 **ТЕСТОВОЕ СООБЩЕНИЕ**\n\nБот работает и может отправлять сообщения!\nВремя: "
                    + str(time.time())
                )

            self.send_message_sync(channel_id, message)
            logger.info(
                f"✅ Тестовое сообщение успешно отправлено в канал {channel_id}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового сообщения: {e}")
            return False
