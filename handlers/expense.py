from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from services.parser import parse_message
from services.database import save_operation, save_normalization_rule, get_user_settings
from services.sheets import backup_to_sheets
from services.categorizer import ALLOWED_CATEGORIES

CONFIRM, EDIT, ASK_BANK, EDIT_CATEGORY = range(4)

PAYMENT_METHODS = ["наличные", "карта", "перевод", "онлайн"]


# ── Вспомогательные функции для построения клавиатур ───────

def build_confirm_keyboard():
    """Клавиатура для карточки подтверждения."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Сохранить", callback_data='confirm_yes')],
        [InlineKeyboardButton("✏️ Редактировать", callback_data='confirm_edit')],
        [InlineKeyboardButton("❌ Отмена", callback_data='confirm_cancel')],
    ])


def build_edit_keyboard(data):
    """Клавиатура режима редактирования — кнопки для каждого поля."""
    category = data.get('category', '—')
    payment = data.get('payment_method', 'наличные')
    op_type = "Доход" if data.get('operation_type') == 'income' else "Расход"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📂 Категория: {category}", callback_data='edit_category')],
        [InlineKeyboardButton(f"💳 Оплата: {payment}", callback_data='edit_payment')],
        [InlineKeyboardButton(f"🔄 Тип: {op_type}", callback_data='edit_optype')],
        [InlineKeyboardButton("✅ Готово", callback_data='edit_done')],
        [InlineKeyboardButton("❌ Отмена", callback_data='confirm_cancel')],
    ])


def build_confirm_text(data, mode="confirm"):
    """Текст карточки подтверждения или редактирования."""
    op_label = "Доход" if data.get('operation_type') == 'income' else "Расход"
    header = "✏️ *Режим редактирования:*" if mode == "edit" else "📋 *Проверьте данные:*"
    source_label = "AI" if data.get('parser_source') == 'ai' else "локально"
    return (
        f"{header}\n\n"
        f"Тип: {op_label}\n"
        f"Сумма: {data['amount']} ₽\n"
        f"Категория: {data['category']} ({source_label})\n"
        f"Оплата: {data.get('payment_method', 'наличные')}\n"
        f"Банк: {data.get('bank', '—') or '—'}\n"
        f"Описание: {data.get('description', '')}\n"
    )


def build_category_keyboard(current_cat):
    """Клавиатура выбора категории."""
    keyboard = []
    row = []
    for cat in ALLOWED_CATEGORIES:
        marker = "✅ " if cat == current_cat else ""
        row.append(InlineKeyboardButton(f"{marker}{cat}", callback_data=f"cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='confirm_edit')])
    return InlineKeyboardMarkup(keyboard)


def build_payment_keyboard(current_payment):
    """Клавиатура выбора способа оплаты."""
    keyboard = []
    for method in PAYMENT_METHODS:
        marker = "✅ " if method == current_payment else ""
        keyboard.append([InlineKeyboardButton(f"{marker}{method}", callback_data=f"pay_{method}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='confirm_edit')])
    return InlineKeyboardMarkup(keyboard)


def build_optype_keyboard(current_type):
    """Клавиатура выбора типа операции."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Расход" if current_type == 'expense' else "Расход",
            callback_data='type_expense'
        )],
        [InlineKeyboardButton(
            "✅ Доход" if current_type == 'income' else "Доход",
            callback_data='type_income'
        )],
        [InlineKeyboardButton("◀️ Назад", callback_data='confirm_edit')],
    ])


# ── Основные обработчики ────────────────────────────────────

