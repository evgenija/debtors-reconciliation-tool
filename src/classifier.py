def classify_document_type(document: str) -> str:
    if "Реализация товаров" in document:
        return "invoice"

    if "Приходный кассовый ордер" in document:
        return "payment"

    if "Возврат покупателя" in document:
        return "return"

    return "unknown"