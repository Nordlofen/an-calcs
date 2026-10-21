"""Optional settlement/stiffness, independent of the bearing check and its U."""

import copy
from functools import lru_cache
import math

from an_calcs.geo import sattning, baddmodul
from .grundplan_loads import bearing_load_length


def positive(value, caption):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{caption} måste vara ett ändligt tal större än noll.")
    return value


def validate_profile(value):
    """None means no project profile / inherit for a footing. Never invent soil data."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"layers", "step"}:
        raise ValueError("Jordprofil anges med layers och step.")
    layers, step = value.get("layers"), positive(value.get("step", .1), "Beräkningsskikt")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 50:
        raise ValueError("Ange 1–50 jordlager, uppifrån och ned.")
    result = []
    count = 0
    for layer in layers:
        if not isinstance(layer, dict) or set(layer) != {"dz", "Ek", "gamma_m"}:
            raise ValueError("Varje jordlager ska ha dz, Ek och gamma_m.")
        result.append({key: positive(layer[key], caption) for key, caption in
                       (("dz", "Lagertjocklek"), ("Ek", "E-modul"), ("gamma_m", "Materialfaktor"))})
        subdivisions = layer["dz"] / step
        if not math.isfinite(subdivisions) or subdivisions > 5000:
            raise ValueError("Jordprofilen får ge högst 5 000 beräkningsskikt. Öka skikttjockleken.")
        count += math.ceil(subdivisions)
    if count > 5000:
        raise ValueError("Jordprofilen får ge högst 5 000 beräkningsskikt. Öka skikttjockleken.")
    return {"layers": result, "step": step}


def evaluate(values, profile):
    if profile is None or values.get("inaktiv") or values.get("endast_h_stabilitet"):
        return None
    # Store only small result summaries in the cache, not thousands of layer posts.
    geometry = tuple(values.get(name) for name in
                     ("lang", "b", "l", "t", "F_vy_bruk", "lasttyp", "L_vagg", "L_vagg_minst_1"))
    layers = tuple(tuple(layer[key] for key in ("dz", "Ek", "gamma_m")) for layer in profile["layers"])
    return copy.deepcopy(_evaluate(geometry, layers, profile["step"]))


@lru_cache(maxsize=1024)
def _evaluate(geometry, layers, step):
    lang, bx, by, thickness, service, load_type, length, at_least_one = geometry
    model = "VS" if lang == 1 else "PS"
    result = {"model": model, "s": None, "k": None, "K": None,
              "support_symbol": "K_linje" if model == "VS" else "K_punkt",
              "support_unit": "kN/m²" if model == "VS" else "kN/m",
              "load_unit": "kN/m" if model == "VS" else "kN",
              "external": None, "self_weight": None, "load": None,
              "settlement_error": "", "stiffness_error": ""}
    dz, E, gamma = (list(values) for values in zip(*layers))
    try:
        positive(bx, "Sulbredd bₓ")
        if model == "PS":
            positive(by, "Sullängd bᵧ")
        details = baddmodul(["Grundplan", model, "yta", bx, by, dz, E, gamma, step])
        result["k"] = positive(details["slutresultat"]["items"][0]["value"], "Bäddmodul")
        result["K"] = positive(result["k"] * bx * (by if model == "PS" else 1), "Stödets styvhet")
    except (ValueError, ArithmeticError) as exc:
        result["stiffness_error"] = result["settlement_error"] = str(exc)
        return result
    try:
        if service is None:
            raise ValueError("Ange Brukslast.")
        if type(service) not in (int, float) or not math.isfinite(service):
            raise ValueError("Brukslasten måste vara ett ändligt tal.")
        positive(thickness, "Sultjocklek")
        support_length = bearing_load_length({"lang": lang, "lasttyp": load_type,
            "L_vagg": length, "L_vagg_minst_1": at_least_one})
        external = service * (support_length if support_length is not None else 1)
        if model == "VS":
            # Adapt the local resultant to the same per-metre footing API as bearing.
            external /= positive(by, "Fördelningslängd bᵧ")
        weight = 25.0 * bx * thickness * (by if model == "PS" else 1)
        total = positive(external + weight, "Brukslast inklusive egentyngd")
        details = sattning([model, step, dz, E, gamma, total, bx, by])
        settlement = details["slutresultat"]["items"][0]["value"]
        if not math.isfinite(settlement) or settlement < 0:
            raise ValueError("Sättningen kunde inte beräknas med angivna indata.")
        result.update(s=settlement, external=external, self_weight=weight, load=total)
    except (ValueError, ArithmeticError) as exc:
        result["settlement_error"] = str(exc)
    return result
