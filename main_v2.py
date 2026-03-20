import pandas as pd

from src.loader import load_excel
from src.utils import extract_sales_manager_from_filename
from src.parser_1c_v2 import parse_1c_report_v2
from src.reconciler_v2 import reconcile_v2

INPUT_PATH = "data/raw/Ткаченко.xlsx"


def main():
    sales_manager = extract_sales_manager_from_filename(INPUT_PATH)

    raw_df = load_excel(INPUT_PATH)
    parsed_df = parse_1c_report_v2(raw_df, sales_manager)
    reconciled_df = reconcile_v2(parsed_df)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 320)
    pd.set_option("display.max_colwidth", 120)

    print("Sales manager:", sales_manager)
    print("Raw shape:", raw_df.shape)

    print("\n=== PARSED V2: first 40 rows ===")
    print(parsed_df.head(40).to_string(index=False))
    print("\nParsed V2 shape:", parsed_df.shape)

    print("\n=== RECONCILIATION V2 ===")
    print(reconciled_df.to_string(index=False))
    print("\nReconciliation V2 shape:", reconciled_df.shape)


if __name__ == "__main__":
    main()