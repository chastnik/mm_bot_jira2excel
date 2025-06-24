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
        self.today = datetime.now()
        
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