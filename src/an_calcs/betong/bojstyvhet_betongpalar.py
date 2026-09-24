"""Modifierad nominell böjstyvhet med lastberoende tryckzon och fyra hörnjärn."""

import math


_PX_NAMN = (
    "b", "c_nom", "phi_b", "phi_h", "l_0", "N_d",
    "f_ck", "f_cd", "E_cd", "E_s", "phi_eff", "M",
)
_OVERRIDE_NAMN = ("K_c_override", "K_c_manuell", "K_s_override", "K_s_manuell")
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


def _andligt_tal(namn, value):
    if isinstance(value, bool):
        raise ValueError(f"{namn} måste vara ett ändligt tal, inte ett booleskt värde.")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{namn} måste vara ett ändligt tal.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{namn} måste vara ett ändligt tal.")
    return value


def _tolka_override(namn, aktiverad, value):
    if not isinstance(aktiverad, bool):
        raise ValueError(f"{namn}_override måste vara True eller False.")
    if not aktiverad:
        return None
    value = _andligt_tal(namn + "_manuell", value)
    if value < 0:
        raise ValueError(f"{namn}_manuell måste vara >= 0.")
    return value


def _tolka_px(px):
    if not isinstance(px, (list, tuple)):
        raise ValueError("px för bojstyvhet_betongpalar måste vara en lista eller tuple.")
    if len(px) not in (len(_PX_NAMN), len(_PX_NAMN) + len(_OVERRIDE_NAMN)):
        raise ValueError(
            "px för bojstyvhet_betongpalar måste innehålla exakt 12 eller 16 värden; "
            "de fyra valfria värdena är K_c_override, K_c_manuell, K_s_override, K_s_manuell."
        )

    values = []
    for namn, value in zip(_PX_NAMN, px):
        value = _andligt_tal(namn, value)
        if namn in {"c_nom", "N_d", "phi_eff"}:
            if value < 0:
                forklaring = " N_d anges positiv i tryck." if namn == "N_d" else ""
                raise ValueError(f"{namn} måste vara >= 0." + forklaring)
        elif namn != "M" and value <= 0:
            raise ValueError(f"{namn} måste vara > 0.")
        values.append(value)
    K_c_manuell = K_s_manuell = None
    if len(px) == len(_PX_NAMN) + len(_OVERRIDE_NAMN):
        K_c_manuell = _tolka_override("K_c", px[12], px[13])
        K_s_manuell = _tolka_override("K_s", px[14], px[15])
    return values, K_c_manuell, K_s_manuell


def _tryckzon(b, d_prim, A_s_rad, alpha, N_d_N, M_Nmm):
    """Löser N-M-jämvikt med dragfri betong och koncentrerade armeringsareor.

    Koordinater räknas från den mest tryckta kanten. Normalisering med b
    och lastens storlek gör toleransen oberoende av enheter och lastnivå.
    Inga K-faktorer eller kryptalsreduktioner används i denna delmodell.
    """
    a = A_s_rad / b**2
    y_1 = d_prim / b
    y_2 = 1.0 - y_1

    def snitt(u):
        # Betong undanträngs endast av en armeringsrad inne i tryckzonen.
        beta_1 = alpha - (1.0 if y_1 <= u else 0.0)
        beta_2 = alpha - (1.0 if y_2 <= u else 0.0)
        area = u + (beta_1 + beta_2) * a
        if not math.isfinite(area) or area <= 0:
            raise ValueError("Tryckzonsmodellen måste ge en positiv transformerad area.")
        z = (u**2 / 2.0 + a * (beta_1 * y_1 + beta_2 * y_2)) / area
        inertia = (
            u**3 / 12.0 + u * (u / 2.0 - z)**2
            + a * (beta_1 * (y_1 - z)**2 + beta_2 * (y_2 - z)**2)
        )
        if not math.isfinite(inertia) or inertia <= 0:
            raise ValueError("Tryckzonsmodellen måste ge ett positivt transformerat tröghetsmoment.")
        return area, z, inertia, beta_1, beta_2

    # I helt tryckt eller obelastat snitt används hela betonghöjden x=b.
    u = 1.0
    area, z, inertia, beta_1, beta_2 = snitt(u)
    lastskala = max(N_d_N, M_Nmm / b)
    iterationer = 0
    sprucket = False
    if lastskala > 0:
        n_last = N_d_N / lastskala
        m_last = (M_Nmm / b) / lastskala

        def rest(u, area, z, inertia):
            # M anges kring b/2. Flytta momentet till snittets tyngdpunkt z.
            m_tp = m_last + n_last * (z - 0.5)
            return n_last * inertia - m_tp * area * (u - z)

        if rest(u, area, z, inertia) < 0:
            sprucket = True
            lo, hi = 0.0, 1.0
            for iterationer in range(1, 101):
                u = (lo + hi) / 2.0
                area, z, inertia, beta_1, beta_2 = snitt(u)
                if rest(u, area, z, inertia) > 0:
                    lo = u
                else:
                    hi = u
                if hi - lo <= 1e-13:
                    break
            else:
                raise ValueError("Tryckzonens höjd x kunde inte bestämmas med angiven tolerans.")

    return {
        "x": u * b,
        "x_tp": z * b,
        "A_II": area * b**2,
        "I_II": inertia * b**4,
        "beta_1": beta_1,
        "beta_2": beta_2,
        "iterationer": iterationer,
        "sprucket": sprucket,
    }


