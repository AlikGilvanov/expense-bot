import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from services.database import init_db
from handlers.expense import start_operation, confirm_callback, edit_operation, ask_bank
from handlers.voice import handle_voice
from handlers.report import report_command, top_command, month_command, stats_command, toggle_confirm

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

init_db()

conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.TEXT & ~filters.COMMAND, start_operation),
        MessageHandler(filters.VOICE, handle_voice)
    ],
    states={
        handlers.expense.CONFIRM: [CallbackQueryHandler(confirm_callback)],
        handlers.expense.EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_operation)],
        handlers.expense.ASK_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_bank)],
    },
    fallbacks=[]
)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("month", month_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("toggleconfirm", toggle_confirm))
    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()