async def start_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_id = update.message.message_id
    text = context.user_data.pop("voice_text", None) or update.message.text
    data = parse_message(text, user_id)

    if not data:
        await update.message.reply_text(
            "Не удалось распознать операцию.\nПример: «Кофе 250» или «Такси 500 карта Тинькофф»."
        )
        return ConversationHandler.END

    # Уточняем банк если карта без банка
    if data.get('payment_method') == 'карта' and not data.get('bank'):
        context.user_data['pending'] = data
        await update.message.reply_text("Какой банк выпустил карту?")
        return ASK_BANK

    # Сохраняем сразу если уверенность высокая и подтверждение выключено
    always_confirm = get_user_settings(user_id)
    if not always_confirm and data.get('confidence_score', 0) >= 0.8:
        save_operation(user_id, message_id, data)
        backup_to_sheets(user_id, data)
        if data.get('parser_source') == 'ai':
            save_normalization_rule(data['original_text'], data['category'], 'ai', user_id)
        await update.message.reply_text(f"✅ Сохранено: {data['amount']} ₽, {data['category']}")
        return ConversationHandler.END

    # Показываем карточку подтверждения
    context.user_data['pending'] = data
    await update.message.reply_text(
        build_confirm_text(data, mode="confirm"),
        parse_mode='Markdown',
        reply_markup=build_confirm_keyboard()
    )
    return CONFIRM


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    message_id = query.message.message_id
    cb = query.data

    # ── Сохранить ──────────────────────────────────────────
    if cb == 'confirm_yes':
        data = context.user_data.pop('pending')
        save_operation(user_id, message_id, data)
        backup_to_sheets(user_id, data)
        if data.get('parser_source') == 'ai':
            save_normalization_rule(data['original_text'], data['category'], 'ai', user_id)
        await query.edit_message_text("✅ Сохранено!")
        return ConversationHandler.END

    # ── Войти в режим редактирования ───────────────────────
    elif cb == 'confirm_edit':
        data = context.user_data.get('pending', {})
        await query.edit_message_text(
            build_confirm_text(data, mode="edit"),
            parse_mode='Markdown',
            reply_markup=build_edit_keyboard(data)
        )
        return EDIT_CATEGORY

    # ── Выбор категории ────────────────────────────────────
    elif cb == 'edit_category':
        data = context.user_data.get('pending', {})
        await query.edit_message_text(
            f"Текущая категория: *{data.get('category', '—')}*\nВыберите новую:",
            parse_mode='Markdown',
            reply_markup=build_category_keyboard(data.get('category', ''))
        )
        return EDIT_CATEGORY

    elif cb.startswith('cat_'):
        new_category = cb[4:]
        data = context.user_data.get('pending', {})
        old_category = data.get('category', '')
        if new_category != old_category:
            data['category'] = new_category
            context.user_data['pending'] = data
            save_normalization_rule(
                data.get('original_text', ''),
                new_category,
                'user_correction',
                user_id
            )
        # Возвращаемся в режим редактирования
        await query.edit_message_text(
            build_confirm_text(data, mode="edit"),
            parse_mode='Markdown',
            reply_markup=build_edit_keyboard(data)
        )
        return EDIT_CATEGORY

    # ── Выбор способа оплаты ───────────────────────────────
    elif cb == 'edit_payment':
        data = context.user_data.get('pending', {})
        await query.edit_message_text(
            f"Текущий способ оплаты: *{data.get('payment_method', 'наличные')}*\nВыберите новый:",
            parse_mode='Markdown',
            reply_markup=build_payment_keyboard(data.get('payment_method', 'наличные'))
        )
        return EDIT_CATEGORY

    elif cb.startswith('pay_'):
        new_payment = cb[4:]
        data = context.user_data.get('pending', {})
        data['payment_method'] = new_payment
        context.user_data['pending'] = data
        # Возвращаемся в режим редактирования
        await query.edit_message_text(
            build_confirm_text(data, mode="edit"),
            parse_mode='Markdown',
            reply_markup=build_edit_keyboard(data)
        )
        return EDIT_CATEGORY

    # ── Выбор типа операции ────────────────────────────────
    elif cb == 'edit_optype':
        data = context.user_data.get('pending', {})
        await query.edit_message_text(
            "Выберите тип операции:",
            reply_markup=build_optype_keyboard(data.get('operation_type', 'expense'))
        )
        return EDIT_CATEGORY

    elif cb.startswith('type_'):
        new_type = cb[5:]
        data = context.user_data.get('pending', {})
        data['operation_type'] = new_type
        context.user_data['pending'] = data
        await query.edit_message_text(
            build_confirm_text(data, mode="edit"),
            parse_mode='Markdown',
            reply_markup=build_edit_keyboard(data)
        )
        return EDIT_CATEGORY

    # ── Готово — сохранить после редактирования ────────────
    elif cb == 'edit_done':
        data = context.user_data.pop('pending')
        save_operation(user_id, message_id, data)
        backup_to_sheets(user_id, data)
        await query.edit_message_text(
            f"✅ Сохранено!\n"
            f"{data['amount']} ₽ · {data['category']} · {data.get('payment_method', 'наличные')}",
        )
        return ConversationHandler.END

    # ── Отмена ─────────────────────────────────────────────
    else:
        await query.edit_message_text("❌ Отменено")
        context.user_data.pop('pending', None)
        return ConversationHandler.END


async def edit_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Резервный обработчик текстового редактирования (не используется в новом флоу)."""
    user_id = update.effective_user.id
    text = update.message.text
    data = parse_message(text, user_id)
    if not data:
        await update.message.reply_text("Не удалось распознать. Попробуйте ещё раз.")
        return EDIT
    context.user_data['pending'] = data
    await update.message.reply_text(
        build_confirm_text(data, mode="confirm"),
        parse_mode='Markdown',
        reply_markup=build_confirm_keyboard()
    )
    return CONFIRM


async def ask_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bank = update.message.text.strip()
    data = context.user_data.get('pending')
    if not data:
        await update.message.reply_text("Ошибка: нет ожидающей операции.")
        return ConversationHandler.END
    data['bank'] = bank
    context.user_data['pending'] = data
    await update.message.reply_text(
        build_confirm_text(data, mode="confirm"),
        parse_mode='Markdown',
        reply_markup=build_confirm_keyboard()
    )
    return CONFIRM
