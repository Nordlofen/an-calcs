"""Physical footing type is independent of the bearing calculation model."""

import re

TYPES = {"vaggsula": "Väggsula", "pelarsula": "Pelarsula"}
CATEGORIES = {"wall": "Väggsula", "wall_pad": "Väggsula m. beräkningsmodell pelarsula", "pad": "Pelarsula"}


def infer_type(tag):
    """Migrate legacy objects without changing their engineering inputs.

    Nonstandard names with a pad model and point loads are ambiguous. They
    retain that model, but require confirmation before automatic references.
    """
    values = tag["values"]
    label = tag.get("label", "").upper()
    if values.get("lang") == 1:
        return "vaggsula", False
    if re.match(r"^VS[.\s_-]?\d", label) or "imported_length" in tag:
        return "vaggsula", False
    if re.match(r"^PS[.\s_-]?\d", label) and values.get("lasttyp", 0) == 0:
        return "pelarsula", False
    return ("vaggsula" if values.get("lasttyp") == 1 else "pelarsula"), True


def footing_type(tag):
    return tag.get("footing_type") or infer_type(tag)[0]


def footing_category(tag):
    if footing_type(tag) == "pelarsula":
        return "pad"
    return "wall" if tag["values"].get("lang") == 1 else "wall_pad"


def validate_model(typ, values):
    if not isinstance(typ, str) or typ not in TYPES:
        raise ValueError("Sultyp måste vara vaggsula eller pelarsula.")
    if typ == "pelarsula" and values["lang"] != 0:
        raise ValueError("Beräkningsmodell kan bara väljas för väggsulor. Pelarsulor använder pelarsulemodellen.")
