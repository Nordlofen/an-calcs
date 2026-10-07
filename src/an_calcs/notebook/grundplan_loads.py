"""Validate support load exports without converting signs or per-metre loads."""

import json
import math

MAX_BYTES = 5 * 1024 * 1024
CATEGORIES = {"Brott": "F_vy", "Bruk": "F_vy_bruk", "EQU": "V_Ed_EQU"}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Lasteffektfilen har ett dubbelt JSON-fält: {key}.")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Lasteffektfilen innehåller ogiltigt tal: {value}.")


def _number(value, caption):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{caption} måste vara ett ändligt tal.")
    return value


def read_loads(data, *, existing_labels=(), available=1000):
    """Validate all supports; existing labels are update targets, not new slots."""
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Lasteffektfilen måste vara mellan 1 byte och 5 MB.")
    try:
        document = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Välj en giltig JSON-fil med lasteffekter.") from exc
    if (not isinstance(document, dict) or type(document.get("schemaVersion")) is not int
            or document["schemaVersion"] != 1):
        raise ValueError("Lasteffektfilen måste ha schemaVersion 1.")
    supports = document.get("supports")
    if not isinstance(supports, list) or not supports:
        raise ValueError("Lasteffektfilen måste innehålla en lista supports med minst ett stöd.")
    existing = set(existing_labels)
    labels, items = set(), []
    for support in supports:
        if not isinstance(support, dict):
            raise ValueError("Varje stöd måste vara ett JSON-objekt.")
        label = support.get("supportId")
        if not isinstance(label, str) or not label.strip() or len(label) > 80:
            raise ValueError("supportId måste innehålla 1–80 tecken.")
        label = label.strip()
        if label in labels:
            raise ValueError(f"Littera {label} förekommer flera gånger i filen.")
        labels.add(label)
        kind = support.get("type")
        if kind not in ("line", "point"):
            raise ValueError(f"{label}: type måste vara line eller point.")
        values = {}
        if kind == "line":
            if document.get("distribution") != "uniform":
                raise ValueError(f"{label}: väggsulor kräver distribution uniform.")
            length = support.get("length")
            if not isinstance(length, dict) or length.get("unit") != "m":
                raise ValueError(f"{label}: linjestödets length måste anges i m.")
            values["L_vagg"] = _number(length.get("value"), f"{label}: linjestödslängden")
            if values["L_vagg"] <= 0:
                raise ValueError(f"{label}: linjestödslängden måste vara större än noll.")
            # Independent inputs, with the same initial value. The project
            # updater preserves a footing length that was subsequently edited.
            values["glid_L"] = values["L_vagg"]
        results = support.get("results")
        if not isinstance(results, list) or len(results) != 3:
            raise ValueError(f"{label}: ange en lasteffekt för vardera Brott, Bruk och EQU.")
        seen = set()
        unit = "kN/m" if kind == "line" else "kN"
        for result in results:
            if not isinstance(result, dict):
                raise ValueError(f"{label}: varje lasteffekt måste vara ett JSON-objekt.")
            category = result.get("category")
            if not isinstance(category, str) or category not in CATEGORIES or category in seen:
                raise ValueError(f"{label}: ange Brott, Bruk och EQU exakt en gång vardera.")
            seen.add(category)
            if result.get("unit") != unit:
                raise ValueError(f"{label}, {category}: lasten måste anges i {unit} för denna sultyp.")
            values[CATEGORIES[category]] = _number(result.get("V"), f"{label}, {category}: V")
        items.append({"label": label, "kind": "vaggsula" if kind == "line" else "pelarsula", "values": values})
    new_count = len(labels - existing)
    if new_count > available:
        raise ValueError(f"Projektet har plats för {available} fler sulor, men filen innehåller {new_count} nya stöd.")
    return items
