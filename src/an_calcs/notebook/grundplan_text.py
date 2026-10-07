"""Drawing text objects, independent of footing inputs and calculations."""

import copy
import math
from datetime import datetime
from zoneinfo import ZoneInfo


def today_text():
    return datetime.now(ZoneInfo("Europe/Stockholm")).strftime("%y/%m/%d")


def validate_text_objects(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Ritningen kan innehålla högst 100 textobjekt.")
    ids = set()
    for item in value:
        required = {"id", "kind", "text", "x", "y", "size"}
        if not isinstance(item, dict) or set(item) not in (required, required | {"subtitle"}):
            raise ValueError("Ogiltigt textobjekt.")
        ident = item["id"]
        if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in ids:
            raise ValueError("Textobjekt ska ha unika id.")
        ids.add(ident)
        if item["kind"] not in ("heading", "date") or not isinstance(item["text"], str):
            raise ValueError("Textobjekt ska vara en rubrik eller ett datum med text.")
        subtitle = item.get("subtitle", "")
        if not isinstance(subtitle, str) or item["kind"] == "date" and subtitle:
            raise ValueError("Underrubrik ska anges som text för ett rubrikobjekt.")
        for name, low, high in (("x", 0, 1), ("y", 0, 1), ("size", 10, 144)):
            number = item[name]
            if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
                raise ValueError(f"Textobjektets {name} ska vara {low}–{high}.")
    return [{**copy.deepcopy(item), "subtitle": item.get("subtitle", "")} for item in value]
