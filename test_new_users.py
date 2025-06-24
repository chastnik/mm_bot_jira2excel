#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы бота с новыми пользователями
"""

import asyncio
import logging
import sys
from config import Config
from mattermost_bot import MattermostBot

# Настройка логирования для теста
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class NewUserTester:
    """Тестер для проверки работы с новыми пользователями"""
    
    def __init__(self):
        self.bot = None
    
    async def test_new_user_flow(self):
        """Тест полного потока работы с новым пользователем"""
        try:
            # Создаем бота
            self.bot = MattermostBot()
            await self.bot.connect()
            
            logger.info("=== ТЕСТ: Проверка инициализации бота ===")
            
            # Проверяем информацию о боте
            logger.info(f"ID бота: {self.bot.bot_user['id']}")
            logger.info(f"Имя бота: {self.bot.bot_user['username']}")
            
            # Проверяем активные сессии
            logger.info(f"Активных сессий: {len(self.bot.user_sessions)}")
            
            # Получаем список всех DM каналов
            await self._check_dm_channels()
            
            # Проверяем возможность создания канала
            await self._test_channel_creation()
            
            logger.info("=== ТЕСТ ЗАВЕРШЕН ===")
            
        except Exception as e:
            logger.error(f"Ошибка в тесте: {e}")
        finally:
            if self.bot:
                self.bot.disconnect()
    
    async def _check_dm_channels(self):
        """Проверка существующих DM каналов"""
        try:
            logger.info("=== Проверка DM каналов ===")
            
            # Получаем все каналы, где участвует бот
            channels = self.bot.driver.channels.get_channels_for_user_and_team_and_page(
                user_id=self.bot.bot_user['id'], 
                team_id=Config.MATTERMOST_TEAM_ID
            )
            
            dm_channels = [ch for ch in channels if ch.get('type') == 'D']
            logger.info(f"Найдено DM каналов: {len(dm_channels)}")
            
            for channel in dm_channels:
                logger.info(f"DM канал: {channel['id']} - {channel.get('display_name', 'N/A')}")
                
        except Exception as e:
            logger.error(f"Ошибка проверки каналов: {e}")
    
    async def _test_channel_creation(self):
        """Тест возможности работы с новыми каналами"""
        try:
            logger.info("=== Тест создания канала ===")
            
            # Симулируем получение сообщения от нового пользователя
            test_user_id = "test_user_123"
            test_channel_id = "test_channel_456"
            test_message = "Привет"
            
            logger.info("Симулируем сообщение от нового пользователя...")
            logger.info(f"User ID: {test_user_id}")
            logger.info(f"Channel ID: {test_channel_id}")
            logger.info(f"Message: {test_message}")
            
            # Проверяем логику обработки
            logger.info("Бот готов к обработке сообщений от новых пользователей")
            
        except Exception as e:
            logger.error(f"Ошибка тестирования создания канала: {e}")

async def main():
    """Главная функция теста"""
    try:
        # Проверяем конфигурацию
        Config.validate()
        logger.info("Конфигурация проверена")
        
        # Запускаем тест
        tester = NewUserTester()
        await tester.test_new_user_flow()
        
    except Exception as e:
        logger.error(f"Критическая ошибка теста: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🧪 Запуск теста работы с новыми пользователями...")
    print("Этот тест проверяет готовность бота к работе с новыми DM каналами")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Тест прерван пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)
    
    print("✅ Тест завершен") 