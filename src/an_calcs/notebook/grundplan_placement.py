"""Shared placement identities for labels and drawing widgets."""

import copy
from .grundplan_canvas import DEFAULT_BOUNDS, valid_coordinate

WIDGET_KINDS = {"symbol", "legend", "colour", "insulation", "comments", "reference"}


def object_key(item):
    return "tag:" + item["id"] if item["type"] == "tag" else f"overlay:{item['page']}:{item['kind']}"


def validate_objects(objects, tags, texts, page, *, coordinates=False, allow_empty=False, coordinate_bounds=DEFAULT_BOUNDS):
    if not isinstance(objects, list) or not (0 if allow_empty else 1) <= len(objects) <= 1106:
        raise ValueError("Ange etiketter eller widgets på ritningen.")
    tag_ids = {tag["id"] for tag in tags if tag["page"] == page}
    text_ids = {item["id"] for item in texts}
    keys = set()
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError("Ogiltigt placeringsobjekt.")
        fields = {"type", "id"} if item.get("type") == "tag" else {"type", "kind", "page"}
        if set(item) != fields | ({"x", "y"} if coordinates else set()):
            raise ValueError("Ogiltigt placeringsobjekt.")
        if item["type"] == "tag":
            if not isinstance(item["id"], str) or item["id"] not in tag_ids:
                raise ValueError("Etiketten finns inte på ritningen.")
        elif item["type"] == "overlay":
            kind = item["kind"]
            if type(item["page"]) is not int or item["page"] != page:
                raise ValueError("Widgetens sida finns inte i vyn.")
            if not isinstance(kind, str) or (kind not in WIDGET_KINDS
                    and not (kind.startswith("text:") and kind[5:] in text_ids)):
                raise ValueError("Widgeten finns inte.")
        else:
            raise ValueError("Okänd objekttyp.")
        key = object_key(item)
        if key in keys:
            raise ValueError("Varje placeringsobjekt får bara anges en gång.")
        keys.add(key)
        if coordinates:
            for axis in ("x", "y"):
                value = item[axis]
                if not valid_coordinate(value, axis, coordinate_bounds):
                    raise ValueError("Objektens positioner har ogiltiga ritningskoordinater.")
    return copy.deepcopy(objects)