def bojstyvhet_betongpalar(px):
    """
    Beräknar modifierad nominell böjstyvhet EI med lastberoende tryckzon.

    Pålen har exakt fyra likadana huvudarmeringsjärn, symmetriskt placerade
    i hörnen innanför byglarna. Böjning avser en huvudaxel parallell med en
    tvärsnittssida; styvheten är lika kring de båda huvudaxlarna.

    Parameterformat (lista eller tuple):
        px = [b, c_nom, phi_b, phi_h, l_0, N_d,
              f_ck, f_cd, E_cd, E_s, phi_eff, M]
        Valfritt tillägg för manuella faktorer (Panel använder detta format):
        px += [K_c_override, K_c_manuell, K_s_override, K_s_manuell]

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
            Noll tillåts som gränsfall och ger EI_c = 0 med automatiskt K_c.
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
        M : float
            Böjande moment [kN*m] kring hela pålens geometriska mittaxel,
            i samma lastkombination som N_d. Båda tecken tillåts; symmetrin
            gör att abs(M) används, med koordinater från mest tryckt kant.
        K_c_override, K_s_override : bool, optional
            True aktiverar respektive manuell faktor; annars används
            K_c = k1*k2/(1+phi_eff) respektive K_s = 1.
        K_c_manuell, K_s_manuell : float, optional
            Ändliga faktorer >= 0 utan övre gräns. Ersätter standardvärdet
            direkt i EI, utan ytterligare reduktion eller begränsning.
            Ett inaktivt manuellt värde ignoreras. Tolv indata ger automatläge.

    Returvärde:
        Standardiserad details-dictionary för an_print.CalcBlock och Panel.
        EI_c, EI_s och EI redovisas i kN*m^2. Inga värden avrundas i
        beräkningen; eventuell avrundning görs av presentationslagret.

    Metod:
        Underlagets avsnitt 5.6, "Nominell böjstyvhet påle", ekv. (5.22)-
        (5.27) och (5.29), s. 11:
        https://kth.diva-portal.org/smash/get/diva2%3A1597682/FULLTEXT01.pdf
        Modifiering: x och x_tp bestäms genom elastisk N-M-jämvikt enligt
        användarens underlag, figur B7.14, med alpha = Es/Ecd. Dragbetong
        försummas och armeringsraderna representeras av koncentrerade areor.
        Ic = b*x**3/12 + b*x*(x/2-x_tp)**2, utan armeringsavdrag.
        Is beräknas kring samma x_tp, inklusive järnens egna tröghetsmoment.
        Kc används som ytterligare reduktion efter tryckzonsberäkningen.
        Kc och Ks kan ersättas var för sig med manuella faktorer.
        Detta är en modifierad modell, inte den oförändrade nominella metoden.
        Ac, rho och slankheten baseras fortsatt på hela tvärsnittet.
        Kryptalet påverkar endast automatiskt Kc. Tryckzonen påverkas inte
        av manuella K-faktorer. Kravet rho >= 0.002 behålls i alla lägen.
        Helt tryckt eller obelastat snitt använder x=b (verksam betonghöjd,
        inte neutralaxelns läge utanför snittet). M är indata; funktionen
        beräknar inte andra ordningens moment eller betongens sprickmoment.

    Exempel:
        px = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2, 30]
        details = bojstyvhet_betongpalar(px)
    """
    values, K_c_manuell, K_s_manuell = _tolka_px(px)
    b, c_nom, phi_b, phi_h, l_0, N_d, f_ck, f_cd, E_cd, E_s, phi_eff, M = values

    n_phi = 4
    l_phi = b / 2.0 - c_nom - phi_b - phi_h / 2.0
    if l_phi <= 0:
        raise ValueError("Geometrin måste ge en positiv hävarm l_phi för hörnarmeringen.")
    if 2.0 * l_phi < phi_h:
        raise ValueError("Huvudarmeringsjärnen överlappar: 2*l_phi måste vara >= phi_h.")

    A_c = b**2
    A_s = n_phi * math.pi * phi_h**2 / 4.0
    rho = A_s / A_c
    # Accepterar avrundningsfel vid den exakta gränsen, inte lägre armeringshalt.
    if rho < _RHO_MIN and not math.isclose(rho, _RHO_MIN, rel_tol=1e-12):
        raise ValueError(
            f"Armeringsinnehållet rho = A_s/A_c = {rho:.8g} är för lågt. "
            "Metoden kräver rho >= 0,002."
        )

    d_prim = c_nom + phi_b + phi_h / 2.0
    d = b - d_prim
    A_s_rad = A_s / 2.0
    alpha = E_s / E_cd
    N_d_N = N_d * 1000.0
    M_Nmm = abs(M) * 1e6
    snitt = _tryckzon(b, d_prim, A_s_rad, alpha, N_d_N, M_Nmm)
    x, x_tp = snitt["x"], snitt["x_tp"]
    I_c_egen = b * x**3 / 12.0
    I_c_steiner = b * x * (x / 2.0 - x_tp)**2
    I_c = I_c_egen + I_c_steiner
    I_phi = math.pi * phi_h**4 / 64.0
    I_s = n_phi * I_phi + A_s_rad * ((d_prim - x_tp)**2 + (d - x_tp)**2)
    M_tp = M_Nmm + N_d_N * (x_tp - b / 2.0)
    if N_d_N == 0 and M_Nmm == 0:
        snittbeskrivning = "Obelastat snitt: hela betonghöjden används, x=b."
    elif snitt["sprucket"]:
        snittbeskrivning = "Delvis tryckt snitt: x bestäms genom iteration med dragfri betong."
    else:
        snittbeskrivning = "Helt tryckt snitt: hela betonghöjden används, x=b."
    i = b / math.sqrt(12.0)
    l_0_mm = l_0 * 1000.0
    lambda_ = l_0_mm / i
    n = N_d_N / (A_c * f_cd)
    k_1 = math.sqrt(f_ck / 20.0)
    k_2_obegransad = n * lambda_ / 170.0
    k_2 = min(k_2_obegransad, 0.20)
    K_s_auto = 1.0
    K_c_auto = k_1 * k_2 / (1.0 + phi_eff)
    K_c = K_c_auto if K_c_manuell is None else K_c_manuell
    K_s = K_s_auto if K_s_manuell is None else K_s_manuell
    override_indata = []
    for namn, latex, value in (
        ("K_c_manuell", r"K_{c,man}", K_c_manuell),
        ("K_s_manuell", r"K_{s,man}", K_s_manuell),
    ):
        if value is not None:
            override_indata.append(_post(namn, latex, value, "", "manuellt angiven faktor", decimals=5))
    faktorbeskrivning = (
        ("Kc är manuellt angivet och ersätter det beräknade värdet. " if K_c_manuell is not None
         else "Kc beräknas automatiskt som k1*k2/(1+phi_eff). ")
        + ("Ks är manuellt angivet och ersätter standardvärdet 1. " if K_s_manuell is not None
           else "Ks använder standardvärdet 1. ")
        + "Valda faktorer används direkt i styvhetsbidragen och påverkar inte tryckzonen."
    )

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
                        "Modifierad nominell böjstyvhet för en kvadratisk betongpåle med fyra "
                        "likadana huvudarmeringsjärn, symmetriskt placerade i hörnen. "
                        "Tryckzonen bestäms av normalkraft och moment. Betongens och "
                        "armeringens bidrag beräknas kring samma transformerade tyngdpunkt. "
                        "Böjningen avser en huvudaxel parallell med en tvärsnittssida."
                    ),
                },
                {
                    "rubrik": "Källa",
                    "text": (
                        "Underlagets avsnitt 5.6, Nominell böjstyvhet påle, s. 11. "
                        "Automatiska koefficienter enligt ekv. (5.23)-(5.26), summa enligt (5.22) "
                        "och hörngeometri enligt (5.29). Tryckzonsmodellen hämtas från "
                        "det kompletterande bildunderlaget, figur B7.14, med "
                        "transformerat tröghetsmoment på sida B236."
                    ),
                },
                {
                    "rubrik": "Förutsättningar",
                    "text": (
                        "Armeringsinnehållet As/Ac ska vara minst 0,002. Ac och "
                        "slankheten avser hela pålen. Slutligt Ic avser tryckzonen "
                        "utan avdrag för armeringen, inklusive förskjutning till x_tp. "
                        "Täckskiktet mäts till bygelns utsida. Materialvärden anges direkt. "
                        "Normalkraften anges positiv i tryck och momentet kring pålens "
                        "mittaxel, i samma lastkombination. Symmetrin medger båda momenttecken."
                    ),
                },
                {
                    "rubrik": "Tryckzon och modellval",
                    "text": (
                        "Tryckzonen löses med linjärelastiska material, alpha=Es/Ecd "
                        "och dragfri betong. Koordinater mäts från mest tryckt kant. "
                        "Armeringen behandlas som koncentrerade areor vid lösning av x; "
                        "järnens egna tröghetsmoment ingår däremot i slutligt Is. "
                        "Kc används som ytterligare reduktion för bland annat sprickning. "
                        "Kc och Ks kan anges manuellt. Kryptalet påverkar endast automatiskt Kc. "
                        "Kombinationen är en modifiering "
                        "av den nominella metoden. Momentet är indata; andra ordningens "
                        "moment och betongens sprickmoment beräknas inte."
                    ),
                },
                {"rubrik": "Val av faktorer", "text": faktorbeskrivning},
                {"rubrik": "Beräknat tvärsnittstillstånd", "text": snittbeskrivning},
                {
                    "rubrik": "Enheter",
                    "text": (
                        "Tvärsnittsmått anges i mm, knäckningslängd i m, normalkraft "
                        "i kN, moment i kN*m och materialvärden i MPa. Beräkningen använder N och mm. "
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
                _post("M", "M", M, "kN*m", "böjande moment kring hela pålens mittaxel"),
                _post("f_ck", r"f_{ck}", f_ck, "MPa", "karakteristisk cylindertryckhållfasthet"),
                _post("f_cd", r"f_{cd}", f_cd, "MPa", "dimensionerande betongtryckhållfasthet"),
                _post("E_cd", r"E_{cd}", E_cd, "MPa", "dimensionerande elasticitetsmodul, betong"),
                _post("E_s", r"E_s", E_s, "MPa", "elasticitetsmodul, armering"),
                _post("phi_eff", r"\varphi_{eff}", phi_eff, "", "effektivt kryptal"),
                *override_indata,
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("A_c", r"A_c", A_c, "mm^2", "hela betongtvärsnittets area"),
                _post("A_s", r"A_s", A_s, "mm^2", "total huvudarmeringsarea"),
                _post("rho", r"\rho", rho, "", "geometriskt armeringsinnehåll", decimals=6),
                _post("rho_min", r"\rho_{min}", _RHO_MIN, "", "metodens minsta armeringsinnehåll"),
                _post("l_phi", r"l_\phi", l_phi, "mm", "hävarm för fyra hörnjärn"),
                _post("d_prim", "d'", d_prim, "mm", "närmaste armeringsrad från mest tryckt kant"),
                _post("d", "d", d, "mm", "bortre armeringsrad från mest tryckt kant"),
                _post("A_s_rad", r"A_{s,rad}", A_s_rad, "mm^2", "armeringsarea per rad, två järn"),
                _post("alpha", r"\alpha", alpha, "", "modulkvot Es/Ecd för tryckzonsmodellen"),
                _post("x", "x", x, "mm", "verksam betonghöjd; x=b vid helt tryckt eller obelastat snitt", decimals=3),
                _post("x_tp", r"x_{tp}", x_tp, "mm", "transformerad tyngdpunkt från mest tryckt kant", decimals=3),
                _post("beta_1", r"\beta_1", snitt["beta_1"], "", "transformationsfaktor för närmaste armeringsrad"),
                _post("beta_2", r"\beta_2", snitt["beta_2"], "", "transformationsfaktor för bortre armeringsrad"),
                _post("A_II", r"A_{II}", snitt["A_II"], "mm^2", "transformerad area i tryckzonsmodellen"),
                _post("I_II", r"I_{II}", snitt["I_II"], "mm^4", "transformerat tröghetsmoment, används endast för tryckzonen"),
                _post("M_Nmm", r"M_{Nmm}", M_Nmm, "N*mm", "momentbelopp omräknat till N*mm"),
                _post("M_tp", r"M_{tp}", M_tp, "N*mm", "moment kring transformerad tyngdpunkt i tryckzonsmodellen"),
                _post("iterationer", r"n_{iter}", snitt["iterationer"], "", "antal bisektionssteg; noll om hela betonghöjden används", decimals=0),
                _post("I_c_egen", r"I_{c,egen}", I_c_egen, "mm^4", "tryckzonens tröghetsmoment kring egen tyngdpunkt"),
                _post("I_c_steiner", r"I_{c,Steiner}", I_c_steiner, "mm^4", "förskjutningsbidrag till gemensam axel"),
                _post("I_c", r"I_c", I_c, "mm^4", "betongens tröghetsmoment kring x_tp"),
                _post("I_phi", r"I_\phi", I_phi, "mm^4", "ett järns tröghetsmoment kring egen tyngdpunkt"),
                _post("I_s", r"I_s", I_s, "mm^4", "armeringens tröghetsmoment kring samma x_tp"),
                _post("i", "i", i, "mm", "hela betongtvärsnittets tröghetsradie", decimals=3),
                _post("l_0_mm", r"l_{0,mm}", l_0_mm, "mm", "knäckningslängd omräknad till mm"),
                _post("N_d_N", r"N_{d,N}", N_d_N, "N", "tryckkraft omräknad till N", decimals=1),
                _post("lambda", r"\lambda", lambda_, "", "slankhetstal"),
                _post("n", "n", n, "", "relativ normalkraft", decimals=5),
                _post("k_1", r"k_1", k_1, "", "hållfasthetsfaktor"),
                _post("k_2_obegransad", r"k_{2,obegr}", k_2_obegransad, "", "normalkrafts- och slankhetsfaktor före begränsning", decimals=5),
                _post("k_2", r"k_2", k_2, "", "normalkrafts- och slankhetsfaktor, högst 0,20", decimals=5),
                _post("K_c_auto", r"K_{c,auto}", K_c_auto, "", "betongfaktor enligt grundmodellen före eventuellt manuellt val", decimals=5),
                _post("K_s_auto", r"K_{s,auto}", K_s_auto, "", "armeringsfaktor enligt grundmodellen före eventuellt manuellt val", decimals=0),
                _post("K_c", r"K_c", K_c, "", "använd betongfaktor, manuellt angiven" if K_c_manuell is not None else "använd betongfaktor, automatiskt beräknad", decimals=5),
                _post("K_s", r"K_s", K_s, "", "använd armeringsfaktor, manuellt angiven" if K_s_manuell is not None else "använd armeringsfaktor, standardvärde", decimals=5),
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("EI_c", r"EI_c", EI_c, "kN*m^2", "betongens bidrag efter tryckzonsberäkning och Kc"),
                _post("EI_s", r"EI_s", EI_s, "kN*m^2", "armeringens bidrag kring gemensam axel"),
                _post("EI", r"EI", EI, "kN*m^2", "total modifierad nominell böjstyvhet"),
                _post(
                    "x", "x", x, "mm",
                    "tryckzonens höjd, reducerad (x < b)" if snitt["sprucket"]
                    else "tryckzonens höjd, oreducerad (x = b)",
                    decimals=3,
                ),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"A_c = b^2", "hela kvadratiska tvärsnittet för relativ normalkraft och armeringsinnehåll"),
                _ekvation(r"n_\phi = 4,\qquad A_s = n_\phi\frac{\pi\phi_h^2}{4}", "fyra likadana huvudarmeringsjärn"),
                _ekvation(r"\rho = \frac{A_s}{A_c} \geq 0{,}002", "giltighetsvillkor för koefficienterna"),
                _ekvation(r"l_\phi = \frac{b}{2} - c_{nom} - \phi_b - \frac{\phi_h}{2}", "hävarm för fyra järn, ekv. (5.29)"),
                _ekvation(r"d' = c_{nom}+\phi_b+\frac{\phi_h}{2},\qquad d = b-d',\qquad A_{s,rad}=\frac{A_s}{2}", "två armeringsrader från mest tryckt kant"),
                _ekvation(r"\alpha = \frac{E_s}{E_{cd}}", "modulkvot vid lösning av tryckzonen, utan K-faktorer eller krypreduktion"),
                _ekvation(r"\beta_j=\alpha-1", "för en armeringsrad inne i tryckzonen: y_j ≤ x, där y_1=d' och y_2=d"),
                _ekvation(r"\beta_j=\alpha", "för en armeringsrad utanför tryckzonen: y_j > x"),
                _ekvation(r"A_{II}=bx+(\beta_1+\beta_2)A_{s,rad}", "transformerad area"),
                _ekvation(r"x_{tp}=\frac{bx^2/2+A_{s,rad}(\beta_1d'+\beta_2d)}{A_{II}}", "transformerad tyngdpunkt"),
                _ekvation(r"I_{II}=\frac{bx^3}{12}+bx\left(\frac{x}{2}-x_{tp}\right)^2+A_{s,rad}\left[\beta_1(d'-x_{tp})^2+\beta_2(d-x_{tp})^2\right]", "figur B7.14, endast för lösning av tryckzonen"),
                _ekvation(r"M_{Nmm}=10^6|M|,\qquad M_{tp}=M_{Nmm}+N_{d,N}\left(x_{tp}-\frac{b}{2}\right)", "momentomvandling och förskjutning från pålens mittaxel"),
                _ekvation(r"\frac{N_{d,N}}{A_{II}}-\frac{M_{tp}}{I_{II}}(x-x_{tp})=0", "nollspänning i tryckzonens underkant; löses för 0<x<b"),
                _ekvation(
                    r"x=b\quad\text{om}\quad\sigma_{min}=\frac{N_{d,N}}{A_{II}(b)}-\frac{M_{Nmm}}{I_{II}(b)}\frac{b}{2}\geq 0",
                    "Hela betonghöjden används om spänningen vid den minst tryckta kanten "
                    "är noll eller tryckande. Annars bestäms x < b genom iteration så att "
                    "spänningen vid tryckzonens underkant blir noll.",
                ),
                _ekvation(r"I_{c,egen}=\frac{bx^3}{12},\qquad I_{c,Steiner}=bx\left(\frac{x}{2}-x_{tp}\right)^2", "betongdelens eget tröghetsmoment och förskjutningsbidrag"),
                _ekvation(r"I_c=I_{c,egen}+I_{c,Steiner}", "betongens tröghetsmoment kring gemensam axel, utan armeringsavdrag"),
                _ekvation(r"I_\phi = \frac{\pi\phi_h^4}{64}", "ett järns tröghetsmoment"),
                _ekvation(r"I_s = n_\phi I_\phi + A_{s,rad}\left[(d'-x_{tp})^2+(d-x_{tp})^2\right]", "armeringens tröghetsmoment kring samma gemensamma axel"),
                _ekvation(r"l_{0,mm} = 1000\,l_0,\qquad N_{d,N} = 1000\,N_d", "omvandling från m och kN till mm och N"),
                _ekvation(r"i = \frac{b}{\sqrt{12}},\qquad \lambda = \frac{l_{0,mm}}{i}", "tröghetsradie och slankhetstal"),
                _ekvation(r"n = \frac{N_{d,N}}{A_c f_{cd}}", "relativ normalkraft, N och mm används"),
                _ekvation(r"k_1 = \sqrt{\frac{f_{ck}}{20}}", "hållfasthetsfaktor med f_ck i MPa, ekv. (5.25)"),
                _ekvation(r"k_2 = \min\left(\frac{n\lambda}{170},\,0{,}20\right)", "begränsad faktor, ekv. (5.26)"),
                _ekvation(r"K_{s,auto} = 1,\qquad K_{c,auto} = \frac{k_1 k_2}{1+\varphi_{eff}}", "grundmodellens koefficienter före eventuellt manuellt val, ekv. (5.23)-(5.24)"),
                _ekvation(r"K_c = K_{c,man}" if K_c_manuell is not None else r"K_c = K_{c,auto}", "manuellt angiven betongfaktor används" if K_c_manuell is not None else "automatiskt beräknad betongfaktor används"),
                _ekvation(r"K_s = K_{s,man}" if K_s_manuell is not None else r"K_s = K_{s,auto}", "manuellt angiven armeringsfaktor används" if K_s_manuell is not None else "standardvärdet för armeringsfaktorn används"),
                _ekvation(r"EI_c = \frac{K_c E_{cd} I_c}{10^9},\qquad EI_s = \frac{K_s E_s I_s}{10^9}", "bidrag i kN*m² från MPa och mm⁴"),
                _ekvation(r"EI = EI_c + EI_s", "modifierad nominell böjstyvhet i kN*m² med valda Kc och Ks"),
            ],
        },
    }


