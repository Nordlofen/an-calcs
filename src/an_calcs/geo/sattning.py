"""Sattningsberakning med 2:1-metoden."""


def _post(namn, latex, value, unit="", etikett="", decimals=None):
    """Skapar en standardiserad datapost for presentations- och berakningsdata."""
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


def _sattningssteg(typ, z_mid, dz_i, Ek, gamma_m, F, b1, b2):
    Ed_MPa = Ek / gamma_m
    Ed_kPa = Ed_MPa * 1000.0

    if typ == "PS":
        delta_sigma_kPa = F / ((b1 + z_mid) * (b2 + z_mid))
    else:
        delta_sigma_kPa = F / (b1 + z_mid)

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
    """
    Beraknar sattning med 2:1-metoden och skiktvis summering.

    Parameterformat:
        px = [typ, t_skikt, dz_lista, Ek_lista, gamma_m_lista, F, b1, b2]

    Enhetskonvention:
        - langder i m
        - laster i kN for PS och kN/m for VS
        - E-moduler i MPa
        - spanningsokning i kPa
        - sattning i mm

    Parametrar:
        typ : str
            "PS" for pelarsula/punktlast/rektangular sula eller "VS" for
            vaggsula/langstrackt last.

        t_skikt : float
            Diskretiseringstjocklek [m].

        dz_lista : list[float]
            Jordlagrens tjocklekar [m].

        Ek_lista : list[float]
            Karakteristisk E-modul per jordlager [MPa].

        gamma_m_lista : list[float]
            Materialfaktor per jordlager [-].

        F : float
            Last. For PS: kraft [kN]. For VS: linjelast [kN/m].

        b1 : float
            Grundmatt [m]. For PS: ena sidmattet. For VS: bredd.

        b2 : float | None
            For PS: andra sidmattet [m]. For VS: anvands ej.

    Returvarde:
        dict
            Dictionary med nycklarna ``metodbeskrivning``, ``indata``,
            ``delresultat``, ``slutresultat`` och ``ekvationer``.
    """
    if px is None:
        raise ValueError("px måste anges.")
    if len(px) != 8:
        raise ValueError("px måste innehålla 8 värden.")

    typ, t_skikt, dz_lista, Ek_lista, gamma_m_lista, F, b1, b2 = px
    typ = typ.upper()

    if typ not in ("PS", "VS"):
        raise ValueError("typ måste vara 'PS' eller 'VS'.")

    _krav_lista_samma_langd(dz_lista, Ek_lista, gamma_m_lista)
    _krav_storre_an_noll("t_skikt", t_skikt)
    _krav_storre_an_noll("F", F)
    _krav_storre_an_noll("b1", b1)

    if typ == "PS":
        if b2 is None:
            raise ValueError("För PS måste b2 anges och vara > 0.")
        _krav_storre_an_noll("b2", b2)

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

        n_full = int(dz / t_skikt)
        rest = dz - n_full * t_skikt

        for i in range(n_full):
            dz_i = t_skikt
            z_mid = z_top + (i + 0.5) * t_skikt
            steg = _sattningssteg(typ, z_mid, dz_i, Ek, gamma_m, F, b1, b2)
            total_sattning_m += steg["s_i_m"]
            layer_sattning_m += steg["s_i_m"]
            layer_delta_sigma_dz += steg["delta_sigma_kPa"] * dz_i
            layer_antal_delskikt += 1
            delskikt.append((layer_idx, z_mid, dz_i, Ek, gamma_m, steg))

        if rest > 1e-12:
            dz_i = rest
            z_mid = z_top + n_full * t_skikt + 0.5 * rest
            steg = _sattningssteg(typ, z_mid, dz_i, Ek, gamma_m, F, b1, b2)
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
    b2_value = b2 if typ == "PS" else None

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
                    "rubrik": "Lastmodell",
                    "text": (
                        "PS används för pelarsula, punktlast eller rektangulär "
                        "lastyta. VS används för väggsula eller långsträckt last."
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
                _post("t_skikt", r"t_{skikt}", t_skikt, "m", "diskretiseringstjocklek"),
                _post("dz_lista", r"dz", list(dz_lista), "m", "jordlagertjocklekar"),
                _post("Ek_lista", r"E_k", list(Ek_lista), "MPa", "karakteristiska E-moduler"),
                _post("gamma_m_lista", r"\gamma_m", list(gamma_m_lista), "", "materialfaktorer"),
                _post("F", "F", F, last_unit, "last"),
                _post("b1", r"b_1", b1, "m", "grundmått 1"),
                _post("b2", r"b_2", b2_value, "m", "grundmått 2 för PS"),
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
                _ekvation(r"\Delta\sigma_i = \frac{F}{(b_1 + z_i)(b_2 + z_i)}", "spänningsökning för PS"),
                _ekvation(r"\Delta\sigma_i = \frac{F}{b_1 + z_i}", "spänningsökning för VS"),
                _ekvation(r"\epsilon_i = \frac{\Delta\sigma_i}{E_d}", "töjning i delskikt"),
                _ekvation(r"s_i = \epsilon_i dz_i", "sättningsbidrag från delskikt"),
                _ekvation(r"s = \sum s_i", "total sättning"),
            ],
        },
    }


sattning.panel_schema = {
    "title": "Sättning",
    "px": ["typ", "t_skikt", "dz_lista", "Ek_lista", "gamma_m_lista", "F", "b1", "b2"],
    "fields": [
        {
            "name": "typ",
            "type": "choice",
            "label": "Lasttyp",
            "symbol": "typ",
            "default": "PS",
            "options": [
                {"label": "PS - pelarsula/punktlast", "value": "PS"},
                {"label": "VS - väggsula/långsträckt last", "value": "VS"},
            ],
        },
        {"name": "t_skikt", "type": "float", "label": "Diskretiseringstjocklek", "symbol": "<i>t</i><sub>skikt</sub>", "unit": "m", "default": 0.1},
        {
            "name": "jordlager",
            "type": "table",
            "label": "Jordlager",
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
        {"name": "F", "type": "float", "label": "Last", "symbol": "F", "unit": "kN eller kN/m", "default": 500.0},
        {"name": "b1", "type": "float", "label": "Grundmått 1", "symbol": "<i>b</i><sub>1</sub>", "unit": "m", "default": 2.0},
        {"name": "b2", "type": "float", "label": "Grundmått 2", "symbol": "<i>b</i><sub>2</sub>", "unit": "m", "default": 3.0},
    ],
}
