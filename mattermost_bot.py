from mattermostdriver import Driver
import asyncio
import logging
import json
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import Config
from jira_client import JiraClient
from excel_generator import ExcelGenerator
from user_auth import UserAuthManager

logger = logging.getLogger(__name__)

class MattermostBot:
    """Бот для Mattermost с интеграцией Jira"""
    
    def __init__(self):
        """Инициализация бота"""
        self.driver = Driver({
            'url': Config.MATTERMOST_URL,
            'token': Config.MATTERMOST_TOKEN,
            'scheme': 'https',
            'port': 443,
            'basepath': '/api/v4'
        })
        
        self.excel_generator = ExcelGenerator()
        self.user_auth = UserAuthManager()  # Управление индивидуальными учетными данными
        
    async def connect(self):
        """Подключение к Mattermost"""
        try:
            self.driver.login()
            logger.info("Успешно подключились к Mattermost")
            
            # Получаем информацию о боте
            self.bot_user = self.driver.users.get_user_by_username(Config.BOT_NAME)
            if not self.bot_user:
                self.bot_user = self.driver.users.get_user('me')
            
            logger.info(f"Бот запущен как: {self.bot_user['username']}")
            
            # Проверяем доступность существующих DM каналов
            await self._verify_dm_channels()
            
        except Exception as e:
            logger.error(f"Ошибка подключения к Mattermost: {e}")
            raise
    
    async def start_listening(self):
        """Запуск прослушивания сообщений"""
        try:
            # Получаем события через WebSocket
            for response in self.driver.init_websocket(event_handler=self.handle_event):
                pass
        except Exception as e:
            logger.error(f"Ошибка в WebSocket соединении: {e}")
    
    async def handle_event(self, event):
        """Обработка событий из Mattermost"""
        try:
            event_type = event.get('event')
            
            # Обрабатываем создание новых DM каналов
            if event_type == 'channel_created':
                await self._handle_channel_created(event)
            
            # Обрабатываем сообщения
            elif event_type == 'posted':
                post = json.loads(event['data']['post'])
                
                # Игнорируем сообщения от самого бота
                if post.get('user_id') == self.bot_user['id']:
                    return
                
                # Обрабатываем только прямые сообщения боту
                message = post.get('message', '').strip()
                channel_id = post.get('channel_id')
                user_id = post.get('user_id')
                
                # Проверяем что это прямое сообщение
                if self._is_direct_message(channel_id):
                    logger.info(f"Получено сообщение от пользователя {user_id} в канале {channel_id}")
                    await self.handle_message(message, channel_id, user_id)
                else:
                    # Логируем, что бот не отвечает в каналах
                    logger.debug(f"Игнорируем сообщение в канале {channel_id}: бот работает только в прямых сообщениях")
            
            # Обрабатываем добавление пользователей в каналы (включая DM)
            elif event_type == 'user_added':
                await self._handle_user_added(event)
                    
        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}")
            
    async def _handle_channel_created(self, event):
        """Обработка создания нового канала"""
        try:
            channel_data = json.loads(event.get('data', '{}'))
            channel = channel_data.get('channel', {})
            
            if channel.get('type') == 'D':  # Direct message
                logger.info(f"Создан новый DM канал: {channel.get('id')}")
                # Дополнительная логика при необходимости
                
        except Exception as e:
            logger.error(f"Ошибка обработки создания канала: {e}")
    
    async def _handle_user_added(self, event):
        """Обработка добавления пользователя в канал"""
        try:
            broadcast = event.get('broadcast', {})
            channel_id = broadcast.get('channel_id')
            user_id = event['data'].get('user_id')
            
            if channel_id and self._is_direct_message(channel_id):
                logger.info(f"Пользователь {user_id} добавлен в DM канал {channel_id}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки добавления пользователя: {e}")
    

    
    def _is_direct_message(self, channel_id: str) -> bool:
        """Проверка, является ли канал приватным сообщением"""
        try:
            channel = self.driver.channels.get_channel(channel_id)
            is_dm = channel.get('type') == 'D'
            
            # Логируем информацию о канале для отладки
            if is_dm:
                logger.debug(f"Канал {channel_id} является DM каналом")
            else:
                logger.debug(f"Канал {channel_id} НЕ является DM каналом (тип: {channel.get('type')})")
                
            return is_dm
        except Exception as e:
            logger.error(f"Ошибка проверки типа канала {channel_id}: {e}")
            return False
    
    async def handle_message(self, message: str, channel_id: str, user_id: str):
        """Обработка сообщения пользователя"""
        try:
            message = message.lower().strip()
            
            # Команды бота
            if any(cmd in message for cmd in ['помощь', 'help', 'команды']):
                await self.send_help(channel_id)
            
            elif any(cmd in message for cmd in ['настройка', 'подключение', 'авторизация']):
                await self.start_jira_auth(channel_id, user_id)
            
            elif any(cmd in message for cmd in ['проекты', 'список проектов']):
                await self.send_projects_list(channel_id, user_id)
            
            elif 'отчет' in message or 'трудозатраты' in message:
                await self.start_report_generation(channel_id, user_id)
            
            elif 'сброс' in message or 'очистить' in message:
                await self.reset_user_auth(channel_id, user_id)
            
            elif self.user_auth.get_user_session(user_id):
                await self.handle_session_input(message, channel_id, user_id)
            
            else:
                await self.send_unknown_command(channel_id)
                
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            await self.send_error_message(channel_id, "Произошла ошибка при обработке команды")
    
    async def send_help(self, channel_id: str):
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

