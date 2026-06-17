import ast
import re


def parse_literal_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    text = text.replace("(", "").replace(")", "")
    items = re.split(r"[,\s]+", text.strip())
    values = []
    for item in items:
        if item == "":
            continue
        try:
            if "." in item:
                values.append(int(float(item)))
            else:
                values.append(int(item))
        except ValueError:
            cleaned = item.strip().strip('"').strip("'")
            if cleaned:
                values.append(cleaned)
    return values


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
