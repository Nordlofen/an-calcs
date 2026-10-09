"""Project sliding model: independent global directions and explicit EQU loads.

The supplied vertical action already includes self-weight. Insulated footings
contribute zero. Direction choices describe the user's assumed force paths;
this module does not distribute horizontal forces or combine X and Y.
"""

import copy
import math
from .grundplan_loads import line_loads


FIELDS = [
    {"name": "glid_x", "type": "bool", "label": "Bidrar i global X-led", "unit": "", "default": False},
    {"name": "glid_y", "type": "bool", "label": "Bidrar i global Y-led", "unit": "", "default": False},
    {"name": "V_Ed_EQU", "type": "number", "label": "Vertikallast i EQU, inkl. egentyngd", "unit": "kN", "default": None,
     "display_symbol": {"base": "V", "subscript": "Ed,EQU"}},
    {"name": "glid_mu", "type": "number", "label": "Dimensionerande friktionskoefficient", "unit": "", "default": None,
     "display_symbol": {"base": "μ", "subscript": "d"}},
    {"name": "glid_L", "type": "number", "label": "Väggsulans totala längd", "unit": "m", "default": None,
     "display_symbol": {"base": "L", "subscript": "su"}},
]
NAMES = {field["name"] for field in FIELDS}
DEFAULT_SETTINGS = {"enabled": False, "check_x": False, "check_y": False,
                    "H_x_Ed": None, "H_y_Ed": None, "placements": {}}
DEFAULT_PLACEMENT = {"symbol": {"x": .06, "y": .55, "size": 160},
                     "legend": {"x": .50, "y": .04, "size": 410}}


def _finite(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


def validate_settings(settings, page_count=None):
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_SETTINGS):
        raise ValueError("Ogiltiga inställningar för glidningskontroll.")
    result = {**copy.deepcopy(DEFAULT_SETTINGS), **copy.deepcopy(settings)}
    for name in ("enabled", "check_x", "check_y"):
        if not isinstance(result[name], bool):
            raise ValueError(f"{name} måste vara True eller False.")
    for name in ("H_x_Ed", "H_y_Ed"):
        if result[name] is not None and not _finite(result[name]):
            raise ValueError(f"{name} måste vara ett ändligt tal.")
    if not isinstance(result["placements"], dict):
        raise ValueError("Ogiltiga placeringar för glidningskontroll.")
    for page, placements in result["placements"].items():
        if (not isinstance(page, str) or not page.isdecimal() or str(int(page)) != page
                or int(page) < 1 or (page_count is not None and int(page) > page_count)):
            raise ValueError("Glidningssymbolens sida finns inte i ritningen.")
        if not isinstance(placements, dict) or set(placements) - {"symbol", "legend"}:
            raise ValueError("Ogiltig glidningsplacering.")
        for kind, position in placements.items():
            if kind == "legend" and isinstance(position, dict) and set(position) == {"x", "y"}:
                # Projects saved before legend scaling retain their original size.
                position["size"] = DEFAULT_PLACEMENT["legend"]["size"]
            if not isinstance(position, dict) or set(position) != {"x", "y", "size"}:
                raise ValueError("Ogiltig glidningsplacering.")
            for axis in ("x", "y"):
                if not _finite(position[axis]) or not 0 <= position[axis] <= 1:
                    raise ValueError("Glidningsplacering måste ligga på ritningen (0–1).")
            low, high = (50, 600) if kind == "symbol" else (205, 1230)
            if not _finite(position["size"]) or not low <= position["size"] <= high:
                caption = "Koordinatsymbolens" if kind == "symbol" else "Glidningsrutans"
                raise ValueError(f"{caption} storlek måste ligga mellan {low} och {high}.")
    return result


def contribution(values):
    selected = {axis: not values.get("inaktiv") and values.get("glid_" + axis) is True for axis in ("x", "y")}
    result = {"selected": selected, "x": 0, "y": 0, "capacity": 0, "status": "inactive", "error": ""}
    if values.get("inaktiv"):
        return result
    if values.get("isolering") is True:
        return {**result, "status": "insulated"}
    if not any(selected.values()):
        return result
    # EQU is a contact load per metre of footing for line inputs. Its global
    # contribution uses the full footing length, independently of the wall
    # length used to convert Brott/Bruk actions in the local bearing check.
    names = ["V_Ed_EQU", "glid_mu"] + (["glid_L"] if line_loads(values) else [])
    for name in names:
        value = values.get(name)
        if not _finite(value) or value < 0 or (name == "glid_L" and value == 0):
            caption = next(field["label"] for field in FIELDS if field["name"] == name)
            return {**result, "status": "incomplete", "capacity": None,
                    **{axis: None if selected[axis] else 0 for axis in selected},
                    "error": "Kontrollera " + caption.lower() + "."}
    capacity = values["V_Ed_EQU"] * values["glid_mu"] * (values["glid_L"] if line_loads(values) else 1)
    if not math.isfinite(capacity):
        return {**result, "status": "incomplete", "capacity": None,
                **{axis: None if selected[axis] else 0 for axis in selected},
                "error": "Glidmotståndet är för stort för att beräknas."}
    return {**result, "status": "ready", "capacity": capacity,
            **{axis: capacity if selected[axis] else 0 for axis in selected}}


def project_results(tags, settings):
    results = {}
    for axis in ("x", "y"):
        demand = settings["H_" + axis + "_Ed"]
        selected = [(tag, contribution(tag["values"])) for tag in tags
                    if not tag["values"].get("inaktiv") and tag["values"].get("glid_" + axis)]
        missing = [tag["label"] for tag, result in selected if result[axis] is None]
        contributors = [{"id": tag["id"], "label": tag["label"], "resistance": result[axis]}
                        for tag, result in selected if result[axis] is not None and result[axis] > 0]
        try:
            resistance = math.fsum(item["resistance"] for item in contributors) if not missing else None
        except OverflowError:
            resistance = None
        active = settings["enabled"] and settings["check_" + axis]
        status, utilization = "off", None
        if active:
            if demand is None or resistance is None:
                status = "incomplete"
            elif resistance == 0:
                status, utilization = ("ok", 0) if demand == 0 else ("over", None)
            else:
                status = "ok" if abs(demand) <= resistance else "over"
                ratio = abs(demand) / resistance
                utilization = ratio if math.isfinite(ratio) else None
        results[axis] = {"H_Ed": demand, "H_Rd": resistance, "count": len(contributors),
                         "contributors": contributors, "missing": missing,
                         "status": status, "utilization": utilization}
    return results
