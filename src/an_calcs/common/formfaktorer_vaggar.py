"""Utvändiga formfaktorer för väggar enligt tabell 1.13 i bildunderlaget."""

import math


def _post(namn, latex, value, unit="", etikett=""):
    return {
        "namn": namn,
        "latex": latex,
        "value": value,
        "unit": unit,
        "etikett": etikett,
    }


def _ekvation(latex, etikett):
    return {"latex": latex, "etikett": etikett}


def _tolka_px(px):
    if not isinstance(px, (list, tuple)):
        raise ValueError("px för formfaktorer_vaggar måste vara en lista eller tuple.")
    if len(px) != 3:
        raise ValueError("px för formfaktorer_vaggar måste innehålla exakt 3 värden: d, b, h.")

    values = []
    for namn, value in zip(("d", "b", "h"), px):
        message = f"{namn} måste vara ett ändligt tal > 0 m."
        if isinstance(value, bool):
            raise ValueError(message)
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(message) from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(message)
        values.append(value)

    d, b, h = values
    h_d = h / d
    if not math.isfinite(h_d) or h_d <= 0:
        raise ValueError("h/d kan inte beräknas med angivna mått.")
    if h_d > 5:
        raise ValueError("h/d måste vara <= 5; tabell 1.13 tillämpas inte över detta intervall.")
    return d, b, h, h_d


