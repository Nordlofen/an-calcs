import math


def _post(namn, latex, value, unit="", etikett=""):
    """Skapar en standardiserad datapost."""
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


def _krav_min(namn, latex, value, krav, unit, etikett):
    status = "OK" if value >= krav else "EJ OK"
    tecken = ">=" if status == "OK" else "<"
    return _post(namn, latex, status, "", f"{etikett}: {value:.3g} {unit} {tecken} {krav:.3g} {unit}")


def _krav_max(namn, latex, value, krav, unit, etikett):
    status = "OK" if value <= krav else "EJ OK"
    tecken = "<=" if status == "OK" else ">"
    return _post(namn, latex, status, "", f"{etikett}: {value:.3g} {unit} {tecken} {krav:.3g} {unit}")


def _tolka_px(px):
    if len(px) != 19:
        raise ValueError(
            "haltagning_limtrabalk kräver 19 värden: "
            "[L, b, h, s, x, d, l_z, anvand_direkta_snittkrafter, E_g, Q_k, V_Ed, M_Ed, "
            "k_mod, gamma_m, f_v_g_k, f_m_g_k, f_t_90_k, F_ax_Rk, kontrollera_forstarkning]."
        )

    (
        L,
        b,
        h,
        s,
        x,
        d,
        l_z,
        anvand_direkta_snittkrafter,
        E_g,
        Q_k,
        V_Ed,
        M_Ed,
        k_mod,
        gamma_m,
        f_v_g_k,
        f_m_g_k,
        f_t_90_k,
        F_ax_Rk,
        kontrollera_forstarkning,
    ) = px

    values = {
        "L": L,
        "b": b,
        "h": h,
        "s": s,
        "x": x,
        "d": d,
        "l_z": l_z,
        "E_g": E_g,
        "Q_k": Q_k,
        "V_Ed": V_Ed,
        "M_Ed": M_Ed,
        "k_mod": k_mod,
        "gamma_m": gamma_m,
        "f_v_g_k": f_v_g_k,
        "f_m_g_k": f_m_g_k,
        "f_t_90_k": f_t_90_k,
        "F_ax_Rk": F_ax_Rk,
    }

    for namn, value in values.items():
        if value <= 0 and namn not in {"E_g", "Q_k", "V_Ed", "M_Ed"}:
            raise ValueError(f"{namn} måste vara > 0.")
    for namn in ("E_g", "Q_k", "M_Ed"):
        if values[namn] < 0:
            raise ValueError(f"{namn} måste vara >= 0.")

    anvand_direkta_snittkrafter = bool(anvand_direkta_snittkrafter)
    if not anvand_direkta_snittkrafter and (E_g <= 0 or Q_k <= 0):
        raise ValueError("E_g och Q_k måste vara > 0 när lasten beräknas från ytlaster.")

    return values | {
        "anvand_direkta_snittkrafter": anvand_direkta_snittkrafter,
        "kontrollera_forstarkning": bool(kontrollera_forstarkning),
    }