**Формат дат:** YYYY-MM-DD (например: 2024-01-15)

**Безопасность:**
• Каждый пользователь подключается под своим аккаунтом Jira
• Доступны только те проекты, к которым у вас есть права
• Учетные данные хранятся в зашифрованном виде

**Дополнительные возможности:**
• При выборе нескольких проектов создается сводный отчет
• Данные сортируются по дате и включают статистику по каждому проекту
• Поддерживается неограниченное количество проектов в одном отчете
        """
        await self.send_message(channel_id, help_text)
    
    async def start_jira_auth(self, channel_id: str, user_id: str):
        """Начало процесса аутентификации в Jira"""
        try:
            # Проверяем, есть ли уже аутентификация
            if self.user_auth.is_user_authenticated(user_id):
                email, _ = self.user_auth.get_user_credentials(user_id)
                message = f"""
✅ **Вы уже подключены к Jira**

**Текущий аккаунт:** {email}

Чтобы изменить учетные данные, введите команду `сброс`, а затем `настройка` заново.
                """
                await self.send_message(channel_id, message)
                return
            
            # Запрашиваем email
            message = """
🔐 **Настройка подключения к Jira**

**Шаг 1 из 2:** Введите ваш email для подключения к Jira

**Пример:** user@company.com
            """
            await self.send_message(channel_id, message)
            
            # Сохраняем состояние ожидания email
            self.user_auth.update_user_session(user_id, 
                step='waiting_email',
                channel_id=channel_id
            )
            
        except Exception as e:
            logger.error(f"Ошибка начала аутентификации: {e}")
            await self.send_error_message(channel_id, "Ошибка инициализации настройки")
    
    async def reset_user_auth(self, channel_id: str, user_id: str):
        """Сброс аутентификации пользователя"""
        try:
            self.user_auth.remove_user_credentials(user_id)
            message = """
🗑️ **Данные авторизации очищены**

Ваши учетные данные Jira удалены из системы.

