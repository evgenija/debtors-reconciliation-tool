import os
import traceback

import streamlit as st

from src.loader import load_excel
from src.utils import extract_sales_manager_from_filename
from src.parser_1c import parse_1c_report
from src.reconciler import reconcile
from src.exporter import dataframe_to_excel_bytes


st.set_page_config(page_title="Звірка дебіторської заборгованості", layout="wide")


def validate_uploaded_filename(filename: str) -> None:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("❌ Будь ласка, завантажте файл у форматі Excel (.xlsx)")


def run_pipeline(temp_path: str, original_filename: str):
    sales_manager = extract_sales_manager_from_filename(original_filename)

    raw_df = load_excel(temp_path)
    parsed_df = parse_1c_report(raw_df, sales_manager)

    if parsed_df.empty:
        raise ValueError("❌ У файлі не знайдено операцій для звірки")

    reconciled_df = reconcile(parsed_df)

    if reconciled_df.empty:
        raise ValueError("❌ Не вдалося сформувати результат звірки")

    return raw_df, parsed_df, reconciled_df


def build_summary(df):
    status_counts = df["status"].value_counts().to_dict()
    return {
        "rows": len(df),
        "ok": status_counts.get("OK", 0),
        "partial": status_counts.get("PARTIAL", 0),
        "not_paid": status_counts.get("NOT_PAID", 0),
        "overpaid": status_counts.get("OVERPAID", 0),
    }


def highlight_status(val):
    if val == "OK":
        return "background-color: #d4edda"
    if val == "PARTIAL":
        return "background-color: #fff3cd"
    if val == "NOT_PAID":
        return "background-color: #f8d7da"
    if val == "OVERPAID":
        return "background-color: #d1ecf1"
    return ""


if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


def clear_form():
    st.session_state.uploader_key += 1
    st.rerun()


st.title("🔍 Звірка дебіторської заборгованості")
st.markdown(
    """
Завантажте Excel-звіт з 1С — система автоматично:
- порахує суми реалізацій, оплат та повернень
- визначить статус по кожному клієнту
- покаже розбіжності

Після цього ви зможете **переглянути результат або скачати Excel**.
"""
)

st.markdown("### 🧾 Що ви отримаєте")
c1, c2, c3 = st.columns(3)
c1.info("✔ Автоматичний підрахунок боргів")
c2.info("⚠ Виявлення розбіжностей")
c3.info("📊 Готовий звіт для роботи")

uploaded_file = st.file_uploader(
    "📂 Завантажте Excel-файл",
    type=["xlsx"],
    key=f"uploader_{st.session_state.uploader_key}",
)

show_debug = st.checkbox("Показати технічну інформацію", value=False)

if uploaded_file is None:
    st.warning("⬆️ Завантажте Excel-файл, щоб автоматично перевірити дебіторську заборгованість")
    st.stop()

try:
    validate_uploaded_filename(uploaded_file.name)

    os.makedirs("data/raw", exist_ok=True)
    temp_path = os.path.join("data/raw", uploaded_file.name)

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    with st.spinner("⏳ Обробка файлу..."):
        raw_df, parsed_df, reconciled_df = run_pipeline(temp_path, uploaded_file.name)

    st.success("✅ Файл успішно оброблено")

    summary = build_summary(reconciled_df)

    st.markdown("## 📊 Підсумок")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Клієнтів", summary["rows"])
    c2.metric("✔ Все оплачено", summary["ok"])
    c3.metric("⚠ Частково", summary["partial"])
    c4.metric("❌ Не оплачено", summary["not_paid"])
    c5.metric("💰 Переплата", summary["overpaid"])

    st.markdown("## 📋 Результат звірки")

    display_df = reconciled_df.rename(
        columns={
            "sales_manager": "Менеджер",
            "client": "Клієнт",
            "entity": "Юр. особа",
            "payment_form": "Форма оплати",
            "invoice_total": "Сума реалізації",
            "payment_total": "Оплати",
            "return_total": "Повернення",
            "documents_count": "К-сть документів",
            "net_due": "Очікувана сума",
            "balance": "Сальдо",
            "amount_match_flag": "Співпадіння сум",
            "status": "Статус",
        }
    ).copy()

    status_map = {
        "OK": "Все оплачено",
        "PARTIAL": "Частково оплачено",
        "NOT_PAID": "Не оплачено",
        "OVERPAID": "Переплата",
        "UNKNOWN": "Невизначено",
    }
    display_df["Статус"] = display_df["Статус"].map(status_map).fillna(display_df["Статус"])

    display_df["Сума реалізації"] = display_df["Сума реалізації"].round(2)
    display_df["Оплати"] = display_df["Оплати"].round(2)
    display_df["Повернення"] = display_df["Повернення"].round(2)
    display_df["Очікувана сума"] = display_df["Очікувана сума"].round(2)
    display_df["Сальдо"] = display_df["Сальдо"].round(2)

    display_df = display_df.sort_values(by="Сальдо", ascending=False)

    styled_df = display_df.style.map(highlight_status, subset=["Статус"])
    st.dataframe(styled_df, use_container_width=True, height=500)

    col_a, col_b = st.columns([1, 1])

    with col_a:
        excel_bytes = dataframe_to_excel_bytes(display_df)
        st.download_button(
            label="⬇️ Скачати результат у Excel",
            data=excel_bytes,
            file_name="reconciliation_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_b:
        st.button("🗑 Очистити форму", on_click=clear_form, use_container_width=True)

    if show_debug:
        st.markdown("## 🧪 Технічний preview")
        st.markdown("### Parsed")
        st.dataframe(parsed_df.head(100), use_container_width=True)
        st.markdown("### Raw")
        st.dataframe(raw_df.head(50), use_container_width=True)

except ValueError as e:
    st.error(str(e))
    st.button("🗑 Очистити форму", on_click=clear_form)

except Exception:
    st.error("❌ Помилка обробки файлу. Перевірте, що це коректний Excel-файл з 1С.")
    st.button("🗑 Очистити форму", on_click=clear_form)

    if show_debug:
        st.code(traceback.format_exc())