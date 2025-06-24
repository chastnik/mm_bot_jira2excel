import json
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

class UserAuthManager:
    """Управление индивидуальными учетными данными пользователей для Jira"""
    
    def __init__(self, sessions_file='user_sessions.json'):
        self.sessions_file = sessions_file
        self._sessions = {}
        self._load_sessions()
        
        # Генерируем ключ шифрования на основе BOT_NAME (в реальном проекте лучше использовать отдельный SECRET_KEY)
        self._encryption_key = self._generate_key()
    
    def _generate_key(self):
        """Генерация ключа шифрования"""
        # В реальном проекте лучше использовать отдельную переменную SECRET_KEY
        password = os.getenv('BOT_NAME', 'jira-timesheet-bot').encode()
        salt = b'stable_salt_for_consistency'  # В продакшене должна быть уникальная соль
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)
    
    def _encrypt_data(self, data):
        """Шифрование данных"""
        if isinstance(data, str):
            data = data.encode()
        return self._encryption_key.encrypt(data).decode()
    
    def _decrypt_data(self, encrypted_data):
        """Расшифровка данных"""
        return self._encryption_key.decrypt(encrypted_data.encode()).decode()
    
    def _load_sessions(self):
        """Загрузка сессий пользователей"""
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    self._sessions = json.load(f)
                logger.info(f"Загружено {len(self._sessions)} пользовательских сессий")
            except Exception as e:
                logger.error(f"Ошибка загрузки сессий: {e}")
                self._sessions = {}
        else:
            self._sessions = {}
    
    def _save_sessions(self):
        """Сохранение сессий пользователей"""
        try:
            os.makedirs(os.path.dirname(self.sessions_file) if os.path.dirname(self.sessions_file) else '.', exist_ok=True)
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self._sessions, f, ensure_ascii=False, indent=2)
            logger.debug("Сессии пользователей сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения сессий: {e}")
    
    def is_user_authenticated(self, user_id):
        """Проверка, аутентифицирован ли пользователь в Jira"""
        user_session = self._sessions.get(user_id, {})
        return bool(user_session.get('jira_email') and user_session.get('jira_token'))
    
    def save_user_credentials(self, user_id, email, api_token):
        """Сохранение учетных данных пользователя"""
        if user_id not in self._sessions:
            self._sessions[user_id] = {}
        
        # Шифруем чувствительные данные
        self._sessions[user_id].update({
            'jira_email': self._encrypt_data(email),
            'jira_token': self._encrypt_data(api_token),
            'authenticated': True
        })
        
        self._save_sessions()
        logger.info(f"Учетные данные Jira сохранены для пользователя {user_id}")
    
    def get_user_credentials(self, user_id):
        """Получение учетных данных пользователя"""
        user_session = self._sessions.get(user_id, {})
        
        if not self.is_user_authenticated(user_id):
            return None, None
        
        try:
            email = self._decrypt_data(user_session['jira_email'])
            token = self._decrypt_data(user_session['jira_token'])
            return email, token
        except Exception as e:
            logger.error(f"Ошибка расшифровки учетных данных для пользователя {user_id}: {e}")
            return None, None
    
    def remove_user_credentials(self, user_id):
        """Удаление учетных данных пользователя"""
        if user_id in self._sessions:
            self._sessions[user_id].pop('jira_email', None)
            self._sessions[user_id].pop('jira_token', None)
            self._sessions[user_id]['authenticated'] = False
            self._save_sessions()
            logger.info(f"Учетные данные Jira удалены для пользователя {user_id}")
    
    def get_user_session(self, user_id):
        """Получение сессии пользователя"""
        return self._sessions.get(user_id, {})
    
    def update_user_session(self, user_id, **kwargs):
        """Обновление сессии пользователя"""
        if user_id not in self._sessions:
            self._sessions[user_id] = {}
        
        self._sessions[user_id].update(kwargs)
        self._save_sessions()
    
    def get_authenticated_users_count(self):
        """Получение количества аутентифицированных пользователей"""
        return sum(1 for session in self._sessions.values() if session.get('authenticated', False)) 