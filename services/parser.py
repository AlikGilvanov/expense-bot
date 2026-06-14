import re
from datetime import datetime
from services.categorizer import normalize_category
from services.llm import gpt_extract

AMOUNT_PATTERN = re.compile(r'(\d+)\s*(?:руб|р|₽)?', re.IGNORECASE)

def local_parse(text, user_id=None):
    """Локальный парсер с использованием таблицы нормализации."""
    # Проверяем нормализацию категории (уже включает таблицу правил)
    category = normalize_category(text, user_id)
    
    # Извлекаем сумму
    am = AMOUNT_PATTERN.search(text)
    if not am:
        return None
    amount = float(am.group(1))
    
    # Определение типа операции
    income_keywords = ["зарплата", "доход", "кэшбэк", "возврат средств", "премия", "стипендия", "подработка"]
    if any(kw in text.lower() for kw in income_keywords):
        op_type = "income"
    else:
        op_type = "expense"
    
    # Способ оплаты и банк
    payment_method = "наличные"
    bank = ""
    if "карт" in text.lower():
        payment_method = "карта"
        # Список банков для поиска
        banks = ["сбер", "тинькофф", "альфа", "втб", "райф", "газпром", "т-банк"]
        for b in banks:
            if b in text.lower():
                bank = b.capitalize()
                break
    
    # Дата
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
    transaction_date = date_match.group(0) if date_match else datetime.now().strftime('%Y-%m-%d')
    
    # Описание – оригинальное сообщение
    description = text.strip()
    
    return {
        "operation_type": op_type,
        "amount": amount,
        "category": category,
        "description": description,
        "transaction_date": transaction_date,
        "payment_method": payment_method,
        "bank": bank,
        "parser_source": "local",
        "confidence_score": 0.8 if category != "Другое" else 0.4,
        "original_text": text
    }

def parse_message(text, user_id=None):
    """Гибридный парсер: локальный, если уверенность высокая, иначе GPT."""
    local_result = local_parse(text, user_id)
    if local_result and local_result['confidence_score'] >= 0.5:
        return local_result
    
    # Если локально не получилось – GPT
    gpt_result = gpt_extract(text)
    if gpt_result:
        # Добавляем недостающие поля
        gpt_result['parser_source'] = 'ai'
        gpt_result['confidence_score'] = 0.9
        gpt_result['original_text'] = text
        return gpt_result
    
    # Fallback – локальный результат (даже с низкой уверенностью)
    return local_result if local_result else None