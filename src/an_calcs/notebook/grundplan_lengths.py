"""Physical footing lengths and immutable source-length load conversion."""
import copy
import math

LOAD_FIELDS = ("V_Ed_EQU", "F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b", "F_vy_bruk", "M_insp_l_bruk", "M_insp_b_bruk")


def intensity_data(values):
    if not values.get("physical_length") or values.get("lasttyp") != 1:
        return None
    source, by = values.get("L_vagg"), values.get("l")
    if type(source) not in (int, float) or type(by) not in (int, float) or source <= 0 or by <= 0:
        return None
    factor = source / by
    if not math.isfinite(factor):
        return None
    equ_length = values.get("equ_reference_length")
    if equ_length is None:
        equ_length = source
    result = {"factor": factor, "adjusted": not math.isclose(factor, 1, rel_tol=1e-10), "original": {}, "current": {}}
    for name in LOAD_FIELDS:
        value = values.get(name)
        if type(value) in (int, float) and math.isfinite(value):
            effective = value * (equ_length / by if name == "V_Ed_EQU" else factor)
            if math.isfinite(effective):
                result["original"][name] = value
                result["current"][name] = effective
    return result


def lock_source(tag, updates):
    source = tag.get("imported_length", tag["values"].get("L_vagg") if tag["values"].get("physical_length") else None)
    if source is not None and "L_vagg" in updates and updates["L_vagg"] != source:
        raise ValueError("Importerad L_stöd är låst. Uppdatera stödlängden genom ny lastimport.")
    if tag["values"].get("physical_length"):
        for name in ("equ_reference_length", "glid_L"):
            if name in updates and updates[name] != tag["values"].get(name):
                raise ValueError("Lastens ursprungliga referenslängd är låst. Ändra sulans b_y i stället.")
    if tag["values"].get("physical_length") and updates.get("physical_length") is False:
        raise ValueError("Den importerade last-/längdmodellen kan inte kopplas bort.")


def wall_axes(angle):
    a = math.radians(angle)
    return (-math.sin(a), -math.cos(a))


def migrate_wall(placement, background):
    if placement.get("kind") != "wall" or "end" not in placement:
        return copy.deepcopy(placement)
    dx = (placement["end"]["x"] - placement["start"]["x"]) * background["width"]
    dy = (placement["end"]["y"] - placement["start"]["y"]) * background["height"]
    return {"kind": "wall", "start": dict(placement["start"]), "angle_deg": math.degrees(math.atan2(-dx, -dy)) % 360}


def metres_per_pixel(calibration, background):
    if not calibration:
        raise ValueError("Kalibrera ritningsskalan före längdjustering vid startpunkten.")
    a, b = calibration["start"], calibration["end"]
    distance = math.hypot((b["x"]-a["x"])*background["width"], (b["y"]-a["y"])*background["height"])
    return calibration["length_m"] / distance


def _shift_point(point, distance, angle, background, calibration):
    if distance == 0:
        return dict(point)
    units = 1 / metres_per_pixel(calibration, background)
    yx, yy = wall_axes(angle)
    return {"x": point["x"] + yx * distance * units / background["width"],
            "y": point["y"] + yy * distance * units / background["height"]}


def referenced_placement(placement, values, background, calibration):
    """Remember the full-length origin while preserving the visible placement."""
    result = migrate_wall(placement, background)
    if result.get("kind") != "wall" or not values.get("physical_length") or "reference_start" in result:
        return result
    source, by = values.get("L_vagg"), values.get("l")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (source, by)):
        return result
    offset = source - by if values.get("length_end", 0) == 1 else 0
    if offset and not calibration:
        return result  # A replaced underlay must be calibrated first.
    result["reference_start"] = _shift_point(result["start"], -offset, result["angle_deg"], background, calibration)
    return result


def resized_placement(placement, before, after, background, calibration):
    """Derive either trimmed end from one full-length placement, without drift."""
    if not placement or placement.get("kind") != "wall" or not after.get("physical_length"):
        return copy.deepcopy(placement)
    basis = before if before.get("physical_length") else {**before, "physical_length": True, "L_vagg": after.get("L_vagg")}
    result = referenced_placement(placement, basis, background, calibration)
    if "reference_start" not in result:
        raise ValueError("Kalibrera ritningsskalan före längdjustering av sulkonturen.")
    source, by = after.get("L_vagg"), after.get("l")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (source, by)):
        return result
    reference = result["reference_start"]
    if after.get("length_end", 0) == 1 and before.get("L_vagg") is not None:
        # A new imported source length keeps the opposite full-length end fixed.
        reference = _shift_point(reference, before["L_vagg"] - source, result["angle_deg"], background, calibration)
    offset = source - by if after.get("length_end", 0) == 1 else 0
    result["reference_start"] = reference
    result["start"] = _shift_point(reference, offset, result["angle_deg"], background, calibration)
    return result
