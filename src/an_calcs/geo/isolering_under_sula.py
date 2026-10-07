"""Tryckkontroll av underliggande isolering över sulans effektiva area."""

import math

from .allmanna_barighetsekvationen import allmanna_barighetsekvationen


_GEOMETRY = ["b", "l", "lang", "t", "e_b_plac", "e_l_plac"]
_LOADS = ["F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b", "l_h"]
_NAMES = _GEOMETRY + _LOADS + [name + "_bruk" for name in _LOADS] + ["f_d_brott", "f_d_bruk"]
_BASE_FIELDS = {field["name"]: field for field in allmanna_barighetsekvationen.panel_schema["fields"]}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} måste vara ett ändligt tal.")
    return value


def _post(name, value, unit, label):
    return {"namn": name, "latex": r"\mathrm{" + name.replace("_", r"\_") + "}",
            "value": value, "unit": unit, "etikett": label}


def isolering_under_sula(px, *, remslangd=None):
    """Kontrollera isolering i brott och bruk (långtid), med q = N / A_eff.

    px = [b, l, lang, t, e_b_plac, e_l_plac,
          F_vy, F_hb, F_hl, M_insp_l, M_insp_b, l_h,
          F_vy_bruk, F_hb_bruk, F_hl_bruk, M_insp_l_bruk, M_insp_b_bruk, l_h_bruk,
          f_d_brott, f_d_bruk]

    Mått anges i m, hållfastheter i kPa. Yttre laster anges exklusive sulans
    egentyngd. För lang=1 avser krafter kN/m och moment kNm/m på en 1 m-remsa;
    annars anges kN och kNm för hela fundamentet. Egentyngd är 25*b*l_ref*t,
    med faktor 1,5 i brott och 1,0 i bruk. Lastkombinationerna anges färdiga.
    Inmatade f_d är färdiga dimensionerande värden; ingen materialfaktor
    appliceras igen. Isoleringen förutsätts täcka hela den effektiva arean.

    Effektiv bredd och längd beräknas separat för respektive lastkombination,
    med samma excentricitets- och teckenkonvention som jordberäkningen.
    Noll hävarm ger direkt angivna moment utan momentbidrag från horisontallast.
    Kontrollen avser tryck över effektiv area, inte maximalt kanttryck eller
    en beräkning av isoleringens krypdeformation.

    Med ``remslangd`` kan väggsulans beräkningsremsa ändras från 1 m. Laster
    och moment anges fortfarande per meter vägg. Trycket beräknas då som
    N_per_meter * remslangd / A_eff; egentyngden redovisas också per meter.
    """
    if px is None or len(px) != len(_NAMES):
        raise ValueError(f"px måste innehålla {len(_NAMES)} värden.")
    values = {name: _number(value, name) for name, value in zip(_NAMES, px)}
    if values["lang"] not in (0, 1):
        raise ValueError("lang måste vara 0 eller 1.")
    for name in ("b", "l", "t", "f_d_brott", "f_d_bruk"):
        if values[name] <= 0:
            raise ValueError(f"{name} måste vara > 0.")
    for name in ("l_h", "l_h_bruk"):
        if values[name] < 0:
            raise ValueError(f"{name} måste vara >= 0.")
    length = 1.0 if values["lang"] == 1 else values["l"]
    if remslangd is not None:
        length = _number(remslangd, "Remslängd")
        if values["lang"] != 1 or length <= 0:
            raise ValueError("Remslängd måste vara positiv och gäller endast väggsulor.")
    force_unit = "kN/m" if values["lang"] == 1 else "kN"
    weight = _number(25 * values["b"] * (1.0 if values["lang"] == 1 else length) * values["t"], "Egentyngd")
    intermediate = [_post("isolering_EG_k", weight, force_unit, "sulans karakteristiska egentyngd")]
    results = []
    for phase, suffix, factor in (("brott", "", 1.5), ("bruk", "_bruk", 1.0)):
        normal = values["F_vy" + suffix] + factor * weight
        _number(normal, f"N_{phase}")
        if normal <= 0:
            raise ValueError(f"Isolering – {phase}: total vertikallast måste vara > 0.")
        e_b = abs(values["e_b_plac"] + (
            values["M_insp_l" + suffix] - values["F_hb" + suffix] * values["l_h" + suffix]
        ) / normal)
        e_l = abs(values["e_l_plac"] + (
            values["M_insp_b" + suffix] - values["F_hl" + suffix] * values["l_h" + suffix]
        ) / normal)
        width_eff = values["b"] - 2 * e_b
        length_eff = length - 2 * e_l
        for name, value in (("b_eff", width_eff), ("l_eff", length_eff)):
            _number(value, name)
            if value <= 0:
                raise ValueError(f"Isolering – {phase}: {name} måste vara > 0. Kontrollera excentricitet och laster.")
        area = _number(width_eff * length_eff, f"A_eff_{phase}")
        if area <= 0:
            raise ValueError(f"Isolering – {phase}: effektiv area måste vara > 0.")
        pressure = _number(normal * (length if values["lang"] == 1 else 1.0) / area, f"q_Ed_{phase}")
        utilization = _number(pressure / values["f_d_" + phase], f"U_{phase}")
        for name, value, unit, label in (
            ("N", normal, force_unit, "total vertikallast inklusive egentyngd"),
            ("e_b", e_b, "m", "total excentricitet i bredd"),
            ("e_l", e_l, "m", "total excentricitet i längd"),
            ("b_eff", width_eff, "m", "effektiv bredd"),
            ("l_eff", length_eff, "m", "effektiv längd"),
            ("A_eff", area, "m^2", "effektiv area (beräkningsremsa för väggsula)"),
        ):
            intermediate.append(_post(f"isolering_{name}_{phase}", value, unit, f"{label}, {phase}"))
        for name, value, unit, label in (
            ("q_Ed", pressure, "kPa", "tryck över effektiv area"),
            ("f_d", values["f_d_" + phase], "kPa", "dimensionerande bärförmåga för isolering"),
            ("U", utilization, "", "utnyttjandegrad för isolering"),
        ):
            results.append(_post(f"isolering_{name}_{phase}", value, unit, f"{label}, {phase}"))
    fields = {field["name"]: field for field in isolering_under_sula.panel_schema["fields"]}
    inputs = []
    for name, value in values.items():
        field = fields[name]
        unit = field.get("unit", "")
        if values["lang"] == 1 and unit in ("kN", "kNm"):
            unit += "/m"
        inputs.append(_post("isolering_" + name, value, unit, field["label"]))
    return {
        "metodbeskrivning": {"title": "Metodbeskrivning", "items": [
            {"rubrik": "Isolering under sula", "text": (
                "Tryck över effektiv area jämförs med inmatad dimensionerande bärförmåga separat i brott och bruk (långtid). "
                "Isoleringen förutsätts täcka hela arean. Inga ytterligare materialfaktorer eller lastkombinationer tillämpas. "
                "Sulans egentyngd läggs till med faktor 1,5 i brott och 1,0 i bruk. "
                "Kontrollen beräknar inte maximalt kanttryck, sättning eller krypdeformation."
            )},
        ]},
        "indata": {"title": "Indata", "items": inputs},
        "delresultat": {"title": "Delresultat", "items": intermediate},
        "slutresultat": {"title": "Slutresultat", "items": results},
        "ekvationer": {"title": "Ekvationer", "items": [
            {"latex": r"EG_k = 25 b t" if remslangd is not None else r"EG_k = 25 b l_{ref} t", "etikett": "sulans egentyngd"},
            {"latex": r"N_{brott}=F_{v,y,brott}+1.5 EG_k,\quad N_{bruk}=F_{v,y,bruk}+EG_k", "etikett": "total vertikallast"},
            {"latex": r"e_b=\left|e_{b,plac}+\frac{M_{insp,l}-F_{h,b}l_h}{N}\right|,\quad e_l=\left|e_{l,plac}+\frac{M_{insp,b}-F_{h,l}l_h}{N}\right|", "etikett": "excentricitet per lastkombination"},
            {"latex": r"A_{eff}=(b-2e_b)(l_{ref}-2e_l)", "etikett": "effektiv area"},
            {"latex": r"q_{Ed}=\frac{N l_{ref}}{A_{eff}},\quad U=\frac{q_{Ed}}{f_d}" if remslangd is not None else r"q_{Ed}=\frac{N}{A_{eff}},\quad U=\frac{q_{Ed}}{f_d}", "etikett": "kontroll separat i brott och bruk"},
        ]},
    }


isolering_under_sula.panel_schema = {
    "title": "Isolering under sula",
    "px": _NAMES,
    "fields": [dict(_BASE_FIELDS[name]) for name in _GEOMETRY + _LOADS] + [
        {**_BASE_FIELDS[name], "name": name + "_bruk",
         "label": _BASE_FIELDS[name]["label"] + " – bruk",
         "default": None if name == "F_vy" else _BASE_FIELDS[name]["default"]}
        for name in _LOADS
    ] + [
        {"name": "f_d_brott", "type": "float", "label": "Dimensionerande bärförmåga f_d.brott", "unit": "kPa", "default": None},
        {"name": "f_d_bruk", "type": "float", "label": "Dimensionerande bärförmåga f_d.bruk", "unit": "kPa", "default": None},
    ],
}