def haltagning_limtrabalk(px):
    """
    Kontrollerar cirkulärt hål i limträbalk enligt Limträhandboken Del 2.

    Funktionen följer repo-kontraktet och returnerar en ``details``-dictionary
    för presentation med ``an_print.CalcBlock``.

    Parameterformat:
        px = [
            L, b, h, s, x, d, l_z,
            anvand_direkta_snittkrafter, E_g, Q_k, V_Ed, M_Ed,
            k_mod, gamma_m,
            f_v_g_k, f_m_g_k, f_t_90_k,
            F_ax_Rk, kontrollera_forstarkning,
        ]

    Enheter:
        Geometri anges i mm, ytlaster i kN/m², hållfastheter i MPa.
        Funktionen räknar om linjelast till kN/m med ``s`` i mm.
    """
    v = _tolka_px(px)
    L = v["L"]
    b = v["b"]
    h = v["h"]
    s = v["s"]
    x = v["x"]
    d = v["d"]
    l_z = v["l_z"]
    anvand_direkta_snittkrafter = v["anvand_direkta_snittkrafter"]
    E_g = v["E_g"]
    Q_k = v["Q_k"]
    V_Ed = v["V_Ed"]
    M_Ed = v["M_Ed"]
    k_mod = v["k_mod"]
    gamma_m = v["gamma_m"]
    f_v_g_k = v["f_v_g_k"]
    f_m_g_k = v["f_m_g_k"]
    f_t_90_k = v["f_t_90_k"]
    F_ax_Rk = v["F_ax_Rk"]
    kontrollera_forstarkning = v["kontrollera_forstarkning"]

    l_A = x - d / 2.0
    l_v = x - d / 2.0 + 100.0
    h_ro = h / 2.0 - d / 2.0
    h_ru = h / 2.0 - d / 2.0
    h_d = d

    krav_l_z = max(300.0, 1.5 * h)
    krav_l_A = 0.5 * h
    krav_l_v = h
    krav_h_r = 0.35 * h

    k_h = min(1.1, (600.0 / h) ** 0.1)
    f_t_90_d = k_mod * f_t_90_k / gamma_m
    f_m_g_d = k_h * k_mod * f_m_g_k / gamma_m
    f_v_g_d = k_mod * f_v_g_k / gamma_m
    F_ax_Rd = k_mod * F_ax_Rk / gamma_m
    k_cr = min(3.0 / f_v_g_k, 1.0)

    if anvand_direkta_snittkrafter:
        q_d = None
        V_d = abs(V_Ed)
        M_d = M_Ed
    else:
        q_d = (s / 1000.0) * (1.2 * E_g + 1.5 * Q_k)
        V_d = abs(q_d * (L / 1000.0 / 2.0 - x / 1000.0))
        M_d = q_d * (L / 1000.0 / 2.0 * x / 1000.0 - (x / 1000.0) ** 2 / 2.0)

    b_ef = k_cr * b
    A_red = b_ef * (h - h_d)
    tau_d = 1.5 * V_d * 1000.0 / A_red
    mu_v = tau_d / f_v_g_d

    I_y = 2.0 * (b * h_ro**3 / 12.0 + b * h_ro * (0.5 * h_ro + d / 2.0) ** 2)
    I_brutto = b * h**3 / 12.0
    I_kvot = I_brutto / I_y
    sigma_m_d = M_d * 1000000.0 / I_y * h / 2.0
    mu_m = sigma_m_d / f_m_g_d
    mu_vm = mu_v + mu_m

    h_r = min(h_ru + 0.15 * h_d, h_ro + 0.15 * h_d)
    l_t_90 = 0.35 * h_d + 0.5 * h
    k_t_90 = min(1.0, math.sqrt(450.0 / h))
    F_t_90_V = V_d * h_d / (4.0 * h) * (3.0 - h_d**2 / h**2)
    F_t_90_M = 0.008 * (M_d * 1000.0) / h_r
    F_t_90 = F_t_90_V + F_t_90_M
    sigma_t_90 = F_t_90 * 1000.0 / (0.5 * l_t_90 * b)
    f_t_90_eff = k_t_90 * f_t_90_d
    mu_t_90 = sigma_t_90 / f_t_90_eff

    mu_skruv = F_t_90 / F_ax_Rd

    tvarsnitt_ok = mu_v <= 1.0 and mu_m <= 1.0 and mu_vm <= 1.0
    drag_t_90_ok = mu_t_90 <= 1.0
    forstarkning_ok = mu_skruv <= 1.0 if kontrollera_forstarkning else None

    slutresultat_items = [
        _krav_min("krav_l_z", r"l_z \geq \max(300, 1.5h)", l_z, krav_l_z, "mm", "avstånd mellan hål eller fri zon"),
        _krav_min("krav_l_A", r"l_A \geq 0.5h", l_A, krav_l_A, "mm", "avstånd från stöd till hålkant"),
        _krav_min("krav_l_v", r"l_v \geq h", l_v, krav_l_v, "mm", "avstånd enligt figur 5.5"),
        _krav_min("krav_h_ro", r"h_{ro} \geq 0.35h", h_ro, krav_h_r, "mm", "höjd över hål"),
        _krav_min("krav_h_ru", r"h_{ru} \geq 0.35h", h_ru, krav_h_r, "mm", "höjd under hål"),
        _post("mu_v", r"\mu_v", mu_v, "", "utnyttjande skjuvning"),
        _post("mu_m", r"\mu_m", mu_m, "", "utnyttjande moment"),
        _post("mu_vm", r"\mu_{vm}", mu_vm, "", "interaktion moment och tvärkraft"),
        _post("mu_t_90", r"\mu_{t,90}", mu_t_90, "", "utnyttjande drag vinkelrätt fiberriktningen"),
    ]
    if kontrollera_forstarkning:
        slutresultat_items.append(
            _post("mu_skruv", r"\mu_{skruv}", mu_skruv, "", "utnyttjande skruvförstärkning")
        )
    slutresultat_items.extend(
        [
            _post("tvarsnitt_ok", r"\mathrm{tv\ddot{a}rsnitt}", "OK" if tvarsnitt_ok else "EJ OK", "", "skjuvning, moment och interaktion"),
            _post("drag_t_90_ok", r"\mathrm{drag}_{t,90}", "OK" if drag_t_90_ok else "EJ OK", "", "drag vinkelrätt fiberriktningen"),
        ]
    )
    if kontrollera_forstarkning:
        slutresultat_items.append(
            _post("forstarkning_ok", r"\mathrm{f\ddot{o}rst\ddot{a}rkning}", "OK" if forstarkning_ok else "EJ OK", "", "självborrande träskruvar")
        )

    indata_items = [
        _post("L", "L", L, "mm", "balklängd"),
        _post("b", "b", b, "mm", "balkbredd"),
        _post("h", "h", h, "mm", "balkhöjd"),
        _post("s", "s", s, "mm", "c/c-avstånd"),
        _post("x", "x", x, "mm", "från stöd till centrum hål"),
        _post("d", "d", d, "mm", "håldiameter"),
        _post("l_z", "l_z", l_z, "mm", "avstånd mellan hål eller fri zon"),
        _post(
            "anvand_direkta_snittkrafter",
            r"\mathrm{direkt}",
            anvand_direkta_snittkrafter,
            "",
            "direkt inmatning av dimensionerande snittkrafter",
        ),
    ]
    if anvand_direkta_snittkrafter:
        indata_items.extend(
            [
                _post("V_Ed", r"V_{Ed}", V_Ed, "kN", "dimensionerande tvärkraft"),
                _post("M_Ed", r"M_{Ed}", M_Ed, "kNm", "dimensionerande moment"),
            ]
        )
    else:
        indata_items.extend(
            [
                _post("E_g", "E_g", E_g, "kN/m^2", "egentyngd"),
                _post("Q_k", "Q_k", Q_k, "kN/m^2", "nyttig last"),
            ]
        )
    indata_items.extend(
        [
            _post("k_mod", r"k_{mod}", k_mod, "", "modifieringsfaktor"),
            _post("gamma_m", r"\gamma_m", gamma_m, "", "partialkoefficient trä"),
            _post("f_v_g_k", r"f_{v,g,k}", f_v_g_k, "MPa", "karakteristisk skjuvhållfasthet"),
            _post("f_m_g_k", r"f_{m,g,k}", f_m_g_k, "MPa", "karakteristisk böjhållfasthet"),
            _post("f_t_90_k", r"f_{t,90,k}", f_t_90_k, "MPa", "karakteristisk draghållfasthet vinkelrätt fibrer"),
            _post("F_ax_Rk", r"F_{ax,Rk}", F_ax_Rk, "kN", "karakteristisk axiell bärförmåga per skruv"),
        ]
    )

    delresultat_items = [
        _post("l_A", "l_A", l_A, "mm", "avstånd från stöd till hålkant"),
        _post("l_v", "l_v", l_v, "mm", "avstånd enligt figur 5.5"),
        _post("h_ro", "h_{ro}", h_ro, "mm", "höjd över hål"),
        _post("h_ru", "h_{ru}", h_ru, "mm", "höjd under hål"),
        _post("h_d", "h_d", h_d, "mm", "hålets höjd"),
        _post("k_h", "k_h", k_h, "", "höjdfaktor för böjhållfasthet"),
        _post("f_v_g_d", r"f_{v,g,d}", f_v_g_d, "MPa", "dimensionerande skjuvhållfasthet"),
        _post("f_m_g_d", r"f_{m,g,d}", f_m_g_d, "MPa", "dimensionerande böjhållfasthet"),
        _post("f_t_90_d", r"f_{t,90,d}", f_t_90_d, "MPa", "dimensionerande draghållfasthet vinkelrätt fibrer"),
        _post("F_ax_Rd", r"F_{ax,Rd}", F_ax_Rd, "kN", "dimensionerande axiell bärförmåga per skruv"),
        _post("k_cr", r"k_{cr}", k_cr, "", "sprickfaktor"),
    ]
    if q_d is not None:
        delresultat_items.append(_post("q_d", "q_d", q_d, "kN/m", "dimensionerande linjelast"))
    delresultat_items.extend(
        [
            _post("V_d", "V_d", V_d, "kN", "dimensionerande tvärkraft vid hål"),
            _post("M_d", "M_d", M_d, "kNm", "dimensionerande moment vid hål"),
            _post("b_ef", "b_{ef}", b_ef, "mm", "effektiv bredd med sprickfaktor"),
            _post("A_red", r"A_{red}", A_red, "mm^2", "reducerad tvärsnittsarea"),
            _post("tau_d", r"\tau_d", tau_d, "MPa", "skjuvspänning i reducerat tvärsnitt"),
            _post("I_y", r"I_y", I_y, "mm^4", "tröghetsmoment reducerat tvärsnitt"),
            _post("I_brutto", "I", I_brutto, "mm^4", "bruttotröghetsmoment"),
            _post("I_kvot", r"I/I_y", I_kvot, "", "förhållande brutto/reducerat tröghetsmoment"),
            _post("sigma_m_d", r"\sigma_{m,d}", sigma_m_d, "MPa", "böjspänning"),
            _post("h_r", "h_r", h_r, "mm", "effektiv kantzon för drag vinkelrätt fibrer"),
            _post("l_t_90", r"l_{t,90}", l_t_90, "mm", "effektiv längd för drag vinkelrätt fibrer"),
            _post("k_t_90", r"k_{t,90}", k_t_90, "", "storleksfaktor för drag vinkelrätt fibrer"),
            _post("F_t_90_V", r"F_{t,90,V}", F_t_90_V, "kN", "andel från tvärkraft"),
            _post("F_t_90_M", r"F_{t,90,M}", F_t_90_M, "kN", "andel från moment"),
            _post("F_t_90", r"F_{t,90}", F_t_90, "kN", "samlad dragkraft vinkelrätt fibrer"),
            _post("sigma_t_90", r"\sigma_{t,90}", sigma_t_90, "MPa", "dragspänning vinkelrätt fibrer"),
            _post("f_t_90_eff", r"k_{t,90} f_{t,90,d}", f_t_90_eff, "MPa", "effektiv draghållfasthet"),
        ]
    )

    ekvationer_items = [
        _ekvation(r"l_A = x - d/2", "avstånd till hålkant"),
        _ekvation(r"l_v = x - d/2 + 100", "avstånd enligt figur 5.5"),
        _ekvation(r"h_{ro} = h/2 - d/2", "höjd över runt hål i neutral linje"),
        _ekvation(r"h_{ru} = h/2 - d/2", "höjd under runt hål i neutral linje"),
    ]
    if anvand_direkta_snittkrafter:
        ekvationer_items.extend(
            [
                _ekvation(r"V_d = |V_{Ed}|", "direkt inmatad tvärkraft"),
                _ekvation(r"M_d = M_{Ed}", "direkt inmatat moment"),
            ]
        )
    else:
        ekvationer_items.extend(
            [
                _ekvation(r"q_d = s(1.2E_g + 1.5Q_k)", "dimensionerande linjelast"),
                _ekvation(r"V_d = |q_d(L/2 - x)|", "tvärkraft vid hål"),
                _ekvation(r"M_d = q_d(Lx/2 - x^2/2)", "moment vid hål"),
            ]
        )
    ekvationer_items.extend(
        [
            _ekvation(r"k_h = \min(1.1, (600/h)^{0.1})", "höjdfaktor för böjhållfasthet"),
            _ekvation(r"f_{t,90,d} = \frac{k_{mod} f_{t,90,k}}{\gamma_m}", "dimensionerande draghållfasthet vinkelrätt fibrer"),
            _ekvation(r"f_{m,g,d} = k_h\frac{k_{mod} f_{m,g,k}}{\gamma_m}", "dimensionerande böjhållfasthet"),
            _ekvation(r"f_{v,g,d} = \frac{k_{mod} f_{v,g,k}}{\gamma_m}", "dimensionerande skjuvhållfasthet"),
            _ekvation(r"F_{ax,Rd} = \frac{k_{mod}}{\gamma_m}F_{ax,Rk}", "dimensionerande axiell skruvbärförmåga"),
            _ekvation(r"k_{cr} = \min(3.0/f_{v,g,k}, 1.0)", "sprickfaktor"),
            _ekvation(r"b_{ef} = k_{cr}b", "effektiv bredd med sprickfaktor"),
            _ekvation(r"A_{red} = b_{ef}h - h_d b_{ef}", "reducerad tvärsnittsarea"),
            _ekvation(r"\tau_d = 1.5\frac{V_d}{A_{red}}", "skjuvspänning i reducerat tvärsnitt"),
            _ekvation(r"\mu_v = \frac{\tau_d}{f_{v,g,d}}", "utnyttjande skjuvning"),
            _ekvation(r"I_y = 2\left(\frac{b h_{ro}^3}{12} + b h_{ro}(0.5h_{ro}+d/2)^2\right)", "tröghetsmoment reducerat tvärsnitt"),
            _ekvation(r"\sigma_{m,d} = \frac{M_d}{I_y}\frac{h}{2}", "böjspänning"),
            _ekvation(r"\mu_m = \frac{\sigma_{m,d}}{f_{m,g,d}}", "utnyttjande moment"),
            _ekvation(r"\mu_{vm} = \mu_v + \mu_m", "interaktion moment och tvärkraft"),
            _ekvation(r"h_r = \min(h_{ru} + 0.15h_d, h_{ro} + 0.15h_d)", "effektiv kantzon"),
            _ekvation(r"l_{t,90} = 0.35h_d + 0.5h", "effektiv längd drag vinkelrätt fibrer"),
            _ekvation(r"k_{t,90} = \min(1, \sqrt{450/h})", "storleksfaktor"),
            _ekvation(r"F_{t,90,V} = \frac{V_dh_d}{4h}\left(3-\frac{h_d^2}{h^2}\right)", "dragkraft från tvärkraft"),
            _ekvation(r"F_{t,90,M} = 0.008\frac{M_d}{h_r}", "dragkraft från moment"),
            _ekvation(r"F_{t,90} = F_{t,90,V} + F_{t,90,M}", "samlad dragkraft vinkelrätt fibrer"),
            _ekvation(r"\sigma_{t,90} = \frac{F_{t,90}}{0.5l_{t,90}b}", "dragspänning vinkelrätt fibrer"),
            _ekvation(r"\mu_{t,90} = \frac{\sigma_{t,90}}{k_{t,90}f_{t,90,d}}", "utnyttjande drag vinkelrätt fiberriktningen"),
            _ekvation(r"\mu_{skruv} = F_{t,90}/F_{ax,Rd}", "utnyttjande skruvförstärkning"),
        ]
    )

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Funktionen kontrollerar cirkulärt hål i limträbalk. "
                        "Placeringskrav kontrolleras enligt tabell 5.2 och "
                        "bärförmåga kontrolleras för reducerat tvärsnitt, "
                        "drag vinkelrätt fiberriktningen kring hål samt valfri "
                        "förstärkning med självborrande träskruvar."
                    ),
                },
                {
                    "rubrik": "Källa",
                    "text": "Limträhandboken Del 2, avsnitt om håltagning i limträbalk.",
                },
                {
                    "rubrik": "Begränsning",
                    "text": (
                        "Funktionen avser cirkulärt hål placerat i balkens neutrala "
                        "linje. Förstärkning med "
                        "plåt/förstärkningsjärn ingår inte."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": indata_items,
        },
        "delresultat": {
            "title": "Delresultat",
            "items": delresultat_items,
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": slutresultat_items,
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": ekvationer_items,
        },
    }


