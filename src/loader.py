import pandas as pd


def load_excel(path: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=0, header=None)