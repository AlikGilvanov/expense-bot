import sqlite3
import os
from datetime import datetime

# Создаём папку database/ если её нет
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, 'database')
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, 'expenses.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Основная таблица операций
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_user_id INTEGER NOT NULL,
        telegram_message_id INTEGER UNIQUE,
        operation_type TEXT CHECK(operation_type IN ('income','expense')) NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        description TEXT DEFAULT '',
        transaction_date TEXT NOT NULL,
        payment_method TEXT DEFAULT 'наличные',
        bank TEXT DEFAULT '',
        source_type TEXT DEFAULT 'text',
        confidence_score REAL DEFAULT 1.0,
        original_text TEXT,
        parser_source TEXT DEFAULT 'local',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Таблица правил нормализации
    c.execute('''CREATE TABLE IF NOT EXISTS normalization_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_text TEXT NOT NULL,
        category TEXT NOT NULL,
        source TEXT CHECK(source IN ('ai', 'user_correction', 'local')) NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(original_text, category, source)
    )''')
    
    # Таблица настроек пользователя
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        telegram_user_id INTEGER PRIMARY KEY,
        always_confirm BOOLEAN DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

def save_operation(user_id, message_id, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''INSERT OR IGNORE INTO expenses 
            (telegram_user_id, telegram_message_id, operation_type, amount,
             category, description, transaction_date, payment_method, bank,
             source_type, confidence_score, original_text, parser_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (user_id, message_id,
             data['operation_type'], data['amount'], data['category'],
             data.get('description',''), data['transaction_date'],
             data.get('payment_method','наличные'), data.get('bank',''),
             data.get('source_type','text'), data.get('confidence_score',1.0),
             data.get('original_text',''), data.get('parser_source','local'))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Дубликат по telegram_message_id – игнорируем
        pass
    finally:
        conn.close()

def save_normalization_rule(original_text, category, source, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO normalization_rules (original_text, category, source, user_id) VALUES (?,?,?,?)",
                  (original_text, category, source, user_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_user_settings(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT always_confirm FROM user_settings WHERE telegram_user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def set_user_settings(user_id, always_confirm):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO user_settings (telegram_user_id, always_confirm) VALUES (?,?)", (user_id, int(always_confirm)))
    c.execute("UPDATE user_settings SET always_confirm=? WHERE telegram_user_id=?", (int(always_confirm), user_id))
    conn.commit()
    conn.close()

def get_user_stats(user_id, month_start=None, month_end=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now()
    if not month_start:
        month_start = now.replace(day=1).strftime('%Y-%m-%d')
    if not month_end:
        month_end = now.strftime('%Y-%m-%d')
    # Доходы
    c.execute("SELECT SUM(amount) FROM expenses WHERE telegram_user_id=? AND operation_type='income' AND transaction_date BETWEEN ? AND ?", (user_id, month_start, month_end))
    income = c.fetchone()[0] or 0
    # Расходы
    c.execute("SELECT SUM(amount) FROM expenses WHERE telegram_user_id=? AND operation_type='expense' AND transaction_date BETWEEN ? AND ?", (user_id, month_start, month_end))
    expense = c.fetchone()[0] or 0
    # Количество операций
    c.execute("SELECT COUNT(*) FROM expenses WHERE telegram_user_id=?", (user_id,))
    count = c.fetchone()[0]
    # Средний чек
    c.execute("SELECT AVG(amount) FROM expenses WHERE telegram_user_id=?", (user_id,))
    avg = c.fetchone()[0] or 0
    # Расходы по категориям
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE telegram_user_id=? AND operation_type='expense' AND transaction_date BETWEEN ? AND ? GROUP BY category ORDER BY SUM(amount) DESC", (user_id, month_start, month_end))
    by_category = dict(c.fetchall())
    # Крупнейшая категория
    top_cat = next(iter(by_category), None)
    conn.close()
    return {
        'income': income,
        'expense': expense,
        'balance': income - expense,
        'count': count,
        'avg_amount': avg,
        'top_category': top_cat,
        'by_category': by_category
    }