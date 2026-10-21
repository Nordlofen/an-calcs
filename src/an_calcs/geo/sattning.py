"""Sättningsberäkning med 2:1-metoden och skiktvis summering."""


def _post(namn, latex, value, unit="", etikett="", decimals=None):
    """Skapar en standardiserad datapost för presentations- och beräkningsdata."""
    post = {
        "namn": namn,
        "latex": latex,
        "value": value,
        "unit": unit,
        "etikett": etikett,
    }
    if decimals is not None:
        post["decimals"] = decimals
    return post


def _ekvation(latex, etikett):
    """Skapar en standardiserad ekvationspost."""
    return {"latex": latex, "etikett": etikett}


def _krav_storre_an_noll(namn, value):
    if value <= 0:
        raise ValueError(f"{namn} måste vara > 0.")


def _krav_lista_samma_langd(*listor):
    langder = {len(lista) for lista in listor}
    if len(langder) != 1:
        raise ValueError("dz_lista, Ek_lista och gamma_m_lista måste ha samma längd.")


def _berakningsskikt(dz, t_skikt, z_top):
    """Ge mittdjup och tjocklek för samma delskikt i sättning och styvhet."""
    n_full = int(dz / t_skikt)
    for i in range(n_full):
        yield z_top + (i + 0.5) * t_skikt, t_skikt
    rest = dz - n_full * t_skikt
    if rest > 1e-12:
        yield z_top + n_full * t_skikt + 0.5 * rest, rest


def _sattningssteg(typ, z_mid, dz_i, Ek, gamma_m, F, bx, by):
    Ed_MPa = Ek / gamma_m
    Ed_kPa = Ed_MPa * 1000.0

    if typ == "PS":
        delta_sigma_kPa = F / ((bx + z_mid) * (by + z_mid))
    else:
        delta_sigma_kPa = F / (bx + z_mid)

    epsilon = delta_sigma_kPa / Ed_kPa
    s_i_m = epsilon * dz_i

    return {
        "delta_sigma_kPa": delta_sigma_kPa,
        "epsilon": epsilon,
        "s_i_m": s_i_m,
        "s_i_mm": s_i_m * 1000.0,
        "Ed_MPa": Ed_MPa,
        "Ed_kPa": Ed_kPa,
    }