bojstyvhet_betongpalar.panel_schema = {
    "title": "Böjstyvhet - Betongpålar",
    "px": list(_PX_NAMN + _OVERRIDE_NAMN),
    "fields": [
        {"name": "b", "type": "float", "label": "Pålsida", "symbol": "<i>b</i>", "unit": "mm", "default": 300.0},
        {"name": "c_nom", "type": "float", "label": "Täckskikt till bygelns utsida", "symbol": "<i>c</i><sub>nom</sub>", "unit": "mm", "default": 30.0},
        {"name": "phi_b", "type": "float", "label": "Bygeldiameter", "symbol": "φ<sub>b</sub>", "unit": "mm", "default": 8.0},
        {"name": "phi_h", "type": "float", "label": "Huvudarmering, 4 hörnjärn", "symbol": "φ<sub>h</sub>", "unit": "mm", "default": 20.0},
        {"name": "l_0", "type": "float", "label": "Knäckningslängd", "symbol": "<i>l</i><sub>0</sub>", "unit": "m", "default": 3.0},
        {"name": "N_d", "type": "float", "label": "Dimensionerande tryckkraft", "symbol": "<i>N</i><sub>d</sub>", "unit": "kN", "default": 300.0},
        {"name": "M", "type": "float", "label": "Böjmoment kring pålens mittaxel", "symbol": "<i>M</i>", "unit": "kN*m", "default": 30.0},
        {"name": "f_ck", "type": "float", "label": "Karakteristisk cylindertryckhållfasthet", "symbol": "<i>f</i><sub>ck</sub>", "unit": "MPa", "default": 30.0},
        {"name": "f_cd", "type": "float", "label": "Dimensionerande betongtryckhållfasthet", "symbol": "<i>f</i><sub>cd</sub>", "unit": "MPa", "default": 20.0},
        {"name": "E_cd", "type": "float", "label": "Dimensionerande E-modul, betong", "symbol": "<i>E</i><sub>cd</sub>", "unit": "MPa", "default": 30000.0},
        {"name": "E_s", "type": "float", "label": "E-modul, armering", "symbol": "<i>E</i><sub>s</sub>", "unit": "MPa", "default": 200000.0},
        {"name": "phi_eff", "type": "float", "label": "Effektivt kryptal", "symbol": "ϕ<sub>eff</sub>", "unit": "", "default": 2.0},
        {"name": "K_c_override", "type": "bool", "label": "Ange Kc manuellt", "symbol": "<i>K</i><sub>c</sub>", "default": False},
        {"name": "K_c_manuell", "type": "float", "label": "Manuellt Kc", "symbol": "<i>K</i><sub>c,man</sub>", "unit": "", "default": 1.0, "visible_if": {"field": "K_c_override", "equals": True}},
        {"name": "K_s_override", "type": "bool", "label": "Ange Ks manuellt", "symbol": "<i>K</i><sub>s</sub>", "default": False},
        {"name": "K_s_manuell", "type": "float", "label": "Manuellt Ks", "symbol": "<i>K</i><sub>s,man</sub>", "unit": "", "default": 1.0, "visible_if": {"field": "K_s_override", "equals": True}},
    ],
}
