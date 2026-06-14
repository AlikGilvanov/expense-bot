from telegram import Update
from telegram.ext import ContextTypes
from services.database import get_user_stats, set_user_settings, get_user_settings
import sqlite3

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Команды бота:*\n\n"
        "💬 *Ввод операций:*\n"
        "Просто напишите или надиктуйте — например: `Кофе 250` или `Зарплата 50000`\n\n"
        "📊 *Отчёты:*\n"
        "/report — сводка за текущий месяц\n"
        "/top — топ категорий расходов\n"
        "/month — сравнение с прошлым месяцем\n"
        "/stats — общая статистика\n\n"
        "⚙️ *Настройки:*\n"
        "/toggleconfirm — вкл/выкл подтверждение перед сохранением\n"
        "/help — эта справка"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)
    text = (
        f"📊 *Отчёт за месяц*\n"
        f"Доходы: {stats['income']:.2f} ₽\n"
        f"Расходы: {stats['expense']:.2f} ₽\n"
        f"Баланс: {stats['balance']:.2f} ₽\n\n"
        f"*По категориям:*\n"
    )
    for cat, amt in stats['by_category'].items():
        text += f"  {cat}: {amt:.2f} ₽\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('database/expenses.db')
    c = conn.cursor()
    c.execute("SELECT amount, category, description FROM expenses WHERE telegram_user_id=? ORDER BY amount DESC LIMIT 5", (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Нет данных.")
        return
    text = "🔝 *Крупные операции:*\n"
    for row in rows:
        text += f"• {row[0]:.2f} ₽ — {row[1]} ({row[2]})\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Сравнение с прошлым месяцем
    from datetime import datetime, timedelta
    now = datetime.now()
    curr_start = now.replace(day=1).strftime('%Y-%m-%d')
    prev_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
    prev_end = now.replace(day=1).strftime('%Y-%m-%d')
    conn = sqlite3.connect('database/expenses.db')
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM expenses WHERE telegram_user_id=? AND operation_type='expense' AND transaction_date >= ?", (user_id, curr_start))
    curr_exp = c.fetchone()[0] or 0
    c.execute("SELECT SUM(amount) FROM expenses WHERE telegram_user_id=? AND operation_type='expense' AND transaction_date BETWEEN ? AND ?", (user_id, prev_start, prev_end))
    prev_exp = c.fetchone()[0] or 0
    conn.close()
    change = ((curr_exp - prev_exp) / prev_exp * 100) if prev_exp else 0
    text = f"Расходы в этом месяце: {curr_exp:.2f} ₽\nПрошлый месяц: {prev_exp:.2f} ₽\nИзменение: {change:.1f}%"
    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_user_stats(update.effective_user.id)
    text = (
        f"Средний чек: {stats['avg_amount']:.2f} ₽\n"
        f"Количество операций: {stats['count']}\n"
        f"Крупнейшая категория: {stats['top_category'] or 'нет'}"
    )
    await update.message.reply_text(text)

async def toggle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current = get_user_settings(user_id)
    new_value = not current
    set_user_settings(user_id, new_value)
    state = "включено" if new_value else "выключено"
    await update.message.reply_text(f"Подтверждение операций {state}.")