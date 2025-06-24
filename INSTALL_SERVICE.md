# Установка Mattermost-Jira бота как системный сервис

## Быстрый запуск

### 1. Обычный запуск
```bash
# Простой запуск
./start_bot.sh

# Показать справку
./start_bot.sh --help

# Только установить зависимости
./start_bot.sh --install

# Только проверить конфигурацию
./start_bot.sh --check

# Перезапустить бота
./start_bot.sh --restart
```

## Установка как системный сервис

### 1. Создание пользователя для бота
```bash
# Создать пользователя mmbot без домашней директории
sudo useradd --system --no-create-home --shell /bin/false mmbot

# Создать группу mmbot (если не создалась автоматически)
sudo groupadd mmbot 2>/dev/null || true
```

### 2. Установка бота в систему
```bash
# Создать директорию для бота
sudo mkdir -p /opt/mm_bot_jira

# Скопировать файлы бота
sudo cp -r * /opt/mm_bot_jira/

# Установить права доступа
sudo chown -R mmbot:mmbot /opt/mm_bot_jira
sudo chmod +x /opt/mm_bot_jira/start_bot.sh
```

### 3. Настройка переменных окружения
```bash
# Скопировать и настроить .env файл
sudo cp /opt/mm_bot_jira/env.example /opt/mm_bot_jira/.env
sudo nano /opt/mm_bot_jira/.env

# Установить права доступа только для чтения владельцем
sudo chmod 600 /opt/mm_bot_jira/.env
sudo chown mmbot:mmbot /opt/mm_bot_jira/.env
```

### 4. Установка systemd сервиса
```bash
# Скопировать файл сервиса
sudo cp mm-bot.service /etc/systemd/system/

# Перезагрузить конфигурацию systemd
sudo systemctl daemon-reload

# Включить автозапуск сервиса
sudo systemctl enable mm-bot.service
```

### 5. Управление сервисом
```bash
# Запустить сервис
sudo systemctl start mm-bot

# Остановить сервис
sudo systemctl stop mm-bot

# Перезапустить сервис
sudo systemctl restart mm-bot

# Проверить статус сервиса
sudo systemctl status mm-bot

# Просмотр логов
sudo journalctl -u mm-bot -f

# Просмотр логов за последний час
sudo journalctl -u mm-bot --since "1 hour ago"
```

### 6. Проверка работы
```bash
# Проверить статус сервиса
sudo systemctl status mm-bot

# Проверить логи
sudo journalctl -u mm-bot --lines=50

# Проверить, что бот работает
ps aux | grep python | grep main.py
```

## Обновление бота

### Обновление файлов
```bash
# Остановить сервис
sudo systemctl stop mm-bot

# Обновить файлы (из директории с новой версией)
sudo cp -r * /opt/mm_bot_jira/

# Установить права доступа
sudo chown -R mmbot:mmbot /opt/mm_bot_jira
sudo chmod +x /opt/mm_bot_jira/start_bot.sh

# Запустить сервис
sudo systemctl start mm-bot
```

## Удаление сервиса

```bash
# Остановить и отключить сервис
sudo systemctl stop mm-bot
sudo systemctl disable mm-bot

# Удалить файлы сервиса
sudo rm /etc/systemd/system/mm-bot.service
sudo systemctl daemon-reload

# Удалить файлы бота (опционально)
sudo rm -rf /opt/mm_bot_jira

# Удалить пользователя (опционально)
sudo userdel mmbot
sudo groupdel mmbot
```

## Мониторинг

### Проверка состояния
```bash
# Статус сервиса
sudo systemctl is-active mm-bot

# Время работы
sudo systemctl show mm-bot --property=ActiveEnterTimestamp

# Использование ресурсов
sudo systemctl status mm-bot
```

### Ротация логов
Создать файл `/etc/logrotate.d/mm-bot`:
```
/opt/mm_bot_jira/bot.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 0644 mmbot mmbot
    postrotate
        systemctl reload mm-bot
    endscript
}
```

## Безопасность

1. **Права доступа**: Бот работает под отдельным пользователем `mmbot`
2. **Изоляция**: Systemd ограничивает доступ к файловой системе
3. **Конфигурация**: Файл `.env` доступен только владельцу
4. **Логи**: Логи доступны через journald с контролем доступа

## Устранение неполадок

### Бот не запускается
```bash
# Проверить логи systemd
sudo journalctl -u mm-bot --lines=50

# Проверить конфигурацию
sudo -u mmbot /opt/mm_bot_jira/start_bot.sh --check

# Проверить права доступа
ls -la /opt/mm_bot_jira/
```

### Проблемы с зависимостями
```bash
# Переустановить зависимости
sudo -u mmbot /opt/mm_bot_jira/start_bot.sh --install
```

### Проблемы с подключением
```bash
# Проверить сетевое подключение
curl -k https://your-mattermost-server/api/v4/system/ping

# Проверить переменные окружения
sudo -u mmbot cat /opt/mm_bot_jira/.env
``` 