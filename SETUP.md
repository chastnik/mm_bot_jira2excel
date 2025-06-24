# Настройка переменных окружения

## Создание файла .env

1. Скопируйте файл `env.example` в `.env`:
```bash
cp env.example .env
```

2. Отредактируйте `.env` файл, заполнив все необходимые параметры:

## Параметры конфигурации

### Mattermost настройки

- **MATTERMOST_URL** - URL вашего сервера Mattermost (например: https://chat.company.com)
- **MATTERMOST_TOKEN** - токен бота, который вы получите при создании бота в Mattermost
- **MATTERMOST_TEAM_ID** - ID команды в Mattermost (можно получить из URL или API)

### Jira настройки

- **JIRA_URL** - URL вашего сервера Jira (например: https://company.atlassian.net)
- **JIRA_EMAIL** - email пользователя для подключения к Jira
- **JIRA_API_TOKEN** - API токен для аутентификации в Jira

### Настройки бота

- **BOT_NAME** - имя бота в Mattermost (по умолчанию: jira-timesheet-bot)
- **LOG_LEVEL** - уровень логирования (DEBUG, INFO, WARNING, ERROR)

## Получение токенов

### Mattermost Bot Token

1. Войдите в Mattermost как администратор
2. Перейдите в **System Console** → **Integrations** → **Bot Accounts**
3. Нажмите **Add Bot Account**
4. Заполните информацию о боте:
   - **Username**: jira-timesheet-bot
   - **Display Name**: Jira Timesheet Bot
   - **Description**: Бот для выгрузки трудозатрат из Jira
5. Скопируйте сгенерированный токен

### Jira API Token

1. Войдите в Jira под своей учетной записью
2. Перейдите в **Account Settings** → **Security** → **API tokens**
3. Нажмите **Create API token**
4. Дайте токену понятное имя (например: "Mattermost Bot")
5. Скопируйте сгенерированный токен

### Team ID в Mattermost

Получить Team ID можно несколькими способами:

**Способ 1 - из URL:**
- Откройте Mattermost в браузере
- Посмотрите на URL: `https://your-mattermost.com/team-name/channels/channel-name`
- `team-name` и есть Team ID

**Способ 2 - через API:**
```bash
curl -H "Authorization: Bearer YOUR_BOT_TOKEN" \
  https://your-mattermost.com/api/v4/teams
```

## Пример заполненного .env файла

```env
# Mattermost настройки
MATTERMOST_URL=https://chat.mycompany.com
MATTERMOST_TOKEN=your_mattermost_bot_token_here
MATTERMOST_TEAM_ID=myteam

# Jira настройки  
JIRA_URL=https://mycompany.atlassian.net
JIRA_EMAIL=bot@mycompany.com
JIRA_API_TOKEN=ATATT3xFfGF0T2...rest_of_token

# Настройки бота
BOT_NAME=jira-timesheet-bot
LOG_LEVEL=INFO
```

## Проверка настроек

После заполнения `.env` файла, запустите бота:

```bash
python main.py
```

Если настройки правильные, вы увидите в логах:
```
INFO - Конфигурация проверена успешно
INFO - Успешно подключились к Mattermost
INFO - Успешно подключились к Jira
INFO - Бот успешно запущен и готов к работе
``` 