def formfaktorer_vaggar(px):
    """Beräkna c_pe,10 och c_pe,1 för väggzonerna A–E.

    Indata: ``px = [d, b, h]``, samtliga mått i meter.
    d är längden i vindriktningen, b bredden vinkelrätt mot vinden och
    h byggnadshöjden. Gäller vertikala väggar i rektangulär planform.

    Figur 1.6 och tabell 1.13 i användarens underlag, avsnitt 1.9.1,
    motsvarar SS-EN 1991-1-4, 7.2.2 (figur 7.5 och tabell 7.1).
    Linjär interpolation används för h/d mellan 0,25, 1 och 5.
    För h/d <= 0,25 används nedersta tabellraden; h/d > 5 avvisas.

    Returnerar standardiserad details med båda formfaktorerna per zon.
    Alla tabellvärden visas; zoner med noll längd märks som utgående.
    Delresultat anger e, h/d, zonfall och zonlängder längs en sidovägg.
    """
    d, b, h, h_d = _tolka_px(px)
    e = min(b, 2 * h)
    l_a = min(e / 5, d)
    l_b = min(e, d) - l_a
    l_c = d - min(e, d)

    if e < d:
        zonfall = "e < d"
    elif e / 5 < d:
        zonfall = "d <= e < 5d"
    else:
        zonfall = "e >= 5d"

    # Tabell 1.13: C och E har gemensamma värden för c_pe,10 och c_pe,1.
    if h_d <= 0.25:
        c_d_10, c_e = 0.7, -0.3
        interpolation = "h/d <= 0,25: nedersta tabellraden används."
    elif h_d <= 1:
        andel = (h_d - 0.25) / 0.75
        c_d_10 = 0.7 + andel * 0.1
        c_e = -0.3 - andel * 0.2
        interpolation = "Linjär interpolation mellan h/d = 0,25 och 1."
    else:
        andel = (h_d - 1) / 4
        c_d_10 = 0.8
        c_e = -0.5 - andel * 0.2
        interpolation = "Linjär interpolation mellan h/d = 1 och 5."

    zoner = (
        ("A", l_a, -1.2, -1.4, "sidovägg, främre zon"),
        ("B", l_b, -0.8, -1.1, "sidovägg, mellanzon"),
        ("C", l_c, -0.5, -0.5, "sidovägg, bakre zon"),
        ("D", b, c_d_10, 1.0, "lovartsvägg"),
        ("E", b, c_e, c_e, "lävägg"),
    )
    slutresultat = []
    for zon, langd, c_10, c_1, beskrivning in zoner:
        etikett = f"zon {zon}, {beskrivning}"
        if langd == 0:
            etikett += "; utgår för vald geometri"
        for area, value in ((10, c_10), (1, c_1)):
            slutresultat.append(_post(
                f"c_pe_{area}_{zon}", rf"c_{{pe,{area},{zon}}}", value, "-", etikett,
            ))

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Underlag",
                    "text": (
                        "Avsnitt 1.9.1 Formfaktorer för väggar, figur 1.6 och tabell 1.13 "
                        "i bildunderlaget. Hänvisning: SS-EN 1991-1-4, 7.2.2, "
                        "figur 7.5 och tabell 7.1."
                    ),
                },
                {
                    "rubrik": "Geometri och zoner",
                    "text": (
                        "Vertikala väggar på en byggnad med rektangulär planform. "
                        "d mäts i vindriktningen, b vinkelrätt mot vinden och h är byggnadshöjden. "
                        "A, B och C följer efter varandra från lovartskanten på båda sidoväggarna. "
                        "D är lovartsväggen och E läväggen. Zonlängder gäller per sidovägg. "
                        "Zoner med noll längd utgår; deras tabellvärden visas endast som referens."
                    ),
                },
                {"rubrik": "Interpolation", "text": interpolation},
                {
                    "rubrik": "Formfaktorer",
                    "text": (
                        "Positivt värde betyder tryck mot väggen, negativt värde sug. "
                        "c_pe,10 avser belastad area minst 10 m² och c_pe,1 högst 1 m². "
                        "Båda tabellvärdena redovisas utan val eller interpolation för belastad area. "
                        "Ingen reduktion för bristande korrelation mellan lovart och lä tillämpas. "
                        "Vindtryck, invändigt tryck och total vindkraft beräknas inte."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("d", "d", d, "m", "byggnadslängd i vindriktningen"),
                _post("b", "b", b, "m", "byggnadsbredd vinkelrätt mot vinden"),
                _post("h", "h", h, "m", "byggnadshöjd"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("h_d", r"h/d", h_d, "-", "höjd/längd för tabellinterpolation"),
                _post("e", "e", e, "m", "minsta värdet av b och 2h"),
                _post("zonfall", r"\text{Zonfall}", zonfall, "", "enligt figur 1.6"),
                _post("aktiva_zoner", r"\text{Aktiva zoner}",
                      ", ".join(zon for zon, langd, *_ in zoner if langd > 0)),
                _post("l_A", r"l_A", l_a, "m", "längd zon A från lovartskanten"),
                _post("l_B", r"l_B", l_b, "m", "längd zon B efter zon A; 0 betyder att zonen utgår"),
                _post("l_C", r"l_C", l_c, "m", "längd zon C efter zon B; 0 betyder att zonen utgår"),
            ],
        },
        "slutresultat": {"title": "Slutresultat", "items": slutresultat},
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"e = \min(b, 2h)", "zonindelningsmått"),
                _ekvation(r"l_A = \min(e/5, d)", "längd zon A"),
                _ekvation(r"l_B = \min(e, d) - l_A", "längd zon B"),
                _ekvation(r"l_C = d - \min(e, d)", "längd zon C"),
                _ekvation(r"r = h/d", "förhållande för tabellinterpolation"),
                _ekvation(
                    r"c_{pe} = c_{pe,a} + \frac{r-r_a}{r_b-r_a}(c_{pe,b}-c_{pe,a})",
                    "linjär interpolation mellan angränsande tabellrader: 0,25–1 eller 1–5",
                ),
            ],
        },
    }


formfaktorer_vaggar.panel_schema = {
    "title": "Formfaktorer för väggar",
    "px": ["d", "b", "h"],
    "fields": [
        {"name": "d", "type": "float", "label": "Längd i vindriktningen", "symbol": "<i>d</i>", "unit": "m", "default": 20.0},
        {"name": "b", "type": "float", "label": "Bredd vinkelrätt mot vinden", "symbol": "<i>b</i>", "unit": "m", "default": 10.0},
        {"name": "h", "type": "float", "label": "Byggnadshöjd", "symbol": "<i>h</i>", "unit": "m", "default": 10.0},
    ],
    "sections": [{"title": "Byggnadsmått", "fields": ["d", "b", "h"], "columns": 3}],
}
