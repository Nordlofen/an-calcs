"""Bäddmodul från skiktvis sättning med 2:1-metoden."""

from copy import deepcopy
import math

from .sattning import sattning, _ekvation, _post


def _positivt_tal(namn, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{namn} måste vara ett ändligt tal > 0.")
    return value


def baddmodul(px):
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
    details["slutresultat"]["items"] = [s_post, _post("k", "k", k, "kN/m^2/m", "bäddmodul", decimals=3)]
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

    # Behåll sättningsmodellens ekvationer, med panelens måttbeteckningar
    # och uttryckliga enhetsomvandlingar mellan MPa/kPa och m/mm.
    equations = []
    inactive = "PS" if typ == "VS" else "VS"
    for equation in details["ekvationer"]["items"]:
        if equation["etikett"] == f"spänningsökning för {inactive}":
            continue
        latex = equation["latex"].replace("b_1", "b_x").replace("b_2", "b_y")
        if equation["etikett"] == "töjning i delskikt":
            latex = r"\epsilon_i = \frac{\Delta\sigma_i}{E_{d,kPa}}"
        elif equation["etikett"] == "total sättning":
            latex = r"s_m = \sum s_i"
        equations.append(_ekvation(latex, equation["etikett"]))
        if equation["etikett"] == "dimensionerande E-modul":
            equations.append(_ekvation(r"E_{d,kPa} = 1000 E_d", "E-modul från MPa till kPa"))
    equations.append(_ekvation(r"s = 1000 s_m", "sättning från meter till millimeter"))
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
_SOIL_FIELD["default_rows"] = [
    {"dz": 0.8, "Ek": 45.0, "gamma_m": 1.3},
    {"dz": 1.5, "Ek": 30.0, "gamma_m": 1.3},
]

baddmodul.panel_schema = {
    "title": "Bäddmodul",
    "px": ["namn", "typ", "F", "bx", "by", "dz_lista", "Ek_lista", "gamma_m_lista", "t_skikt"],
    "groups": {"Beräkningsinställningar": {"collapsed": True}},
    "fields": [
        {"name": "namn", "type": "text", "label": "Beräkningsfall", "symbol": "", "default": "Hus1"},
        {"name": "typ", "type": "choice", "label": "Lasttyp", "symbol": "", "default": "PS", "options": [
            {"label": "PS – pelarsula/rektangulär lastyta", "value": "PS"},
            {"label": "VS – väggsula/långsträckt last", "value": "VS"},
        ]},
        {"name": "F", "type": "float", "label": "Resultantlast", "symbol": "F", "unit": "kN", "default": 1163.0,
         "presentation_if": {"field": "typ", "equals": "VS", "label": "Linjelast", "unit": "kN/m"}},
        {"name": "bx", "type": "float", "label": "Grundbredd", "symbol": "<i>b</i><sub>x</sub>", "unit": "m", "default": 3.8},
        {"name": "by", "type": "float", "label": "Grundlängd", "symbol": "<i>b</i><sub>y</sub>", "unit": "m", "default": 2.7,
         "fixed_if": {"field": "typ", "equals": "VS", "value": 1.0},
         "presentation_if": {"field": "typ", "equals": "VS", "label": "Beräkningsremsa (låst)"}},
        _SOIL_FIELD,
        {"name": "t_skikt", "type": "float", "label": "Beräkningsskiktets tjocklek", "symbol": "<i>t</i><sub>skikt</sub>",
         "unit": "m", "default": 0.1, "group": "Beräkningsinställningar"},
    ],
}