Для повторного подключения введите команду `настройка`.
            """
            await self.send_message(channel_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка сброса аутентификации: {e}")
            await self.send_error_message(channel_id, "Ошибка сброса данных")
    
    async def send_projects_list(self, channel_id: str, user_id: str):
        """Отправка списка проектов"""
        try:
            # Проверяем аутентификацию пользователя
            if not self.user_auth.is_user_authenticated(user_id):
                await self.send_message(channel_id, 
                    "❌ **Требуется подключение к Jira**\n\n"
                    "Введите команду `настройка` для подключения к вашему аккаунту Jira.")
                return
            
            # Получаем учетные данные пользователя
            email, token = self.user_auth.get_user_credentials(user_id)
            
            # Создаем Jira клиент для пользователя
            jira_client = JiraClient(email, token)
            projects = jira_client.get_projects()
            
            if not projects:
                await self.send_message(channel_id, "❌ Не удалось получить список проектов")
                return
            
            projects_text = "**Доступные проекты:**\n\n"
            for project in projects[:20]:  # Ограничиваем до 20 проектов
                projects_text += f"• `{project['key']}` - {project['name']}\n"
            
            if len(projects) > 20:
                projects_text += f"\n... и еще {len(projects) - 20} проектов"
            
            await self.send_message(channel_id, projects_text)
            
        except Exception as e:
            logger.error(f"Ошибка получения списка проектов: {e}")
            await self.send_error_message(channel_id, "Ошибка получения списка проектов")
    
    async def start_report_generation(self, channel_id: str, user_id: str):
        """Начало процесса генерации отчета"""
        try:
            # Проверяем аутентификацию пользователя
            if not self.user_auth.is_user_authenticated(user_id):
                await self.send_message(channel_id, 
                    "❌ **Требуется подключение к Jira**\n\n"
                    "Введите команду `настройка` для подключения к вашему аккаунту Jira.")
                return
            
            # Инициализируем сессию пользователя
            self.user_auth.update_user_session(user_id,
                step='project_selection',
                channel_id=channel_id
            )
            
            await self.send_message(channel_id, 
                "📋 **Генерация отчета по трудозатратам**\n\n"
                "Введите ключ проекта или несколько ключей через запятую:\n"
                "• Один проект: `PROJ`\n"
                "• Несколько проектов: `PROJ1, PROJ2, PROJ3`\n"
                "• Введите `проекты` для просмотра списка доступных проектов"
            )
        except Exception as e:
            logger.error(f"Ошибка начала генерации отчета: {e}")
            await self.send_error_message(channel_id, "Ошибка инициализации генерации отчета")
    
    async def handle_session_input(self, message: str, channel_id: str, user_id: str):
        """Обработка ввода в рамках сессии пользователя"""
        try:
            session = self.user_auth.get_user_session(user_id)
            step = session.get('step')
            
            # Обработка аутентификации
            if step == 'waiting_email':
                await self._handle_email_input(message, channel_id, user_id)
                return
            elif step == 'waiting_token':
                await self._handle_token_input(message, channel_id, user_id)
                return
        
            # Генерация отчета
            if step == 'project_selection':
                if 'проекты' in message:
                    await self.send_projects_list(channel_id, user_id)
                    return
                
                # Получаем учетные данные пользователя
                email, token = self.user_auth.get_user_credentials(user_id)
                jira_client = JiraClient(email, token)
                
                # Обрабатываем несколько проектов через запятую
                project_keys = [key.strip().upper() for key in message.split(',')]
                projects = jira_client.get_projects()
            
            # Проверяем все указанные проекты
            selected_projects = []
            invalid_projects = []
            
            for project_key in project_keys:
                project = next((p for p in projects if p['key'] == project_key), None)
                if project:
                    selected_projects.append(project)
                else:
                    invalid_projects.append(project_key)
            
            # Если есть несуществующие проекты
            if invalid_projects:
                await self.send_message(channel_id, 
                    f"❌ Проекты не найдены: `{', '.join(invalid_projects)}`\n"
                    f"Введите корректные ключи проектов или `проекты` для просмотра списка.")
                return
            
            # Если не выбран ни один проект
            if not selected_projects:
                await self.send_message(channel_id, 
                    "❌ Не указан ни один проект. Введите ключ проекта или `проекты` для просмотра списка.")
                return
            
                self.user_auth.update_user_session(user_id,
                    projects=selected_projects,
                    step='start_date'
                )
            
            # Формируем сообщение о выбранных проектах
            if len(selected_projects) == 1:
                projects_text = f"**{selected_projects[0]['name']}** ({selected_projects[0]['key']})"
            else:
                projects_list = [f"• **{p['name']}** ({p['key']})" for p in selected_projects]
                projects_text = f"{len(selected_projects)} проектов:\n" + "\n".join(projects_list)
            
            await self.send_message(channel_id, 
                f"✅ Выбрано {projects_text}\n\n"
                "Введите дату начала периода в формате YYYY-MM-DD (например: 2024-01-01):"
            )
        
            elif step == 'start_date':
                if not self._validate_date(message):
                    await self.send_message(channel_id, 
                        "❌ Некорректный формат даты. Используйте формат YYYY-MM-DD (например: 2024-01-01)")
                    return
                
                self.user_auth.update_user_session(user_id,
                    start_date=message.strip(),
                    step='end_date'
                )
                await self.send_message(channel_id, 
                    f"✅ Дата начала: {message}\n\n"
                    "Введите дату окончания периода в формате YYYY-MM-DD:"
                )
        
            elif step == 'end_date':
                if not self._validate_date(message):
                    await self.send_message(channel_id, 
                        "❌ Некорректный формат даты. Используйте формат YYYY-MM-DD")
                    return
                
                end_date = message.strip()
                
                # Проверяем, что дата окончания не раньше даты начала
                if end_date < session.get('start_date', ''):
                    await self.send_message(channel_id, 
                        "❌ Дата окончания не может быть раньше даты начала")
                    return
                
                # Добавляем конечную дату в сессию
                self.user_auth.update_user_session(user_id, end_date=end_date)
                session = self.user_auth.get_user_session(user_id)  # Получаем обновленную сессию
                
                # Генерируем отчет
                await self.generate_and_send_report(session, user_id)
                
                # Очищаем сессию
                self.user_auth.update_user_session(user_id, 
                    step=None, projects=None, start_date=None, end_date=None, channel_id=None)
        
        except Exception as e:
            logger.error(f"Ошибка обработки сессии: {e}")
            await self.send_error_message(channel_id, "Ошибка обработки команды")
    
    async def _handle_email_input(self, email: str, channel_id: str, user_id: str):
        """Обработка ввода email для аутентификации"""
        try:
            email = email.strip()
            
            # Простая валидация email
            if '@' not in email or '.' not in email:
                await self.send_message(channel_id, 
                    "❌ Некорректный формат email. Введите корректный email адрес.")
                return
            
            # Сохраняем email и переходим к следующему шагу
            self.user_auth.update_user_session(user_id,
                temp_email=email,
                step='waiting_token'
            )
            
            message = """
