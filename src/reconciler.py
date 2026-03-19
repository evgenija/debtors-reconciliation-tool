import pandas as pd
from src.classifier import classify_document_type


def reconcile(parsed_df: pd.DataFrame) -> pd.DataFrame:
    if parsed_df.empty:
        return pd.DataFrame()

    df = parsed_df.copy()

    df["doc_type"] = df["document"].apply(classify_document_type)

    # Реалізація = нарахування
    df["invoice_amount"] = df.apply(
        lambda row: float(row["incoming"]) if row["doc_type"] == "invoice" else 0.0,
        axis=1,
    )

    # Для касових ордерів 1С може класти суму або в incoming, або в outgoing
    df["payment_amount"] = df.apply(
        lambda row: max(float(row["incoming"]), float(row["outgoing"]))
        if row["doc_type"] == "payment"
        else 0.0,
        axis=1,
    )

    # Повернення покупця зменшує борг
    df["return_amount"] = df.apply(
        lambda row: abs(float(row["incoming"])) if row["doc_type"] == "return" else 0.0,
        axis=1,
    )

    result = (
        df.groupby(
            ["sales_manager", "client", "entity", "payment_form"],
            as_index=False,
            dropna=False,
        )
        .agg(
            invoice_total=("invoice_amount", "sum"),
            payment_total=("payment_amount", "sum"),
            return_total=("return_amount", "sum"),
            documents_count=("document", "count"),
        )
    )

    result["net_due"] = result["invoice_total"] - result["return_total"]
    result["balance"] = result["payment_total"] - result["net_due"]

    def get_status(row):
        net_due = row["net_due"]
        payment_total = row["payment_total"]
        balance = row["balance"]

        if net_due > 0 and payment_total == 0:
            return "NOT_PAID"

        if abs(balance) < 0.01:
            return "OK"

        if balance < 0 and payment_total > 0:
            return "PARTIAL"

        if balance > 0:
            return "OVERPAID"

        return "UNKNOWN"

    result["amount_match_flag"] = result["balance"].apply(
        lambda x: "MATCH" if abs(x) < 0.01 else "MISMATCH"
    )

    result["status"] = result.apply(get_status, axis=1)

    return result.sort_values(
        by=["sales_manager", "client", "entity", "payment_form"]
    ).reset_index(drop=True)