import math


def _post(namn, latex, value, unit="", etikett=""):
    """Skapar en standardiserad datapost för presentations- och beräkningsdata."""
    return {
        "namn": namn,
        "latex": latex,
        "value": value,
        "unit": unit,
        "etikett": etikett,
    }


def _ekvation(latex, etikett):
    """Skapar en standardiserad ekvationspost."""
    return {"latex": latex, "etikett": etikett}


def _grader_till_radianer(vinkel):
    return math.radians(vinkel)


def _ar_noll(value, tol=1e-12):
    return abs(value) <= tol


def _krav_storre_an_noll(namn, value):
    if value <= 0:
        raise ValueError(f"{namn} måste vara > 0.")


def _krav_icke_negativ(namn, value):
    if value < 0:
        raise ValueError(f"{namn} måste vara >= 0.")


def allmanna_barighetsekvationen(px):
    """
    Beräknar dimensionerande bärförmåga för jord i brottgränstillstånd enligt
    användarens Mathcad-modell för allmänna bärighetsekvationen.

    Funktionen är avsedd för ytliga fundament och bortser helt från
    bruksgränstillstånd. Resultatet returneras som en standardiserad
    ``details``-dictionary med både numeriska värden och presentationsmetadata.

    Parameterformat:
        px = [
            b, l, lang, d, delta_h, t, e_b_plac, e_l_plac, F_vy, F_hb, F_hl,
            M_insp_l, M_insp_b, l_h, c_prime, c_uk, gamma, gamma_prime, phi_k,
            eta, gamma_m, gamma_m0, gamma_Rd, beta, alpha
        ]

    Enhetskonvention:
        - längder i m
        - laster i kN
        - spänningar/hållfastheter i kPa
        - vinklar i grader

    Parametrar:
        b : float
            Fundamentbredd [m]

        l : float
            Fundamentlängd [m]

        lang : int
            1 för långsträckt fundament, annars 0 [-]

        d : float
            Grundläggningsdjup [m]

        delta_h : float
            Avstånd mellan underkant fundament och grundvattenyta [m]

        t : float
            Fundamenttjocklek [m]

        e_b_plac : float
            Placeringsexcentricitet i breddriktning [m]

        e_l_plac : float
            Placeringsexcentricitet i längdriktning [m]

        F_vy : float
            Dimensionerande vertikallast från yttre last [kN]

        F_hb : float
            Dimensionerande horisontallast i breddriktning [kN]

        F_hl : float
            Dimensionerande horisontallast i längdriktning [kN]

        M_insp_l : float
            Inspänningsmoment kring l-axel [kNm]

        M_insp_b : float
            Inspänningsmoment kring b-axel [kNm]

        l_h : float
            Hävarm för horisontallast [m]

        c_prime : float
            Dränerad kohesion [kPa]

        c_uk : float
            Odränerad skjuvhållfasthet [kPa]

        gamma : float
            Tunghet för jord under grundläggningsnivå [kN/m^3]

        gamma_prime : float
            Effektiv tunghet för jord under grundläggningsnivå [kN/m^3]

        phi_k : float
            Karakteristisk friktionsvinkel [deg]

        eta : float
            Omräkningsfaktor [-]

        gamma_m : float
            Partialkoefficient för friktionsvinkel och effektiv kohesion [-]

        gamma_m0 : float
            Partialkoefficient för odränerad skjuvhållfasthet [-]

        gamma_Rd : float
            Modellfaktor/osäkerhet i beräkningsmodell [-]

        beta : float
            Lutning på intilliggande markyta [deg]

        alpha : float
            Lutning på fundamentets basyta [deg]

    Exempel:
        Ett kopierbart exempel för långsträckt fundament:

        px_lang = [
            0.8, 6.0, 1,
            1.0, 1.5, 0.4,
            0.0, 0.0,
            350.0, 0.0, 0.0,
            0.0, 0.0, 1.0,
            0.0, 0.0,
            18.0, 10.0, 35.0,
            1.0, 1.3, 1.5, 1.0,
            0.0, 0.0,
        ]

        details = allmanna_barighetsekvationen(px_lang)

    Returvärde:
        dict
            Dictionary med nycklarna ``metodbeskrivning``, ``indata``,
            ``delresultat``, ``slutresultat`` och ``ekvationer``.
    """
    if px is None:
        raise ValueError("px måste anges.")
    if len(px) != 25:
        raise ValueError("px måste innehålla 25 värden.")

    (
        b,
        l,
        lang,
        d,
        delta_h,
        t,
        e_b_plac,
        e_l_plac,
        F_vy,
        F_hb,
        F_hl,
        M_insp_l,
        M_insp_b,
        l_h,
        c_prime,
        c_uk,
        gamma,
        gamma_prime,
        phi_k,
        eta,
        gamma_m,
        gamma_m0,
        gamma_Rd,
        beta,
        alpha,
    ) = px

    if lang not in (0, 1, False, True):
        raise ValueError("lang måste vara 0 eller 1.")

    lang = int(lang)

    _krav_storre_an_noll("b", b)
    _krav_storre_an_noll("l", l)
    _krav_icke_negativ("d", d)
    _krav_storre_an_noll("t", t)
    _krav_storre_an_noll("l_h", l_h)
    _krav_icke_negativ("c_prime", c_prime)
    _krav_icke_negativ("c_uk", c_uk)
    _krav_icke_negativ("gamma", gamma)
    _krav_icke_negativ("gamma_prime", gamma_prime)
    _krav_icke_negativ("phi_k", phi_k)
    _krav_icke_negativ("beta", beta)
    _krav_icke_negativ("alpha", alpha)
    _krav_storre_an_noll("eta", eta)
    _krav_storre_an_noll("gamma_m", gamma_m)
    _krav_storre_an_noll("gamma_m0", gamma_m0)
    _krav_storre_an_noll("gamma_Rd", gamma_Rd)

    if phi_k >= 90:
        raise ValueError("phi_k måste vara < 90 grader.")
    if beta >= 90:
        raise ValueError("beta måste vara < 90 grader.")
    if alpha >= 90:
        raise ValueError("alpha måste vara < 90 grader.")

    l_ref = 1.0 if lang == 1 else l

    phi_k_rad = _grader_till_radianer(phi_k)
    beta_rad = _grader_till_radianer(beta)
    alpha_rad = _grader_till_radianer(alpha)

    phi_d_rad = math.atan(math.tan(phi_k_rad) * eta / gamma_m)
    phi_d = math.degrees(phi_d_rad)
    sin_phi_d = math.sin(phi_d_rad)
    tan_phi_d = math.tan(phi_d_rad)

    if not _ar_noll(c_prime):
        c_ud = eta * c_prime / gamma_m
    elif not _ar_noll(c_uk):
        c_ud = eta * c_uk / gamma_m0
    else:
        c_ud = 0.0

    EG_k = 25.0 * b * l_ref * t
    F_v = F_vy + 1.5 * EG_k
    if F_v <= 0:
        raise ValueError("F_v måste vara > 0.")

    F_h = math.sqrt(F_hb**2 + F_hl**2)

    e_b_last = (M_insp_l - F_hb * l_h) / F_v
    e_l_last = (M_insp_b - F_hl * l_h) / F_v
    e_b = abs(e_b_plac + e_b_last)
    e_l = abs(e_l_plac + e_l_last)

    b_ef = b - 2.0 * e_b
    l_ef = l_ref - 2.0 * e_l

    if b_ef <= 0:
        raise ValueError("b_ef måste vara > 0.")
    if l_ef <= 0:
        raise ValueError("l_ef måste vara > 0.")

    q_d_prime = gamma * d

    if delta_h <= 0:
        gamma_fri = gamma_prime
    elif delta_h < b_ef:
        gamma_fri = gamma * (delta_h / b_ef) + gamma_prime * ((b_ef - delta_h) / b_ef)
    else:
        gamma_fri = gamma

    F = 0.08705 + 0.3231 * math.sin(2.0 * phi_d_rad) - 0.04836 * math.sin(2.0 * phi_d_rad) ** 2
    N_q = ((1.0 + sin_phi_d) / (1.0 - sin_phi_d)) * math.exp(math.pi * tan_phi_d)
    N_c_0 = math.pi + 2.0
    if _ar_noll(phi_d_rad):
        N_c = N_c_0
    else:
        N_c = (N_q - 1.0) / tan_phi_d

    if _ar_noll(phi_d_rad) and not _ar_noll(beta_rad):
        N_gamma = -2.0 * math.sin(beta_rad)
    else:
        N_gamma = F * (
            ((1.0 + sin_phi_d) / (1.0 - sin_phi_d)) * math.exp(1.5 * math.pi * tan_phi_d) - 1.0
        )

    d_c_raw = 1.0 + 0.35 * d / b_ef
    d_c = min(d_c_raw, 1.7)
    d_q = d_c
    d_gamma = 1.0

    if lang == 1:
        s_c = 1.0
        s_q = 1.0
        s_gamma = 1.0
    else:
        if _ar_noll(phi_d_rad):
            s_c = 1.0 + 0.2 * b_ef / l_ef
        else:
            s_c = 1.0 + N_q * b_ef / (N_c * l_ef)
        s_q = 1.0 + tan_phi_d * b_ef / l_ef
        s_gamma = 1.0 - 0.4 * b_ef / l_ef

    m_i = (2.0 * l_ef + b_ef) / (l_ef + b_ef)

    if _ar_noll(F_h) or lang == 1 or _ar_noll(phi_d_rad):
        i_q = 1.0
        i_gamma = 1.0
    else:
        denominator = F_v + b_ef * l_ef * c_ud / tan_phi_d
        if denominator <= 0:
            raise ValueError("Uttrycket för i_q och i_gamma blev ogiltigt.")
        base = 1.0 - F_h / denominator
        if base < 0:
            raise ValueError("Uttrycket för i_q och i_gamma blev negativt.")
        i_q = base**m_i
        i_gamma = base ** (m_i + 1.0)

    if _ar_noll(F_h):
        i_c = 1.0
    elif _ar_noll(phi_d_rad) and lang == 1:
        i_c = 1.0
    elif _ar_noll(phi_d_rad):
        denominator = b_ef * l_ef * c_ud * N_c
        if denominator <= 0:
            raise ValueError("Uttrycket för i_c blev ogiltigt.")
        i_c = 1.0 - m_i * F_h / denominator
    else:
        i_c = i_q - (1.0 - i_q) / (N_c * tan_phi_d)

    if _ar_noll(beta_rad):
        g_c = 1.0
        g_q = 1.0
        g_gamma = 1.0
    else:
        if _ar_noll(phi_d_rad):
            g_c = 1.0 - 2.0 * beta_rad / N_c
        else:
            g_c = math.exp(-2.0 * beta_rad * tan_phi_d)
        g_q = 1.0 - math.sin(2.0 * beta_rad)
        g_gamma = 1.0 - math.sin(2.0 * beta_rad)

    if _ar_noll(alpha_rad):
        b_q = 1.0
        b_c = 1.0
        b_gamma = 1.0
    else:
        b_q = 1.0 - alpha_rad * tan_phi_d**2
        b_gamma = 1.0 - alpha_rad * tan_phi_d**2
        if _ar_noll(phi_d_rad):
            b_c = 1.0 - 2.0 * alpha_rad / (math.pi + 2.0)
        else:
            b_c = b_q - (1.0 - b_q) / (N_c * tan_phi_d)

    xi_c = d_c * s_c * i_c * g_c * b_c
    xi_q = d_q * s_q * i_q * g_q * b_q
    xi_gamma = d_gamma * s_gamma * i_gamma * g_gamma * b_gamma

    q_bd = (
        c_ud * N_c * xi_c + q_d_prime * N_q * xi_q + 0.5 * gamma_fri * b_ef * N_gamma * xi_gamma
    ) / gamma_Rd

    if lang == 1:
        F_bd = q_bd * b
        F_bd_unit = "kN/m"
        F_bd_etikett = "dimensionerande bärförmåga för jord som linjelast"
    else:
        F_bd = q_bd * b * l
        F_bd_unit = "kN"
        F_bd_etikett = "dimensionerande bärförmåga för jord som punktlast"

    slutresultat_items = [
        _post("q_bd", r"q_{bd}", q_bd, "kPa", "dimensionerande bärförmåga för jord"),
        _post("F_bd", r"F_{bd}", F_bd, F_bd_unit, F_bd_etikett),
        _post("EG_k", r"EG_k", EG_k, "kN", "fundamentets egentyngd"),
        _post("F_v", r"F_v", F_v, "kN", "dimensionerande vertikallast"),
        _post("b_ef", r"b_{ef}", b_ef, "m", "effektiv bredd"),
    ]
    if lang == 0:
        slutresultat_items.append(_post("l_ef", r"l_{ef}", l_ef, "m", "effektiv längd"))

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Denna funktion beräknar dimensionerande bärförmåga för jord i "
                        "brottgränstillstånd enligt användarens Mathcad-modell för den "
                        "allmänna bärighetsekvationen. Beräkningen omfattar "
                        "dimensionerande jordparametrar, effektiv geometri, "
                        "bärighetsfaktorer samt korrektioner för geometri, last och "
                        "omgivande förhållanden."
                    ),
                },
                {
                    "rubrik": "Referens",
                    "text": (
                        "Beräkningsgången följer den Mathcad-modell som ligger till "
                        "grund för projektet, med teoretiskt stöd i allmän "
                        "geoteknisk litteratur såsom Göran Sällfors, Geoteknik."
                    ),
                },
                {
                    "rubrik": "Tillstånd",
                    "text": (
                        "Funktionen avser enbart brottgränstillstånd. Eventuell "
                        "information om bruksgränstillstånd beaktas inte i "
                        "beräkningsgången."
                    ),
                },
                {
                    "rubrik": "Begränsning",
                    "text": (
                        "Funktionen är avsedd för ytliga fundament. Djupa fundament "
                        "och pålar hanteras inte i denna version. Ogiltig effektiv "
                        "geometri, exempelvis b_ef <= 0 eller l_ef <= 0, ger fel."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("b", "b", b, "m", "fundamentbredd"),
                _post("l", "l", l, "m", "fundamentlängd"),
                _post("lang", r"\mathrm{lang}", lang, "", "1 för långsträckt fundament"),
                _post("d", "d", d, "m", "grundläggningsdjup"),
                _post("delta_h", r"\Delta h", delta_h, "m", "avstånd till grundvatten"),
                _post("t", "t", t, "m", "fundamenttjocklek"),
                _post("e_b_plac", r"e_{b,plac}", e_b_plac, "m", "placeringsexcentricitet i breddriktning"),
                _post("e_l_plac", r"e_{l,plac}", e_l_plac, "m", "placeringsexcentricitet i längdriktning"),
                _post("F_vy", r"F_{v,y}", F_vy, "kN", "dimensionerande vertikallast yttre last"),
                _post("F_hb", r"F_{h,b}", F_hb, "kN", "horisontallast i breddriktning"),
                _post("F_hl", r"F_{h,l}", F_hl, "kN", "horisontallast i längdriktning"),
                _post("M_insp_l", r"M_{insp,l}", M_insp_l, "kNm", "inspänningsmoment kring l-axel"),
                _post("M_insp_b", r"M_{insp,b}", M_insp_b, "kNm", "inspänningsmoment kring b-axel"),
                _post("l_h", r"l_h", l_h, "m", "hävarm för horisontallast"),
                _post("c_prime", r"c^{\prime}", c_prime, "kPa", "dränerad kohesion"),
                _post("c_uk", r"c_{uk}", c_uk, "kPa", "odränerad skjuvhållfasthet"),
                _post("gamma", r"\gamma", gamma, "kN/m^3", "tunghet under grundläggningsnivå"),
                _post("gamma_prime", r"\gamma^{\prime}", gamma_prime, "kN/m^3", "effektiv tunghet"),
                _post("phi_k", r"\phi_k", phi_k, "deg", "karakteristisk friktionsvinkel"),
                _post("eta", r"\eta", eta, "", "omräkningsfaktor"),
                _post("gamma_m", r"\gamma_m", gamma_m, "", "partialkoefficient för friktionsvinkel och kohesion"),
                _post("gamma_m0", r"\gamma_{m,0}", gamma_m0, "", "partialkoefficient för odränerad skjuvhållfasthet"),
                _post("gamma_Rd", r"\gamma_{Rd}", gamma_Rd, "", "modellfaktor"),
                _post("beta", r"\beta", beta, "deg", "lutning på intilliggande markyta"),
                _post("alpha", r"\alpha", alpha, "deg", "lutning på fundamentets basyta"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("l_ref", r"l_{ref}", l_ref, "m", "referenslängd i beräkningen"),
                _post("phi_d", r"\phi^{\prime}_d", phi_d, "deg", "dimensionerande friktionsvinkel"),
                _post("c_ud", r"c_{ud}", c_ud, "kPa", "dimensionerande skjuvhållfasthet"),
                _post("EG_k", r"EG_k", EG_k, "kN", "fundamentets egentyngd"),
                _post("F_v", r"F_v", F_v, "kN", "dimensionerande vertikallast"),
                _post("F_h", r"F_h", F_h, "kN", "resultant horisontallast"),
                _post("e_b_last", r"e_{b,last}", e_b_last, "m", "lastexcentricitet i breddriktning"),
                _post("e_l_last", r"e_{l,last}", e_l_last, "m", "lastexcentricitet i längdriktning"),
                _post("e_b", r"e_b", e_b, "m", "total excentricitet i breddriktning"),
                _post("e_l", r"e_l", e_l, "m", "total excentricitet i längdriktning"),
                _post("b_ef", r"b_{ef}", b_ef, "m", "effektiv bredd"),
                _post("l_ef", r"l_{ef}", l_ef, "m", "effektiv längd"),
                _post("q_d_prime", r"q^{\prime}_d", q_d_prime, "kPa", "stapellast på grundläggningsnivå"),
                _post("gamma_fri", r"\gamma_{fri}", gamma_fri, "kN/m^3", "tunghet för friktionsjord under G-nivå"),
                _post("F", "F", F, "", "hjälpparameter för N-gamma"),
                _post("N_c_0", r"N_{c,0}", N_c_0, "", "specialvärde för N-c vid phi-d = 0"),
                _post("N_q", r"N_q", N_q, "", "bärighetsfaktor N-q"),
                _post("N_c", r"N_c", N_c, "", "bärighetsfaktor N-c"),
                _post("N_gamma", r"N_{\gamma}", N_gamma, "", "bärighetsfaktor N-gamma"),
                _post("d_c_raw", r"d_{c,raw}", d_c_raw, "", "oklippt djupfaktor för c-termen"),
                _post("d_c", r"d_c", d_c, "", "djupfaktor för c-termen"),
                _post("d_q", r"d_q", d_q, "", "djupfaktor för q-termen"),
                _post("d_gamma", r"d_{\gamma}", d_gamma, "", "djupfaktor för gamma-termen"),
                _post("s_c", r"s_c", s_c, "", "formfaktor för c-termen"),
                _post("s_q", r"s_q", s_q, "", "formfaktor för q-termen"),
                _post("s_gamma", r"s_{\gamma}", s_gamma, "", "formfaktor för gamma-termen"),
                _post("m_i", r"m_i", m_i, "", "hjälpparameter för lastlutning"),
                _post("i_c", r"i_c", i_c, "", "lastlutningsfaktor för c-termen"),
                _post("i_q", r"i_q", i_q, "", "lastlutningsfaktor för q-termen"),
                _post("i_gamma", r"i_{\gamma}", i_gamma, "", "lastlutningsfaktor för gamma-termen"),
                _post("g_c", r"g_c", g_c, "", "marklutningsfaktor för c-termen"),
                _post("g_q", r"g_q", g_q, "", "marklutningsfaktor för q-termen"),
                _post("g_gamma", r"g_{\gamma}", g_gamma, "", "marklutningsfaktor för gamma-termen"),
                _post("b_c", r"b_c", b_c, "", "baslutningsfaktor för c-termen"),
                _post("b_q", r"b_q", b_q, "", "baslutningsfaktor för q-termen"),
                _post("b_gamma", r"b_{\gamma}", b_gamma, "", "baslutningsfaktor för gamma-termen"),
                _post("xi_c", r"\xi_c", xi_c, "", "sammanlagd korrektionsfaktor för c-termen"),
                _post("xi_q", r"\xi_q", xi_q, "", "sammanlagd korrektionsfaktor för q-termen"),
                _post("xi_gamma", r"\xi_{\gamma}", xi_gamma, "", "sammanlagd korrektionsfaktor för gamma-termen"),
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": slutresultat_items,
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"l_{ref} = 1", "referenslängd för långsträckt fundament"),
                _ekvation(r"l_{ref} = l", "referenslängd för övrigt fundament"),
                _ekvation(r"\phi^{\prime}_d = \arctan\left(\tan(\phi_k)\frac{\eta}{\gamma_m}\right)", "dimensionerande friktionsvinkel"),
                _ekvation(r"c_{ud} = \eta c^{\prime} / \gamma_m", "dimensionerande skjuvhållfasthet från dränerad kohesion"),
                _ekvation(r"c_{ud} = \eta c_{uk} / \gamma_{m,0}", "dimensionerande skjuvhållfasthet från odränerad skjuvhållfasthet"),
                _ekvation(r"EG_k = 25 \, b \, l_{ref} \, t", "fundamentets egentyngd"),
                _ekvation(r"F_v = F_{v,y} + 1.5 \, EG_k", "dimensionerande vertikallast"),
                _ekvation(r"F_h = \sqrt{F_{h,b}^2 + F_{h,l}^2}", "resultant horisontallast"),
                _ekvation(r"e_{b,last} = \frac{M_{insp,l} - F_{h,b} l_h}{F_v}", "lastexcentricitet i breddriktning"),
                _ekvation(r"e_{l,last} = \frac{M_{insp,b} - F_{h,l} l_h}{F_v}", "lastexcentricitet i längdriktning"),
                _ekvation(r"e_b = \left|e_{b,plac} + e_{b,last}\right|", "total excentricitet i breddriktning"),
                _ekvation(r"e_l = \left|e_{l,plac} + e_{l,last}\right|", "total excentricitet i längdriktning"),
                _ekvation(r"b_{ef} = b - 2 e_b", "effektiv bredd"),
                _ekvation(r"l_{ef} = l_{ref} - 2 e_l", "effektiv längd"),
                _ekvation(r"q^{\prime}_d = \gamma d", "stapellast på grundläggningsnivå"),
                _ekvation(r"\gamma_{fri} = \gamma^{\prime}", "tunghet för friktionsjord under G-nivå, grundvatten vid eller över G-nivå"),
                _ekvation(r"\gamma_{fri} = \gamma \frac{\Delta h}{b_{ef}} + \gamma^{\prime}\frac{b_{ef} - \Delta h}{b_{ef}}", "tunghet för friktionsjord under G-nivå, grundvatten inom effektiv bredd"),
                _ekvation(r"\gamma_{fri} = \gamma", "tunghet för friktionsjord under G-nivå, grundvatten under effektiv bredd"),
                _ekvation(r"F = 0.08705 + 0.3231\sin(2\phi^{\prime}_d) - 0.04836\sin^2(2\phi^{\prime}_d)", "hjälpparameter för N-gamma"),
                _ekvation(r"N_{c,0} = \pi + 2", "specialvärde för N-c vid phi-d = 0"),
                _ekvation(r"N_q = \frac{1 + \sin(\phi^{\prime}_d)}{1 - \sin(\phi^{\prime}_d)} e^{\pi \tan(\phi^{\prime}_d)}", "bärighetsfaktor N-q"),
                _ekvation(r"N_c = \pi + 2", "bärighetsfaktor N-c för phi-d = 0"),
                _ekvation(r"N_c = \frac{N_q - 1}{\tan(\phi^{\prime}_d)}", "bärighetsfaktor N-c för phi-d > 0"),
                _ekvation(r"N_{\gamma} = F \left(\frac{1 + \sin(\phi^{\prime}_d)}{1 - \sin(\phi^{\prime}_d)} e^{1.5 \pi \tan(\phi^{\prime}_d)} - 1\right)", "bärighetsfaktor N-gamma"),
                _ekvation(r"d_{c,raw} = 1 + 0.35 \frac{d}{b_{ef}}", "oklippt djupfaktor för c-termen"),
                _ekvation(r"d_c = \min(d_{c,raw}, 1.7)", "djupfaktor för c-termen"),
                _ekvation(r"d_q = d_c", "djupfaktor för q-termen"),
                _ekvation(r"d_{\gamma} = 1", "djupfaktor för gamma-termen"),
                _ekvation(r"s_c = 1", "formfaktor för c-termen, långsträckt fundament"),
                _ekvation(r"s_c = 1 + 0.2 \frac{b_{ef}}{l_{ef}}", "formfaktor för c-termen, phi-d = 0"),
                _ekvation(r"s_c = 1 + \frac{N_q b_{ef}}{N_c l_{ef}}", "formfaktor för c-termen, phi-d > 0"),
                _ekvation(r"s_q = 1", "formfaktor för q-termen, långsträckt fundament"),
                _ekvation(r"s_q = 1 + \tan(\phi^{\prime}_d)\frac{b_{ef}}{l_{ef}}", "formfaktor för q-termen"),
                _ekvation(r"s_{\gamma} = 1", "formfaktor för gamma-termen, långsträckt fundament"),
                _ekvation(r"s_{\gamma} = 1 - 0.4 \frac{b_{ef}}{l_{ef}}", "formfaktor för gamma-termen"),
                _ekvation(r"m_i = \frac{2 l_{ef} + b_{ef}}{l_{ef} + b_{ef}}", "hjälpparameter för lastlutning"),
                _ekvation(r"i_q = 1", "lastlutningsfaktor för q-termen, specialfall"),
                _ekvation(r"i_q = \left(1 - \frac{F_h}{F_v + b_{ef} l_{ef} c_{ud} / \tan(\phi^{\prime}_d)}\right)^{m_i}", "lastlutningsfaktor för q-termen"),
                _ekvation(r"i_{\gamma} = 1", "lastlutningsfaktor för gamma-termen, specialfall"),
                _ekvation(r"i_{\gamma} = \left(1 - \frac{F_h}{F_v + b_{ef} l_{ef} c_{ud} / \tan(\phi^{\prime}_d)}\right)^{m_i + 1}", "lastlutningsfaktor för gamma-termen"),
                _ekvation(r"i_c = 1", "lastlutningsfaktor för c-termen, specialfall"),
                _ekvation(r"i_c = 1 - \frac{m_i F_h}{b_{ef} l_{ef} c_{ud} N_c}", "lastlutningsfaktor för c-termen, phi-d = 0"),
                _ekvation(r"i_c = i_q - \frac{1 - i_q}{N_c \tan(\phi^{\prime}_d)}", "lastlutningsfaktor för c-termen, phi-d > 0"),
                _ekvation(r"g_c = 1", "marklutningsfaktor för c-termen, plan markyta"),
                _ekvation(r"g_c = 1 - \frac{2 \beta}{N_c}", "marklutningsfaktor för c-termen, phi-d = 0"),
                _ekvation(r"g_c = e^{-2 \beta \tan(\phi^{\prime}_d)}", "marklutningsfaktor för c-termen, phi-d > 0"),
                _ekvation(r"g_q = 1", "marklutningsfaktor för q-termen, plan markyta"),
                _ekvation(r"g_q = 1 - \sin(2 \beta)", "marklutningsfaktor för q-termen"),
                _ekvation(r"g_{\gamma} = 1", "marklutningsfaktor för gamma-termen, plan markyta"),
                _ekvation(r"g_{\gamma} = 1 - \sin(2 \beta)", "marklutningsfaktor för gamma-termen"),
                _ekvation(r"b_c = 1", "baslutningsfaktor för c-termen, horisontell basyta"),
                _ekvation(r"b_c = 1 - \frac{2 \alpha}{\pi + 2}", "baslutningsfaktor för c-termen, phi-d = 0"),
                _ekvation(r"b_c = b_q - \frac{1 - b_q}{N_c \tan(\phi^{\prime}_d)}", "baslutningsfaktor för c-termen, phi-d > 0"),
                _ekvation(r"b_q = 1", "baslutningsfaktor för q-termen, horisontell basyta"),
                _ekvation(r"b_q = 1 - \alpha \tan^2(\phi^{\prime}_d)", "baslutningsfaktor för q-termen"),
                _ekvation(r"b_{\gamma} = 1", "baslutningsfaktor för gamma-termen, horisontell basyta"),
                _ekvation(r"b_{\gamma} = 1 - \alpha \tan^2(\phi^{\prime}_d)", "baslutningsfaktor för gamma-termen"),
                _ekvation(r"\xi_c = d_c s_c i_c g_c b_c", "sammanlagd korrektionsfaktor för c-termen"),
                _ekvation(r"\xi_q = d_q s_q i_q g_q b_q", "sammanlagd korrektionsfaktor för q-termen"),
                _ekvation(r"\xi_{\gamma} = d_{\gamma} s_{\gamma} i_{\gamma} g_{\gamma} b_{\gamma}", "sammanlagd korrektionsfaktor för gamma-termen"),
                _ekvation(
                    r"q_{bd} = \frac{c_{ud} N_c \xi_c + q^{\prime}_d N_q \xi_q + 0.5 \gamma_{fri} b_{ef} N_{\gamma} \xi_{\gamma}}{\gamma_{Rd}}",
                    "dimensionerande bärförmåga",
                ),
                _ekvation(r"F_{bd} = q_{bd} b", "dimensionerande bärförmåga som linjelast för långsträckt sula"),
                _ekvation(r"F_{bd} = q_{bd} b l", "dimensionerande bärförmåga som punktlast för punktfundament"),
            ],
        },
    }


