#!/usr/bin/env python3
"""
Тест индивидуальной аутентификации пользователей в Jira
"""

import os
import sys
import logging
from datetime import datetime
from user_auth import UserAuthManager
from jira_client import JiraClient
from config import Config

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_user_auth():
    """Тестирование индивидуальной аутентификации"""
    
    print("🔐 Тест индивидуальной аутентификации пользователей\n")
    
    try:
        # Проверяем конфигурацию
        Config.validate()
        print(f"✅ Конфигурация OK. Jira URL: {Config.JIRA_URL}\n")
        
        # Создаем менеджер аутентификации
        auth_manager = UserAuthManager()
        print("✅ UserAuthManager создан\n")
        
        # Тестовые пользователи
        test_users = [
            {"id": "user1", "username": "test_user1", "password": "fake_password_1"},
            {"id": "user2", "username": "test_user2", "password": "fake_password_2"},
        ]
        
        # Тест 1: Проверка изначального состояния
        print("📋 Тест 1: Проверка изначального состояния")
        for user in test_users:
            authenticated = auth_manager.is_user_authenticated(user["id"])
            print(f"  Пользователь {user['id']}: {'✅ аутентифицирован' if authenticated else '❌ не аутентифицирован'}")
        
        print(f"  Всего аутентифицированных: {auth_manager.get_authenticated_users_count()}\n")
        
        # Тест 2: Сохранение учетных данных
        print("📋 Тест 2: Сохранение учетных данных")
        for user in test_users:
            auth_manager.save_user_credentials(user["id"], user["username"], user["password"])
            print(f"  ✅ Сохранены данные для {user['id']}")
        
        print(f"  Всего аутентифицированных: {auth_manager.get_authenticated_users_count()}\n")
        
        # Тест 3: Получение учетных данных
        print("📋 Тест 3: Получение учетных данных")
        for user in test_users:
            username, password = auth_manager.get_user_credentials(user["id"])
            if username and password:
                print(f"  ✅ {user['id']}: username={username}, password={'*' * len(password)}")
            else:
                print(f"  ❌ {user['id']}: учетные данные не найдены")
        print()
        
        # Тест 4: Работа с сессиями
        print("📋 Тест 4: Работа с сессиями")
        auth_manager.update_user_session("user1", 
            step="project_selection", 
            projects=["PROJ1", "PROJ2"],
            test_data="some_data"
        )
        
        session = auth_manager.get_user_session("user1")
        print(f"  ✅ Сессия user1: {session}\n")
        
        # Тест 5: Удаление учетных данных
        print("📋 Тест 5: Удаление учетных данных")
        auth_manager.remove_user_credentials("user1")
        print(f"  ✅ Удалены данные для user1")
        
        authenticated = auth_manager.is_user_authenticated("user1")
        print(f"  user1 аутентифицирован: {'✅ да' if authenticated else '❌ нет'}")
        print(f"  Всего аутентифицированных: {auth_manager.get_authenticated_users_count()}\n")
        
        # Тест 6: Тестирование шифрования (проверяем файл)
        print("📋 Тест 6: Проверка шифрования в файле")
        try:
            with open('user_sessions.json', 'r') as f:
                content = f.read()
                if 'test_user2' in content:
                    print("  ❌ Имя пользователя найдено в открытом виде в файле!")
                else:
                    print("  ✅ Имя пользователя не найдено в открытом виде - данные зашифрованы")
                    
                if 'fake_password' in content:
                    print("  ❌ Пароль найден в открытом виде в файле!")
                else:
                    print("  ✅ Пароль не найден в открытом виде - данные зашифрованы")
        except FileNotFoundError:
            print("  ℹ️  Файл сессий не найден")
        print()
        
        # Реальный тест подключения (если введены настоящие данные)
        if len(sys.argv) > 1 and sys.argv[1] == "--real-test":
            print("📋 Реальный тест подключения к Jira")
            
            username = input("Введите ваше имя пользователя для Jira: ").strip()
            password = input("Введите ваш пароль: ").strip()
            
            if username and password:
                print("🔄 Тестируем подключение...")
                jira_client = JiraClient()
                success, message = jira_client.test_connection(username, password)
                
                if success:
                    print(f"✅ {message}")
                    
                    # Тестируем создание клиента с учетными данными
                    jira_client_auth = JiraClient(username, password)
                    projects = jira_client_auth.get_projects()
                    print(f"✅ Получено {len(projects)} проектов")
                    
                    if projects:
                        print("📋 Первые 5 проектов:")
                        for project in projects[:5]:
                            print(f"  • {project['key']} - {project['name']}")
                else:
                    print(f"❌ {message}")
            else:
                print("❌ Не введены имя пользователя или пароль")
        
        print("\n🎉 Все тесты завершены!")
        
    except Exception as e:
        logger.error(f"Ошибка в тесте: {e}")
        print(f"\n❌ Ошибка: {e}")

def cleanup():
    """Очистка тестовых данных"""
    try:
        if os.path.exists('user_sessions.json'):
            os.remove('user_sessions.json')
            print("🗑️  Тестовый файл сессий удален")
    except Exception as e:
        print(f"Ошибка очистки: {e}")

if __name__ == "__main__":
    print("Запуск тестов индивидуальной аутентификации")
    print("Для реального теста подключения к Jira используйте: python test_user_auth.py --real-test")
    print("(будет запрошено имя пользователя и пароль для Jira)\n")
    
    try:
        test_user_auth()
    finally:
        cleanup_input = input("\nОчистить тестовые данные? (y/N): ").strip().lower()
        if cleanup_input == 'y':
            cleanup() 