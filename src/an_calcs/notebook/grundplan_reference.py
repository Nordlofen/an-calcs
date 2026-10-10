"""Automatic bookkeeping for further design in Foundation, never a calculation."""

import copy
import json
import math
import re

from .grundplan_loads import line_loads, load_resultants
from .grundplan_types import footing_category

DEFAULT_SETTINGS = {"enabled": False, "x": .05, "y": .3, "size": 410}
# Insulation may differ within a group and is documented explicitly. Soil,
# placement and calculation assumptions must match; loads choose the reference.
CONDITIONS = ("d", "e_b_plac", "e_l_plac", "c_prime", "c_uk", "gamma", "gamma_prime",
              "phi_k", "delta_h", "beta", "alpha", "eta", "gamma_m", "gamma_m0", "gamma_Rd")


def validate_settings(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SETTINGS):
        raise ValueError("Ogiltiga inställningar för Referens.")
    result = {**DEFAULT_SETTINGS, **value}
    if type(result["enabled"]) is not bool:
        raise ValueError("enabled måste vara True eller False.")
    for name, low, high in (("x", 0, 1), ("y", 0, 1), ("size", 205, 1230)):
        number = result[name]
        if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError("Referensens placering ska vara inom ritningen och storleken 205–1230.")
    return copy.deepcopy(result)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _order(tag):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r"(\d+)", tag["label"])) + ((1, tag["id"]),)


def _canonical(value):
    """Give numerically equal ints/floats the same key, without rounding."""
    if isinstance(value, dict):
        return {name: _canonical(number) for name, number in value.items()}
    if isinstance(value, list):
        return [_canonical(number) for number in value]
    if type(value) is float and value.is_integer():
        return int(value)
    return value


def group_data(tags):
    groups, excluded = {}, []
    for tag in sorted(tags, key=_order):
        values, summary = tag["values"], tag.get("summary") or {}
        reason = ("Inaktiv" if values.get("inaktiv") else "Endast H-stabilitet" if values.get("endast_h_stabilitet")
                  else "Bekräfta sultyp" if tag.get("footing_type_inferred")
                  else "Saknar aktuellt beräkningsresultat" if tag.get("status") != "calculated"
                  or not _finite(summary.get("utnyttjandegrad")) else None)
        category = footing_category(tag)
        geometry = {"t": values.get("t"), "b": values.get("b")}
        if category != "wall" or values.get("l") != 1:
            geometry["l"] = values.get("l")
        if category == "wall_pad" and line_loads(values):
            geometry["L_vagg"] = values.get("L_vagg")
        if not reason and any(not _finite(number) or number <= 0 for number in geometry.values()):
            reason = "Ofullständiga gruppmått"
        if reason:
            excluded.append({"id": tag["id"], "label": tag["label"], "reason": reason})
            continue
        # Separate line and point inputs. Ordinary walls may have different
        # local load lengths; bookkeeping never changes their individual checks.
        # Wall-pad models still group by L_vagg through geometry above.
        key = json.dumps(_canonical([category, geometry, line_loads(values),
                          [values.get(name) for name in CONDITIONS]]), sort_keys=True, separators=(",", ":"))
        groups.setdefault(key, {"category": category, "geometry": geometry, "members": []})["members"].append(tag)
    result = []
    for key, group in groups.items():
        members = group.pop("members")
        reference = min(members, key=lambda tag: (-tag["summary"]["utnyttjandegrad"], _order(tag)))
        values = reference["values"]
        uninsulated = [tag["label"] for tag in members if not tag["values"].get("isolering")]
        stabilizing = [tag["label"] for tag in members if not tag["values"].get("isolering")
                       and (tag["values"].get("glid_x") or tag["values"].get("glid_y"))]
        comments = ["Styrande för " + reference["label"] + ": " + reference["summary"]["styrande"]]
        if uninsulated:
            comments.append("Utan isolering" if len(uninsulated) == len(members)
                            else "Utan isolering: " + ", ".join(uninsulated))
        if stabilizing:
            comments.append("H-stabiliserande: " + ", ".join(stabilizing))
        result.append({**group, "key": key, "reference_id": reference["id"], "label": reference["label"],
                       "utilization": reference["summary"]["utnyttjandegrad"],
                       "utilization_range": {"min": min(tag["summary"]["utnyttjandegrad"] for tag in members),
                                             "max": reference["summary"]["utnyttjandegrad"]},
                       "members": [{"id": tag["id"], "label": tag["label"]} for tag in members],
                       "unit": "kN/m" if line_loads(values) else "kN",
                       "loads": {"brott": values.get("F_vy"), "bruk": values.get("F_vy_bruk")},
                       "resultants": load_resultants(values), "comments": comments})
    category_order = {"wall": 0, "wall_pad": 1, "pad": 2}
    result.sort(key=lambda group: (category_order[group["category"]], _order({"label": group["label"], "id": group["reference_id"]})))
    return {"groups": result, "excluded": excluded}
