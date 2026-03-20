from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd

from src.config import (
    STATUS_PAID,
    STATUS_NOT_PAID,
    STATUS_UNDERPAID,
    STATUS_OVERPAID,
    STATUS_PAYMENT_WITHOUT_REALIZATION,
    STATUS_AMOUNT_MISMATCH,
    COMMENT_TT_MISMATCH,
)


def safe_days_from_date(value) -> Optional[int]:
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return (datetime.now().date() - value.date()).days
    return None


def payment_amount_from_row(row) -> float:
    return max(float(row["incoming"]), float(row["outgoing"]))


def reconcile(parsed_df: pd.DataFrame) -> pd.DataFrame:
    if parsed_df.empty:
        return pd.DataFrame()

    work_df = parsed_df.copy()
    results: List[Dict[str, Any]] = []

    group_keys = [
        "customer_legal_entity",
        "trade_point_or_store",
        "internal_entity",
        "payment_form",
    ]

    grouped = work_df.groupby(group_keys, dropna=False, as_index=False)

    for _, group in grouped:
        realization_rows = group[group["document_type"] == "realization"].copy()
        payment_rows = group[group["document_type"] == "payment"].copy()
        return_rows = group[group["document_type"] == "return"].copy()

        realization_sum = realization_rows["incoming"].sum()
        payment_sum = (
            payment_rows.apply(payment_amount_from_row, axis=1).sum()
            if not payment_rows.empty
            else 0.0
        )
        return_sum = (
            return_rows["incoming"].abs().sum()
            if not return_rows.empty
            else 0.0
        )

        expected_sum = realization_sum - return_sum
        difference = payment_sum - expected_sum

        realization_date = None
        days_overdue = None

        if not realization_rows.empty:
            realization_date = realization_rows["document_date"].min()
            days_overdue = safe_days_from_date(realization_date)

        if realization_sum > 0 and abs(difference) < 0.01:
            status = STATUS_PAID
        elif realization_sum > 0 and payment_sum == 0:
            status = STATUS_NOT_PAID
        elif realization_sum == 0 and payment_sum > 0:
            status = STATUS_PAYMENT_WITHOUT_REALIZATION
        elif difference > 0.01:
            status = STATUS_OVERPAID
        elif difference < -0.01 and payment_sum > 0:
            status = STATUS_UNDERPAID
        else:
            status = STATUS_AMOUNT_MISMATCH

        comment = ""

        if status == STATUS_PAYMENT_WITHOUT_REALIZATION:
            same_customer_other_tt = work_df[
                (work_df["customer_legal_entity"] == group["customer_legal_entity"].iloc[0])
                & (work_df["internal_entity"] == group["internal_entity"].iloc[0])
                & (work_df["payment_form"] == group["payment_form"].iloc[0])
                & (work_df["trade_point_or_store"] != group["trade_point_or_store"].iloc[0])
                & (work_df["document_type"] == "realization")
            ]
            if not same_customer_other_tt.empty:
                comment = COMMENT_TT_MISMATCH

        results.append(
            {
                "Юрособа замовника": group["customer_legal_entity"].iloc[0],
                "ТТ / магазин": group["trade_point_or_store"].iloc[0],
                "Статус": status,
                "Днів прострочки": days_overdue,
                "Очікувана сума": round(expected_sum, 2),
                "Різниця": round(difference, 2),
                "Сума реалізації": round(realization_sum, 2),
                "Сума оплат": round(payment_sum, 2),
                "Сума повернення": round(return_sum, 2),
                "Дата реалізації товарів": realization_date,
                "Наша юрособа": group["internal_entity"].iloc[0],
                "Форма оплати": group["payment_form"].iloc[0],
                "Сигнал бухгалтеру": comment,
            }
        )

    result_df = pd.DataFrame(results)

    if not result_df.empty:
        result_df = result_df[result_df["Статус"] != STATUS_PAID].copy()
        result_df = result_df.sort_values(
            by=["Днів прострочки", "ТТ / магазин"],
            ascending=[False, True],
            na_position="last",
        ).reset_index(drop=True)

    return result_df