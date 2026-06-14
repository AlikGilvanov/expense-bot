import os
import traceback
from faster_whisper import WhisperModel
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.expense import start_operation

_model = None

def get_model():
    global _model
    if _model is None:
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice_file = await update.message.voice.get_file()
    voice_path = f"voice_{update.message.message_id}.ogg"
    await voice_file.download_to_drive(voice_path)
    try:
        model = get_model()
        segments, _ = model.transcribe(voice_path, language="ru", beam_size=5)
        text = " ".join(seg.text for seg in segments).strip()
        if not text:
            await update.message.reply_text("Не удалось распознать речь.")
            return ConversationHandler.END
        await update.message.reply_text(f"🎤 Распознано: {text}")
        context.user_data["voice_text"] = text  # передаём через context
        return await start_operation(update, context)
    except Exception as e:
        print(f"ОШИБКА ГОЛОСА: {e}")
        traceback.print_exc()
        await update.message.reply_text("Ошибка обработки голоса.")
        return ConversationHandler.END
    finally:
        if os.path.exists(voice_path):
            os.remove(voice_path)