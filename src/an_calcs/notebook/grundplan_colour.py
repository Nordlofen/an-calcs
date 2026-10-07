"""Visual grouping only; input values and engineering results are never changed."""

import copy
import json
import math
import re
from bisect import bisect_right


PALETTE = ["#cce7ff", "#e5d8ff", "#ffdfba", "#cfeee5", "#ffd9e5", "#f3edbb",
           "#d6e0ff", "#dcf0ca", "#f3d8ca", "#d2eef3", "#eedaf1", "#e7e3d1"]
DEFAULT_SETTINGS = {"enabled": False, "category": "t", "secondary": None, "phase": "brott", "edit_type": "pad",
                    "show_legend": True, "bounds": {"pad": [100, 200, 400], "wall": [100, 200, 400]},
                    "colors": {}, "legend": {"x": .65, "y": .08, "size": 300}}
CATEGORIES = {"t": "Tjocklek t", "b": "Bredd bₓ", "l": "Längd bᵧ", "V": "Vertikallast V", "isolering": "Isolering"}
PHASES = {"brott": "Brott", "bruk": "Bruk", "EQU": "EQU"}
LOAD_FIELDS = {"brott": "F_vy", "bruk": "F_vy_bruk", "EQU": "V_Ed_EQU"}
INSULATION_GROUPS = [
    ("1", "Med isolering · inget bidrag", "#cce7ff"),
    ("0", "Utan isolering · inget bidrag", "#e4e9ed"),
    ("x", "Utan isolering · bidrag i X_g", "#ffdfba"),
    ("y", "Utan isolering · bidrag i Y_g", "#e5d8ff"),
    ("xy", "Utan isolering · bidrag i X_g och Y_g", "#cfeee5"),
]


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_SETTINGS):
        raise ValueError("Ogiltiga inställningar för färggruppering.")
    result = {**copy.deepcopy(DEFAULT_SETTINGS), **copy.deepcopy(settings)}
    for name in ("enabled", "show_legend"):
        if type(result[name]) is not bool:
            raise ValueError(f"{name} måste vara True eller False.")
    for name, choices in (("category", CATEGORIES), ("phase", PHASES), ("edit_type", ("pad", "wall"))):
        if not isinstance(result[name], str) or result[name] not in choices:
            raise ValueError("Okänt val för färggruppering: " + name + ".")
    secondary = result["secondary"]
    if secondary is not None and (not isinstance(secondary, str) or secondary not in CATEGORIES
                                  or secondary == result["category"]):
        raise ValueError("Välj högst två olika kategorier för färggruppering.")
    bounds = result["bounds"]
    if not isinstance(bounds, dict) or set(bounds) != {"pad", "wall"}:
        raise ValueError("Ange separata intervallgränser för pelarsulor och väggsulor.")
    for values in bounds.values():
        if (not isinstance(values, list) or not 1 <= len(values) <= 20
                or not all(_finite(value) for value in values)
                or any(a >= b for a, b in zip(values, values[1:]))):
            raise ValueError("Ange 1–20 ändliga intervallgränser i stigande ordning.")
    colors = result["colors"]
    if (not isinstance(colors, dict) or len(colors) > 5000
            or any(not isinstance(key, str) or not 1 <= len(key) <= 200
                   or not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value)
                   for key, value in colors.items())):
        raise ValueError("Välj giltiga färger i formatet #RRGGBB.")
    result["colors"] = {key: value.lower() for key, value in colors.items()}
    legend = result["legend"]
    if (not isinstance(legend, dict) or set(legend) != {"x", "y", "size"}
            or any(not _finite(legend[axis]) or not 0 <= legend[axis] <= 1 for axis in ("x", "y"))
            or not _finite(legend["size"]) or not 150 <= legend["size"] <= 900):
        raise ValueError("Legendens placering ska vara inom ritningen och storleken 150–900.")
    return result


def number_key(value):
    # Same stable key in Python and JavaScript, independent of decimal separator.
    mantissa, exponent = format(float(value) if value else 0., ".12e").split("e")
    return mantissa + "e" + str(int(exponent))


def palette_color(index):
    if index < len(PALETTE):
        return PALETTE[index]
    code = (index * 2654435761) & 0xffffff
    return "#" + "".join(f"{195 + ((code >> shift) & 255) % 45:02x}" for shift in (16, 8, 0))


