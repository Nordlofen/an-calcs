"""Explicit physical plates with multiple supports; independent of reference groups."""

import copy
import math

from .grundplan_loads import line_loads
from .grundplan_settlement import evaluate, positive, validate_profile, FORM_UNITS


def validate_foundations(items, tags):
    if not isinstance(items, list) or len(items) > 1000:
        raise ValueError("Gemensamma fundament ska anges som en lista med högst 1 000 plattor.")
    by_id = {tag["id"]: tag for tag in tags}
    ids, labels, assigned, result = set(), set(), set(), []
    fields = {"id", "label", "members", "values", "soil_profile", "form", "show_labels", "label_member"}
    for item in items:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Ogiltiga uppgifter för gemensamt fundament.")
        ident, label, members = item["id"], item["label"], item["members"]
        if not isinstance(ident, str) or not 1 <= len(ident) <= 80 or ident in ids:
            raise ValueError("Fundamentets id är ogiltigt eller upprepat.")
        if not isinstance(label, str) or not label.strip() or len(label) > 80 or label.casefold().strip() in labels:
            raise ValueError("Ange ett unikt fundamentnamn med 1–80 tecken.")
        if (not isinstance(members, list) or not members or any(not isinstance(key, str) or key not in by_id for key in members)
                or len(set(members)) != len(members) or assigned.intersection(members)):
            raise ValueError("Varje stöd får ingå i ett gemensamt fundament. Välj befintliga stöd utan upprepningar.")
        if len({by_id[key]["page"] for key in members}) != 1:
            raise ValueError("Stöden på ett gemensamt fundament måste ligga på samma ritningssida.")
        values = item["values"]
        if not isinstance(values, dict) or set(values) != {"b", "l", "t"}:
            raise ValueError("Ange plattans bₓ, bᵧ och t.")
        for name, caption in (("b", "Plattbredd bₓ"), ("l", "Plattlängd bᵧ"), ("t", "Plattjocklek t")):
            positive(values[name], caption)
        if item["form"] not in ("yta", "punkt") or type(item["show_labels"]) is not bool:
            raise ValueError("Välj ytstyvhet eller punktstyvhet samt visning på etikett för plattan.")
        if item["label_member"] not in members:
            raise ValueError("Välj ett anslutet stöd vars etikett ska visa fundamentets resultat.")
        result.append({**copy.deepcopy(item), "label": label.strip(), "soil_profile": validate_profile(item["soil_profile"])})
        ids.add(ident); labels.add(label.casefold().strip()); assigned.update(members)
    return result


def prune_foundations(items, tags):
    """Deleting supports prunes only their links; copies never inherit membership."""
    ids = {tag["id"] for tag in tags}
    result = []
    for item in items:
        members = [key for key in item["members"] if key in ids]
        if members:
            result.append({**item, "members": members,
                           "label_member": item["label_member"] if item["label_member"] in members else members[0]})
    return result


def foundation_result(item, tags, project_profile):
    by_id = {tag["id"]: tag for tag in tags}
    loads, errors, total, active = [], [], 0., 0
    for key in item["members"]:
        tag, value, error = by_id[key], None, ""
        values = tag["values"]
        inactive = bool(values.get("inaktiv"))
        line = line_loads(values)
        length = values.get("L_vagg") if line else None
        if not inactive:
            active += 1
            load = values.get("F_vy_bruk")
            if type(load) not in (int, float) or not math.isfinite(load):
                error = "Ange Brukslast."
            elif line and (type(length) not in (int, float) or not math.isfinite(length) or length <= 0):
                error = "Ange hela belastade längden L_vägg."
            else:
                value = load * length if line else load
                if not math.isfinite(value):
                    value, error = None, "Brukslastresultanten måste vara ändlig."
                else:
                    total += value
            if error:
                errors.append(tag["label"] + ": " + error)
        loads.append({"id": key, "label": tag["label"], "inactive": inactive, "line": line,
                      "load": values.get("F_vy_bruk"), "length": length, "resultant": value, "error": error})
    if not math.isfinite(total):
        errors.append("Summan av Brukslasterna måste vara ändlig.")
    profile = item["soil_profile"] or project_profile
    result = evaluate({**item["values"], "lang": 0, "lasttyp": 0,
                       "F_vy_bruk": None if errors or not active else total}, profile) if active else None
    if result is not None:
        if errors:
            result["settlement_error"] = " ".join(errors)
        form = item["form"]
        result.update(display_form=form, display_value=result["k"] if form == "yta" else result["K"],
                      display_unit=FORM_UNITS[form], display_error=result["stiffness_error"],
                      profile_source="own" if item["soil_profile"] else "project")
    return {**copy.deepcopy(item), "page": by_id[item["members"][0]]["page"], "loads": loads,
            "display_member": next((key for key in [item["label_member"], *item["members"]]
                                    if not by_id[key]["values"].get("inaktiv")), item["label_member"]),
            "active_count": active, "external": None if errors or not active else total,
            "effective_profile": copy.deepcopy(profile), "settlement": result}
