from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from typing import List, Dict
import logging
from datetime import datetime
import io

logger = logging.getLogger(__name__)

class ExcelGenerator:
    """Генератор Excel отчетов с трудозатратами"""
    
    def __init__(self):
        self.headers = [
            "Дата работы",
            "Исполнитель", 
            "Часы",
            "Содержание работы",
            "Проектная задача",
            "Проект"
        ]
    
    def generate_timesheet_report(self, worklogs: List[Dict], project_name: str, start_date: str, end_date: str, projects: List[Dict] = None) -> bytes:
        """
        Генерировать Excel отчет с трудозатратами
        
        Args:
            worklogs: Список данных о трудозатратах
            project_name: Название проекта
            start_date: Дата начала периода
            end_date: Дата окончания периода
            
        Returns:
            Байты Excel файла
        """
        try:
            # Создаем новую книгу
            wb = Workbook()
            ws = wb.active
            ws.title = f"Трудозатраты {project_name}"
            
            # Заголовок отчета  
            if projects and len(projects) > 1:
                report_title = f"Сводный отчет по трудозатратам ({len(projects)} проектов) с {start_date} по {end_date}"
            else:
                report_title = f"Отчет по трудозатратам проекта '{project_name}' с {start_date} по {end_date}"
            
            ws.merge_cells('A1:F1')
            ws['A1'] = report_title
            ws['A1'].font = Font(bold=True, size=14)
            ws['A1'].alignment = Alignment(horizontal='center')
            
            # Добавляем информацию о проектах для сводного отчета
            if projects and len(projects) > 1:
                ws.merge_cells('A2:F2')
                project_list = ', '.join([f"{p['name']} ({p['key']})" for p in projects])
                ws['A2'] = f"Проекты: {project_list}"
                ws['A2'].font = Font(size=10)
                ws['A2'].alignment = Alignment(horizontal='center')
                header_row = 4
            else:
                header_row = 3
            
            # Заголовки столбцов
            for col, header in enumerate(self.headers, 1):
                cell = ws.cell(row=header_row, column=col, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')
                cell.border = Border(
                    top=Side(style='thin'),
                    bottom=Side(style='thin'),
                    left=Side(style='thin'),
                    right=Side(style='thin')
                )
            
            # Заполняем данными
            data_start_row = header_row + 1
            for row, worklog in enumerate(worklogs, data_start_row):
                ws.cell(row=row, column=1, value=worklog['date'])
                ws.cell(row=row, column=2, value=worklog['executor'])
                ws.cell(row=row, column=3, value=worklog['hours'])
                ws.cell(row=row, column=4, value=worklog['description'])
                ws.cell(row=row, column=5, value=worklog['project_task'])
                ws.cell(row=row, column=6, value=worklog['project'])
                
                # Добавляем границы к ячейкам
                for col in range(1, 7):
                    cell = ws.cell(row=row, column=col)
                    cell.border = Border(
                        top=Side(style='thin'),
                        bottom=Side(style='thin'),
                        left=Side(style='thin'),
                        right=Side(style='thin')
                    )
            
            # Автоширина столбцов
            for col in range(1, 7):
                column_letter = get_column_letter(col)
                ws.column_dimensions[column_letter].width = self._get_column_width(col)
            
            # Итоговая строка с общим количеством часов
            if worklogs:
                total_hours = sum(float(w['hours'].replace(',', '.')) for w in worklogs)
                total_row = data_start_row + len(worklogs) + 1
                ws.merge_cells(f'A{total_row}:B{total_row}')
                ws[f'A{total_row}'] = 'Итого часов:'
                ws[f'A{total_row}'].font = Font(bold=True)
                ws[f'C{total_row}'] = str(total_hours).replace('.', ',')
                ws[f'C{total_row}'].font = Font(bold=True)
                
                # Добавляем статистику по проектам для сводного отчета
                if projects and len(projects) > 1:
                    stats_row = total_row + 2
                    ws.merge_cells(f'A{stats_row}:F{stats_row}')
                    ws[f'A{stats_row}'] = 'Статистика по проектам:'
                    ws[f'A{stats_row}'].font = Font(bold=True, size=12)
                    
                    # Группируем данные по проектам
                    project_stats = {}
                    for worklog in worklogs:
                        project_name = worklog['project']
                        if project_name not in project_stats:
                            project_stats[project_name] = {'records': 0, 'hours': 0.0}
                        project_stats[project_name]['records'] += 1
                        project_stats[project_name]['hours'] += float(worklog['hours'].replace(',', '.'))
                    
                    # Выводим статистику
                    for i, (project_name, stats) in enumerate(project_stats.items(), 1):
                        stat_row = stats_row + i
                        ws[f'A{stat_row}'] = f"• {project_name}:"
                        ws[f'B{stat_row}'] = f"{stats['records']} записей"
                        ws[f'C{stat_row}'] = str(stats['hours']).replace('.', ',') + " ч"
            
            # Сохраняем в память
            excel_buffer = io.BytesIO()
            wb.save(excel_buffer)
            excel_buffer.seek(0)
            
            logger.info(f"Сгенерирован Excel отчет с {len(worklogs)} записями")
            return excel_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка генерации Excel отчета: {e}")
            raise
    
    def _get_column_width(self, column_index: int) -> int:
        """Получить оптимальную ширину столбца"""
        widths = {
            1: 20,  # Дата работы
            2: 15,  # Исполнитель
            3: 10,  # Часы
            4: 50,  # Содержание работы
            5: 25,  # Проектная задача
            6: 20   # Проект
        }
        return widths.get(column_index, 15)
    
    def generate_filename(self, project_name: str, start_date: str, end_date: str) -> str:
        """Генерировать имя файла для отчета"""
        # Убираем недопустимые символы из названия проекта
        safe_project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_project_name = safe_project_name.replace(' ', '_')
        
        return f"trudozatraty_{safe_project_name}_{start_date}_{end_date}.xlsx"
    
    def generate_filename_for_multiple_projects(self, projects: List[Dict], start_date: str, end_date: str) -> str:
        """Генерировать имя файла для отчета по нескольким проектам"""
        if len(projects) == 1:
            return self.generate_filename(projects[0]['name'], start_date, end_date)
        
        # Для нескольких проектов используем их ключи
        project_keys = [p['key'] for p in projects]
        
        # Если проектов слишком много, используем сокращенное имя
        if len(project_keys) > 3:
            filename_projects = f"{len(project_keys)}_proektov"
        else:
            filename_projects = "_".join(project_keys)
        
        return f"trudozatraty_svodnyj_{filename_projects}_{start_date}_{end_date}.xlsx" 