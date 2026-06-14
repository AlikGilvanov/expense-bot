import os
from faster_whisper import WhisperModel
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.expense import start_operation  # повторно используем логику текстовых

model = WhisperModel("base", device="cpu", compute_type="int8")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice_file = await update.message.voice.get_file()
    voice_path = f"voice_{update.message.message_id}.ogg"
    await voice_file.download_to_drive(voice_path)
    try:
        segments, _ = model.transcribe(voice_path, language="ru", beam_size=5)
        text = " ".join(seg.text for seg in segments).strip()
        if not text:
            await update.message.reply_text("Не удалось распознать речь.")
            return ConversationHandler.END
        await update.message.reply_text(f"🎤 Распознано: {text}")
        # Подменяем текст и вызываем стандартный обработчик
        update.message.text = text
        return await start_operation(update, context)
    except Exception as e:
        await update.message.reply_text("Ошибка обработки голоса.")
    finally:
        if os.path.exists(voice_path):
            os.remove(voice_path)