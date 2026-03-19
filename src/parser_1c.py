import pandas as pd


def is_document_row(label: str) -> bool:
    return (
        "Реализация товаров" in label
        or "Приходный кассовый ордер" in label
        or "Возврат покупателя" in label
    )


def is_payment_form(label: str) -> bool:
    return label in ["1 форма", "2 форма"]


def is_client_start(label: str) -> bool:
    return "1. Клієнти" in label


def is_entity(label: str) -> bool:
    return "ФОП" in label or "ТОВ" in label


def parse_1c_report(df: pd.DataFrame, sales_manager: str) -> pd.DataFrame:
    records = []

    started = False

    current_entity = None
    current_form = None

    for _, row in df.iterrows():
        label = str(row[1]) if pd.notna(row[1]) else ""
        label = label.strip()

        col_in = row[3] if pd.notna(row[3]) else 0
        col_out = row[4] if pd.notna(row[4]) else 0
        col_close = row[5] if pd.notna(row[5]) else 0

        if not label:
            continue

        # 🚀 старт
        if not started:
            if is_client_start(label):
                started = True
            continue

        # ❌ сміття
        if any(x in label for x in [
            "Групування",
            "Відбори",
            "Додаткові поля",
            "Валюта",
            "Показники",
            "Період",
            "<>",
        ]):
            continue

        # 🏢 ENTITY (і одночасно CLIENT для MVP)
        if is_entity(label):
            current_entity = label
            current_form = None
            continue

        # 💳 форма
        if is_payment_form(label):
            current_form = label
            continue

        # 📄 документ
        if is_document_row(label):
            records.append(
                {
                    "sales_manager": sales_manager,
                    "client": current_entity,  # ← ключовий фікс
                    "entity": current_entity,
                    "payment_form": current_form,
                    "document": label,
                    "incoming": col_in,
                    "outgoing": col_out,
                    "closing_balance": col_close,
                }
            )

    return pd.DataFrame(records)