✅ **Email сохранен**

**Шаг 2 из 2:** Введите ваш API токен для Jira

**Как получить токен:**
1. Войдите в Jira под своей учетной записью
2. Перейдите в **Account Settings** → **Security** → **API tokens**
3. Нажмите **Create API token**
4. Скопируйте сгенерированный токен и введите его здесь

**Важно:** Токен будет сохранен в зашифрованном виде
            """
            await self.send_message(channel_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка обработки email: {e}")
            await self.send_error_message(channel_id, "Ошибка обработки email")
    
    async def _handle_token_input(self, token: str, channel_id: str, user_id: str):
        """Обработка ввода API токена"""
        try:
            token = token.strip()
            
            # Получаем временно сохраненный email
            session = self.user_auth.get_user_session(user_id)
            email = session.get('temp_email')
            
            if not email:
                await self.send_message(channel_id, "❌ Ошибка: email не найден. Начните заново с команды `настройка`")
                return
            
            await self.send_message(channel_id, "🔄 Проверяю подключение к Jira...")
            
            # Тестируем подключение
            jira_client = JiraClient()
            success, message = jira_client.test_connection(email, token)
            
            if success:
                # Сохраняем учетные данные
                self.user_auth.save_user_credentials(user_id, email, token)
                
                # Очищаем временные данные
                self.user_auth.update_user_session(user_id,
                    temp_email=None,
                    step=None
                )
                
                await self.send_message(channel_id, 
                    f"✅ **Подключение к Jira установлено!**\n\n"
                    f"{message}\n\n"
                    f"Теперь вы можете использовать:\n"
                    f"• `проекты` - список доступных проектов\n"
                    f"• `отчет` - генерация отчета по трудозатратам"
                )
            else:
                await self.send_message(channel_id, 
                    f"❌ **Ошибка подключения**\n\n"
                    f"{message}\n\n"
                    f"Проверьте правильность email и API токена, затем попробуйте снова."
                )
            
        except Exception as e:
            logger.error(f"Ошибка обработки токена: {e}")
            await self.send_error_message(channel_id, "Ошибка обработки токена")
    
    def _validate_date(self, date_str: str) -> bool:
        """Валидация формата даты"""
        try:
            datetime.strptime(date_str.strip(), '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    async def generate_and_send_report(self, session: Dict, user_id: str):
        """Генерация и отправка отчета"""
        try:
            channel_id = session['channel_id']
            projects = session['projects']
            start_date = session['start_date']
            end_date = session['end_date']
            
            await self.send_message(channel_id, 
                "⏳ Генерирую отчет... Это может занять некоторое время.")
            
            # Получаем учетные данные пользователя
            email, token = self.user_auth.get_user_credentials(user_id)
            jira_client = JiraClient(email, token)
            
            # Получаем трудозатраты из Jira для всех проектов
            all_worklogs = []
            project_stats = []
            
            for project in projects:
                project_worklogs = jira_client.get_worklogs_for_project(
                    project['key'], start_date, end_date
                )
                
                if project_worklogs:
                    all_worklogs.extend(project_worklogs)
                    project_hours = sum(float(w['hours'].replace(',', '.')) for w in project_worklogs)
                    project_stats.append({
                        'name': project['name'],
                        'key': project['key'],
                        'records': len(project_worklogs),
                        'hours': project_hours
                    })
                    logger.info(f"Проект {project['key']}: {len(project_worklogs)} записей, {project_hours:.1f} ч")
            
            if not all_worklogs:
                projects_names = [p['name'] for p in projects]
                await self.send_message(channel_id, 
                    f"📭 Трудозатраты по проектам **{', '.join(projects_names)}** "
                    f"за период с {start_date} по {end_date} не найдены."
                )
                return
            
            # Сортируем записи по дате
            all_worklogs.sort(key=lambda x: x['date'])
            
            # Генерируем название для отчета
            if len(projects) == 1:
                report_name = projects[0]['name']
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
            total_hours = sum(float(w['hours'].replace(',', '.')) for w in all_worklogs)
            
            # Формируем детальную статистику по проектам
            stats_text = ""
            if len(projects) > 1:
                stats_text = "\n\n**Статистика по проектам:**\n"
                for stat in project_stats:
                    stats_text += f"• **{stat['name']}** ({stat['key']}): {stat['records']} записей, {stat['hours']:.1f} ч\n"
            
            # Отправляем файл
            await self.send_file(channel_id, excel_data, filename, 
                f"📊 **Отчет по трудозатратам готов!**\n\n"
                f"**Проекты:** {', '.join([p['name'] for p in projects])}\n"
                f"**Период:** с {start_date} по {end_date}\n"
                f"**Всего записей:** {total_records}\n"
                f"**Общее время:** {total_hours:.1f} ч"
                f"{stats_text}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета: {e}")
            await self.send_error_message(session['channel_id'], 
                "Произошла ошибка при генерации отчета")
    
    async def send_message(self, channel_id: str, message: str):
        """Отправка сообщения в канал"""
        try:
            self.driver.posts.create_post({
                'channel_id': channel_id,
                'message': message
            })
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
    
    async def send_file(self, channel_id: str, file_data: bytes, filename: str, message: str = ""):
        """Отправка файла в канал"""
        try:
            # Загружаем файл
            file_response = self.driver.files.upload_file(
                channel_id=channel_id,
                files={'files': (filename, file_data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            )
            
            file_id = file_response['file_infos'][0]['id']
            
            # Отправляем сообщение с файлом
            self.driver.posts.create_post({
                'channel_id': channel_id,
                'message': message,
                'file_ids': [file_id]
            })
            
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            await self.send_error_message(channel_id, "Ошибка отправки файла")
    
    async def send_error_message(self, channel_id: str, error_msg: str):
        """Отправка сообщения об ошибке"""
        await self.send_message(channel_id, f"❌ **Ошибка:** {error_msg}")
    
    async def send_unknown_command(self, channel_id: str):
        """Отправка сообщения о неизвестной команде"""
        await self.send_message(channel_id, 
            "❓ Неизвестная команда. Введите `помощь` для просмотра доступных команд.")
    
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
                logger.info(f"Найдено {authenticated_count} аутентифицированных пользователей")
            else:
                logger.info("Нет аутентифицированных пользователей")
                        
        except Exception as e:
            logger.error(f"Ошибка проверки пользователей: {e}")
    
    def _ensure_dm_channel_access(self, user_id: str, channel_id: str):
        """Обеспечение доступа к DM каналу"""
        try:
            # Получаем информацию о канале
            channel = self.driver.channels.get_channel(channel_id)
            
            if channel.get('type') != 'D':
                logger.warning(f"Канал {channel_id} не является DM каналом")
                return False
            
            # Проверяем, что бот является участником канала
            members = self.driver.channels.get_channel_members(channel_id)
            bot_is_member = any(member['user_id'] == self.bot_user['id'] for member in members)
            
            if not bot_is_member:
                logger.warning(f"Бот не является участником DM канала {channel_id}")
                # В DM каналах бот автоматически становится участником при создании
                return False
            
            logger.debug(f"Доступ к DM каналу {channel_id} подтвержден")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки доступа к каналу {channel_id}: {e}")
            return False 