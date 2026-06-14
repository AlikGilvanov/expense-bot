# SETUP.md — Окружение и установки проекта expense-bot

## Структура проекта

```
expense-bot/
├── bot.py                  # Точка входа Telegram-бота
├── .env                    # Переменные окружения (не в Git!)
├── .gitignore
├── requirements.txt
├── credentials.json        # Ключ Google сервисного аккаунта (не в Git!)
├── database/
│   └── expenses.db         # SQLite база данных (создаётся автоматически)
├── dashboard/
│   └── app.py              # Streamlit веб-панель
├── handlers/
│   ├── expense.py          # Обработчик текстовых операций
│   ├── voice.py            # Обработчик голосовых сообщений
│   └── report.py           # Команды /report, /top, /month, /stats
└── services/
    ├── database.py         # Работа с SQLite
    ├── parser.py           # Парсинг и AI-категоризация
    └── sheets.py           # Бэкап в Google Sheets
```

---

## Требования к серверу

| Параметр | Значение |
|----------|----------|
| ОС | Ubuntu 24.04 LTS |
| CPU | 2 vCPU |
| RAM | 4 ГБ (Whisper требует памяти) |
| Диск | 20 ГБ |
| Python | 3.12 |

---

## Файл .env

Создать файл `.env` в корне проекта:

```
TELEGRAM_TOKEN=ваш_токен_от_botfather
OPENAI_API_KEY=sk-...
SPREADSHEET_NAME=expense-bot_expenses
```

---

## Установка Python-зависимостей

### Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### Файл requirements.txt

```
python-telegram-bot==21.x
openai>=1.12.0
gspread==6.0.2
google-auth==2.27.0
python-dotenv==1.0.0
faster-whisper==1.1.1
pandas==2.2.0
streamlit>=1.32
openpyxl>=3.1
plotly>=5.20
```

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### ⚠️ Важно: версия setuptools

На некоторых системах `pkg_resources` недоступен в новых версиях `setuptools`.
Если при запуске возникает ошибка `No module named 'pkg_resources'`:

```bash
pip install "setuptools<71"
```

Проверка:
```bash
python -c "import pkg_resources; print('OK')"
```

### ⚠️ Важно: версия ctranslate2

Версия `ctranslate2 4.8.0` нестабильна. Использовать строго:

```bash
pip uninstall faster-whisper ctranslate2 -y
pip install ctranslate2==4.5.0 faster-whisper==1.1.1
```

Проверка модели Whisper:
```bash
python -c "
from faster_whisper import WhisperModel
m = WhisperModel('base', device='cpu', compute_type='int8')
print('Модель загружена!')
"
```

При первом запуске модель скачается автоматически (~150 МБ).
Модель сохраняется в `~/.cache/huggingface/hub/models--Systran--faster-whisper-base/`.

---

## Google Sheets API

### Что нужно настроить

1. Зайти на [console.cloud.google.com](https://console.cloud.google.com)
2. Создать проект (или выбрать существующий)
3. Включить **Google Sheets API**
4. Включить **Google Drive API**
5. Создать сервисный аккаунт: **APIs & Services → Credentials → Create Credentials → Service Account**
6. Роль сервисного аккаунта: **Basic → Editor**
7. Скачать JSON-ключ → переименовать в `credentials.json` → положить в корень проекта
8. Скопировать `client_email` из `credentials.json`
9. Открыть таблицу Google Sheets и дать доступ этому email как **Редактор**

### Структура таблицы (первая строка — заголовки)

```
User ID | Date | Type | Amount | Category | Description | Payment | Bank
```

### Возможные ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `invalid_grant` | Часы компьютера расходятся с реальным временем | Синхронизировать время: `w32tm /resync /force` (Windows) или `ntpdate -u pool.ntp.org` (Linux) |
| `403 Drive API disabled` | Google Drive API не включён | Включить в Cloud Console |
| `404 Spreadsheet not found` | Неверное название таблицы в `.env` | Проверить `SPREADSHEET_NAME` |
| `403 Permission denied` | Email сервисного аккаунта не добавлен в таблицу | Добавить email как Редактор |

---

## Запуск бота

```bash
source venv/bin/activate
python bot.py
```

### Фоновый запуск через systemd (Linux)

Создать файл `/etc/systemd/system/expense-bot.service`:

```ini
[Unit]
Description=Expense Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/expense-bot
ExecStart=/home/ubuntu/expense-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запустить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable expense-bot
sudo systemctl start expense-bot
sudo systemctl status expense-bot
```

---

## Запуск веб-панели

```bash
source venv/bin/activate
streamlit run dashboard/app.py
```

Открыть в браузере: `http://localhost:8501`

### Фоновый запуск Streamlit через systemd (Linux)

```ini
[Unit]
Description=Expense Bot Dashboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/expense-bot
ExecStart=/home/ubuntu/expense-bot/venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Перенос проекта на сервер

```bash
# На локальной машине — создать архив
zip -r expense-bot.zip expense-bot/ --exclude "*/venv/*" --exclude "*/__pycache__/*" --exclude "*/database/*"

# Скопировать на сервер
scp expense-bot.zip ubuntu@ВАШ_IP:/home/ubuntu/

# На сервере — распаковать и установить
ssh ubuntu@ВАШ_IP
unzip expense-bot.zip
cd expense-bot
python3 -m venv venv
source venv/bin/activate
pip install "setuptools<71"
pip install ctranslate2==4.5.0 faster-whisper==1.1.1
pip install -r requirements.txt
```

Не забыть скопировать отдельно:
- `.env` (содержит секретные ключи, не в архиве)
- `credentials.json` (ключ Google, не в архиве)

---

## .gitignore

```
venv/
.env
credentials.json
__pycache__/
*.pyc
database/
*.ogg
*.db
```
