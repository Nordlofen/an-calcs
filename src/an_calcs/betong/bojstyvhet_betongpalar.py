"""Nominell böjstyvhet för kvadratiska betongpålar med fyra hörnjärn."""

import math


_PX_NAMN = (
    "b", "c_nom", "phi_b", "phi_h", "l_0", "N_d",
    "f_ck", "f_cd", "E_cd", "E_s", "phi_eff",
)
_RHO_MIN = 0.002


def _post(namn, latex, value, unit="", etikett="", decimals=None):
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
    return {"latex": latex, "etikett": etikett}


def _tolka_px(px):
    if not isinstance(px, (list, tuple)):
        raise ValueError("px för bojstyvhet_betongpalar måste vara en lista eller tuple.")
    if len(px) != len(_PX_NAMN):
        raise ValueError("px för bojstyvhet_betongpalar måste innehålla exakt 11 värden.")

    values = []
    for namn, value in zip(_PX_NAMN, px):
        if isinstance(value, bool):
            raise ValueError(f"{namn} måste vara ett ändligt tal, inte ett booleskt värde.")
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{namn} måste vara ett ändligt tal.") from exc
        if not math.isfinite(value):
            raise ValueError(f"{namn} måste vara ett ändligt tal.")
        if namn in {"c_nom", "N_d", "phi_eff"}:
            if value < 0:
                forklaring = " N_d anges positiv i tryck." if namn == "N_d" else ""
                raise ValueError(f"{namn} måste vara >= 0." + forklaring)
        elif value <= 0:
            raise ValueError(f"{namn} måste vara > 0.")
        values.append(value)
    return values


