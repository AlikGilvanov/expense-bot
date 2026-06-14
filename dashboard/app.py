# ============================================================
# app.py — Streamlit Dashboard для учёта расходов
# Запуск: streamlit run app.py
# ============================================================

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import os
import io

# ── Путь к базе данных ──────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "expenses.db")

# ── Настройки страницы ──────────────────────────────────────
st.set_page_config(
    page_title="Учёт расходов",
    page_icon="💰",
    layout="wide",
)

# ── CSS: минималистичный стиль ──────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 16px 20px;
        border-left: 4px solid #4CAF50;
    }
    .metric-card.red { border-left-color: #f44336; }
    .metric-card.blue { border-left-color: #2196F3; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ── Загрузка данных из SQLite ───────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    """Загружает все операции из базы данных."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT
            id,
            telegram_user_id,
            operation_type,
            amount,
            category,
            description,
            transaction_date,
            payment_method,
            bank,
            created_at
        FROM expenses
        ORDER BY transaction_date DESC
    """, conn)
    conn.close()
    if not df.empty:
        df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def get_users(df):
    """Возвращает список уникальных user_id."""
    if df.empty:
        return []
    return sorted(df["telegram_user_id"].unique().tolist())


# ── Боковая панель: выбор пользователя и месяца ────────────
def sidebar(df):
    st.sidebar.title("⚙️ Фильтры")

    # Выбор пользователя
    users = get_users(df)
    if not users:
        st.sidebar.info("Нет данных")
        return None, None, None

    user_options = {str(u): u for u in users}
    selected_user_str = st.sidebar.selectbox(
        "Пользователь",
        options=list(user_options.keys()),
        format_func=lambda x: f"ID: {x}"
    )
    selected_user = user_options[selected_user_str]

    # Выбор месяца
    now = datetime.now()
    months = pd.date_range(
        start=df["transaction_date"].min() if not df.empty else now,
        end=now,
        freq="MS"
    ).to_pydatetime()
    month_labels = [m.strftime("%B %Y") for m in months]

    if month_labels:
        selected_month_label = st.sidebar.selectbox(
            "Месяц",
            options=month_labels[::-1],
            index=0
        )
        selected_month = datetime.strptime(selected_month_label, "%B %Y")
    else:
        selected_month = now

    return selected_user, selected_month, df[df["telegram_user_id"] == selected_user]


# ══════════════════════════════════════════════════════════════
# СТРАНИЦА 1: ГЛАВНАЯ
# ══════════════════════════════════════════════════════════════
def page_main(df_user, selected_month):
    st.title("📊 Главная")

    # Фильтр по выбранному месяцу
    month_start = selected_month.replace(day=1)
    if selected_month.month == 12:
        month_end = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        month_end = selected_month.replace(month=selected_month.month + 1, day=1)

    df_month = df_user[
        (df_user["transaction_date"] >= month_start) &
        (df_user["transaction_date"] < month_end)
    ]

    income = df_month[df_month["operation_type"] == "income"]["amount"].sum()
    expense = df_month[df_month["operation_type"] == "expense"]["amount"].sum()
    balance = income - expense

    # Карточки метрик
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💚 Доходы", f"{income:,.0f} ₽")
    with col2:
        st.metric("❤️ Расходы", f"{expense:,.0f} ₽")
    with col3:
        st.metric("💙 Баланс", f"{balance:,.0f} ₽", delta=f"{balance:,.0f} ₽")

    st.divider()

    if df_month.empty:
        st.info("В этом месяце нет операций.")
        return

    # График: расходы по дням
    df_exp = df_month[df_month["operation_type"] == "expense"].copy()
    if not df_exp.empty:
        df_daily = df_exp.groupby("transaction_date")["amount"].sum().reset_index()
        fig = px.bar(
            df_daily,
            x="transaction_date",
            y="amount",
            title="Расходы по дням",
            labels={"transaction_date": "Дата", "amount": "Сумма, ₽"},
            color_discrete_sequence=["#f44336"],
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Последние 10 операций
    st.subheader("Последние операции")
    df_recent = df_month.head(10)[
        ["transaction_date", "operation_type", "amount", "category", "description", "payment_method", "bank"]
    ].copy()
    df_recent["transaction_date"] = df_recent["transaction_date"].dt.strftime("%d.%m.%Y")
    df_recent["operation_type"] = df_recent["operation_type"].map({"income": "Доход", "expense": "Расход"})
    df_recent.columns = ["Дата", "Тип", "Сумма", "Категория", "Описание", "Оплата", "Банк"]
    st.dataframe(df_recent, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# СТРАНИЦА 2: КАТЕГОРИИ
# ══════════════════════════════════════════════════════════════
def page_categories(df_user, selected_month):
    st.title("📂 Категории")

    month_start = selected_month.replace(day=1)
    if selected_month.month == 12:
        month_end = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        month_end = selected_month.replace(month=selected_month.month + 1, day=1)

    df_month = df_user[
        (df_user["transaction_date"] >= month_start) &
        (df_user["transaction_date"] < month_end) &
        (df_user["operation_type"] == "expense")
    ]

    if df_month.empty:
        st.info("Нет расходов за выбранный месяц.")
        return

    df_cat = df_month.groupby("category")["amount"].sum().reset_index()
    df_cat = df_cat.sort_values("amount", ascending=False)

    col1, col2 = st.columns(2)

    with col1:
        # Круговая диаграмма
        fig_pie = px.pie(
            df_cat,
            values="amount",
            names="category",
            title="Доля по категориям",
            hole=0.4,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Горизонтальный бар
        fig_bar = px.bar(
            df_cat,
            x="amount",
            y="category",
            orientation="h",
            title="Сумма по категориям",
            labels={"amount": "Сумма, ₽", "category": "Категория"},
            color="amount",
            color_continuous_scale="Reds",
        )
        fig_bar.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    # Таблица
    st.subheader("Детализация")
    df_cat.columns = ["Категория", "Сумма, ₽"]
    df_cat["Сумма, ₽"] = df_cat["Сумма, ₽"].map("{:,.0f}".format)
    st.dataframe(df_cat, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# СТРАНИЦА 3: ПОИСК И ФИЛЬТРЫ
# ══════════════════════════════════════════════════════════════
def page_search(df_user):
    st.title("🔍 Поиск и фильтры")

    if df_user.empty:
        st.info("Нет данных.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        # Фильтр по типу операции
        op_type = st.selectbox(
            "Тип операции",
            options=["Все", "Расходы", "Доходы"]
        )

    with col2:
        # Фильтр по категории
        categories = ["Все"] + sorted(df_user["category"].unique().tolist())
        selected_cat = st.selectbox("Категория", options=categories)

    with col3:
        # Фильтр по сумме
        max_amount = int(df_user["amount"].max()) if not df_user.empty else 100000
        amount_range = st.slider(
            "Диапазон суммы, ₽",
            min_value=0,
            max_value=max_amount,
            value=(0, max_amount),
        )

    # Фильтр по дате
    col4, col5 = st.columns(2)
    with col4:
        date_from = st.date_input(
            "Дата от",
            value=df_user["transaction_date"].min().date() if not df_user.empty else date.today()
        )
    with col5:
        date_to = st.date_input("Дата до", value=date.today())

    # Поиск по описанию
    search_text = st.text_input("Поиск по описанию", placeholder="Например: кофе")

    # Применяем фильтры
    df_filtered = df_user.copy()

    if op_type == "Расходы":
        df_filtered = df_filtered[df_filtered["operation_type"] == "expense"]
    elif op_type == "Доходы":
        df_filtered = df_filtered[df_filtered["operation_type"] == "income"]

    if selected_cat != "Все":
        df_filtered = df_filtered[df_filtered["category"] == selected_cat]

    df_filtered = df_filtered[
        (df_filtered["amount"] >= amount_range[0]) &
        (df_filtered["amount"] <= amount_range[1])
    ]

    df_filtered = df_filtered[
        (df_filtered["transaction_date"].dt.date >= date_from) &
        (df_filtered["transaction_date"].dt.date <= date_to)
    ]

    if search_text:
        df_filtered = df_filtered[
            df_filtered["description"].str.contains(search_text, case=False, na=False)
        ]

    st.divider()
    st.write(f"Найдено операций: **{len(df_filtered)}** | Сумма: **{df_filtered['amount'].sum():,.0f} ₽**")

    # Таблица результатов
    df_show = df_filtered[
        ["transaction_date", "operation_type", "amount", "category", "description", "payment_method", "bank"]
    ].copy()
    df_show["transaction_date"] = df_show["transaction_date"].dt.strftime("%d.%m.%Y")
    df_show["operation_type"] = df_show["operation_type"].map({"income": "Доход", "expense": "Расход"})
    df_show.columns = ["Дата", "Тип", "Сумма", "Категория", "Описание", "Оплата", "Банк"]
    st.dataframe(df_show, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# СТРАНИЦА 4: ЭКСПОРТ В EXCEL
# ══════════════════════════════════════════════════════════════
def page_export(df_user):
    st.title("📥 Экспорт в Excel")

    if df_user.empty:
        st.info("Нет данных для экспорта.")
        return

    st.write("Выберите период для экспорта:")

    col1, col2 = st.columns(2)
    with col1:
        export_from = st.date_input(
            "От",
            value=df_user["transaction_date"].min().date()
        )
    with col2:
        export_to = st.date_input("До", value=date.today())

    df_export = df_user[
        (df_user["transaction_date"].dt.date >= export_from) &
        (df_user["transaction_date"].dt.date <= export_to)
    ].copy()

    st.write(f"Операций для экспорта: **{len(df_export)}**")

    if st.button("📥 Сформировать Excel", type="primary"):
        if df_export.empty:
            st.warning("Нет данных за выбранный период.")
            return

        # Формируем Excel в памяти через pandas + openpyxl
        df_export["transaction_date"] = df_export["transaction_date"].dt.strftime("%d.%m.%Y")
        df_export["operation_type"] = df_export["operation_type"].map(
            {"income": "Доход", "expense": "Расход"}
        )
        df_export = df_export[[
            "transaction_date", "operation_type", "amount",
            "category", "description", "payment_method", "bank"
        ]]
        df_export.columns = [
            "Дата", "Тип", "Сумма", "Категория",
            "Описание", "Способ оплаты", "Банк"
        ]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Операции")

            # Добавляем лист со сводкой по категориям
            df_summary = df_export[df_export["Тип"] == "Расход"].groupby("Категория")["Сумма"].sum()
            df_summary.to_excel(writer, sheet_name="По категориям")

        buffer.seek(0)
        filename = f"расходы_{export_from}_{export_to}.xlsx"

        st.download_button(
            label="💾 Скачать файл",
            data=buffer,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.success("Файл готов!")


# ══════════════════════════════════════════════════════════════
# ОСНОВНОЙ КОД
# ══════════════════════════════════════════════════════════════
def main():
    # Загружаем данные
    df = load_data()

    if df.empty:
        st.title("💰 Учёт расходов")
        st.warning("База данных пуста или не найдена. Отправьте боту несколько операций.")
        st.code(f"Ожидаемый путь к БД: {DB_PATH}")
        return

    # Боковая панель с фильтрами
    selected_user, selected_month, df_user = sidebar(df)
    if selected_user is None:
        return

    # Навигация по страницам
    page = st.sidebar.radio(
        "Страница",
        options=["🏠 Главная", "📂 Категории", "🔍 Поиск", "📥 Экспорт"],
    )

    if page == "🏠 Главная":
        page_main(df_user, selected_month)
    elif page == "📂 Категории":
        page_categories(df_user, selected_month)
    elif page == "🔍 Поиск":
        page_search(df_user)
    elif page == "📥 Экспорт":
        page_export(df_user)


if __name__ == "__main__":
    main()
