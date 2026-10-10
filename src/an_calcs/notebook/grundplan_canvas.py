"""Page bounds in the original drawing's stable, top-left coordinate system."""

import math

DEFAULT_BOUNDS = {"left": 0, "top": 0, "right": 1, "bottom": 1}
COORDINATE_BOUNDS = {"left": -10, "top": -10, "right": 11, "bottom": 11}


def validate_bounds(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_BOUNDS):
        raise ValueError("Ange ritningsytans fyra kanter: left, top, right och bottom.")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not -10 <= v <= 11
           for v in value.values()):
        raise ValueError("Ritningsytans kanter måste vara ändliga koordinater mellan -10 och 11.")
    for start, end in (("left", "right"), ("top", "bottom")):
        if not .05 - 1e-10 <= value[end] - value[start] <= 10 + 1e-10:
            raise ValueError("Ritningsytans bredd och höjd ska vara 5–1000 % av originalet.")
    return dict(value)


def valid_coordinate(value, axis, bounds=DEFAULT_BOUNDS):
    low, high = ("left", "right") if axis == "x" else ("top", "bottom")
    return type(value) in (int, float) and math.isfinite(value) and bounds[low] <= value <= bounds[high]


def placement_bounds(bounds, before=None):
    # Cropping keeps objects outside the visible frame in the project.
    before = before or {"x": 0, "y": 0}
    return {"left": min(0, bounds["left"], before["x"]), "top": min(0, bounds["top"], before["y"]),
            "right": max(1, bounds["right"], before["x"]), "bottom": max(1, bounds["bottom"], before["y"])}
