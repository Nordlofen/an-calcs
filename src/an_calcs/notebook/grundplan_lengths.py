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


def resized_placement(placement, before, after, background, calibration):
    """Move only the selected end, leaving the opposite end fixed."""
    if not placement or placement.get("kind") != "wall" or not after.get("physical_length"):
        return copy.deepcopy(placement)
    result = migrate_wall(placement, background)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (before["l"], after["l"])):
        return result
    if after.get("length_end", 0) == 1 and after["l"] != before["l"]:
        units = 1 / metres_per_pixel(calibration, background)
        yx, yy = wall_axes(result["angle_deg"])
        delta = (before["l"] - after["l"]) * units
        result["start"] = {"x": result["start"]["x"] + yx*delta/background["width"],
                           "y": result["start"]["y"] + yy*delta/background["height"]}
    return result