def sattning(px):
    """Beräkna sättning med 2:1-metoden och returnera CalcBlock-details.

    px = [typ, t_skikt, dz_lista, Ek_lista, gamma_m_lista, F, bx, by]

    ``typ`` är PS (pelarsula/rektangulär lastyta) eller VS (väggsula/
    långsträckt last). F anges i kN för PS och kN/m för VS. Grundmått,
    jordlagertjocklekar och beräkningsskiktets tjocklek anges i m,
    karakteristiska E-moduler i MPa och materialfaktorer dimensionslöst.
    Lagren anges uppifrån och ned. Ed = Ek / gamma_m.

    För VS används en 1 m-remsa, by = 1 m, och spridning enbart i x-led.
    Inmatat by påverkar inte VS-beräkningen; äldre anrop med None fungerar.
    Spänningsökningar redovisas i kPa och total sättning i mm med två
    decimaler. Funktionen lägger inte till egentyngd eller lastfaktorer.

    Befintliga åttavärdeslistor har samma ordning och ger samma sättning.
    Nycklarna b1/b2 i details och sparade panelfall behålls för kompatibilitet;
    deras synliga beteckningar är b_x/b_y.
    """
    if px is None:
        raise ValueError("px måste anges.")
    if len(px) != 8:
        raise ValueError("px måste innehålla 8 värden.")

    typ, t_skikt, dz_lista, Ek_lista, gamma_m_lista, F, bx, by = px
    typ = typ.upper()

    if typ not in ("PS", "VS"):
        raise ValueError("typ måste vara 'PS' eller 'VS'.")

    _krav_lista_samma_langd(dz_lista, Ek_lista, gamma_m_lista)
    _krav_storre_an_noll("t_skikt", t_skikt)
    _krav_storre_an_noll("F", F)
    _krav_storre_an_noll("bx", bx)

    if typ == "PS":
        if by is None:
            raise ValueError("För PS måste by anges och vara > 0.")
        _krav_storre_an_noll("by", by)
    else:
        by = 1.0

    for dz in dz_lista:
        _krav_storre_an_noll("jordlagertjocklek", dz)
    for Ek in Ek_lista:
        _krav_storre_an_noll("E-modul", Ek)
    for gamma_m in gamma_m_lista:
        _krav_storre_an_noll("gamma_m", gamma_m)

    delskikt = []
    jordlager_summering = []
    total_sattning_m = 0.0
    z_top = 0.0

    for layer_idx, (dz, Ek, gamma_m) in enumerate(zip(dz_lista, Ek_lista, gamma_m_lista), start=1):
        Ed_MPa = Ek / gamma_m
        layer_sattning_m = 0.0
        layer_delta_sigma_dz = 0.0
        layer_antal_delskikt = 0

        for z_mid, dz_i in _berakningsskikt(dz, t_skikt, z_top):
            steg = _sattningssteg(typ, z_mid, dz_i, Ek, gamma_m, F, bx, by)
            total_sattning_m += steg["s_i_m"]
            layer_sattning_m += steg["s_i_m"]
            layer_delta_sigma_dz += steg["delta_sigma_kPa"] * dz_i
            layer_antal_delskikt += 1
            delskikt.append((layer_idx, z_mid, dz_i, Ek, gamma_m, steg))

        jordlager_summering.append(
            {
                "lager": layer_idx,
                "dz": dz,
                "Ed_MPa": Ed_MPa,
                "antal_delskikt": layer_antal_delskikt,
                "delta_sigma_medel_kPa": layer_delta_sigma_dz / dz,
                "s_lager_mm": layer_sattning_m * 1000.0,
            }
        )
        z_top += dz

    total_djup = sum(dz_lista)
    total_sattning_mm = total_sattning_m * 1000.0
    lastbeskrivning = "punktlast/rektangulär lastyta" if typ == "PS" else "linjelast/långsträckt last"
    last_unit = "kN" if typ == "PS" else "kN/m"

    delresultat_items = [
        _post("total_djup", r"z_{tot}", total_djup, "m", "sammanlagd jordlagertjocklek"),
        _post("antal_delskikt", r"n_{delskikt}", len(delskikt), "", "antal beräknade delskikt"),
    ]
    for lager in jordlager_summering:
        idx = lager["lager"]
        delresultat_items.extend(
            [
                _post(f"dz_{idx}", rf"dz_{{{idx}}}", lager["dz"], "m", f"tjocklek jordlager {idx}"),
                _post(f"Ed_{idx}", rf"E_{{d,{idx}}}", lager["Ed_MPa"], "MPa", f"dimensionerande E-modul jordlager {idx}"),
                _post(f"n_delskikt_{idx}", rf"n_{{i,{idx}}}", lager["antal_delskikt"], "", f"antal delskikt i jordlager {idx}"),
                _post(
                    f"delta_sigma_medel_{idx}",
                    rf"\overline{{\Delta\sigma}}_{{{idx}}}",
                    lager["delta_sigma_medel_kPa"],
                    "kPa",
                    f"medelspänningsökning i jordlager {idx}",
                ),
                _post(f"s_lager_{idx}", rf"s_{{{idx}}}", lager["s_lager_mm"], "mm", f"sättningsbidrag från jordlager {idx}", decimals=2),
            ]
        )

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Funktionen beräknar sättning med 2:1-metoden genom att "
                        "dela jordprofilen i beräkningsskikt, beräkna "
                        "spänningsökning i varje skikt och summera elastiska "
                        "sättningsbidrag."
                    ),
                },
                {
                    "rubrik": "Beräkningsmodell",
                    "text": (
                        "PS används för pelarsula, punktlast eller rektangulär "
                        "lastyta, med spridning i x- och y-led. VS används för väggsula eller "
                        "långsträckt last, med spridning enbart i x-led och en 1 m-remsa (b_y = 1 m)."
                    ),
                },
                {
                    "rubrik": "Begränsning",
                    "text": (
                        "Beräkningen är en förenklad bruksgränsmodell och tar inte "
                        "hänsyn till konsolideringstid, krypning eller "
                        "spänningsberoende styvhet."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("typ", r"\mathrm{typ}", typ, "", lastbeskrivning),
                _post("F", "F", F, last_unit, "resultantlast" if typ == "PS" else "linjelast"),
                # Behåll äldre postnycklar; endast visningsbeteckningarna ändras.
                _post("b1", r"b_x", bx, "m", "grundbredd"),
                _post("b2", r"b_y", by, "m", "grundlängd" if typ == "PS" else "beräkningsremsa, låst till 1 m"),
                _post("dz_lista", r"dz", list(dz_lista), "m", "jordlagertjocklekar"),
                _post("Ek_lista", r"E_k", list(Ek_lista), "MPa", "karakteristiska E-moduler"),
                _post("gamma_m_lista", r"\gamma_m", list(gamma_m_lista), "", "materialfaktorer"),
                _post("t_skikt", r"t_{skikt}", t_skikt, "m", "beräkningsskiktets tjocklek"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": delresultat_items,
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("s", "s", total_sattning_mm, "mm", "total sättning", decimals=2),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"E_d = E_k / \gamma_m", "dimensionerande E-modul"),
                _ekvation(r"E_{d,kPa} = 1000 E_d", "E-modul från MPa till kPa"),
                _ekvation(
                    r"\Delta\sigma_i = \frac{F}{(b_x + z_i)(b_y + z_i)}" if typ == "PS" else
                    r"\Delta\sigma_i = \frac{F}{b_x + z_i}",
                    f"spänningsökning för {typ}",
                ),
                _ekvation(r"\epsilon_i = \frac{\Delta\sigma_i}{E_{d,kPa}}", "töjning i delskikt"),
                _ekvation(r"s_i = \epsilon_i dz_i", "sättningsbidrag från delskikt"),
                _ekvation(r"s_m = \sum s_i", "total sättning"),
                _ekvation(r"s = 1000 s_m", "sättning från meter till millimeter"),
            ],
        },
    }


