import streamlit as st
import pandas as pd

from src.loader import load_excel
from src.utils import extract_sales_manager_from_filename
from src.parser_1c import parse_1c_report
from src.reconciler import reconcile
from src.exporter import dataframe_to_excel_bytes

st.title("📊 Звірка дебіторської заборгованості")

st.markdown("Завантаж Excel (.xlsx) файл для звірки")

uploaded_file = st.file_uploader("Завантаж файл", type=["xlsx"])

if uploaded_file:
    try:
        # 👉 крок 1: пробуємо прочитати файл
        df_raw = load_excel(uploaded_file)

    except Exception as e:
        st.error("❌ Файл пошкоджений або має неправильний формат.")
        st.info("👉 Відкрийте файл в Excel і перезбережіть як .xlsx, після чого завантажте повторно.")
        st.stop()

    try:
        # 👉 крок 2: обробка
        sales_manager = extract_sales_manager_from_filename(uploaded_file.name)

        df_parsed = parse_1c_report(df_raw)
        df_result = reconcile(df_parsed)

        st.success("✅ Файл успішно оброблено")
        st.markdown(f"**Менеджер у файлі:** {sales_manager}")

        st.dataframe(df_result)

        # 👉 експорт
        excel_bytes = dataframe_to_excel_bytes(df_result)

        st.download_button(
            label="📥 Завантажити результат",
            data=excel_bytes,
            file_name="reconciliation_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error("❌ Помилка обробки файлу")
        st.text(str(e))