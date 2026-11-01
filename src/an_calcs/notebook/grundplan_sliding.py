"""Project sliding model: independent global directions and explicit EQU loads.

The supplied vertical action already includes self-weight. Insulated footings
contribute zero. Direction choices describe the user's assumed force paths;
this module does not distribute horizontal forces or combine X and Y.
"""

import copy
import math
from .grundplan_canvas import DEFAULT_BOUNDS, valid_coordinate
from .grundplan_loads import line_loads


FIELDS = [
    {"name": "stability_group", "type": "choice", "label": "Stabilitetsgrupp", "unit": "", "default": 0,
     "options": [{"value": 0, "label": "Hus 1"}]},
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
                    "H_x_Ed": None, "H_y_Ed": None, "placements": {},
                    "name": "Hus 1", "angle_deg": 0, "groups": [], "next_group_id": 1, "group_mode": False}
DEFAULT_PLACEMENT = {"symbol": {"x": .06, "y": .55, "size": 160},
                     "legend": {"x": .50, "y": .04, "size": 410}}


def _finite(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


def validate_settings(settings, page_count=None, *, coordinate_bounds=DEFAULT_BOUNDS):
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_SETTINGS):
        raise ValueError("Ogiltiga inställningar för glidningskontroll.")
    result = {**copy.deepcopy(DEFAULT_SETTINGS), **copy.deepcopy(settings)}
    for name in ("enabled", "check_x", "check_y"):
        if not isinstance(result[name], bool):
            raise ValueError(f"{name} måste vara True eller False.")
    for name in ("H_x_Ed", "H_y_Ed"):
        if result[name] is not None and not _finite(result[name]):
            raise ValueError(f"{name} måste vara ett ändligt tal.")
    name, angle = result["name"], result["angle_deg"]
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError("Ange ett gruppnamn med 1–80 tecken.")
    result["name"] = name.strip()
    if not _finite(angle) or abs(angle) > 36000:
        raise ValueError("Ange en ändlig riktning i grader.")
    result["angle_deg"] = angle % 360
    if type(result["group_mode"]) is not bool or type(result["next_group_id"]) is not int or not 1 <= result["next_group_id"] <= 1000000000:
        raise ValueError("Ogiltiga stabilitetsgrupper.")
    groups = result["groups"]
    if not isinstance(groups, list) or len(groups) > 99:
        raise ValueError("Grundplanen kan ha högst 100 stabilitetsgrupper.")
    ids, names, validated = {0}, {result["name"].casefold()}, []
    fields = {"id", "name", "angle_deg", "check_x", "check_y", "H_x_Ed", "H_y_Ed", "placements"}
    for group in groups:
        if not isinstance(group, dict) or set(group) - fields or type(group.get("id")) is not int or not 1 <= group["id"] < 1000000000 or group["id"] in ids:
            raise ValueError("Stabilitetsgruppernas id måste vara unika.")
        checked = validate_settings({k:v for k,v in group.items() if k != "id"}, page_count, coordinate_bounds=coordinate_bounds)
        if checked["name"].casefold() in names:
            raise ValueError("Stabilitetsgruppernas namn måste vara unika.")
        ids.add(group["id"]); names.add(checked["name"].casefold())
        validated.append({"id":group["id"], **{k:checked[k] for k in fields - {"id"}}})
    result["groups"] = validated
    result["next_group_id"] = max(result["next_group_id"], max(ids) + 1)
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
                if not valid_coordinate(position[axis], axis, coordinate_bounds):
                    raise ValueError("Glidningsplaceringen har ogiltiga ritningskoordinater.")
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
    # EQU already includes self-weight. Preserve its source resultant when
    # footing length changes; legacy records retain their old reference length.
    names = ["V_Ed_EQU", "glid_mu"] + (["glid_L"] if line_loads(values) and not values.get("physical_length") else [])
    for name in names:
        value = values.get(name)
        if not _finite(value) or value < 0 or (name == "glid_L" and value == 0):
            caption = next(field["label"] for field in FIELDS if field["name"] == name)
            return {**result, "status": "incomplete", "capacity": None,
                    **{axis: None if selected[axis] else 0 for axis in selected},
                    "error": "Kontrollera " + caption.lower() + "."}
    if values.get("physical_length") and line_loads(values):
        ref = values.get("equ_reference_length") if values.get("equ_reference_length") is not None else values.get("L_vagg")
        if not _finite(ref) or ref <= 0:
            return {**result, "status":"incomplete", "capacity":None,
                    **{axis:None if selected[axis] else 0 for axis in selected}, "error":"Ange giltig L_stöd för EQU-resultanten."}
    capacity = values["V_Ed_EQU"] * values["glid_mu"] * (ref
        if values.get("physical_length") and line_loads(values) else values["glid_L"] if line_loads(values) else 1)
    if not math.isfinite(capacity):
        return {**result, "status": "incomplete", "capacity": None,
                **{axis: None if selected[axis] else 0 for axis in selected},
                "error": "Glidmotståndet är för stort för att beräknas."}
    return {**result, "status": "ready", "capacity": capacity,
            **{axis: capacity if selected[axis] else 0 for axis in selected}}


def project_results(tags, settings):
    tags = [tag for tag in tags if tag["values"].get("stability_group", 0) == settings.get("id", 0)]
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


def groups(settings):
    return [{**{k:v for k,v in settings.items() if k not in {"groups", "next_group_id"}}, "id":0},
            *[{**group, "enabled":settings["enabled"]} for group in settings.get("groups", [])]]


def validate_membership(values, settings):
    ident = values.get("stability_group", 0)
    if not _finite(ident) or ident != int(ident) or ident not in {group["id"] for group in groups(settings)}:
        raise ValueError("Sulans stabilitetsgrupp finns inte. Välj ett befintligt hus.")
    values["stability_group"] = int(ident)


def grouped_results(tags, settings):
    return [{"id":group["id"], "name":group["name"], "angle_deg":group["angle_deg"],
             "results":project_results(tags, group)} for group in groups(settings)]


def overlay_identity(kind):
    if kind in ("symbol", "legend"):
        return 0, kind
    if isinstance(kind, str):
        parts = kind.split(":")
        if len(parts) == 3 and parts[0] == "stability" and parts[1].isdecimal() and 0 < int(parts[1]) < 1000000000 and parts[2] in ("symbol", "legend"):
            return int(parts[1]), parts[2]
    return None


def overlay_kinds(settings):
    return [f"stability:{group['id']}:{kind}" for group in settings.get("groups", []) for kind in ("symbol", "legend")]
