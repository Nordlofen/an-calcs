"""Optional physical footprint placements, independent of label positions."""
import copy
import math
from .grundplan_canvas import COORDINATE_BOUNDS, valid_coordinate

DEFAULTS = {"enabled": False, "fill_opacity": .18, "line_width_mm": .10, "show_print_width": False, "hatch_density": 1.0, "placements": {}}


def point(value):
    if not isinstance(value, dict) or set(value) != {"x", "y"} or any(
            not valid_coordinate(value[a], a, COORDINATE_BOUNDS) for a in ("x", "y")):
        raise ValueError("Ange en giltig placeringspunkt för sulan.")
    return dict(value)


def placement(value):
    if not isinstance(value, dict):
        raise ValueError("Ogiltig konturplacering.")
    kind = value.get("kind")
    anchor = "center" if kind == "pad" else "start"
    keys = set(value) - ({"reference_start"} if kind == "wall" else set())
    if kind in ("pad", "wall") and keys == {"kind", anchor, "angle_deg"}:
        angle = value["angle_deg"]
        if type(angle) not in (int, float) or not math.isfinite(angle) or abs(angle) > 36000:
            raise ValueError("Ange en ändlig riktning i grader.")
        result = {"kind": kind, anchor: point(value[anchor]), "angle_deg": angle % 360}
        if "reference_start" in value:
            result["reference_start"] = point(value["reference_start"])
        return result
    if value.get("kind") == "wall" and set(value) == {"kind", "start", "end"}:
        start, end = point(value["start"]), point(value["end"])
        if math.hypot(end["x"] - start["x"], end["y"] - start["y"]) < 1e-8:
            raise ValueError("Väggsulans start och slut måste vara olika punkter.")
        return {"kind": "wall", "start": start, "end": end}
    raise ValueError("Ange centrum/riktning eller väggsulans start/slut.")


def settings(value, tags, *, prune=False):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("Ogiltiga konturinställningar.")
    result = {**copy.deepcopy(DEFAULTS), **copy.deepcopy(value)}
    alpha = result["fill_opacity"]
    if type(result["enabled"]) is not bool or type(alpha) not in (int, float) or not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("Ange konturvisning och fyllning mellan 0 och 1.")
    width = result["line_width_mm"]
    if type(width) not in (int, float) or not math.isfinite(width) or not .01 <= width <= 2:
        raise ValueError("Konturens linjetjocklek ska vara 0,01–2 mm.")
    density = result["hatch_density"]
    if type(density) not in (int, float) or not math.isfinite(density) or not .25 <= density <= 4:
        raise ValueError("Skrafferingstätheten ska vara 25–400 %.")
    if type(result["show_print_width"]) is not bool:
        raise ValueError("Visa utskriftstjocklek ska vara True eller False.")
    if not isinstance(result["placements"], dict) or len(result["placements"]) > 1000:
        raise ValueError("Ogiltiga konturplaceringar.")
    ids = {t["id"] for t in tags}
    result["placements"] = {ident: placement(item) for ident, item in result["placements"].items()
                            if not prune or ident in ids}
    if set(result["placements"]) - ids:
        raise ValueError("Konturens sula finns inte i projektet.")
    return result
