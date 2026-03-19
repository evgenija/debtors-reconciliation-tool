from src.loader import load_excel
from src.utils import extract_sales_manager_from_filename
from src.parser_1c import parse_1c_report
from src.reconciler import reconcile

import pandas as pd

INPUT_PATH = "data/raw/Ткаченко.xlsx"


def main():
    sales_manager = extract_sales_manager_from_filename(INPUT_PATH)

    df = load_excel(INPUT_PATH)
    parsed = parse_1c_report(df, sales_manager)
    reconciled = reconcile(parsed)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 120)

    print("Sales manager:", sales_manager)
    print("Raw shape:", df.shape)

    print("\n=== PARSED RESULT: first 20 rows ===")
    print(parsed.head(20).to_string(index=False))
    print("\nParsed shape:", parsed.shape)

    print("\n=== RECONCILIATION RESULT: first 30 rows ===")
    print(reconciled.head(30).to_string(index=False))
    print("\nReconciliation shape:", reconciled.shape)


if __name__ == "__main__":
    main()