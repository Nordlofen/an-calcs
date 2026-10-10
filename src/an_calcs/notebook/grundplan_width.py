"""Discrete b_x proposals using the authoritative footing calculations."""

import math
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from .grundplan_reference import exclusion_reason, group_key, group_keys
from .grundplan_width_optimizer import optimize


DEFAULT_SETTINGS = {"step_mm": 100, "u_min": 70, "u_max": 99, "b_min": .2, "b_max": 5,
                    "max_reference_groups": None}


def validate_settings(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SETTINGS):
        raise ValueError("Ogiltiga inställningar för Auto bₓ.")
    settings = {**DEFAULT_SETTINGS, **value}
    for key, number in settings.items():
        if key == "max_reference_groups" and number is None:
            continue
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError("Ange ändliga tal för måttsteg, U-spann och sökbredd.")
    maximum = settings["max_reference_groups"]
    if maximum is not None and (maximum != int(maximum) or not 1 <= maximum <= 1000):
        raise ValueError("Max referensgrupper ska vara ett heltal 1–1 000, eller tomt för individuell tilldelning.")
    if settings["step_mm"] != int(settings["step_mm"]) or not 1 <= settings["step_mm"] <= 10000:
        raise ValueError("Måttsteget ska vara 1–10 000 hela millimeter.")
    if not 0 <= settings["u_min"] <= settings["u_max"] <= 100:
        raise ValueError("U-spannet ska vara 0–100 %, med undre gränsen högst lika med den övre.")
    if not .01 <= settings["b_min"] <= settings["b_max"] <= 100:
        raise ValueError("Sökbredden ska vara 0,01–100 m, med minsta bredd högst lika med den största.")
    widths = allowed_widths(settings)
    if not widths:
        raise ValueError("Sökbredden innehåller inget helt måttsteg. Justera måttsteget eller sökbredden.")
    if len(widths) > 500:
        raise ValueError("Högst 500 breddsteg kan provas per sula. Öka måttsteget eller minska sökbredden.")
    return settings


def allowed_widths(settings):
    # Integer multiples of the chosen step, anchored at zero, with no float drift.
    step = Decimal(str(settings["step_mm"])) / 1000
    first = int((Decimal(str(settings["b_min"])) / step).to_integral_value(rounding=ROUND_CEILING))
    last = int((Decimal(str(settings["b_max"])) / step).to_integral_value(rounding=ROUND_FLOOR))
    # Bound allocation even for settings coming directly from Python or a client.
    return [float(step * index) for index in range(first, min(last, first + 500) + 1)]


def utilization(summary):
    value = summary.get("utnyttjandegrad")
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Sulan saknar giltig utnyttjandegrad.")
    return value


def propose(tags, settings, calculate, *, all_tags=None):
    settings = validate_settings(settings)
    project = tags if all_tags is None else all_tags
    widths = allowed_widths(settings)
    if len(tags) * len(widths) > 50000:
        raise ValueError("Urvalet innehåller för många breddsteg. Välj färre sulor eller ett större måttsteg.")
    rows, prepared, joint = [], [], []
    maximum = settings["max_reference_groups"]
    lower, upper = settings["u_min"] / 100, settings["u_max"] / 100
    for tag in tags:
        values = tag["values"]
        row = {"id": tag["id"], "label": tag["label"], "b_before": values["b"],
               "b_after": None, "u_before": None, "u_after": None, "status": "skipped", "reason": ""}
        rows.append(row)
        reason = ("Låsta indata" if tag.get("input_locked") else "Inaktiv" if values["inaktiv"]
                  else "Endast H" if values["endast_h_stabilitet"] else None)
        if reason:
            row["reason"] = reason
            continue
        if maximum is not None and exclusion_reason(tag):
            row["reason"] = exclusion_reason(tag)
            continue
        try:
            _, summary = calculate(values)
            row["u_before"] = utilization(summary)
        except (ValueError, ArithmeticError) as exc:
            row["reason"] = "Fel i indata: " + str(exc)
            continue
        fallback = chosen = None
        candidates = []
        # Do not assume monotonic behavior: self-weight and governing checks may
        # change. Prefer the smallest width in the interval; otherwise the first
        # width below the upper limit. The lower limit is a goal, not a rejection.
        for width in widths:
            candidate = {**values, "b": width}
            try:
                details, summary = calculate(candidate)
                u = utilization(summary)
            except (ValueError, ArithmeticError):
                continue
            if u <= upper + 1e-12:
                if maximum is not None:
                    candidates.append((width, u, group_key(tag, width=width)))
                    continue
                result = (candidate, details, summary, u)
                if fallback is None:
                    fallback = result
                if u + 1e-12 >= lower:
                    chosen = result
                    break
        if maximum is not None:
            if candidates:
                joint.append((tag, row, candidates))
            else:
                row["reason"] = "Ingen giltig bredd inom sökbredden uppfyller övre U-gränsen."
            continue
        chosen = chosen or fallback
        if chosen is None:
            row["reason"] = "Ingen giltig bredd inom sökbredden uppfyller övre U-gränsen."
            continue
        candidate, details, summary, u = chosen
        row.update(b_after=candidate["b"], u_after=u,
                   status="unchanged" if candidate["b"] == values["b"] else "changed")
        if row["status"] == "changed":
            prepared.append({"id": tag["id"], "values": candidate, "details": details, "summary": summary})
    feasible, message, minimum = True, "", None
    if maximum is not None:
        joint.sort(key=lambda item: item[0]["id"])
        changing_ids = {tag["id"] for tag, _, _ in joint}
        fixed = group_keys([tag for tag in project if tag["id"] not in changing_ids])
        choices, minimum = optimize([candidates for _, _, candidates in joint], fixed,
                                    maximum, settings["step_mm"], lower)
        feasible = choices is not None
        if not feasible:
            message = (f"Max {int(maximum)} referensgrupper kan inte uppfyllas med detta urval, måttsteg och sökbredd. "
                       f"Minst {minimum} grupper behövs. Inga bredder ändras.")
            for _, row, _ in joint:
                row["reason"] = "Max referensgrupper kan inte uppfyllas."
        else:
            for (tag, row, candidates), choice in zip(joint, choices):
                width, _, _ = candidates[choice]
                candidate = {**tag["values"], "b": width}
                details, summary = calculate(candidate)
                u = utilization(summary)
                if u > upper + 1e-12:
                    raise ValueError("En föreslagen bredd uppfyller inte övre U-gränsen. Förhandsvisa igen.")
                row.update(b_after=width, u_after=u, status="unchanged" if width == tag["values"]["b"] else "changed")
                if row["status"] == "changed":
                    prepared.append({"id": tag["id"], "values": candidate, "details": details, "summary": summary})
    replacements = {result["id"]: result for result in prepared}
    after = [{**tag, **replacements[tag["id"]], "status": "calculated"}
             if tag["id"] in replacements else tag for tag in project]
    before_count, after_count = len(group_keys(project)), len(group_keys(after))
    if feasible and maximum is not None and after_count > maximum:
        raise ValueError("Förslaget överskrider Max referensgrupper. Inga bredder har ändrats.")
    return {"settings": settings, "rows": rows, "feasible": feasible, "message": message,
            "reference_groups": {"before": before_count, "after": after_count, "maximum": maximum,
                                 **({"minimum": minimum} if minimum is not None else {})},
            "changed": sum(row["status"] == "changed" for row in rows),
            "unchanged": sum(row["status"] == "unchanged" for row in rows),
            "skipped": sum(row["status"] == "skipped" for row in rows)}, prepared
