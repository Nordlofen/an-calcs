"""Visual grouping only; input values and engineering results are never changed."""

import copy
import json
import math
import re
from bisect import bisect_right
from .grundplan_loads import line_loads


# ColorBrewer Set3 (12 classes), kept at its original strength in every view.
PALETTE = ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
           "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5", "#ffed6f"]
PATTERNS = ("plain", "bands", "dots", "cross", "horizontal", "vertical")
DEFAULT_SETTINGS = {"enabled": False, "category": "t", "secondary": None, "categories": None, "phase": "brott", "edit_type": "pad",
                    "show_legend": True, "include_only_h": False,
                    "bounds": {"pad": [100, 200, 400], "wall": [100, 200, 400]},
                    "colors": {}, "styles": {}, "legend": {"x": .65, "y": .08, "size": 300}}
CATEGORIES = {"t": "Tjocklek t", "b": "Bredd bₓ", "l": "Längd bᵧ", "V": "Vertikallast V", "isolering": "Isolering"}
PHASES = {"brott": "Brott", "bruk": "Bruk", "EQU": "EQU"}
LOAD_FIELDS = {"brott": "F_vy", "bruk": "F_vy_bruk", "EQU": "V_Ed_EQU"}
INSULATION_GROUPS = [
    ("1", "Med isolering · inget bidrag"),
    ("0", "Utan isolering · inget bidrag"),
    ("x", "Utan isolering · bidrag i X_g"),
    ("y", "Utan isolering · bidrag i Y_g"),
    ("xy", "Utan isolering · bidrag i X_g och Y_g"),
]


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_SETTINGS):
        raise ValueError("Ogiltiga inställningar för färggruppering.")
    result = {**copy.deepcopy(DEFAULT_SETTINGS), **copy.deepcopy(settings)}
    for name in ("enabled", "show_legend", "include_only_h"):
        if type(result[name]) is not bool:
            raise ValueError(f"{name} måste vara True eller False.")
    for name, choices in (("category", CATEGORIES), ("phase", PHASES), ("edit_type", ("pad", "wall"))):
        if not isinstance(result[name], str) or result[name] not in choices:
            raise ValueError("Okänt val för färggruppering: " + name + ".")
    secondary = result["secondary"]
    if secondary is not None and (not isinstance(secondary, str) or secondary not in CATEGORIES
                                  or secondary == result["category"]):
        raise ValueError("Välj olika giltiga kategorier för färggruppering.")
    categories = result["categories"]
    if categories is not None:
        if (not isinstance(categories, list) or not 1 <= len(categories) <= len(CATEGORIES)
                or any(not isinstance(name, str) or name not in CATEGORIES for name in categories)
                or len(set(categories)) != len(categories)):
            raise ValueError("Välj minst en av de tillgängliga kategorierna utan upprepningar.")
        result["categories"] = selected_categories(result)
        result["category"] = result["categories"][0]
        result["secondary"] = result["categories"][1] if len(categories) > 1 else None
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
    styles = result["styles"]
    if (not isinstance(styles, dict) or len(styles) > 100
            or any(not isinstance(scope, str) or not 1 <= len(scope) <= 80
                   or not isinstance(mapping, dict) for scope, mapping in styles.items())):
        raise ValueError("Ogiltiga sparade gruppmarkeringar.")
    if (any(len(mapping) > 5000 for mapping in styles.values())
            or any(not isinstance(key, str) or not 1 <= len(key) <= 200
                   or type(index) is not int or not 0 <= index < 5000
                   for mapping in styles.values() for key, index in mapping.items())
            or any(len(set(mapping.values())) != len(mapping) for mapping in styles.values())):
        raise ValueError("Ogiltiga sparade gruppmarkeringar.")
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
    return PALETTE[index % len(PALETTE)]


def background_color(color):
    """Keep dark custom colours legible using the same pastel tint in both views."""
    channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    weight = 1 if color.lower() in PALETTE or min(channels) >= 150 else .3
    return "#" + "".join(f"{int(channel * weight + 255 * (1 - weight) + .5):02x}" for channel in channels)


def selected_categories(settings):
    """Canonical order preserves colours regardless of selection order, including old projects."""
    selected = settings.get("categories") or [settings["category"], settings.get("secondary")]
    return [name for name in CATEGORIES if name in selected]


def style_scope(settings):
    categories = selected_categories(settings)
    return "+".join(categories) + (":" + settings["phase"] if "V" in categories else "")


