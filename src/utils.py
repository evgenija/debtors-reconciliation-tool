import os
import re


def extract_sales_manager_from_filename(path: str) -> str:
    filename = os.path.basename(path)
    filename = os.path.splitext(filename)[0]
    filename = re.sub(r"\s*\(\d+\)$", "", filename).strip()
    return filename