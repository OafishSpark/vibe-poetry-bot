# Performance Artist Bot

Telegram-бот, который каждый день рассылает подписчикам поэтические строки о погоде, сгенерированные GigaChat. Содержит инлайн-кнопки для фиксированного сообщения и генерации случайных слов.

---

## Требования

- Ubuntu 22.04 / 24.04 (или любой Linux с systemd)
- Docker Engine + docker compose plugin
- Токен Telegram-бота ([@BotFather](https://t.me/BotFather))
- Credentials GigaChat API
- API-ключ OpenWeatherMap

---

## Структура проекта

```
.
├── Dockerfile
├── docker-compose.yml
├── .env                     # секреты — не коммитить в git
├── .env.example             # шаблон для .env
├── performance_artist.py
├── weather.py
├── requirements.txt
└── data/
    └── subscribers.json     # хранится снаружи контейнера (volume)
```

---

## Установка Docker (если не установлен)

```bash
# Удалить возможные конфликтующие старые ключи
sudo rm -f /etc/apt/keyrings/docker.gpg
sudo rm -f /etc/apt/keyrings/docker.asc
sudo rm -f /etc/apt/sources.list.d/docker.list

# Добавить официальный репозиторий Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установить
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Запустить и включить автозапуск
sudo systemctl start docker
sudo systemctl enable docker

# Добавить текущего пользователя в группу docker (чтобы не писать sudo)
sudo usermod -aG docker $USER
newgrp docker

# Проверить
docker info
```

---

## Деплой бота

### 1. Скопировать файлы на сервер

```bash
scp Dockerfile docker-compose.yml .env.example \
    performance_artist.py weather.py requirements.txt \
    user@your-server:~/bot/
```

Или клонировать репозиторий если используется git:

```bash
git clone <repo-url> ~/bot
```

### 2. Перейти в папку проекта

```bash
cd ~/bot
```

### 3. Создать файл с секретами

```bash
cp .env.example .env
nano .env
```

Заполнить значения:

```env
BOT_TOKEN=your_telegram_bot_token_here
GIGACHAT_AUTH_KEY=your_gigachat_credentials_here
WEATHER_API_KEY=your_openweathermap_api_key_here
```

### 4. Создать папку для данных

```bash
mkdir -p data
echo "[]" > data/subscribers.json
```

### 5. Собрать образ и запустить

```bash
docker compose up -d --build
```

Флаг `-d` запускает контейнер в фоне. При первом запуске сборка займёт 1–3 минуты.

### 6. Проверить что бот работает

```bash
# Статус контейнера
docker compose ps

# Логи в реальном времени
docker compose logs -f
```

Если в логах нет ошибок и бот отвечает на `/start` в Telegram — всё готово.

---

## Управление ботом

| Действие | Команда |
|---|---|
| Запустить | `docker compose up -d` |
| Остановить | `docker compose down` |
| Перезапустить | `docker compose restart` |
| Посмотреть логи | `docker compose logs -f` |
| Пересобрать после изменений | `docker compose up -d --build` |

Параметр `restart: unless-stopped` в `docker-compose.yml` обеспечивает автоматический перезапуск бота после перезагрузки сервера или краша.

---

## Обновление бота

```bash
# Остановить
docker compose down

# Обновить файлы (например через git pull или scp)
git pull

# Пересобрать и запустить
docker compose up -d --build
```

Данные подписчиков в `data/subscribers.json` сохраняются между обновлениями — они хранятся снаружи контейнера.

---

## Конфигурация

Основные настройки находятся в начале `performance_artist.py`:

| Параметр | По умолчанию | Описание |
|---|---|---|
| `CITY` | `498817` | ID города OpenWeatherMap (498817 = Санкт-Петербург) |
| `UNITS` | `metric` | Единицы измерения (`metric` / `imperial`) |
| `TIMEZONE` | `Europe/Moscow` | Часовой пояс для расписания |
| `SCHEDULE_HOUR` | `16` | Час отправки ежедневного сообщения |
| `SCHEDULE_MINUTE` | `16` | Минута отправки |
| `FIXED_BUTTON_MESSAGE` | — | Текст фиксированной кнопки |
| `AI_PROMPT` | — | Промпт для кнопки генерации слов |

После изменения конфигурации пересобрать контейнер:

```bash
docker compose up -d --build
```

---

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие и список команд |
| `/subscribe` | Подписаться на ежедневные сообщения |
| `/unsubscribe` | Отписаться |
| `/status` | Проверить статус подписки |
| `/menu` | Показать инлайн-кнопки |

---

## Устранение неполадок

**Бот не отвечает сразу после запуска**
Подождите 10–15 секунд — Telegram polling инициализируется с небольшой задержкой.

**Ошибка `certificate verify failed` в логах**
Сертификат не добавился при сборке. Пересобрать образ:
```bash
docker compose down
docker compose up -d --build --no-cache
```

**Бот перестал работать после перезагрузки сервера**
Убедиться что Docker настроен на автозапуск:
```bash
sudo systemctl enable docker
```

**Посмотреть ошибки контейнера**
```bash
docker compose logs --tail=50
```
