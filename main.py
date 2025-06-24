#!/usr/bin/env python3
"""
Бот для Mattermost с интеграцией Jira для выгрузки трудозатрат
"""

import asyncio
import logging
import signal
import sys
from config import Config
from mattermost_bot import MattermostBot

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class BotManager:
    """Менеджер для управления ботом"""
    
    def __init__(self):
        self.bot = None
        self.running = False
    
    async def start(self):
        """Запуск бота"""
        try:
            # Проверяем конфигурацию
            Config.validate()
            logger.info("Конфигурация проверена успешно")
            
            # Создаем и запускаем бота
            self.bot = MattermostBot()
            await self.bot.connect()
            
            # Тестируем подключение к Jira
            if not self.bot.jira_client.test_connection():
                logger.error("Не удалось подключиться к Jira")
                return
            
            logger.info("Бот успешно запущен и готов к работе")
            self.running = True
            
            # Запускаем прослушивание сообщений
            await self.bot.start_listening()
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка бота"""
        if self.bot:
            logger.info("Останавливаем бота...")
            self.bot.disconnect()
        self.running = False
        logger.info("Бот остановлен")

# Глобальный менеджер для обработки сигналов
bot_manager = None

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Получен сигнал {signum}")
    if bot_manager:
        asyncio.create_task(bot_manager.stop())

async def main():
    """Главная функция"""
    global bot_manager
    
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bot_manager = BotManager()
    await bot_manager.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прерывание с клавиатуры")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1) 