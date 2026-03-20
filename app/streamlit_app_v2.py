import os
import sys
import traceback
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd

from src.loader import load_excel
from src.utils import extract_sales_manager_from_filename
from src.parser_1c_v2 import parse_1c_report_v2
from src.reconciler_v2 import reconcile_v2
from src.exporter import dataframe_to_excel_bytes


st.set_page_config(page_title="Звірка дебіторської заборгованості V2", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stDataFrame"] table {
        table-layout: auto;
    }
    div[data-testid="stDataFrame"] td {
        white-space: normal !important;
        word-break: break-word !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def validate_uploaded_file(filename: str) -> None:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("❌ Будь ласка, завантажте файл у форматі Excel (.xlsx)")

    name_without_ext = filename.replace(".xlsx", "")
    if not re.match(r"^[А-Яа-яІіЇїЄєA-Za-z.\s]+$", name_without_ext):
        raise ValueError(
            "❌ Назва файлу має бути у форматі: Прізвище.xlsx (наприклад: Ткаченко.xlsx)"
        )


def run_pipeline(temp_path: str, original_filename: str):
    sales_manager = extract_sales_manager_from_filename(original_filename)

    raw_df = load_excel(temp_path)
    parsed_df = parse_1c_report_v2(raw_df, sales_manager)

    if parsed_df.empty:
        raise ValueError("❌ У файлі не знайдено операцій для звірки")

    reconciled_df = reconcile_v2(parsed_df)

    if reconciled_df.empty:
        raise ValueError("❌ Не вдалося сформувати результат звірки")

    return sales_manager, raw_df, parsed_df, reconciled_df


def style_status(val: str) -> str:
    base = "font-size: 11px; white-space: normal; word-wrap: break-word; line-height: 1.2;"

    if val == "Не сплачено":
        return base + "background-color: #ff4d4f; color: white; font-weight: 700;"
    if val == "Недоплата":
        return base + "background-color: #ff9f43; color: black; font-weight: 700;"
    if val == "Переплата":
        return base + "background-color: #74b9ff; color: black; font-weight: 700;"
    if val == "Оплата без реалізації":
        return base + "background-color: #ffeaa7; color: black; font-weight: 700;"
    if val == "Не співпадають суми":
        return base + "background-color: #fab1a0; color: black; font-weight: 700;"
    if val == "Сплачено":
        return base + "background-color: #55efc4; color: black; font-weight: 700;"
    return base


def style_days(val):
    if pd.isna(val):
        return ""
    try:
        days = int(val)
    except Exception:
        return ""

    if days > 30:
        return "background-color: #ff4d4f; color: white; font-weight: 700;"
    if days > 20:
        return "background-color: #ff9f43; color: black; font-weight: 700;"
    if days > 10:
        return "background-color: #ffd6a5; color: black;"
    if days > 0:
        return "background-color: #fff3cd; color: black;"
    return ""


def format_display_df(df: pd.DataFrame) -> pd.DataFrame:
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


if "uploader_key_v2" not in st.session_state:
    st.session_state.uploader_key_v2 = 0


def clear_form():
    st.session_state.uploader_key_v2 += 1
    st.rerun()


st.title("🧪 Звірка дебіторської заборгованості — тестова V2")

st.markdown(
    """
Перед завантаженням:
1. Вивантажити файл з 1С  
2. Відкрити в Excel  
3. Перезберегти у форматі **.xlsx**  
4. Назвати файл у форматі **Прізвище.xlsx**
"""
)

uploaded_file = st.file_uploader(
    "📂 Завантаж Excel",
    type=["xlsx"],
    key=f"uploader_v2_{st.session_state.uploader_key_v2}",
)

show_debug = st.checkbox("Показати технічну інформацію")

if uploaded_file is None:
    st.info("⬆️ Завантажте файл для перевірки нових правил")
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
    validate_uploaded_file(uploaded_file.name)

    os.makedirs("data/raw", exist_ok=True)
    temp_path = os.path.join("data/raw", uploaded_file.name)

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    sales_manager, raw_df, parsed_df, reconciled_df = run_pipeline(
        temp_path, uploaded_file.name
    )

    st.success("✅ Обробка завершена")
    st.info(f"Менеджер: **{sales_manager}**")

    df = reconciled_df.copy()

    if "Статус" in df.columns:
        df = df[df["Статус"] != "Сплачено"].copy()

    df = format_display_df(df)

    if "Днів прострочки" in df.columns:
        df = df.sort_values(by="Днів прострочки", ascending=False, na_position="last")

    ordered_columns = [
        "Юрособа замовника",
        "ТТ / магазин",
        "Статус",
        "Днів прострочки",
        "Очікувана сума",
        "Різниця",
        "Сума реалізації",
        "Сума оплат",
        "Сума повернення",
        "Дата реалізації товарів",
        "Наша юрособа",
        "Форма оплати",
    ]

    if (
        "Сигнал бухгалтеру" in df.columns
        and df["Сигнал бухгалтеру"].fillna("").astype(str).str.strip().ne("").any()
    ):
        ordered_columns.append("Сигнал бухгалтеру")

    ordered_columns = [c for c in ordered_columns if c in df.columns]
    df = df[ordered_columns].copy()

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
        "Колонка «Сигнал бухгалтеру» потрібна для окремих нестандартних ситуацій, "
        "наприклад коли оплата прийшла по іншій ТТ і в системі потрібен перенос коштів."
    )

    excel_bytes = dataframe_to_excel_bytes(df)

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "⬇️ Excel",
            data=excel_bytes,
            file_name="result_v2.xlsx",
            use_container_width=True,
        )

    with col2:
        st.button("🗑 Очистити", on_click=clear_form, use_container_width=True)

    if show_debug:
        st.markdown("## Parsed V2")
        st.dataframe(parsed_df.head(100), use_container_width=True)

        st.markdown("## Raw preview")
        st.dataframe(raw_df.head(50), use_container_width=True)

except Exception:
    st.error("❌ Помилка")
    if show_debug:
        st.code(traceback.format_exc())