def bojstyvhet_betongpalar(px):
    """
    Beräknar nominell böjstyvhet EI för en kvadratisk betongpåle.

    Pålen har exakt fyra likadana huvudarmeringsjärn, symmetriskt placerade
    i hörnen innanför byglarna. Böjning avser en huvudaxel parallell med en
    tvärsnittssida; styvheten är lika kring de båda huvudaxlarna.

    Parameterformat (lista eller tuple):
        px = [b, c_nom, phi_b, phi_h, l_0, N_d,
              f_ck, f_cd, E_cd, E_s, phi_eff]

    Parametrar:
        b : float
            Pålsida [mm].
        c_nom : float
            Nominellt täckskikt till bygelns utsida [mm], >= 0.
        phi_b : float
            Bygeldiameter [mm].
        phi_h : float
            Diameter för vart och ett av de fyra huvudarmeringsjärnen [mm].
        l_0 : float
            Knäckningslängd [m]. Omvandlas till mm i slankhetstalet.
        N_d : float
            Dimensionerande normalkraft [kN], positiv i tryck, >= 0.
            Noll tillåts som gränsfall och ger EI_c = 0 enligt modellen.
        f_ck : float
            Karakteristisk cylindertryckhållfasthet [MPa].
        f_cd : float
            Dimensionerande tryckhållfasthet för betong [MPa].
        E_cd : float
            Dimensioneringsvärde för betongens elasticitetsmodul [MPa].
        E_s : float
            Dimensioneringsvärde för armeringens elasticitetsmodul [MPa].
        phi_eff : float
            Effektivt kryptal [-], >= 0.

    Returvärde:
        Standardiserad details-dictionary för an_print.CalcBlock och Panel.
        EI_c, EI_s och EI redovisas i kN*m^2. Inga värden avrundas i
        beräkningen; eventuell avrundning görs av presentationslagret.

    Metod:
        Underlagets avsnitt 5.6, "Nominell böjstyvhet påle", ekv. (5.22)-
        (5.27) och (5.29), s. 11:
        https://kth.diva-portal.org/smash/get/diva2%3A1597682/FULLTEXT01.pdf
        Ac och Ic avser hela betongtvärsnittets geometri utan avdrag för
        armering. Materialvärden och effektivt kryptal anges direkt.
        Koefficienterna förutsätter rho = As/Ac >= 0.002.

    Exempel:
        px = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2]
        details = bojstyvhet_betongpalar(px)
    """
    b, c_nom, phi_b, phi_h, l_0, N_d, f_ck, f_cd, E_cd, E_s, phi_eff = _tolka_px(px)

    n_phi = 4
    l_phi = b / 2.0 - c_nom - phi_b - phi_h / 2.0
    if l_phi <= 0:
        raise ValueError("Geometrin måste ge en positiv hävarm l_phi för hörnarmeringen.")
    if 2.0 * l_phi < phi_h:
        raise ValueError("Huvudarmeringsjärnen överlappar: 2*l_phi måste vara >= phi_h.")

    A_c = b**2
    I_c = b**4 / 12.0
    A_s = n_phi * math.pi * phi_h**2 / 4.0
    rho = A_s / A_c
    # Accepterar avrundningsfel vid den exakta gränsen, inte lägre armeringshalt.
    if rho < _RHO_MIN and not math.isclose(rho, _RHO_MIN, rel_tol=1e-12):
        raise ValueError(
            f"Armeringsinnehållet rho = A_s/A_c = {rho:.8g} är för lågt. "
            "Metoden kräver rho >= 0,002."
        )

    I_phi = math.pi * phi_h**4 / 64.0
    I_s = n_phi * I_phi + A_s * l_phi**2
    i = b / math.sqrt(12.0)
    l_0_mm = l_0 * 1000.0
    N_d_N = N_d * 1000.0
    lambda_ = l_0_mm / i
    n = N_d_N / (A_c * f_cd)
    k_1 = math.sqrt(f_ck / 20.0)
    k_2_obegransad = n * lambda_ / 170.0
    k_2 = min(k_2_obegransad, 0.20)
    K_s = 1.0
    K_c = k_1 * k_2 / (1.0 + phi_eff)

    # MPa * mm^4 = N*mm^2; 1 kN*m^2 = 10^9 N*mm^2.
    EI_c = K_c * E_cd * I_c / 1e9
    EI_s = K_s * E_s * I_s / 1e9
    EI = EI_c + EI_s

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Nominell böjstyvhet för en kvadratisk betongpåle med fyra "
                        "likadana huvudarmeringsjärn, symmetriskt placerade i hörnen. "
                        "Betongens och armeringens bidrag summeras. Böjningen avser "
                        "en huvudaxel parallell med en tvärsnittssida."
                    ),
                },
                {
                    "rubrik": "Källa",
                    "text": (
                        "Underlagets avsnitt 5.6, Nominell böjstyvhet påle, s. 11. "
                        "Ekvationerna (5.22)-(5.27) och (5.29). Underlaget hänvisar "
                        "till eurokoderna (SIS, 2008); ekvationsnumren avser underlaget."
                    ),
                },
                {
                    "rubrik": "Förutsättningar",
                    "text": (
                        "Armeringsinnehållet As/Ac ska vara minst 0,002. Ac och Ic "
                        "beräknas utan avdrag för armeringen. Täckskiktet mäts till "
                        "bygelns utsida. Materialvärden och effektivt kryptal anges "
                        "direkt. Normalkraften anges positiv i tryck."
                    ),
                },
                {
                    "rubrik": "Enheter",
                    "text": (
                        "Tvärsnittsmått anges i mm, knäckningslängd i m, normalkraft "
                        "i kN och materialvärden i MPa. Beräkningen använder N och mm. "
                        "Böjstyvheten omvandlas från N*mm² till kN*m² genom division med 10⁹."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("b", "b", b, "mm", "pålsida"),
                _post("c_nom", r"c_{nom}", c_nom, "mm", "täckskikt till bygelns utsida"),
                _post("phi_b", r"\phi_b", phi_b, "mm", "bygeldiameter"),
                _post("phi_h", r"\phi_h", phi_h, "mm", "huvudarmeringsdiameter"),
                _post("n_phi", r"n_\phi", n_phi, "", "antal hörnjärn, fast förutsättning", decimals=0),
                _post("l_0", r"l_0", l_0, "m", "knäckningslängd"),
                _post("N_d", r"N_d", N_d, "kN", "dimensionerande tryckkraft"),
                _post("f_ck", r"f_{ck}", f_ck, "MPa", "karakteristisk cylindertryckhållfasthet"),
                _post("f_cd", r"f_{cd}", f_cd, "MPa", "dimensionerande betongtryckhållfasthet"),
                _post("E_cd", r"E_{cd}", E_cd, "MPa", "dimensionerande elasticitetsmodul, betong"),
                _post("E_s", r"E_s", E_s, "MPa", "elasticitetsmodul, armering"),
                _post("phi_eff", r"\varphi_{eff}", phi_eff, "", "effektivt kryptal"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("A_c", r"A_c", A_c, "mm^2", "betongtvärsnittets area"),
                _post("I_c", r"I_c", I_c, "mm^4", "betongtvärsnittets tröghetsmoment"),
                _post("A_s", r"A_s", A_s, "mm^2", "total huvudarmeringsarea"),
                _post("rho", r"\rho", rho, "", "geometriskt armeringsinnehåll", decimals=6),
                _post("rho_min", r"\rho_{min}", _RHO_MIN, "", "metodens minsta armeringsinnehåll"),
                _post("l_phi", r"l_\phi", l_phi, "mm", "hävarm för fyra hörnjärn"),
                _post("I_phi", r"I_\phi", I_phi, "mm^4", "ett järns tröghetsmoment kring egen tyngdpunkt"),
                _post("I_s", r"I_s", I_s, "mm^4", "armeringens tröghetsmoment kring betongens tyngdpunkt"),
                _post("i", "i", i, "mm", "tröghetsradie", decimals=3),
                _post("l_0_mm", r"l_{0,mm}", l_0_mm, "mm", "knäckningslängd omräknad till mm"),
                _post("N_d_N", r"N_{d,N}", N_d_N, "N", "tryckkraft omräknad till N", decimals=1),
                _post("lambda", r"\lambda", lambda_, "", "slankhetstal"),
                _post("n", "n", n, "", "relativ normalkraft", decimals=5),
                _post("k_1", r"k_1", k_1, "", "hållfasthetsfaktor"),
                _post("k_2_obegransad", r"k_{2,obegr}", k_2_obegransad, "", "normalkrafts- och slankhetsfaktor före begränsning", decimals=5),
                _post("k_2", r"k_2", k_2, "", "normalkrafts- och slankhetsfaktor, högst 0,20", decimals=5),
                _post("K_c", r"K_c", K_c, "", "faktor för betongens bidrag", decimals=5),
                _post("K_s", r"K_s", K_s, "", "faktor för armeringens bidrag", decimals=0),
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("EI_c", r"EI_c", EI_c, "kN*m^2", "betongens bidrag till nominell böjstyvhet"),
                _post("EI_s", r"EI_s", EI_s, "kN*m^2", "armeringens bidrag till nominell böjstyvhet"),
                _post("EI", r"EI", EI, "kN*m^2", "total nominell böjstyvhet"),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"A_c = b^2,\qquad I_c = \frac{b^4}{12}", "kvadratiskt tvärsnitt"),
                _ekvation(r"n_\phi = 4,\qquad A_s = n_\phi\frac{\pi\phi_h^2}{4}", "fyra likadana huvudarmeringsjärn"),
                _ekvation(r"\rho = \frac{A_s}{A_c} \geq 0{,}002", "giltighetsvillkor för koefficienterna"),
                _ekvation(r"l_\phi = \frac{b}{2} - c_{nom} - \phi_b - \frac{\phi_h}{2}", "hävarm för fyra järn, ekv. (5.29)"),
                _ekvation(r"I_\phi = \frac{\pi\phi_h^4}{64}", "ett järns tröghetsmoment"),
                _ekvation(r"I_s = n_\phi I_\phi + A_s l_\phi^2", "armeringens tröghetsmoment, ekv. (5.27)"),
                _ekvation(r"l_{0,mm} = 1000\,l_0,\qquad N_{d,N} = 1000\,N_d", "omvandling från m och kN till mm och N"),
                _ekvation(r"i = \frac{b}{\sqrt{12}},\qquad \lambda = \frac{l_{0,mm}}{i}", "tröghetsradie och slankhetstal"),
                _ekvation(r"n = \frac{N_{d,N}}{A_c f_{cd}}", "relativ normalkraft, N och mm används"),
                _ekvation(r"k_1 = \sqrt{\frac{f_{ck}}{20}}", "hållfasthetsfaktor med f_ck i MPa, ekv. (5.25)"),
                _ekvation(r"k_2 = \min\left(\frac{n\lambda}{170},\,0{,}20\right)", "begränsad faktor, ekv. (5.26)"),
                _ekvation(r"K_s = 1,\qquad K_c = \frac{k_1 k_2}{1+\varphi_{eff}}", "koefficienter, ekv. (5.23)-(5.24)"),
                _ekvation(r"EI_c = \frac{K_c E_{cd} I_c}{10^9},\qquad EI_s = \frac{K_s E_s I_s}{10^9}", "bidrag i kN*m² från MPa och mm⁴"),
                _ekvation(r"EI = EI_c + EI_s", "total nominell böjstyvhet i kN*m², ekv. (5.22)"),
            ],
        },
    }


