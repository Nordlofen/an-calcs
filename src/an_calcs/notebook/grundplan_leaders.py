"""Validated drawing annotations; leaders never alter calculation inputs."""

import math
from .grundplan_canvas import DEFAULT_BOUNDS, valid_coordinate


def validate_leader(value, *, coordinate_bounds=DEFAULT_BOUNDS):
    if not isinstance(value, dict) or set(value) != {"enabled", "attachment", "nodes", "end_handle"}:
        raise ValueError("Ogiltig hänvisningslinje.")
    if not isinstance(value["enabled"], bool):
        raise ValueError("Hänvisningslinjens aktivering måste vara ett booleskt värde.")

    def number(raw, low, high):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or not low <= raw <= high:
            raise ValueError("Ogiltig position för hänvisningslinjen.")
        return float(raw)

    def point(raw, limit=2):
        if not isinstance(raw, dict) or set(raw) != {"x", "y"}:
            raise ValueError("Ogiltigt kontrollhandtag.")
        return {axis: number(raw[axis], -limit, limit) for axis in ("x", "y")}

    attachment = value["attachment"]
    if (not isinstance(attachment, dict) or set(attachment) != {"side", "offset"}
            or attachment["side"] not in ("left", "right", "top", "bottom")):
        raise ValueError("Ogiltig anslutningspunkt på etiketten.")
    nodes = value["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 64:
        raise ValueError("Hänvisningslinjen måste ha mellan 1 och 64 noder.")
    valid = []
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"x", "y", "in", "out"}:
            raise ValueError("Ogiltig nod i hänvisningslinjen.")
        valid.append({"x": number(node["x"], coordinate_bounds["left"], coordinate_bounds["right"]), "y": number(node["y"], coordinate_bounds["top"], coordinate_bounds["bottom"]),
                      "in": point(node["in"]), "out": point(node["out"])})
    return {"enabled": value["enabled"],
            "attachment": {"side": attachment["side"], "offset": number(attachment["offset"], 0, 1)},
            "nodes": valid, "end_handle": point(value["end_handle"])}
