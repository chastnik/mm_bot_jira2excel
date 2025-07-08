#!/usr/bin/env python3
"""
Модуль для парсинга дат в свободном формате
Поддерживает русский язык и различные форматы ввода периодов
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional
import calendar


class DateParser:
    """Парсер дат в свободном формате"""
    
    # Месяцы на русском языке
    MONTHS_RU = {
        'январь': 1, 'января': 1, 'янв': 1,
        'февраль': 2, 'февраля': 2, 'фев': 2,
        'март': 3, 'марта': 3, 'мар': 3,
        'апрель': 4, 'апреля': 4, 'апр': 4,
        'май': 5, 'мая': 5,
        'июнь': 6, 'июня': 6, 'июн': 6,
        'июль': 7, 'июля': 7, 'июл': 7,
        'август': 8, 'августа': 8, 'авг': 8,
        'сентябрь': 9, 'сентября': 9, 'сен': 9, 'сент': 9,
        'октябрь': 10, 'октября': 10, 'окт': 10,
        'ноябрь': 11, 'ноября': 11, 'ноя': 11,
        'декабрь': 12, 'декабря': 12, 'дек': 12
    }
    
    def __init__(self):
        # Убираем кеширование даты - будем вычислять при каждом запросе
        pass
    
    @property
    def today(self):
        """Возвращает актуальную текущую дату при каждом обращении"""
        return datetime.now()
        
    def parse_period(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Парсит период из текста в свободном формате
        
        Args:
            text: Текст с описанием периода
            
        Returns:
            Tuple[start_date, end_date, explanation]
            Даты в формате YYYY-MM-DD или None при ошибке
            explanation - объяснение что было распознано
        """
        text = text.lower().strip()
        
        # Удаляем лишние слова
        text = re.sub(r'\b(за|в|на|с|по|до|период|времени?|отчет|отчёт)\b', '', text).strip()
        
        # Проверяем стандартный формат YYYY-MM-DD
        if self._is_standard_date_format(text):
            return self._parse_standard_dates(text)
            
        # Специальные периоды
        special_periods = [
            (r'сегодня|сейчас', self._get_today),
            (r'вчера', self._get_yesterday),
            (r'позавчера', self._get_day_before_yesterday),
            (r'эт(?:а|у|ой?|им)\s+недел[ияею]', self._get_this_week),
            (r'прошл(?:ая|ой|ую)\s+недел[ияею]', self._get_last_week),
            (r'эт(?:от|ому|им)\s+месяц[еау]?', self._get_this_month),
            (r'прошл(?:ый|ого|ому)\s+месяц[еау]?', self._get_last_month),
            (r'эт(?:от|ому|им|ом)\s+квартал[еауо]?', self._get_this_quarter),
            (r'прошл(?:ый|ого|ому|ом)\s+квартал[еауо]?', self._get_last_quarter),
            (r'эт(?:от|ому|им)\s+год[уа]?', self._get_this_year),
            (r'прошл(?:ый|ого|ому)\s+год[уа]?', self._get_last_year),
        ]
        
        for pattern, func in special_periods:
            if re.search(pattern, text):
                return func()
        
        # Периоды типа "май", "июнь 2024", "с мая по июнь"
        month_period = self._parse_month_period(text)
        if month_period[0]:
            return month_period
            
        # Конкретные кварталы типа "2 квартал 2024", "первый квартал"
        quarter_period = self._parse_specific_quarter(text)
        if quarter_period[0]:
            return quarter_period
            
        # Период типа "последние N дней/недель/месяцев"
        last_period = self._parse_last_period(text)
        if last_period[0]:
            return last_period
            
        # Конкретные числа типа "с 15 мая по 20 июня"
        concrete_period = self._parse_concrete_period(text)
        if concrete_period[0]:
            return concrete_period
            
        return None, None, f"❌ Не удалось распознать период: '{text}'"
    
    def _is_standard_date_format(self, text: str) -> bool:
        """Проверяет, содержит ли текст стандартный формат дат"""
        pattern = r'\d{4}-\d{2}-\d{2}'
        return bool(re.search(pattern, text))
    
    def _parse_standard_dates(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """Парсит стандартный формат дат YYYY-MM-DD"""
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', text)
        
        if len(dates) == 1:
            # Одна дата - период на один день
            return dates[0], dates[0], f"✅ Период: {dates[0]} (один день)"
        elif len(dates) >= 2:
            start_date, end_date = dates[0], dates[1]
            if start_date <= end_date:
                return start_date, end_date, f"✅ Период: с {start_date} по {end_date}"
            else:
                return end_date, start_date, f"✅ Период: с {end_date} по {start_date} (даты переставлены)"
        
        return None, None, "❌ Не найдены корректные даты в стандартном формате"
    
    def _get_today(self) -> Tuple[str, str, str]:
        """Сегодняшний день"""
        date_str = self.today.strftime('%Y-%m-%d')
        return date_str, date_str, f"✅ Сегодня: {date_str}"
    
    def _get_yesterday(self) -> Tuple[str, str, str]:
        """Вчерашний день"""
        yesterday = self.today - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
        return date_str, date_str, f"✅ Вчера: {date_str}"
    
    def _get_day_before_yesterday(self) -> Tuple[str, str, str]:
        """Позавчера"""
        day = self.today - timedelta(days=2)
        date_str = day.strftime('%Y-%m-%d')
        return date_str, date_str, f"✅ Позавчера: {date_str}"
    
    def _get_this_week(self) -> Tuple[str, str, str]:
        """Текущая неделя (понедельник-воскресенье)"""
        monday = self.today - timedelta(days=self.today.weekday())
        sunday = monday + timedelta(days=6)
        return (monday.strftime('%Y-%m-%d'), 
                sunday.strftime('%Y-%m-%d'),
                f"✅ Текущая неделя: с {monday.strftime('%Y-%m-%d')} по {sunday.strftime('%Y-%m-%d')}")
    
    def _get_last_week(self) -> Tuple[str, str, str]:
        """Прошлая неделя"""
        last_monday = self.today - timedelta(days=self.today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        return (last_monday.strftime('%Y-%m-%d'),
                last_sunday.strftime('%Y-%m-%d'),
                f"✅ Прошлая неделя: с {last_monday.strftime('%Y-%m-%d')} по {last_sunday.strftime('%Y-%m-%d')}")
    
    def _get_this_month(self) -> Tuple[str, str, str]:
        """Текущий месяц"""
        first_day = self.today.replace(day=1)
        last_day = self.today.replace(day=calendar.monthrange(self.today.year, self.today.month)[1])
        return (first_day.strftime('%Y-%m-%d'),
                last_day.strftime('%Y-%m-%d'),
                f"✅ Текущий месяц: с {first_day.strftime('%Y-%m-%d')} по {last_day.strftime('%Y-%m-%d')}")
    
    def _get_last_month(self) -> Tuple[str, str, str]:
        """Прошлый месяц"""
        if self.today.month == 1:
            last_month = self.today.replace(year=self.today.year - 1, month=12, day=1)
        else:
            last_month = self.today.replace(month=self.today.month - 1, day=1)
        
        last_day = last_month.replace(day=calendar.monthrange(last_month.year, last_month.month)[1])
        
        return (last_month.strftime('%Y-%m-%d'),
                last_day.strftime('%Y-%m-%d'),
                f"✅ Прошлый месяц: с {last_month.strftime('%Y-%m-%d')} по {last_day.strftime('%Y-%m-%d')}")
    
    def _get_this_year(self) -> Tuple[str, str, str]:
        """Текущий год"""
        first_day = self.today.replace(month=1, day=1)
        last_day = self.today.replace(month=12, day=31)
        return (first_day.strftime('%Y-%m-%d'),
                last_day.strftime('%Y-%m-%d'),
                f"✅ Текущий год: с {first_day.strftime('%Y-%m-%d')} по {last_day.strftime('%Y-%m-%d')}")
    
    def _get_last_year(self) -> Tuple[str, str, str]:
        """Прошлый год"""
        last_year = self.today.year - 1
        first_day = datetime(last_year, 1, 1)
        last_day = datetime(last_year, 12, 31)
        return (first_day.strftime('%Y-%m-%d'),
                last_day.strftime('%Y-%m-%d'),
                f"✅ Прошлый год: с {first_day.strftime('%Y-%m-%d')} по {last_day.strftime('%Y-%m-%d')}")
    
    def _get_this_quarter(self) -> Tuple[str, str, str]:
        """Текущий квартал"""
        current_month = self.today.month
        current_year = self.today.year
        
        # Определяем квартал по месяцу
        if current_month <= 3:  # Q1: январь-март
            quarter_start = datetime(current_year, 1, 1)
            quarter_end = datetime(current_year, 3, 31)
            quarter_name = "I"
        elif current_month <= 6:  # Q2: апрель-июнь
            quarter_start = datetime(current_year, 4, 1)
            quarter_end = datetime(current_year, 6, 30)
            quarter_name = "II"
        elif current_month <= 9:  # Q3: июль-сентябрь
            quarter_start = datetime(current_year, 7, 1)
            quarter_end = datetime(current_year, 9, 30)
            quarter_name = "III"
        else:  # Q4: октябрь-декабрь
            quarter_start = datetime(current_year, 10, 1)
            quarter_end = datetime(current_year, 12, 31)
            quarter_name = "IV"
        
        return (quarter_start.strftime('%Y-%m-%d'),
                quarter_end.strftime('%Y-%m-%d'),
                f"✅ Текущий квартал ({quarter_name} кв. {current_year}): с {quarter_start.strftime('%Y-%m-%d')} по {quarter_end.strftime('%Y-%m-%d')}")
    
    def _get_last_quarter(self) -> Tuple[str, str, str]:
        """Прошлый квартал"""
        current_month = self.today.month
        current_year = self.today.year
        
        # Определяем прошлый квартал
        if current_month <= 3:  # Текущий Q1, прошлый Q4 прошлого года
            quarter_start = datetime(current_year - 1, 10, 1)
            quarter_end = datetime(current_year - 1, 12, 31)
            quarter_name = "IV"
            quarter_year = current_year - 1
        elif current_month <= 6:  # Текущий Q2, прошлый Q1
            quarter_start = datetime(current_year, 1, 1)
            quarter_end = datetime(current_year, 3, 31)
            quarter_name = "I"
            quarter_year = current_year
        elif current_month <= 9:  # Текущий Q3, прошлый Q2
            quarter_start = datetime(current_year, 4, 1)
            quarter_end = datetime(current_year, 6, 30)
            quarter_name = "II"
            quarter_year = current_year
        else:  # Текущий Q4, прошлый Q3
            quarter_start = datetime(current_year, 7, 1)
            quarter_end = datetime(current_year, 9, 30)
            quarter_name = "III"
            quarter_year = current_year
        
        return (quarter_start.strftime('%Y-%m-%d'),
                quarter_end.strftime('%Y-%m-%d'),
                f"✅ Прошлый квартал ({quarter_name} кв. {quarter_year}): с {quarter_start.strftime('%Y-%m-%d')} по {quarter_end.strftime('%Y-%m-%d')}")
    
    def _parse_specific_quarter(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """Парсит конкретные кварталы типа '2 квартал 2024', 'первый квартал'"""
        
        # Словарь для перевода в номер квартала
        quarter_numbers = {
            # Цифры
            '1': 1, '2': 2, '3': 3, '4': 4,
            # С дефисом
            '1-й': 1, '2-й': 2, '3-й': 3, '4-й': 4,
            # Римские цифры
            'i': 1, 'ii': 2, 'iii': 3, 'iv': 4,
            # Словами
            'первый': 1, 'второй': 2, 'третий': 3, 'четвертый': 4,
            'первого': 1, 'второго': 2, 'третьего': 3, 'четвертого': 4,
        }
        
        # Паттерны для поиска кварталов
        patterns = [
            # "2 квартал 2024", "первый квартал 2024"  
            r'(\w+(?:-\w+)?)\s+квартал[еауо]?\s+(\d{4})',
            # "2 квартал", "первый квартал" (без года)
            r'(\w+(?:-\w+)?)\s+квартал[еауо]?(?:\s|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                quarter_str = match.group(1).lower()
                year_str = match.group(2) if len(match.groups()) >= 2 else None
                
                # Получаем номер квартала
                quarter_num = quarter_numbers.get(quarter_str)
                if not quarter_num:
                    continue
                
                # Определяем год
                year = int(year_str) if year_str else self.today.year
                
                # Вычисляем даты квартала
                if quarter_num == 1:  # Q1: январь-март
                    quarter_start = datetime(year, 1, 1)
                    quarter_end = datetime(year, 3, 31)
                    quarter_name = "I"
                elif quarter_num == 2:  # Q2: апрель-июнь
                    quarter_start = datetime(year, 4, 1)
                    quarter_end = datetime(year, 6, 30)
                    quarter_name = "II"
                elif quarter_num == 3:  # Q3: июль-сентябрь
                    quarter_start = datetime(year, 7, 1)
                    quarter_end = datetime(year, 9, 30)
                    quarter_name = "III"
                else:  # Q4: октябрь-декабрь
                    quarter_start = datetime(year, 10, 1)
                    quarter_end = datetime(year, 12, 31)
                    quarter_name = "IV"
                
                return (quarter_start.strftime('%Y-%m-%d'),
                        quarter_end.strftime('%Y-%m-%d'),
                        f"✅ {quarter_name} квартал {year}: с {quarter_start.strftime('%Y-%m-%d')} по {quarter_end.strftime('%Y-%m-%d')}")
        
        return None, None, ""
    
    def _parse_month_period(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """Парсит периоды типа 'май', 'июнь 2024', 'с мая по июнь'"""
        
        # Ищем паттерн "с месяц по месяц"
        month_range_pattern = r'с\s+(\w+)\s+по\s+(\w+)(?:\s+(\d{4}))?'
        match = re.search(month_range_pattern, text)
        if match:
            start_month_name, end_month_name, year = match.groups()
            start_month = self.MONTHS_RU.get(start_month_name.lower())
            end_month = self.MONTHS_RU.get(end_month_name.lower())
            
            if start_month and end_month:
                year = int(year) if year else self.today.year
                
                # Если конечный месяц меньше начального, значит переходим через год
                if end_month < start_month:
                    end_year = year + 1
                else:
                    end_year = year
                
                start_date = datetime(year, start_month, 1)
                end_date = datetime(end_year, end_month, calendar.monthrange(end_year, end_month)[1])
                
                return (start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        f"✅ Период: с {start_month_name} {year} по {end_month_name} {end_year}")
        
        # Ищем один месяц с годом или без (только если нет других паттернов)
        single_month_pattern = r'\b(\w+)(?:\s+(\d{4}))?\b'
        matches = re.findall(single_month_pattern, text)
        
        for month_name, year in matches:
            month_num = self.MONTHS_RU.get(month_name.lower())
            if month_num:
                year = int(year) if year else self.today.year
                start_date = datetime(year, month_num, 1)
                end_date = datetime(year, month_num, calendar.monthrange(year, month_num)[1])
                
                return (start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        f"✅ Месяц: {month_name} {year}")
        
        return None, None, ""
    
    def _parse_last_period(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """Парсит периоды типа 'последние 7 дней', 'последние 2 недели'"""
        
        patterns = [
            (r'последни[ехий]+\s+(\d+)\s+дн[ияей]+', 'days'),
            (r'последни[ехий]+\s+(\d+)\s+недел[иьяю]+', 'weeks'),
            (r'последни[ехий]+\s+(\d+)\s+месяц[аеов]+', 'months'),
        ]
        
        for pattern, unit in patterns:
            match = re.search(pattern, text)
            if match:
                count = int(match.group(1))
                
                if unit == 'days':
                    start_date = self.today - timedelta(days=count-1)
                    end_date = self.today
                    explanation = f"✅ Последние {count} дней"
                elif unit == 'weeks':
                    start_date = self.today - timedelta(weeks=count) + timedelta(days=1)
                    end_date = self.today
                    explanation = f"✅ Последние {count} недель"
                elif unit == 'months':
                    # Приблизительно, 30 дней на месяц
                    start_date = self.today - timedelta(days=count*30)
                    end_date = self.today
                    explanation = f"✅ Последние {count} месяцев (приблизительно)"
                
                return (start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        explanation)
        
        return None, None, ""
    
    def _parse_concrete_period(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """Парсит конкретные даты типа 'с 15 мая по 20 июня'"""
        
        # Паттерн для дат с днями и месяцами
        pattern = r'с\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?\s+по\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?'
        match = re.search(pattern, text)
        
        if match:
            start_day, start_month_name, start_year, end_day, end_month_name, end_year = match.groups()
            
            start_month = self.MONTHS_RU.get(start_month_name.lower())
            end_month = self.MONTHS_RU.get(end_month_name.lower())
            
            if start_month and end_month:
                start_year = int(start_year) if start_year else self.today.year
                end_year = int(end_year) if end_year else self.today.year
                
                # Если год не указан, но конечный месяц меньше начального, увеличиваем год
                if not match.group(6) and end_month < start_month:
                    end_year = start_year + 1
                
                try:
                    start_date = datetime(start_year, start_month, int(start_day))
                    end_date = datetime(end_year, end_month, int(end_day))
                    
                    return (start_date.strftime('%Y-%m-%d'),
                            end_date.strftime('%Y-%m-%d'),
                            f"✅ Период: с {start_day} {start_month_name} {start_year} по {end_day} {end_month_name} {end_year}")
                except ValueError:
                    return None, None, f"❌ Некорректные даты: {start_day} {start_month_name} - {end_day} {end_month_name}"
        
        return None, None, ""


def test_date_parser():
    """Тестирование парсера дат"""
    parser = DateParser()
    
    test_cases = [
        "сегодня",
        "вчера", 
        "эта неделя",
        "прошлая неделя",
        "этот месяц",
        "прошлый месяц",
        "этот квартал",
        "прошлый квартал",
        "2 квартал 2024",
        "первый квартал",
        "май",
        "июнь 2024",
        "с мая по июнь",
        "с 15 мая по 20 июня",
        "последние 7 дней",
        "последние 2 недели",
        "2024-01-01",
        "с 2024-01-01 по 2024-01-31"
    ]
    
    print("=== Тестирование парсера дат ===")
    for case in test_cases:
        start, end, explanation = parser.parse_period(case)
        print(f"'{case}' -> {start} - {end} | {explanation}")


if __name__ == "__main__":
    test_date_parser() 