def background_color(color):
    """Keep dark custom colours legible using the same pastel tint in both views."""
    channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    weight = 1 if min(channels) >= 150 else .3
    return "#" + "".join(f"{int(channel * weight + 255 * (1 - weight) + .5):02x}" for channel in channels)


def group_data(tags, settings):
    """Return groups with counts and tag assignments, including every interval."""
    if settings.get("secondary"):
        # Canonical order keeps custom colours when the same pair is selected in reverse.
        categories = [name for name in CATEGORIES if name in (settings["category"], settings["secondary"])]
        parts = [group_data(tags, {**settings, "category": name, "secondary": None}) for name in categories]
        order = [{group["key"]: i for i, group in enumerate(part["groups"])} for part in parts]
        pairs = {}
        for tag in tags:
            pair = tuple(part["assignments"][tag["id"]]["key"] for part in parts)
            pairs.setdefault(pair, []).append(tag["id"])
        groups, assignments = [], {}
        for pair in sorted(pairs, key=lambda pair: tuple(order[i][key] for i, key in enumerate(pair))):
            key = "combo:" + json.dumps(pair, separators=(",", ":"))
            color = settings["colors"].get(key, palette_color(len(groups)))
            group = {"key": key, "color": color, "background": background_color(color),
                     "count": len(pairs[pair]), "kind": "combination", "unit": "", "categories": categories,
                     "parts": [parts[i]["assignments"][pairs[pair][0]] for i in range(2)]}
            groups.append(group)
            for ident in pairs[pair]:
                assignments[ident] = group
        return {"groups": groups, "assignments": assignments}
    category, phase = settings["category"], settings["phase"]
    groups, assignments = [], {}
    def make(key, default_color=None, **data):
        color = settings["colors"].get(key, default_color or palette_color(len(groups)))
        group = {"key": key, "color": color, "background": background_color(color), "count": 0, **data}
        groups.append(group)
        return group
    by_key = {}
    if category == "isolering":
        for suffix, label, color in INSULATION_GROUPS:
            # Keep the original 1/0 keys for saved insulated/no-contribution colours.
            by_key[suffix] = make("isolering:" + suffix, color, label=label, kind="insulation", unit="")
    elif category == "V":
        for kind in ("pad", "wall"):
            if not any((tag["values"]["lang"] == 1) == (kind == "wall") for tag in tags):
                continue
            bounds = settings["bounds"][kind]
            for index in range(len(bounds) + 1):
                low = bounds[index - 1] if index else None
                high = bounds[index] if index < len(bounds) else None
                key = f"V:{phase}:{kind}:{number_key(low) if low is not None else '*'}:{number_key(high) if high is not None else '*'}"
                by_key[kind, index] = make(key, kind=kind, low=low, high=high, unit="kN/m" if kind == "wall" else "kN")
    else:
        unique = sorted({tag["values"][category] for tag in tags
                         if not tag["values"].get("endast_h_stabilitet") and _finite(tag["values"].get(category))})
        for value in unique:
            key = category + ":" + number_key(value)
            if key not in by_key:
                by_key[key] = make(key, value=value, unit="m", kind="geometry")
    special = {}
    for tag in tags:
        values = tag["values"]
        if category == "isolering":
            insulated = not values.get("endast_h_stabilitet") and values.get("isolering") is True
            direction = ("x" if values.get("glid_x") else "") + ("y" if values.get("glid_y") else "")
            group = by_key["1" if insulated else direction or "0"]
            group["count"] += 1
            assignments[tag["id"]] = group
            continue
        inapplicable = values.get("endast_h_stabilitet") and (category != "V" or phase != "EQU")
        value = values.get(LOAD_FIELDS[phase] if category == "V" else category)
        if inapplicable or not _finite(value):
            key = "na" if inapplicable else "missing"
            if key not in special:
                group = make(key, label="Ej tillämpligt" if inapplicable else "Saknar värde", kind="special", unit="")
                group["color"] = settings["colors"].get(key, "#d5dde1")
                group["background"] = background_color(group["color"])
                special[key] = group
            group = special[key]
        elif category == "V":
            kind = "wall" if values["lang"] == 1 else "pad"
            group = by_key[kind, bisect_right(settings["bounds"][kind], value)]
        else:
            group = by_key[category + ":" + number_key(value)]
        group["count"] += 1
        assignments[tag["id"]] = group
    return {"groups": groups, "assignments": assignments}
