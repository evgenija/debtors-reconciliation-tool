import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd

from src.config import INTERNAL_ENTITIES


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_number(value) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def parse_document_date(document_name: str) -> Optional[datetime]:
    match = re.search(r"від\s+(\d{2}\.\d{2}\.\d{4})", document_name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d.%m.%Y")
    except ValueError:
        return None


def is_start_block(label: str) -> bool:
    return "1. Клієнти" in label


def is_payment_form(label: str) -> bool:
    return label in ["1 форма", "2 форма"]


def is_document_row(label: str) -> bool:
    return (
        "Реализация товаров" in label
        or "Приходный кассовый ордер" in label
        or "Платежное поручение входящее" in label
        or "Возврат покупателя" in label
    )


def get_document_type(document_name: str) -> str:
    if "Реализация товаров" in document_name:
        return "realization"
    if "Приходный кассовый ордер" in document_name:
        return "payment"
    if "Платежное поручение входящее" in document_name:
        return "payment"
    if "Возврат покупателя" in document_name:
        return "return"
    return "unknown"


def is_garbage_row(label: str) -> bool:
    garbage_patterns = [
        "Відомість",
        "Період",
        "Показники",
        "Групування",
        "Відбори",
        "Додаткові поля",
        "Контрагент",
        "Торгова точка",
        "Організація",
        "Форма роботи",
        "Документ руху",
        "Поч. залишок",
        "Надходження",
        "Видаток",
        "Кін. залишок",
    ]
    return any(pattern in label for pattern in garbage_patterns)


def is_internal_entity(label: str) -> bool:
    return label in INTERNAL_ENTITIES


def looks_like_customer_legal_entity(label: str) -> bool:
    legal_markers = [
        "ФОП",
        "ТОВ",
        "ПП",
        "ПрАТ",
        "ПРАТ",
        "АТ",
        "ТДВ",
        "КП",
    ]
    return "<>" in label or any(marker in label for marker in legal_markers)


def clean_customer_legal_entity(label: str) -> str:
    return label.replace("<>", "").strip()


def build_record(
    sales_manager: str,
    customer_legal_entity: Optional[str],
    trade_point_or_store: Optional[str],
    internal_entity: Optional[str],
    payment_form: Optional[str],
    document_name: str,
    incoming: float,
    outgoing: float,
    closing_balance: float,
) -> Dict[str, Any]:
    doc_date = parse_document_date(document_name)

    return {
        "sales_manager": sales_manager,
        "customer_legal_entity": customer_legal_entity,
        "trade_point_or_store": trade_point_or_store,
        "internal_entity": internal_entity,
        "payment_form": payment_form,
        "document_name": document_name,
        "document_type": get_document_type(document_name),
        "document_date": doc_date,
        "incoming": incoming,
        "outgoing": outgoing,
        "closing_balance": closing_balance,
    }


def parse_1c_report_v2(df: pd.DataFrame, sales_manager: str) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []

    started = False

    current_customer_legal_entity: Optional[str] = None
    current_trade_point_or_store: Optional[str] = None
    current_internal_entity: Optional[str] = None
    current_payment_form: Optional[str] = None

    last_significant_type: Optional[str] = None

    for _, row in df.iterrows():
        label = normalize_text(row[1])

        incoming = safe_number(row[3] if len(row) > 3 else None)
        outgoing = safe_number(row[4] if len(row) > 4 else None)
        closing_balance = safe_number(row[5] if len(row) > 5 else None)

        if not label:
            continue

        if not started:
            if is_start_block(label):
                started = True
            continue

        if label == "<>":
            continue

        if is_garbage_row(label):
            continue

        if is_document_row(label):
            records.append(
                build_record(
                    sales_manager=sales_manager,
                    customer_legal_entity=current_customer_legal_entity,
                    trade_point_or_store=current_trade_point_or_store,
                    internal_entity=current_internal_entity,
                    payment_form=current_payment_form,
                    document_name=label,
                    incoming=incoming,
                    outgoing=outgoing,
                    closing_balance=closing_balance,
                )
            )
            last_significant_type = "document"
            continue

        if is_payment_form(label):
            current_payment_form = label
            last_significant_type = "payment_form"
            continue

        if is_internal_entity(label):
            current_internal_entity = label
            current_payment_form = None
            last_significant_type = "internal_entity"
            continue

        # Якщо рядок схожий на юрособу замовника — запам'ятовуємо її
        if looks_like_customer_legal_entity(label) and not is_internal_entity(label):
            current_customer_legal_entity = clean_customer_legal_entity(label)
            current_trade_point_or_store = None
            current_internal_entity = None
            current_payment_form = None
            last_significant_type = "customer_legal_entity"
            continue

        # Усі інші значущі рядки — це ТТ / назва магазину.
        # Якщо вони йдуть після документів/внутрішньої юрособи/форми, це новий блок.
        if last_significant_type in {"document", "internal_entity", "payment_form"}:
            current_internal_entity = None
            current_payment_form = None

        current_trade_point_or_store = label
        last_significant_type = "trade_point_or_store"

    return pd.DataFrame(records)