import json
import requests
import os
from datetime import datetime
from services.categorizer import ALLOWED_CATEGORIES

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def gpt_extract(text):
    if not OPENAI_API_KEY:
        return None
    prompt = f"""
Ты — ассистент по финансам. Извлеки из сообщения данные об операции.

Правила категоризации:
- Продукты: еда, напитки из магазина, супермаркет
- Вкусняшки: газировка, чипсы, кириешки, сухарики, конфеты, шоколад, мороженое, снэки
- Кафе и рестораны: кофе в кафе, ресторан, обед вне дома
- Коммунальные услуги: ЖКХ, электричество, вода, отопление, газ (не газировка!)
- Транспорт: такси, метро, автобус, бензин

Верни ТОЛЬКО JSON без пояснений:
{{
  "operation_type": "income" или "expense",
  "amount": число,
  "category": одна из {ALLOWED_CATEGORIES},
  "description": краткое описание,
  "transaction_date": "ГГГГ-ММ-ДД" (если нет — {datetime.now().strftime('%Y-%m-%d')}),
  "payment_method": "наличные" или "карта",
  "bank": "название банка или пусто"
}}

Сообщение: {text}
"""
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4.1-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 200
            },
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content']
        content = content.strip().removeprefix('```json').removesuffix('```').strip()
        parsed = json.loads(content)
        # Валидация категории
        if parsed.get('category') not in ALLOWED_CATEGORIES:
            parsed['category'] = "Другое"
        return parsed
    except Exception:
        return None