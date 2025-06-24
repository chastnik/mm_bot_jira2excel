#!/bin/bash

# Скрипт запуска Mattermost-Jira бота
# Автор: MM Bot Team

set -e  # Выход при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
print_message() {
    echo -e "${BLUE}[BOT]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверяем наличие Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 не найден! Установите Python 3.8 или выше."
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2)
    print_message "Найден Python $python_version"
}

# Проверяем и создаем виртуальное окружение
setup_venv() {
    if [ ! -d "venv" ]; then
        print_message "Создаем виртуальное окружение..."
        python3 -m venv venv
        print_success "Виртуальное окружение создано"
    else
        print_message "Виртуальное окружение уже существует"
    fi
}

# Активируем виртуальное окружение
activate_venv() {
    if [ -f "venv/bin/activate" ]; then
        print_message "Активируем виртуальное окружение..."
        source venv/bin/activate
        print_success "Виртуальное окружение активировано"
    else
        print_error "Файл активации виртуального окружения не найден!"
        exit 1
    fi
}

# Устанавливаем зависимости
install_dependencies() {
    if [ -f "requirements.txt" ]; then
        print_message "Проверяем и устанавливаем зависимости..."
        pip install --upgrade pip
        pip install -r requirements.txt
        print_success "Зависимости установлены"
    else
        print_warning "Файл requirements.txt не найден!"
    fi
}

# Проверяем наличие .env файла
check_env_file() {
    if [ ! -f ".env" ]; then
        print_warning "Файл .env не найден!"
        if [ -f "env.example" ]; then
            print_message "Создаем .env из примера..."
            cp env.example .env
            print_warning "Пожалуйста, отредактируйте файл .env с вашими настройками!"
            print_message "После настройки запустите скрипт повторно."
            exit 1
        else
            print_error "Файл env.example не найден! Создайте файл .env с настройками."
            exit 1
        fi
    else
        print_success "Файл .env найден"
    fi
}

# Запускаем бота
start_bot() {
    print_message "Запускаем Mattermost-Jira бота..."
    print_message "Для остановки используйте Ctrl+C"
    echo
    python3 main.py
}

# Функция для отображения помощи
show_help() {
    echo "Использование: $0 [опции]"
    echo
    echo "Опции:"
    echo "  -h, --help      Показать эту справку"
    echo "  -i, --install   Только установить зависимости"
    echo "  -c, --check     Только проверить конфигурацию"
    echo "  -s, --stop      Только остановить запущенные процессы бота"
    echo "  -r, --restart   Перезапустить бота (убить процесс и запустить)"
    echo
    echo "Без опций: полная проверка и запуск бота (с остановкой уже запущенных)"
}

# Функция для проверки конфигурации
check_config() {
    print_message "Проверяем конфигурацию..."
    python3 -c "from config import Config; Config.validate(); print('Конфигурация корректна')"
}

# Функция для остановки существующего процесса бота
stop_existing_bot() {
    print_message "Проверяем запущенные процессы бота..."
    
    # Ищем процессы, запущенные из текущей директории
    current_dir=$(pwd)
    pids=$(pgrep -f "python.*main.py" | xargs -I {} sh -c 'ps -p {} -o pid,cmd --no-headers 2>/dev/null | grep "'$current_dir'" | cut -d" " -f1' 2>/dev/null || true)
    
    if [ ! -z "$pids" ] && [ "$pids" != "" ]; then
        print_warning "Найдены запущенные процессы бота: $pids"
        print_message "Останавливаем существующие процессы..."
        
        # Сначала пробуем мягкое завершение
        for pid in $pids; do
            if kill -0 $pid 2>/dev/null; then
                print_message "Отправляем SIGTERM процессу $pid..."
                kill -TERM $pid 2>/dev/null || true
            fi
        done
        
        # Ждем 5 секунд
        sleep 5
        
        # Проверяем, остались ли живые процессы
        remaining_pids=""
        for pid in $pids; do
            if kill -0 $pid 2>/dev/null; then
                remaining_pids="$remaining_pids $pid"
            fi
        done
        
        # Принудительно завершаем оставшиеся процессы
        if [ ! -z "$remaining_pids" ] && [ "$remaining_pids" != " " ]; then
            print_warning "Принудительно завершаем процессы: $remaining_pids"
            for pid in $remaining_pids; do
                kill -KILL $pid 2>/dev/null || true
            done
            sleep 2
        fi
        
        print_success "Существующие процессы бота остановлены"
    else
        print_message "Запущенные процессы бота не найдены"
    fi
}

# Обработка аргументов командной строки
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -i|--install)
        print_message "Режим установки зависимостей"
        check_python
        setup_venv
        activate_venv
        install_dependencies
        print_success "Установка завершена"
        exit 0
        ;;
    -c|--check)
        print_message "Режим проверки конфигурации"
        check_python
        setup_venv
        activate_venv
        check_env_file
        check_config
        print_success "Проверка завершена"
        exit 0
        ;;
    -s|--stop)
        print_message "Режим остановки бота"
        stop_existing_bot
        print_success "Остановка завершена"
        exit 0
        ;;
    -r|--restart)
        print_message "Режим перезапуска бота"
        stop_existing_bot
        ;;
    -*)
        print_error "Неизвестная опция: $1"
        show_help
        exit 1
        ;;
esac

# Основная логика запуска
main() {
    print_message "=== Запуск Mattermost-Jira бота ==="
    
    # Проверяем, не запущен ли уже бот
    stop_existing_bot
    
    # Проверяем все необходимые компоненты
    check_python
    setup_venv
    activate_venv
    install_dependencies
    check_env_file
    
    # Проверяем конфигурацию
    if ! check_config; then
        print_error "Ошибка в конфигурации! Проверьте файл .env"
        exit 1
    fi
    
    # Запускаем бота
    start_bot
}

# Обработка сигналов для корректного завершения
trap 'print_message "Получен сигнал завершения"; exit 0' SIGINT SIGTERM

# Запуск основной функции
main 