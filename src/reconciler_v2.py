from datetime import datetime
import pandas as pd
from src.config import *


def clean_store_name(value):
    if pd.isna(value):
        return None
    val = str(value).strip()

    if val in ["", ",", "None"]:
        return None

    if "платежное поручение" in val.lower():
        return None

    return val


def days_from_date(date):
    if pd.isna(date):
        return None
    return (datetime.now().date() - date.date()).days


def reconcile(parsed_df: pd.DataFrame) -> pd.DataFrame:
    results = []

    parsed_df["trade_point_or_store"] = parsed_df["trade_point_or_store"].apply(clean_store_name)

    grouped = parsed_df.groupby(
        ["customer_legal_entity", "trade_point_or_store", "internal_entity", "payment_form"],
        dropna=False
    )

    for (customer, store, internal, payment_form), group in grouped:

        realizations = group[group["document_type"] == "realization"]
        payments = group[group["document_type"] == "payment"]
        returns = group[group["document_type"] == "return"]

        realization_sum = realizations["incoming"].sum()
        payment_sum = payments[["incoming", "outgoing"]].max(axis=1).sum()
        return_sum = returns["incoming"].abs().sum()

        expected = realization_sum - return_sum
        diff = payment_sum - expected

        date = realizations["document_date"].min() if not realizations.empty else None
        days = days_from_date(date) if date is not None else None

        # статуси
        if realization_sum > 0 and abs(diff) < 0.01:
            status = STATUS_PAID
        elif realization_sum > 0 and payment_sum == 0:
            status = STATUS_NOT_PAID
        elif realization_sum == 0 and payment_sum > 0:
            status = STATUS_PAYMENT_WITHOUT_REALIZATION
        elif diff > 0:
            status = STATUS_OVERPAID
        elif diff < 0:
            status = STATUS_UNDERPAID
        else:
            status = STATUS_AMOUNT_MISMATCH

        results.append({
            "Юрособа замовника": customer,
            "ТТ / магазин": store,
            "Статус": status,
            "Днів прострочки": days,
            "Очікувана сума": expected,
            "Різниця": diff,
            "Сума реалізації": realization_sum,
            "Сума оплат": payment_sum,
            "Сума повернення": return_sum,
            "Дата реалізації товарів": date,
            "Наша юрособа": internal,
            "Форма оплати": payment_form,
        })

    df = pd.DataFrame(results)

    df = df[df["Статус"] != STATUS_PAID]

    df = df.sort_values(by="Днів прострочки", ascending=False, na_position="last")

    return df.reset_index(drop=True)