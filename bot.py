# ============================================================
# bot.py — точка входа Telegram-бота для учёта расходов
# ============================================================

# Импорт обработчиков (выполняется до load_dotenv, поэтому токен
# не нужен на этом этапе)
from handlers import expense
from handlers.voice import handle_voice
from handlers.report import report_command
import handlers.expense
import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
)
from services.database import init_db
from handlers.expense import start_operation, confirm_callback, edit_operation, ask_bank
from handlers.voice import handle_voice
from handlers.report import report_command, top_command, month_command, stats_command, toggle_confirm
import logging

from handlers.report import report_command, top_command, month_command, stats_command, toggle_confirm, help_command  # для отображения списка команд в боте

# Уровень WARNING — только важные сообщения (убрано детальное DEBUG-логирование)
logging.basicConfig(level=logging.WARNING)

# Загружаем переменные окружения из файла .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Инициализируем базу данных SQLite (создаём таблицы если их нет)
init_db()

# ============================================================
# ConversationHandler — управляет многошаговыми диалогами:
#   - CONFIRM: ожидание подтверждения операции кнопками
#   - EDIT:    ожидание исправленного текста от пользователя
#   - ASK_BANK: ожидание названия банка при оплате картой
# ============================================================
conv_handler = ConversationHandler(
    entry_points=[
        # Текстовое сообщение запускает разбор операции
        MessageHandler(filters.TEXT & ~filters.COMMAND, start_operation),
        # Голосовое сообщение — транскрипция и затем разбор
        MessageHandler(filters.VOICE, handle_voice),
    ],
    states={
    handlers.expense.CONFIRM: [CallbackQueryHandler(confirm_callback)],
    handlers.expense.EDIT_CATEGORY: [CallbackQueryHandler(confirm_callback)],  # ← новое
    handlers.expense.EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_operation)],
    handlers.expense.ASK_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_bank)],
    },
    fallbacks=[],
)

async def error_handler(update, context):
    """Глобальный обработчик ошибок — логирует все необработанные исключения."""
    import traceback
    print(f"ОШИБКА: {context.error}")
    traceback.print_exc()

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("month", month_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("toggleconfirm", toggle_confirm))
    app.add_handler(CommandHandler("help", help_command))  # ← должна быть здесь
    app.add_error_handler(error_handler)
    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()