bojstyvhet_betongpalar.panel_schema = {
    "title": "Böjstyvhet - Betongpålar",
    "px": list(_PX_NAMN),
    "fields": [
        {"name": "b", "type": "float", "label": "Pålsida", "symbol": "<i>b</i>", "unit": "mm", "default": 300.0},
        {"name": "c_nom", "type": "float", "label": "Täckskikt till bygelns utsida", "symbol": "<i>c</i><sub>nom</sub>", "unit": "mm", "default": 30.0},
        {"name": "phi_b", "type": "float", "label": "Bygeldiameter", "symbol": "φ<sub>b</sub>", "unit": "mm", "default": 8.0},
        {"name": "phi_h", "type": "float", "label": "Huvudarmering, 4 hörnjärn", "symbol": "φ<sub>h</sub>", "unit": "mm", "default": 20.0},
        {"name": "l_0", "type": "float", "label": "Knäckningslängd", "symbol": "<i>l</i><sub>0</sub>", "unit": "m", "default": 3.0},
        {"name": "N_d", "type": "float", "label": "Dimensionerande tryckkraft", "symbol": "<i>N</i><sub>d</sub>", "unit": "kN", "default": 300.0},
        {"name": "f_ck", "type": "float", "label": "Karakteristisk cylindertryckhållfasthet", "symbol": "<i>f</i><sub>ck</sub>", "unit": "MPa", "default": 30.0},
        {"name": "f_cd", "type": "float", "label": "Dimensionerande betongtryckhållfasthet", "symbol": "<i>f</i><sub>cd</sub>", "unit": "MPa", "default": 20.0},
        {"name": "E_cd", "type": "float", "label": "Dimensionerande E-modul, betong", "symbol": "<i>E</i><sub>cd</sub>", "unit": "MPa", "default": 30000.0},
        {"name": "E_s", "type": "float", "label": "E-modul, armering", "symbol": "<i>E</i><sub>s</sub>", "unit": "MPa", "default": 200000.0},
        {"name": "phi_eff", "type": "float", "label": "Effektivt kryptal", "symbol": "ϕ<sub>eff</sub>", "unit": "", "default": 2.0},
    ],
}
