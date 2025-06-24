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
        
        self.jira_client = JiraClient()
        self.excel_generator = ExcelGenerator()
        self.user_sessions = {}  # Хранение состояния пользователей
        self.sessions_file = 'user_sessions.json'  # Файл для сохранения сессий
        
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
            
            # Загружаем сохраненные сессии пользователей
            self._load_user_sessions()
            
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
            
            elif any(cmd in message for cmd in ['проекты', 'список проектов']):
                await self.send_projects_list(channel_id)
            
            elif 'отчет' in message or 'трудозатраты' in message:
                await self.start_report_generation(channel_id, user_id)
            
            elif user_id in self.user_sessions:
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

Доступные команды:
• `проекты` - показать список доступных проектов
• `отчет` или `трудозатраты` - сгенерировать отчет по трудозатратам
• `помощь` - показать эту справку

**Для генерации отчета:**
1. Введите команду `отчет`
2. Выберите один или несколько проектов:
   • Один проект: `PROJ`
   • Несколько проектов: `PROJ1, PROJ2, PROJ3`
3. Укажите период (начальную и конечную дату)
4. Получите Excel файл с трудозатратами

**Формат дат:** YYYY-MM-DD (например: 2024-01-15)

**Дополнительные возможности:**
• При выборе нескольких проектов создается сводный отчет
• Данные сортируются по дате и включают статистику по каждому проекту
• Поддерживается неограниченное количество проектов в одном отчете
        """
        await self.send_message(channel_id, help_text)
    
    async def send_projects_list(self, channel_id: str):
        """Отправка списка проектов"""
        try:
            projects = self.jira_client.get_projects()
            
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
        # Инициализируем сессию пользователя
        self.user_sessions[user_id] = {
            'step': 'project_selection',
            'channel_id': channel_id
        }
        self._save_user_sessions()
        
        await self.send_message(channel_id, 
            "📋 **Генерация отчета по трудозатратам**\n\n"
            "Введите ключ проекта или несколько ключей через запятую:\n"
            "• Один проект: `PROJ`\n"
            "• Несколько проектов: `PROJ1, PROJ2, PROJ3`\n"
            "• Введите `проекты` для просмотра списка доступных проектов"
        )
    
    async def handle_session_input(self, message: str, channel_id: str, user_id: str):
        """Обработка ввода в рамках сессии пользователя"""
        session = self.user_sessions[user_id]
        step = session['step']
        
        if step == 'project_selection':
            if 'проекты' in message:
                await self.send_projects_list(channel_id)
                return
            
            # Обрабатываем несколько проектов через запятую
            project_keys = [key.strip().upper() for key in message.split(',')]
            projects = self.jira_client.get_projects()
            
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
            
            session['projects'] = selected_projects
            session['step'] = 'start_date'
            self._save_user_sessions()
            
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
            
            session['start_date'] = message.strip()
            session['step'] = 'end_date'
            self._save_user_sessions()
            await self.send_message(channel_id, 
                f"✅ Дата начала: {message}\n\n"
                "Введите дату окончания периода в формате YYYY-MM-DD:"
            )
        
        elif step == 'end_date':
            if not self._validate_date(message):
                await self.send_message(channel_id, 
                    "❌ Некорректный формат даты. Используйте формат YYYY-MM-DD")
                return
            
            session['end_date'] = message.strip()
            
            # Проверяем, что дата окончания не раньше даты начала
            if session['end_date'] < session['start_date']:
                await self.send_message(channel_id, 
                    "❌ Дата окончания не может быть раньше даты начала")
                return
            
            # Генерируем отчет
            await self.generate_and_send_report(session)
            
            # Очищаем сессию
            del self.user_sessions[user_id]
            self._save_user_sessions()
    
    def _validate_date(self, date_str: str) -> bool:
        """Валидация формата даты"""
        try:
            datetime.strptime(date_str.strip(), '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    async def generate_and_send_report(self, session: Dict):
        """Генерация и отправка отчета"""
        try:
            channel_id = session['channel_id']
            projects = session['projects']
            start_date = session['start_date']
            end_date = session['end_date']
            
            await self.send_message(channel_id, 
                "⏳ Генерирую отчет... Это может занять некоторое время.")
            
            # Получаем трудозатраты из Jira для всех проектов
            all_worklogs = []
            project_stats = []
            
            for project in projects:
                project_worklogs = self.jira_client.get_worklogs_for_project(
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
            # Сохраняем сессии перед отключением
            self._save_user_sessions()
            self.driver.logout()
            logger.info("Отключились от Mattermost")
        except Exception as e:
            logger.error(f"Ошибка отключения: {e}")
    
    def _save_user_sessions(self):
        """Сохранение сессий пользователей в файл"""
        try:
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_sessions, f, ensure_ascii=False, indent=2)
            logger.debug(f"Сессии сохранены в {self.sessions_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения сессий: {e}")
    
    def _load_user_sessions(self):
        """Загрузка сессий пользователей из файла"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    self.user_sessions = json.load(f)
                logger.info(f"Загружено {len(self.user_sessions)} активных сессий")
            else:
                logger.info("Файл сессий не найден, начинаем с пустыми сессиями")
                self.user_sessions = {}
        except Exception as e:
            logger.error(f"Ошибка загрузки сессий: {e}")
            self.user_sessions = {}
    
    async def _verify_dm_channels(self):
        """Проверка доступности DM каналов для активных сессий"""
        try:
            if not self.user_sessions:
                logger.info("Нет активных сессий для проверки")
                return
            
            logger.info(f"Проверяем доступность {len(self.user_sessions)} DM каналов")
            
            for user_id, session in self.user_sessions.items():
                channel_id = session.get('channel_id')
                if channel_id:
                    try:
                        # Проверяем доступность канала
                        channel = self.driver.channels.get_channel(channel_id)
                        if channel.get('type') == 'D':
                            logger.debug(f"DM канал {channel_id} для пользователя {user_id} доступен")
                        else:
                            logger.warning(f"Канал {channel_id} для пользователя {user_id} не является DM")
                    except Exception as e:
                        logger.error(f"Ошибка проверки канала {channel_id} для пользователя {user_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Ошибка проверки DM каналов: {e}")
    
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