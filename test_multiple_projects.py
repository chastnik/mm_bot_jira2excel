#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы с несколькими проектами
"""

import asyncio
import logging
import sys
from config import Config
from jira_client import JiraClient
from excel_generator import ExcelGenerator

# Настройка логирования для теста
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class MultipleProjectsTester:
    """Тестер для проверки работы с несколькими проектами"""
    
    def __init__(self):
        self.jira_client = None
        self.excel_generator = None
    
    async def test_multiple_projects_flow(self):
        """Тест работы с несколькими проектами"""
        try:
            logger.info("=== ТЕСТ: Работа с несколькими проектами ===")
            
            # Инициализируем клиенты
            self.jira_client = JiraClient()
            self.excel_generator = ExcelGenerator()
            
            # Получаем список проектов
            projects = self.jira_client.get_projects()
            logger.info(f"Доступно проектов: {len(projects)}")
            
            if len(projects) < 2:
                logger.warning("Для тестирования нужно минимум 2 проекта")
                return
            
            # Тестируем обработку нескольких проектов
            await self._test_project_parsing()
            
            # Тестируем генерацию отчета
            await self._test_multiple_projects_report(projects[:3])  # Берем первые 3 проекта
            
            logger.info("=== ТЕСТ ЗАВЕРШЕН УСПЕШНО ===")
            
        except Exception as e:
            logger.error(f"Ошибка в тесте: {e}")
            raise
    
    async def _test_project_parsing(self):
        """Тест парсинга нескольких проектов"""
        logger.info("--- Тестирование парсинга проектов ---")
        
        test_cases = [
            "PROJ1",
            "PROJ1, PROJ2",
            "PROJ1, PROJ2, PROJ3",
            " PROJ1 , PROJ2 , PROJ3 ",  # С пробелами
            "proj1, proj2",  # Нижний регистр
        ]
        
        for test_input in test_cases:
            logger.info(f"Тест ввода: '{test_input}'")
            
            # Симулируем обработку как в боте
            project_keys = [key.strip().upper() for key in test_input.split(',')]
            logger.info(f"Результат парсинга: {project_keys}")
            
            # Проверяем валидацию
            projects = self.jira_client.get_projects()
            valid_projects = []
            invalid_projects = []
            
            for project_key in project_keys:
                project = next((p for p in projects if p['key'] == project_key), None)
                if project:
                    valid_projects.append(project)
                else:
                    invalid_projects.append(project_key)
            
            logger.info(f"  Найдено проектов: {len(valid_projects)}")
            logger.info(f"  Не найдено: {invalid_projects}")
            print()
    
    async def _test_multiple_projects_report(self, test_projects):
        """Тест генерации отчета для нескольких проектов"""
        logger.info("--- Тестирование генерации отчета ---")
        
        if len(test_projects) < 2:
            logger.warning("Недостаточно проектов для тестирования")
            return
        
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        logger.info(f"Проекты для тестирования:")
        for project in test_projects:
            logger.info(f"  • {project['name']} ({project['key']})")
        
        # Получаем трудозатраты
        all_worklogs = []
        for project in test_projects:
            worklogs = self.jira_client.get_worklogs_for_project(
                project['key'], start_date, end_date
            )
            if worklogs:
                all_worklogs.extend(worklogs)
                logger.info(f"  {project['key']}: {len(worklogs)} записей")
            else:
                logger.info(f"  {project['key']}: нет данных")
        
        if not all_worklogs:
            logger.warning("Нет данных для генерации отчета")
            return
        
        # Тестируем генерацию Excel
        logger.info(f"Генерируем Excel отчет с {len(all_worklogs)} записями...")
        
        try:
            # Сортируем по дате
            all_worklogs.sort(key=lambda x: x['date'])
            
            # Генерируем отчет
            report_name = f"Тестовый сводный отчет по {len(test_projects)} проектам"
            excel_data = self.excel_generator.generate_timesheet_report(
                all_worklogs, report_name, start_date, end_date, test_projects
            )
            
            # Генерируем имя файла
            filename = self.excel_generator.generate_filename_for_multiple_projects(
                test_projects, start_date, end_date
            )
            
            # Сохраняем для проверки
            with open(f"test_{filename}", 'wb') as f:
                f.write(excel_data)
            
            logger.info(f"✅ Excel файл сохранен: test_{filename}")
            logger.info(f"   Размер файла: {len(excel_data)} байт")
            
            # Статистика
            total_hours = sum(float(w['hours'].replace(',', '.')) for w in all_worklogs)
            logger.info(f"   Общее время: {total_hours:.1f} ч")
            
        except Exception as e:
            logger.error(f"Ошибка генерации Excel: {e}")
            raise

async def main():
    """Главная функция теста"""
    try:
        # Проверяем конфигурацию
        Config.validate()
        logger.info("Конфигурация проверена")
        
        # Запускаем тест
        tester = MultipleProjectsTester()
        await tester.test_multiple_projects_flow()
        
    except Exception as e:
        logger.error(f"Критическая ошибка теста: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🧪 Запуск теста работы с несколькими проектами...")
    print("Этот тест проверяет функциональность сводных отчетов")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Тест прерван пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)
    
    print("\n✅ Тест завершен")
    print("Проверьте сгенерированный тестовый Excel файл") 