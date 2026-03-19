import os
import re
import sys
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st

from src.loader import load_excel
from src.utils import extract_sales_manager_from_filename
from src.parser_1c import parse_1c_report
from src.reconciler import reconcile
from src.exporter import dataframe_to_excel_bytes


st.set_page_config(page_title="Звірка дебіторської заборгованості", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stDataFrame"] table {
        table-layout: auto;
    }
    div[data-testid="stDataFrame"] td {
        white-space: normal !important;
        word-break: break-word !important;
        font-size: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def validate(filename: str) -> None:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("❌ Файл має бути у форматі .xlsx")

    name = filename.replace(".xlsx", "")
    if not re.match(r"^[А-Яа-яІіЇїЄєA-Za-z\\s.]+$", name):
        raise ValueError(
            "❌ Назва файлу має бути у форматі Прізвище.xlsx, наприклад: Ткаченко.xlsx"
        )


def style_status(val):
    base = "font-size: 11px; white-space: normal; word-wrap: break-word; line-height: 1.2;"
    if val == "Не сплачено":
        return base + "background-color:#ff4d4f;color:white;font-weight:700;"
    if val == "Недоплата":
        return base + "background-color:#ff9f43;color:black;font-weight:700;"
    if val == "Переплата":
        return base + "background-color:#74b9ff;color:black;font-weight:700;"
    if val == "Оплата без реалізації":
        return base + "background-color:#ffeaa7;color:black;font-weight:700;"
    if val == "Не співпадають суми":
        return base + "background-color:#fab1a0;color:black;font-weight:700;"
    return base


def style_days(val):
    if pd.isna(val):
        return ""
    try:
        days = int(val)
    except Exception:
        return ""

    if days > 30:
        return "background-color:#ff4d4f;color:white;font-weight:700;"
    if days > 20:
        return "background-color:#ff9f43;color:black;font-weight:700;"
    if days > 10:
        return "background-color:#ffd6a5;color:black;"
    if days > 0:
        return "background-color:#fff3cd;color:black;"
    return ""


def format_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    money_cols = [
        "Очікувана сума",
        "Різниця",
        "Сума реалізації",
        "Сума оплат",
        "Сума повернення",
    ]

    for col in money_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Днів прострочки" in df.columns:
        df["Днів прострочки"] = pd.to_numeric(df["Днів прострочки"], errors="coerce")

    return df


if "uploader_key_live" not in st.session_state:
    st.session_state.uploader_key_live = 0


def clear_form():
    st.session_state.uploader_key_live += 1
    st.rerun()


st.title("🧪 Звірка дебіторської заборгованості")

st.markdown(
    """
Перед завантаженням:

1. Вивантажте файл з 1С  
2. Відкрийте його в Excel  
3. Перезбережіть файл у форматі **.xlsx**  
4. Назвіть файл у форматі **Прізвище.xlsx** (наприклад: `Ткаченко.xlsx`)

Після завантаження система:
- перевірить проблемні рядки
- покаже неоплачені, недоплати, переплати
- порахує дні прострочки
- підготує результат для скачування в Excel
"""
)

st.markdown("### 🧾 Що ви отримаєте")
c1, c2, c3 = st.columns(3)
c1.info("✔ Автоматичний контроль проблемних рядків")
c2.info("⚠ Виявлення розбіжностей по оплатах")
c3.info("📊 Готовий звіт для роботи бухгалтера")

uploaded = st.file_uploader(
    "📂 Завантаж Excel (.xlsx)",
    type=["xlsx"],
    key=f"uploader_live_{st.session_state.uploader_key_live}",
)

if uploaded is None:
    st.info("⬆️ Завантажте файл для перевірки")
    st.markdown("### Що з’явиться після обробки")
    st.markdown(
        """
- таблиця тільки з проблемними рядками  
- статус по кожному магазину / ТТ  
- дні прострочки  
- суми реалізації, оплат і повернень  
- кнопка для скачування Excel
"""
    )
    st.stop()

try:
    validate(uploaded.name)

    os.makedirs("data/raw", exist_ok=True)
    path = os.path.join("data/raw", uploaded.name)

    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())

    sales = extract_sales_manager_from_filename(uploaded.name)

    raw = load_excel(path)
    parsed = parse_1c_report(raw, sales)
    df = reconcile(parsed)

    df = format_df(df)

    if "Днів прострочки" in df.columns:
        df = df.sort_values(by="Днів прострочки", ascending=False, na_position="last")

    st.success("✅ Обробка завершена")
    st.info(f"Менеджер у файлі: **{sales}**")

    styled = df.style

    if "Статус" in df.columns:
        styled = styled.map(style_status, subset=["Статус"])

    if "Днів прострочки" in df.columns:
        styled = styled.map(style_days, subset=["Днів прострочки"])

    format_dict = {}

    if "Днів прострочки" in df.columns:
        format_dict["Днів прострочки"] = "{:.0f}"

    for col in ["Очікувана сума", "Різниця", "Сума реалізації", "Сума оплат", "Сума повернення"]:
        if col in df.columns:
            format_dict[col] = "{:.2f}"

    if format_dict:
        styled = styled.format(format_dict, na_rep="")

    st.dataframe(styled, use_container_width=True, height=650)

    st.caption(
        "У таблиці показуються тільки проблемні рядки. "
        "Сплачені позиції приховані, щоб не перевантажувати документ."
    )

    if "Сигнал бухгалтеру" in df.columns and df["Сигнал бухгалтеру"].fillna("").astype(str).str.strip().ne("").any():
        st.caption(
            "Колонка «Сигнал бухгалтеру» використовується для нестандартних ситуацій, "
            "наприклад коли оплата прийшла по іншій ТТ і потрібен перенос коштів."
        )

    excel = dataframe_to_excel_bytes(df)

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "⬇️ Скачати Excel",
            data=excel,
            file_name="result.xlsx",
            use_container_width=True,
        )

    with col2:
        st.button("🗑 Очистити форму", on_click=clear_form, use_container_width=True)

except Exception:
    st.error("❌ Помилка обробки файлу")
    st.code(traceback.format_exc())