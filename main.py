#!/usr/bin/env python3
"""
Бот для Mattermost с интеграцией Jira для выгрузки трудозатрат
"""

import logging
import signal
import sys
import time
import urllib3
from config import Config
from mattermost_bot import MattermostBot

# Отключаем SSL предупреждения для production среды
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    
    def start(self):
        """Запуск бота"""
        try:
            # Проверяем конфигурацию
            Config.validate()
            logger.info("Конфигурация проверена успешно")
            
            # Создаем и запускаем бота
            self.bot = MattermostBot()
            self.bot.connect_sync()
            
            logger.info("Бот успешно запущен и готов к работе")
            self.running = True
            
            # Запускаем прослушивание сообщений
            self.bot.start_listening()
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            self.stop()
    
    def stop(self):
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
        bot_manager.stop()

def main():
    """Главная функция"""
    global bot_manager
    
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bot_manager = BotManager()
    bot_manager.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Прерывание с клавиатуры")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1) 