allmanna_barighetsekvationen.panel_schema = {
    "title": "Allmänna bärighetsekvationen",
    "px": [
        "b",
        "l",
        "lang",
        "d",
        "delta_h",
        "t",
        "e_b_plac",
        "e_l_plac",
        "F_vy",
        "F_hb",
        "F_hl",
        "M_insp_l",
        "M_insp_b",
        "l_h",
        "c_prime",
        "c_uk",
        "gamma",
        "gamma_prime",
        "phi_k",
        "eta",
        "gamma_m",
        "gamma_m0",
        "gamma_Rd",
        "beta",
        "alpha",
    ],
    "fields": [
        {"name": "b", "type": "float", "label": "Fundamentbredd", "symbol": "<i>b</i>", "unit": "m", "default": 1.4},
        {"name": "l", "type": "float", "label": "Fundamentlängd", "symbol": "<i>l</i>", "unit": "m", "default": 1.4},
        {
            "name": "lang",
            "type": "choice",
            "label": "Fundamenttyp",
            "symbol": "lang",
            "default": 1,
            "options": [
                {"label": "Långsträckt fundament", "value": 1},
                {"label": "Platta/rektangulärt fundament", "value": 0},
            ],
        },
        {"name": "d", "type": "float", "label": "Grundläggningsdjup", "symbol": "<i>d</i>", "unit": "m", "default": 0.0},
        {"name": "delta_h", "type": "float", "label": "Avstånd till grundvatten", "symbol": "Δ<i>h</i>", "unit": "m", "default": 1.9},
        {"name": "t", "type": "float", "label": "Fundamenttjocklek", "symbol": "<i>t</i>", "unit": "m", "default": 0.3},
        {
            "name": "e_b_plac",
            "type": "float",
            "label": "Placeringsexcentricitet bredd",
            "symbol": "<i>e</i><sub>b,plac</sub>",
            "unit": "m",
            "default": 0.0,
        },
        {
            "name": "e_l_plac",
            "type": "float",
            "label": "Placeringsexcentricitet längd",
            "symbol": "<i>e</i><sub>l,plac</sub>",
            "unit": "m",
            "default": 0.0,
        },
        {"name": "F_vy", "type": "float", "label": "Vertikallast yttre last", "symbol": "<i>F</i><sub>v,y</sub>", "unit": "kN", "default": 529.0},
        {"name": "F_hb", "type": "float", "label": "Horisontallast bredd", "symbol": "<i>F</i><sub>h,b</sub>", "unit": "kN", "default": 0.0},
        {"name": "F_hl", "type": "float", "label": "Horisontallast längd", "symbol": "<i>F</i><sub>h,l</sub>", "unit": "kN", "default": 0.0},
        {"name": "M_insp_l", "type": "float", "label": "Inspänningsmoment l-axel", "symbol": "<i>M</i><sub>insp,l</sub>", "unit": "kNm", "default": 0.0},
        {"name": "M_insp_b", "type": "float", "label": "Inspänningsmoment b-axel", "symbol": "<i>M</i><sub>insp,b</sub>", "unit": "kNm", "default": 0.0},
        {"name": "l_h", "type": "float", "label": "Hävarm horisontallast", "symbol": "<i>l</i><sub>h</sub>", "unit": "m", "default": 1.0},
        {"name": "c_prime", "type": "float", "label": "Dränerad kohesion", "symbol": "<i>c</i>'", "unit": "kPa", "default": 0.0},
        {"name": "c_uk", "type": "float", "label": "Odränerad skjuvhållfasthet", "symbol": "<i>c</i><sub>uk</sub>", "unit": "kPa", "default": 0.0},
        {"name": "gamma", "type": "float", "label": "Tunghet", "symbol": "γ", "unit": "kN/m^3", "default": 18.0},
        {"name": "gamma_prime", "type": "float", "label": "Effektiv tunghet", "symbol": "γ'", "unit": "kN/m^3", "default": 10.0},
        {"name": "phi_k", "type": "float", "label": "Karakteristisk friktionsvinkel", "symbol": "φ<sub>k</sub>", "unit": "deg", "default": 45.0},
        {"name": "eta", "type": "float", "label": "Omräkningsfaktor", "symbol": "η", "unit": "", "default": 1.0},
        {"name": "gamma_m", "type": "float", "label": "Partialkoefficient gamma_m", "symbol": "γ<sub>m</sub>", "unit": "", "default": 1.3},
        {"name": "gamma_m0", "type": "float", "label": "Partialkoefficient gamma_m0", "symbol": "γ<sub>m,0</sub>", "unit": "", "default": 1.5},
        {"name": "gamma_Rd", "type": "float", "label": "Modellfaktor", "symbol": "γ<sub>Rd</sub>", "unit": "", "default": 1.0},
        {"name": "beta", "type": "float", "label": "Markytans lutning", "symbol": "β", "unit": "deg", "default": 0.0},
        {"name": "alpha", "type": "float", "label": "Basytans lutning", "symbol": "α", "unit": "deg", "default": 0.0},
    ],
}
