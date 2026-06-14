import os
import logging
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

def backup_to_sheets(user_id, data):
    sheet_name = os.getenv("SPREADSHEET_NAME")  # читаем здесь, не при импорте
    
    if not sheet_name:
        logger.warning("SPREADSHEET_NAME не задана — пропускаем бэкап в Sheets")
        return

    creds_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json")
    
    if not os.path.exists(creds_path):
        logger.warning("credentials.json не найден — пропускаем бэкап в Sheets")
        return

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).sheet1
        sheet.append_row([
            str(user_id),
            data["transaction_date"],
            data["operation_type"],
            data["amount"],
            data["category"],
            data.get("description", ""),
            data.get("payment_method", ""),
            data.get("bank", ""),
        ])
        logger.info(f"Бэкап в Sheets выполнен для user {user_id}")
    except Exception as e:
        logger.error(f"Ошибка бэкапа в Sheets: {e}")
        # не прерываем работу бота