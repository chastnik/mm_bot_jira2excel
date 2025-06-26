from jira import JIRA
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class JiraClient:
    """Клиент для работы с Jira API с индивидуальными учетными данными"""
    
    def __init__(self, username: str = None, password: str = None):
        """
        Инициализация клиента Jira с индивидуальными учетными данными
        
        Args:
            username: Имя пользователя для аутентификации в Jira
            password: Пароль пользователя для Jira
        """
        self.jira = None
        if username and password:
            self._connect(username, password)
    
    def _connect(self, username: str, password: str):
        """Подключение к Jira с указанными учетными данными"""
        try:
            self.jira = JIRA(
                server=Config.JIRA_URL,
                basic_auth=(username, password)
            )
            logger.info(f"Успешно подключились к Jira для пользователя {username}")
        except Exception as e:
            logger.error(f"Ошибка подключения к Jira для {username}: {e}")
            raise
    
    def test_connection(self, username: str, password: str) -> tuple[bool, str]:
        """
        Проверить соединение с Jira для указанных учетных данных
        
        Returns:
            tuple: (успешно, сообщение)
        """
        try:
            test_jira = JIRA(
                server=Config.JIRA_URL,
                basic_auth=(username, password)
            )
            user = test_jira.current_user()
            logger.info(f"Тестовое подключение к Jira успешно для: {user}")
            return True, f"Успешно! Подключен как: {user}"
        except Exception as e:
            error_msg = f"Ошибка подключения к Jira: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_projects(self) -> List[Dict]:
        """Получить список доступных проектов"""
        if not self.jira:
            logger.error("Jira клиент не инициализирован")
            return []
            
        try:
            projects = self.jira.projects()
            return [{"key": p.key, "name": p.name} for p in projects]
        except Exception as e:
            logger.error(f"Ошибка получения списка проектов: {e}")
            return []
    
    def get_worklogs_for_project(self, project_key: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Получить трудозатраты по проекту за период
        
        Args:
            project_key: Ключ проекта в Jira
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD
        
        Returns:
            Список словарей с данными о трудозатратах
        """
        if not self.jira:
            logger.error("Jira клиент не инициализирован")
            return []
            
        try:
            # JQL запрос для поиска задач проекта с worklog в указанном периоде
            jql = f'project = {project_key} AND worklogDate >= "{start_date}" AND worklogDate <= "{end_date}"'
            
            issues = self.jira.search_issues(jql, expand='worklog', maxResults=1000)
            
            worklogs_data = []
            
            for issue in issues:
                # Получаем все worklog для задачи
                worklogs = self.jira.worklogs(issue.key)
                
                for worklog in worklogs:
                    # Проверяем что worklog попадает в наш период
                    worklog_date = datetime.strptime(worklog.started[:10], '%Y-%m-%d')
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    
                    if start_dt <= worklog_date <= end_dt:
                        # Получаем автора worklog
                        author_email = worklog.author.emailAddress if hasattr(worklog.author, 'emailAddress') else worklog.author.name
                        author_name = author_email.split('@')[0] if '@' in author_email else author_email
                        
                        # Получаем часы (timeSpentSeconds переводим в часы)
                        hours = round(worklog.timeSpentSeconds / 3600, 1)
                        
                        # Формируем месяц для проектной задачи
                        month_names = {
                            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
                        }
                        month_name = month_names.get(worklog_date.month, f"Месяц {worklog_date.month}")
                        
                        # Получаем тему задачи для отдельного столбца
                        issue_summary = issue.fields.summary if hasattr(issue.fields, 'summary') else "Без темы"
                        
                        # Формируем описание работы в формате "Номер задачи - Тема задачи: Состав работ"
                        if worklog.comment:
                            ticket_description = f"{issue.key} - {issue_summary}: {worklog.comment}"
                        else:
                            ticket_description = f"{issue.key} - {issue_summary}"
                        
                        worklog_data = {
                            'date': worklog_date.strftime('%Y-%-m-%-d %H:%M'),
                            'executor': author_name,
                            'hours': str(hours).replace('.', ','),  # Заменяем точку на запятую для Excel
                            'description': ticket_description,
                            'project_task': f'Сопровождение {month_name}',
                            'task_summary': issue_summary,  # Тема задачи в отдельном столбце
                            'project': issue.fields.project.name
                        }
                        
                        worklogs_data.append(worklog_data)
            
            logger.info(f"Найдено {len(worklogs_data)} записей трудозатрат для проекта {project_key}")
            return worklogs_data
            
        except Exception as e:
            logger.error(f"Ошибка получения трудозатрат: {e}")
            return []
    
    def test_current_connection(self) -> bool:
        """Проверить текущее соединение с Jira"""
        if not self.jira:
            logger.error("Jira клиент не инициализирован")
            return False
            
        try:
            user = self.jira.current_user()
            logger.info(f"Подключен к Jira как: {user}")
            return True
        except Exception as e:
            logger.error(f"Ошибка тестирования соединения с Jira: {e}")
            return False 