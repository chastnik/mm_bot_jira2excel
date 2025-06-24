import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация для бота"""
    
    # Mattermost настройки
    MATTERMOST_URL = os.getenv('MATTERMOST_URL')
    MATTERMOST_TOKEN = os.getenv('MATTERMOST_TOKEN')
    MATTERMOST_TEAM_ID = os.getenv('MATTERMOST_TEAM_ID')
    MATTERMOST_SSL_VERIFY = os.getenv('MATTERMOST_SSL_VERIFY', 'true').lower() == 'true'
    MATTERMOST_USE_WEBSOCKET = os.getenv('MATTERMOST_USE_WEBSOCKET', 'true').lower() == 'true'
    
    # Jira настройки (только URL, учетные данные индивидуальные)
    JIRA_URL = os.getenv('JIRA_URL')
    
    # Настройки бота
    BOT_NAME = os.getenv('BOT_NAME', 'jira-timesheet-bot')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Проверка что все необходимые настройки заданы"""
        required_vars = [
            'MATTERMOST_URL', 'MATTERMOST_TOKEN', 'MATTERMOST_TEAM_ID',
            'JIRA_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        
        return True 