def _decorate(groups, settings):
    # Only occupied groups in the current view consume styles. Keep their plain
    # colours where possible, then fill all 12 plain slots before using patterns.
    saved = settings.get("styles", {}).get(style_scope(settings), {})
    active = [group for group in groups if group["count"] and group["kind"] != "special"]
    mapping = {}
    start = 0
    while active:
        end = start + len(PALETTE)
        retained = {group["key"]: saved[group["key"]] for group in active
                    if group["key"] in saved and start <= saved[group["key"]] < end}
        mapping.update(retained)
        used = set(retained.values())
        pending = [group for group in active if group["key"] not in mapping]
        next_index = start
        for group in pending[:min(len(active), len(PALETTE)) - len(retained)]:
            while next_index in used:
                next_index += 1
            mapping[group["key"]] = next_index
            used.add(next_index)
        active = [group for group in pending if group["key"] not in mapping]
        start = end
    for group in groups:
        if group["kind"] == "special":
            index = None
            color = settings["colors"].get(group["key"], "#d5dde1")
        else:
            index = mapping.get(group["key"])
            color = settings["colors"].get(group["key"], palette_color(index) if index is not None else "#d5dde1")
        batch = (index or 0) // len(PALETTE)
        group.update(color=color, background=background_color(color), style_index=index,
                     pattern=PATTERNS[1 + (batch - 1) % (len(PATTERNS) - 1)] if batch else "plain",
                     pattern_variant=(batch - 1) // (len(PATTERNS) - 1) if batch else 0)


def remember_styles(tags, settings):
    """Persist active styles and retain history only while its slots remain free."""
    result = copy.deepcopy(settings)
    scope = style_scope(settings)
    active = {group["key"]: group["style_index"] for group in group_data(tags, settings)["groups"]
              if group["count"] and group["style_index"] is not None}
    used = set(active.values())
    mapping = {key: index for key, index in result["styles"].get(scope, {}).items()
               if key not in active and index not in used}
    result["styles"][scope] = {**mapping, **active}
    return result


def group_data(tags, settings):
    """Return groups with counts and tag assignments, including every interval."""
    categories = selected_categories(settings)
    include_h = (settings.get("include_only_h", False) and not set(categories) & {"t", "b", "l"}
                 and ("V" not in categories or settings["phase"] == "EQU"))
    # Filter before combining categories, so excluded footings create no group
    # or palette slot and every remaining footing has an assignment in each part.
    tags = [tag for tag in tags if include_h or not tag["values"].get("endast_h_stabilitet")]
    if len(categories) > 1:
        parts = [group_data(tags, {**settings, "categories": [name]}) for name in categories]
        order = [{group["key"]: i for i, group in enumerate(part["groups"])} for part in parts]
        pairs = {}
        for tag in tags:
            pair = tuple(part["assignments"][tag["id"]]["key"] for part in parts)
            pairs.setdefault(pair, []).append(tag["id"])
        groups, assignments = [], {}
        for pair in sorted(pairs, key=lambda pair: tuple(order[i][key] for i, key in enumerate(pair))):
            key = "combo:" + json.dumps(pair, separators=(",", ":"))
            group = {"key": key, "count": len(pairs[pair]), "kind": "combination", "unit": "", "categories": categories,
                     "parts": [parts[i]["assignments"][pairs[pair][0]] for i in range(len(categories))]}
            groups.append(group)
            for ident in pairs[pair]:
                assignments[ident] = group
        _decorate(groups, settings)
        return {"groups": groups, "assignments": assignments}
    category, phase = categories[0], settings["phase"]
    groups, assignments = [], {}
    def make(key, **data):
        group = {"key": key, "count": 0, **data}
        groups.append(group)
        return group
    by_key = {}
    if category == "isolering":
        for suffix, label in INSULATION_GROUPS:
            # Keep the original 1/0 keys for saved insulated/no-contribution colours.
            by_key[suffix] = make("isolering:" + suffix, label=label, kind="insulation", unit="")
    elif category == "V":
        for kind in ("pad", "wall"):
            if not any(line_loads(tag["values"]) == (kind == "wall") for tag in tags):
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
        value = values.get(LOAD_FIELDS[phase] if category == "V" else category)
        if not _finite(value):
            key = "missing"
            if key not in special:
                group = make(key, label="Saknar värde", kind="special", unit="")
                special[key] = group
            group = special[key]
        elif category == "V":
            kind = "wall" if line_loads(values) else "pad"
            group = by_key[kind, bisect_right(settings["bounds"][kind], value)]
        else:
            group = by_key[category + ":" + number_key(value)]
        group["count"] += 1
        assignments[tag["id"]] = group
    _decorate(groups, settings)
    return {"groups": groups, "assignments": assignments}
