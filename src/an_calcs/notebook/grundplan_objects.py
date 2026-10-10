"""Presentation transforms, independent of footing inputs and source page size."""

import copy
import math


def scale_value(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not .1 <= value <= 10:
        raise ValueError("Objektets skala ska vara 10–1000 procent.")
    return value


def drawing_layout(value, background):
    defaults = {"x": 0, "y": 0, "scale": 1,
                "canvas_width": background.get("source_width", background.get("width", 0)),
                "canvas_height": background.get("source_height", background.get("height", 0)),
                "canvas_width_pt": background.get("width_pt", background.get("width", 0) * .75),
                "canvas_height_pt": background.get("height_pt", background.get("height", 0) * .75)}
    if not isinstance(value, dict) or set(value) - set(defaults):
        raise ValueError("Ogiltig placering av ritningsunderlaget.")
    result = {**defaults, **value}
    scale_value(result["scale"])
    for axis in ("x", "y"):
        if type(result[axis]) not in (int, float) or not math.isfinite(result[axis]) or not -10 <= result[axis] <= 11:
            raise ValueError("Ritningsunderlagets position är ogiltig.")
    for axis in ("canvas_width", "canvas_height", "canvas_width_pt", "canvas_height_pt"):
        value = result[axis]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100000:
            raise ValueError("Ritningsytans koordinatmått är ogiltiga.")
        if background and value <= 0:
            raise ValueError("Ritningsytans koordinatmått måste vara positiva.")
    return copy.deepcopy(result)


def object_keys(tags, texts, page):
    return [*("tag:" + tag["id"] for tag in tags if tag["page"] == page),
            *(f"overlay:{page}:{kind}" for kind in ("symbol", "legend", "colour", "insulation", "comments", "reference")),
            *(f"overlay:{page}:text:{text['id']}" for text in texts)] if page else []


def object_layout(value, tags, texts, page, *, prune=False):
    if not isinstance(value, dict) or set(value) - {"scales", "order"}:
        raise ValueError("Ogiltiga objektinställningar.")
    keys = object_keys(tags, texts, page)
    scales, order = value.get("scales", {}), value.get("order", [])
    if not isinstance(scales, dict) or not isinstance(order, list) or any(not isinstance(key, str) for key in order):
        raise ValueError("Ogiltig skala eller lagerordning.")
    if len(set(order)) != len(order) or not prune and (set(scales) | set(order)) - set(keys):
        raise ValueError("Lagerordningen innehåller okända eller upprepade objekt.")
    ordered = [key for key in order if key in keys]
    for key in keys:
        if key in ordered:
            continue
        # Preserve the established default: labels below widgets. Explicitly
        # reordered existing objects retain their order when a new label is added.
        if key.startswith("tag:"):
            index = next((i for i, item in enumerate(ordered) if item.startswith("overlay:")), len(ordered))
            ordered.insert(index, key)
        else:
            ordered.append(key)
    return {"scales": {key: scale_value(scale) for key, scale in scales.items() if key in keys}, "order": ordered}


def reorder(order, selected, operation):
    if operation not in {"forward", "backward", "front", "back"}:
        raise ValueError("Välj flytta fram, flytta bak, längst fram eller längst bak.")
    result, chosen = list(order), set(selected)
    if operation == "front":
        return [key for key in order if key not in chosen] + [key for key in order if key in chosen]
    if operation == "back":
        return [key for key in order if key in chosen] + [key for key in order if key not in chosen]
    indices = range(len(result) - 2, -1, -1) if operation == "forward" else range(1, len(result))
    offset = 1 if operation == "forward" else -1
    for index in indices:
        other = index + offset
        if result[index] in chosen and result[other] not in chosen:
            result[index], result[other] = result[other], result[index]
    return result