sattning.panel_schema = {
    "title": "Sättning",
    "px": ["typ", "t_skikt", "dz_lista", "Ek_lista", "gamma_m_lista", "F", "b1", "b2"],
    "groups": {"Beräkningsinställningar": {"collapsed": True}},
    "sections": [
        {"fields": ["typ"], "columns": 1},
        {"title": "Last och grundmått", "fields": ["F", "b1", "b2"], "columns": 3},
        {"fields": ["jordlager"]},
        {"title": "Beräkningsinställningar", "fields": ["t_skikt"], "columns": 3,
         "collapsible": True, "collapsed": True},
    ],
    "fields": [
        {
            "name": "typ",
            "type": "choice",
            "label": "Beräkningsmodell",
            "symbol": "",
            "default": "PS",
            "options": [
                {"label": "PS – pelarsula/rektangulär lastyta", "value": "PS"},
                {"label": "VS – väggsula/långsträckt last", "value": "VS"},
            ],
        },
        {"name": "t_skikt", "type": "float", "label": "Beräkningsskiktets tjocklek", "symbol": "<i>t</i><sub>skikt</sub>", "unit": "m", "default": 0.1, "group": "Beräkningsinställningar"},
        {
            "name": "jordlager",
            "type": "table",
            "label": "Jordlager – uppifrån och ned",
            "add_label": "+ Lägg till jordlager",
            "outputs": ["dz_lista", "Ek_lista", "gamma_m_lista"],
            "columns": [
                {"name": "dz", "output": "dz_lista", "type": "float", "label": "Tjocklek", "symbol": "dz", "unit": "m", "default": 1.0},
                {"name": "Ek", "output": "Ek_lista", "type": "float", "label": "E-modul", "symbol": "<i>E</i><sub>k</sub>", "unit": "MPa", "default": 10.0},
                {"name": "gamma_m", "output": "gamma_m_lista", "type": "float", "label": "Materialfaktor", "symbol": "γ<sub>m</sub>", "unit": "", "default": 1.0},
            ],
            "default_rows": [
                {"dz": 1.0, "Ek": 10.0, "gamma_m": 1.0},
                {"dz": 1.0, "Ek": 15.0, "gamma_m": 1.0},
            ],
        },
        {"name": "F", "type": "float", "label": "Resultantlast", "symbol": "F", "unit": "kN", "default": 500.0,
         "presentation_if": {"field": "typ", "equals": "VS", "label": "Linjelast", "unit": "kN/m"}},
        # Lagringsnycklarna b1/b2 gör gamla panelfall direkt läsbara.
        {"name": "b1", "type": "float", "label": "Grundbredd", "symbol": "<i>b</i><sub>x</sub>", "unit": "m", "default": 2.0},
        {"name": "b2", "type": "float", "label": "Grundlängd", "symbol": "<i>b</i><sub>y</sub>", "unit": "m", "default": 3.0,
         "fixed_if": {"field": "typ", "equals": "VS", "value": 1.0},
         "presentation_if": {"field": "typ", "equals": "VS", "label": "Beräkningsremsa (låst)"}},
    ],
}