haltagning_limtrabalk.panel_schema = {
    "title": "Håltagning i limträbalk",
    "px": [
        "L",
        "b",
        "h",
        "s",
        "x",
        "d",
        "l_z",
        "anvand_direkta_snittkrafter",
        "E_g",
        "Q_k",
        "V_Ed",
        "M_Ed",
        "k_mod",
        "gamma_m",
        "f_v_g_k",
        "f_m_g_k",
        "f_t_90_k",
        "F_ax_Rk",
        "kontrollera_forstarkning",
    ],
    "fields": [
        {"name": "L", "type": "float", "label": "Balklängd", "symbol": "<i>L</i>", "unit": "mm", "default": 3900.0},
        {"name": "b", "type": "float", "label": "Balkbredd", "symbol": "<i>b</i>", "unit": "mm", "default": 45.0},
        {"name": "h", "type": "float", "label": "Balkhöjd", "symbol": "<i>h</i>", "unit": "mm", "default": 220.0},
        {"name": "s", "type": "float", "label": "c/c-avstånd", "symbol": "<i>s</i>", "unit": "mm", "default": 600.0},
        {"name": "x", "type": "float", "label": "Från stöd till centrum hål", "symbol": "<i>x</i>", "unit": "mm", "default": 300.0},
        {"name": "d", "type": "float", "label": "Håldiameter", "symbol": "<i>d</i>", "unit": "mm", "default": 115.0},
        {"name": "l_z", "type": "float", "label": "Avstånd mellan hål eller fri zon", "symbol": "<i>l</i><sub>z</sub>", "unit": "mm", "default": 300.0},
        {
            "name": "anvand_direkta_snittkrafter",
            "type": "bool",
            "label": "Ange direkta snittkrafter",
            "symbol": "",
            "default": False,
        },
        {
            "name": "E_g",
            "type": "float",
            "label": "Egentyngd",
            "symbol": "<i>E</i><sub>g</sub>",
            "unit": "kN/m²",
            "default": 0.84,
            "visible_if": {"field": "anvand_direkta_snittkrafter", "equals": False},
        },
        {
            "name": "Q_k",
            "type": "float",
            "label": "Nyttig last",
            "symbol": "<i>Q</i><sub>k</sub>",
            "unit": "kN/m²",
            "default": 2.0,
            "visible_if": {"field": "anvand_direkta_snittkrafter", "equals": False},
        },
        {
            "name": "V_Ed",
            "type": "float",
            "label": "Dimensionerande tvärkraft",
            "symbol": "<i>V</i><sub>Ed</sub>",
            "unit": "kN",
            "default": 4.0,
            "visible_if": {"field": "anvand_direkta_snittkrafter", "equals": True},
        },
        {
            "name": "M_Ed",
            "type": "float",
            "label": "Dimensionerande moment",
            "symbol": "<i>M</i><sub>Ed</sub>",
            "unit": "kNm",
            "default": 1.3,
            "visible_if": {"field": "anvand_direkta_snittkrafter", "equals": True},
        },
        {"name": "k_mod", "type": "float", "label": "Modifieringsfaktor", "symbol": "<i>k</i><sub>mod</sub>", "default": 0.8},
        {"name": "gamma_m", "type": "float", "label": "Partialkoefficient trä", "symbol": "γ<sub>m</sub>", "default": 1.3},
        {"name": "f_v_g_k", "type": "float", "label": "Karakteristisk skjuvhållfasthet", "symbol": "<i>f</i><sub>v,g,k</sub>", "unit": "MPa", "default": 4.0},
        {"name": "f_m_g_k", "type": "float", "label": "Karakteristisk böjhållfasthet", "symbol": "<i>f</i><sub>m,g,k</sub>", "unit": "MPa", "default": 24.0},
        {"name": "f_t_90_k", "type": "float", "label": "Karakteristisk draghållfasthet vinkelrätt fibrer", "symbol": "<i>f</i><sub>t,90,k</sub>", "unit": "MPa", "default": 0.4},
        {
            "name": "F_ax_Rk",
            "type": "float",
            "label": "Karakteristisk axiell bärförmåga per skruv",
            "symbol": "<i>F</i><sub>ax,Rk</sub>",
            "unit": "kN",
            "default": 2.08,
        },
        {
            "name": "kontrollera_forstarkning",
            "type": "bool",
            "label": "Kontrollera skruvförstärkning",
            "symbol": "",
            "default": True,
        },
    ],
}
