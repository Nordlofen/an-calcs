"""Lastoberoende grundstyvhet med 2:1-metoden och stöd för äldre lastanrop."""

from copy import deepcopy
import math

from .sattning import sattning, _berakningsskikt, _ekvation, _post


def _positivt_tal(namn, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{namn} måste vara ett ändligt tal > 0.")
    return value


def baddmodul(px):
    """Beräkna styvhet direkt från grundmått och lastoberoende jordmoduler.

    Nytt format:
        [namn, typ, form, bx, by, dz_lista, Ek_lista, gamma_m_lista, t_skikt]

    ``form`` är "yta" eller "punkt" för PS, "yta" eller "linje" för VS.
    Utan form (8 värden) används "yta". Mått anges i m, Ek i MPa.
    VS använder alltid by = 1 m och spridning enbart i x-led.
    Slutresultatet är vald styvhet, i potensform med två decimaler.

    Äldre format med numerisk F på tredje plats fungerar oförändrat:
        [namn, typ, F, bx, by, dz_lista, Ek_lista, gamma_m_lista, t_skikt]
    Det formatet behåller även sättning, last och marktryck i redovisningen.
    """
    if not isinstance(px, (list, tuple)) or len(px) not in (8, 9):
        raise ValueError("px måste innehålla 8 eller 9 värden.")
    if len(px) == 9 and not isinstance(px[2], str):
        return _baddmodul_med_last(px)
    if len(px) == 8:
        namn, typ, bx, by, dz_lista, Ek_lista, gamma_m_lista, t_skikt = px
        form = "yta"
    else:
        namn, typ, form, bx, by, dz_lista, Ek_lista, gamma_m_lista, t_skikt = px
    if not isinstance(namn, str):
        raise ValueError("namn måste vara en text.")
    if not isinstance(typ, str) or typ.upper() not in ("PS", "VS"):
        raise ValueError("typ måste vara 'PS' eller 'VS'.")
    typ = typ.upper()
    if form not in ("yta", "punkt" if typ == "PS" else "linje"):
        raise ValueError("PS tillåter form 'yta' eller 'punkt'; VS tillåter 'yta' eller 'linje'.")
    bx = _positivt_tal("bx", bx)
    by = 1.0 if typ == "VS" else _positivt_tal("by", by)
    t_skikt = _positivt_tal("t_skikt", t_skikt)
    lists = (dz_lista, Ek_lista, gamma_m_lista)
    if any(not isinstance(values, (list, tuple)) or not values for values in lists):
        raise ValueError("Minst ett jordlager måste anges i dz_lista, Ek_lista och gamma_m_lista.")
    if len({len(values) for values in lists}) != 1:
        raise ValueError("dz_lista, Ek_lista och gamma_m_lista måste ha samma längd.")
    for label, values in zip(("Jordlagertjocklek", "E-modul", "Materialfaktor"), lists):
        for value in values:
            _positivt_tal(label, value)

    area = _positivt_tal("Grundarea", bx * by)
    c_unit = "m/kN" if typ == "PS" else "m^2/kN"
    c_total, z_top, count = 0.0, 0.0, 0
    layer_items = []
    for j, (dz, Ek, gamma) in enumerate(zip(*lists), 1):
        Ed = _positivt_tal("Dimensionerande E-modul", Ek / gamma * 1000.0)
        c_layer, n_layer = 0.0, 0
        for z_mid, dz_i in _berakningsskikt(dz, t_skikt, z_top):
            spread = (bx + z_mid) * (by + z_mid) if typ == "PS" else bx + z_mid
            c_i = dz_i / Ed / spread
            c_total += c_i
            c_layer += c_i
            n_layer += 1
        layer_items.extend([
            _post(f"dz_{j}", rf"h_{{{j}}}", dz, "m", f"tjocklek jordlager {j}"),
            _post(f"Ed_{j}", rf"E_{{d,{j}}}", Ed / 1000.0, "MPa", f"dimensionerande E-modul jordlager {j}"),
            _post(f"n_delskikt_{j}", rf"n_{{{j}}}", n_layer, etikett=f"antal delskikt i jordlager {j}"),
            _potenspost(f"C_lager_{j}", rf"C_{{lager,{j}}}", c_layer, c_unit, f"eftergivlighetsbidrag jordlager {j}"),
        ])
        count += n_layer
        z_top += dz
    c_total = _positivt_tal("Eftergivlighet", c_total)
    support = _positivt_tal("Stödets styvhet", 1.0 / c_total)
    k = _positivt_tal("Ytstyvhet", support / (area if typ == "PS" else bx))
    results = {
        "yta": _potenspost("k", "k", k, "kN/m^2/m", "ytstyvhet (bäddmodul)"),
        "punkt": _potenspost("K_punkt", r"K_{punkt}", support, "kN/m", "punktstyvhet"),
        "linje": _potenspost("K_linje", r"K_{linje}", support, "kN/m/m", "linjestyvhet"),
    }
    equations = [
        _ekvation(r"E_{d,j} = E_{k,j}/\gamma_{m,j}", "dimensionerande E-modul i MPa"),
        _ekvation(r"E_{d,j,kPa} = 1000 E_{d,j}", "modul i kN/m^2"),
        _ekvation(r"A = b_x b_y", "grundarea"),
    ]
    if typ == "PS":
        equations.extend([
            _ekvation(r"C_i = \frac{\Delta z_i}{E_{d,i,kPa}(b_x+z_i)(b_y+z_i)}", "eftergivlighet i delskikt, PS"),
            _ekvation(r"C = \sum_i C_i", "total eftergivlighet i m/kN"),
            _ekvation(r"K_{punkt} = \frac{1}{C} = k A", "punktstyvhet i kN/m"),
            _ekvation(r"k = \frac{1}{A C}", "ytstyvhet i kN/m^2/m"),
        ])
    else:
        equations.extend([
            _ekvation(r"b_y = 1\,\mathrm{m}", "beräkningsremsans längd"),
            _ekvation(r"C_i = \frac{\Delta z_i}{E_{d,i,kPa}(b_x+z_i)}", "eftergivlighet i delskikt, VS"),
            _ekvation(r"C = \sum_i C_i", "total eftergivlighet i m^2/kN"),
            _ekvation(r"K_{linje} = \frac{1}{C} = k b_x", "linjestyvhet i kN/m/m"),
            _ekvation(r"k = \frac{1}{b_x C}", "ytstyvhet i kN/m^2/m"),
        ])
    return {
        "metodbeskrivning": {"title": "Metodbeskrivning", "items": [
            {"rubrik": "Lastoberoende styvhet", "text":
             "Styvheten beräknas direkt från grundgeometri och lager med konstanta dimensionerande E-moduler. "
             "Eftergivligheten summeras skiktvis enligt 2:1-metoden med samma mittpunktsindelning som sattning(). "
             "Ingen last eller referenslast används. Faktisk sättning och spänning beräknas inte."},
            {"rubrik": "Beräkningsmodell", "text":
             ("PS: spridning i x- och y-led. Punktstyvheten gäller hela sulan; ytstyvheten är punktstyvheten dividerad med grundarean."
              if typ == "PS" else
              "VS: långsträckt sula med spridning enbart i x-led och b_y = 1 m. Linjestyvheten gäller per meter vägg; ytstyvheten är linjestyvheten dividerad med grundbredden.")},
            {"rubrik": "Förutsättningar", "text":
             "Fast geometri och lastoberoende jordmoduler. Modellen omfattar inte konsolideringstid, krypning eller spänningsberoende styvhet. "
             "z_i avser delskiktets mittdjup under grundytan och E_d,i modulen i det jordlager som delskiktet tillhör."},
        ]},
        "indata": {"title": "Indata", "items": [
            _post("namn", r"\mathrm{namn}", namn, etikett="beräkningsfall"),
            _post("typ", r"\mathrm{typ}", typ, etikett="pelarsula" if typ == "PS" else "väggsula"),
            _post("form", r"\mathrm{form}", {"yta": "Ytstyvhet", "punkt": "Punktstyvhet", "linje": "Linjestyvhet"}[form], etikett="redovisningsform"),
            _post("bx", "b_x", bx, "m", "grundbredd"),
            _post("by", "b_y", by, "m", "grundlängd" if typ == "PS" else "beräkningsremsa, låst till 1 m"),
            _post("dz_lista", "dz", list(dz_lista), "m", "jordlagertjocklekar"),
            _post("Ek_lista", "E_k", list(Ek_lista), "MPa", "karakteristiska E-moduler"),
            _post("gamma_m_lista", r"\gamma_m", list(gamma_m_lista), etikett="materialfaktorer"),
            _post("t_skikt", "t_{skikt}", t_skikt, "m", "beräkningsskiktets tjocklek"),
        ]},
        "delresultat": {"title": "Delresultat", "items": [
            _post("A", "A", area, "m^2", "grundarea" if typ == "PS" else "grundarea för 1 m-remsa"),
            _post("total_djup", "z_{tot}", z_top, "m", "sammanlagd jordlagertjocklek"),
            _post("antal_delskikt", "n_{delskikt}", count, etikett="antal beräknade delskikt"),
            *layer_items,
            _potenspost("C", "C", c_total, c_unit, "total eftergivlighet"),
        ]},
        "slutresultat": {"title": "Slutresultat", "items": [results[form]]},
        "ekvationer": {"title": "Ekvationer", "items": equations},
    }


def _potenspost(namn, latex, value, unit, etikett):
    post = _post(namn, latex, value, unit, etikett, decimals=2)
    post["format"] = "scientific"
    return post


def _baddmodul_med_last(px):
    """Beräkna bäddmodul k = q / s_m och returnera CalcBlock-details.

    px = [namn, typ, F, bx, by, dz_lista, Ek_lista, gamma_m_lista, t_skikt]

    ``typ`` är PS (pelarsula/rektangulär lastyta) eller VS (väggsula/
    långsträckt last). F anges som positiv trycklast i kN för PS och kN/m
    för VS. Mått och lagertjocklekar anges i m, E-moduler i MPa och
    materialfaktorer dimensionslöst. Lagren anges uppifrån och ned.

    För VS används alltid by = 1 m oavsett inmatat by. F avser linjelasten
    och F_remsa = F * by avser kraften på beräkningsremsan. Sättningen
    beräknas med sattning() i VS-läge, utan lastspridning i y-led.

    Slutresultat: s i mm och k i kN/m^2/m. Oavrundad sättning används
    i beräkningen. Funktionen lägger inte till egentyngd eller lastfaktorer.
    """
    if not isinstance(px, (list, tuple)) or len(px) != 9:
        raise ValueError("px måste innehålla 9 värden.")
    namn, typ, F, bx, by, dz_lista, Ek_lista, gamma_m_lista, t_skikt = px
    if not isinstance(namn, str):
        raise ValueError("namn måste vara en text.")
    if not isinstance(typ, str) or typ.upper() not in ("PS", "VS"):
        raise ValueError("typ måste vara 'PS' eller 'VS'.")
    typ = typ.upper()
    F = _positivt_tal("F", F)
    bx = _positivt_tal("bx", bx)
    by = 1.0 if typ == "VS" else _positivt_tal("by", by)
    t_skikt = _positivt_tal("t_skikt", t_skikt)
    lists = (dz_lista, Ek_lista, gamma_m_lista)
    if any(not isinstance(values, (list, tuple)) or not values for values in lists):
        raise ValueError("Minst ett jordlager måste anges i dz_lista, Ek_lista och gamma_m_lista.")
    if len({len(values) for values in lists}) != 1:
        raise ValueError("dz_lista, Ek_lista och gamma_m_lista måste ha samma längd.")
    for label, values in zip(("Jordlagertjocklek", "E-modul", "Materialfaktor"), lists):
        for value in values:
            _positivt_tal(label, value)

    A = _positivt_tal("Grundarea", bx * by)
    F_area = F * by if typ == "VS" else F
    q = _positivt_tal("Marktryck", F_area / A)
    details = sattning([typ, t_skikt, dz_lista, Ek_lista, gamma_m_lista, F, bx, by])
    s_post = next(post for post in details["slutresultat"]["items"] if post["namn"] == "s")
    s_m = _positivt_tal("Sättning i meter", s_post["value"] / 1000.0)
    k = _positivt_tal("Bäddmodul", q / s_m)

    base_inputs = {post["namn"]: post for post in details["indata"]["items"]}
    details["indata"]["items"] = [
        _post("namn", r"\mathrm{namn}", namn, etikett="beräkningsfall"),
        base_inputs["typ"],
        _post("F", "F", F, "kN/m" if typ == "VS" else "kN", "linjelast" if typ == "VS" else "resultantlast"),
        _post("bx", "b_x", bx, "m", "grundbredd"),
        _post("by", "b_y", by, "m", "beräkningsremsa, låst till 1 m" if typ == "VS" else "grundlängd"),
        base_inputs["dz_lista"], base_inputs["Ek_lista"], base_inputs["gamma_m_lista"],
        base_inputs["t_skikt"],
    ]
    extra_results = [_post("A", "A", A, "m^2", "grundarea för 1 m-remsa" if typ == "VS" else "grundarea")]
    if typ == "VS":
        extra_results.append(_post("F_remsa", "F_{remsa}", F_area, "kN", "kraft på 1 m-remsa"))
    extra_results.extend([
        _post("q", "q", q, "kN/m^2", "medeltryck under grundytan"),
        _post("s_m", "s_m", s_m, "m", "total sättning i meter", decimals=6),
    ])
    details["delresultat"]["items"] = extra_results + details["delresultat"]["items"]
    k_post = _post("k", "k", k, "kN/m^2/m", "bäddmodul", decimals=2)
    k_post["format"] = "scientific"
    details["slutresultat"]["items"] = [s_post, k_post]
    details["metodbeskrivning"]["items"].append({
        "rubrik": "Bäddmodul",
        "text": (
            "Bäddmodulen beräknas som medeltryck dividerat med oavrundad sättning i meter. "
            "Lasten anges färdig; ingen egentyngd eller ytterligare lastfaktor läggs till. "
            + ("För VS används en 1 m-remsa: b_y = 1 m, A = b_x · b_y och remsans kraft är linjelasten gånger b_y. "
               "Sättningen beräknas för långsträckt last med lastspridning endast i x-led."
               if typ == "VS" else "För PS används hela den rektangulära grundytan A = b_x · b_y.")
        ),
    })

    # Sättning använder samma måttbeteckningar och enhetsomvandlingar.
    equations = list(details["ekvationer"]["items"])
    equations.append(_ekvation(r"A = b_x b_y", "grundarea"))
    if typ == "VS":
        equations.extend([
            _ekvation(r"b_y = 1\,\mathrm{m}", "beräkningsremsans längd"),
            _ekvation(r"F_{remsa} = F b_y", "linjelast omräknad till kraft på remsan"),
            _ekvation(r"q = \frac{F_{remsa}}{A} = \frac{F}{b_x}", "marktryck för VS"),
        ])
    else:
        equations.append(_ekvation(r"q = \frac{F}{A}", "marktryck för PS"))
    equations.append(_ekvation(r"k = \frac{q}{s_m}", "bäddmodul i kN/m^2/m"))
    details["ekvationer"]["items"] = equations
    return details


_SOIL_FIELD = deepcopy(next(field for field in sattning.panel_schema["fields"] if field["name"] == "jordlager"))
_SOIL_FIELD["label"] = "Jordlager – uppifrån och ned"
_SOIL_FIELD["add_label"] = "+ Lägg till jordlager"
_SOIL_FIELD["default_rows"] = [
    {"dz": 0.8, "Ek": 45.0, "gamma_m": 1.3},
    {"dz": 1.5, "Ek": 30.0, "gamma_m": 1.3},
]

baddmodul.panel_schema = {
    "title": "Bäddmodul",
    "px": ["namn", "typ", "form", "bx", "by", "dz_lista", "Ek_lista", "gamma_m_lista", "t_skikt"],
    "preserve_state_fields": ["F"],
    "groups": {"Beräkningsinställningar": {"collapsed": True}},
    "sections": [
        {"fields": ["namn", "typ"], "columns": 3},
        {"title": "Grundmått och styvhet", "fields": ["bx", "by", "form"], "columns": 3},
        {"fields": ["jordlager"]},
        {"title": "Beräkningsinställningar", "fields": ["t_skikt"], "columns": 3,
         "collapsible": True, "collapsed": True},
    ],
    "fields": [
        {"name": "namn", "type": "text", "label": "Beräkningsfall", "symbol": "", "default": "Hus1"},
        {"name": "typ", "type": "choice", "label": "Beräkningsmodell", "symbol": "", "default": "PS", "span": 2, "options": [
            {"label": "PS – pelarsula/rektangulär lastyta", "value": "PS"},
            {"label": "VS – väggsula/långsträckt last", "value": "VS"},
        ]},
        {"name": "form", "type": "choice", "label": "Redovisningsform", "symbol": "", "default": "yta", "span": 3,
         "options": [
             {"label": "Ytstyvhet [kN/m²/m]", "value": "yta"},
             {"label": "Punktstyvhet [kN/m]", "value": "punkt"},
         ],
         "options_if": {"field": "typ", "equals": "VS", "options": [
             {"label": "Ytstyvhet [kN/m²/m]", "value": "yta"},
             {"label": "Linjestyvhet [kN/m/m]", "value": "linje"},
         ]}},
        {"name": "bx", "type": "float", "label": "Grundbredd", "symbol": "<i>b</i><sub>x</sub>", "unit": "m", "default": 3.8},
        {"name": "by", "type": "float", "label": "Grundlängd", "symbol": "<i>b</i><sub>y</sub>", "unit": "m", "default": 2.7,
         "fixed_if": {"field": "typ", "equals": "VS", "value": 1.0},
         "presentation_if": {"field": "typ", "equals": "VS", "label": "Beräkningsremsa (låst)"}},
        _SOIL_FIELD,
        {"name": "t_skikt", "type": "float", "label": "Beräkningsskiktets tjocklek", "symbol": "<i>t</i><sub>skikt</sub>",
         "unit": "m", "default": 0.1, "group": "Beräkningsinställningar"},
    ],
}
