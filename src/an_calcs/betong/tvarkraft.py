"""Tvärkraft enligt SS-EN 1992-1-1:2005, 6.2.2 och 6.2.3 (normalbetong)."""

import math
from collections.abc import Mapping


_GRUNDINDATA = ("b_w", "d", "f_ck", "A_sl", "phi_w", "n_skar", "s", "f_ywk")
_STANDARD = {
    "N_Ed": 0.0, "A_c": None,
    "kontrollera_last": False, "V_Ed": None,
    "reducera_tvarkraft": False, "a_v": None, "m_eff": 0,
    "cot_theta": 2.5, "cot_theta_min": 1.0, "cot_theta_max": 2.5,
    "alpha": 90.0, "z_auto": True, "z_manuell": None,
    "gamma_c": 1.5, "gamma_s": 1.15, "alpha_cc": 1.0,
}
_PX_NAMN = _GRUNDINDATA + tuple(_STANDARD)


def _post(namn, latex, value, unit="", etikett="", decimals=3):
    return {"namn": namn, "latex": latex, "value": value, "unit": unit,
            "etikett": etikett, "decimals": decimals}


def _ekvation(latex, etikett):
    return {"latex": latex, "etikett": etikett}


def _tal(namn, value, *, minimum=None, maximum=None, heltal=False):
    if isinstance(value, bool):
        raise ValueError(f"{namn} måste vara ett ändligt tal, inte ett booleskt värde.")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{namn} måste vara ett ändligt tal.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{namn} måste vara ett ändligt tal.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{namn} måste vara >= {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{namn} måste vara <= {maximum}.")
    if heltal and not value.is_integer():
        raise ValueError(f"{namn} måste vara ett heltal.")
    return int(value) if heltal else value


def _positivt(namn, value):
    value = _tal(namn, value)
    if value <= 0:
        raise ValueError(f"{namn} måste vara > 0.")
    return value


def _tolka_px(px):
    if isinstance(px, Mapping):
        if set(px) - set(_PX_NAMN):
            raise ValueError(f"Okända indata: {sorted(set(px) - set(_PX_NAMN), key=str)}.")
        saknade = [name for name in _GRUNDINDATA if name not in px]
        if saknade:
            raise ValueError(f"Saknade indata: {', '.join(saknade)}.")
        v = {**_STANDARD, **px}
        if "kontrollera_last" not in px and px.get("V_Ed") is not None:
            v["kontrollera_last"] = True
    elif isinstance(px, (list, tuple)) and len(px) in (8, len(_PX_NAMN)):
        v = {**_STANDARD, **dict(zip(_PX_NAMN, px))}
    else:
        raise ValueError(
            f"px för Tvärkraft måste vara en dictionary eller lista/tuple med 8 eller {len(_PX_NAMN)} värden."
        )

    for name in ("kontrollera_last", "reducera_tvarkraft", "z_auto"):
        if not isinstance(v[name], bool):
            raise ValueError(f"{name} måste vara True eller False.")
    for name in ("b_w", "d", "s", "f_ywk"):
        v[name] = _positivt(name, v[name])
    v["f_ck"] = _tal("f_ck", v["f_ck"], minimum=12, maximum=90)
    for name in ("A_sl", "phi_w"):
        v[name] = _tal(name, v[name], minimum=0)
    v["n_skar"] = _tal("n_skar", v["n_skar"], minimum=0, heltal=True)
    if v["n_skar"] and v["phi_w"] == 0:
        raise ValueError("phi_w måste vara > 0 när n_skar > 0.")
    for name in ("gamma_c", "gamma_s"):
        v[name] = _tal(name, v[name], minimum=1)
    v["alpha_cc"] = _tal("alpha_cc", v["alpha_cc"], minimum=0.8, maximum=1)
    # Denna normprofil använder EC2:s rekommenderade intervall. Egna snävare
    # gränser kan väljas, men inte en annan nationell profil via större intervall.
    for name in ("cot_theta_min", "cot_theta_max"):
        v[name] = _tal(name, v[name], minimum=1, maximum=2.5)
    if v["cot_theta_min"] > v["cot_theta_max"]:
        raise ValueError("cot_theta_min får inte överstiga cot_theta_max.")
    v["cot_theta"] = _tal("cot_theta", v["cot_theta"],
                           minimum=v["cot_theta_min"], maximum=v["cot_theta_max"])
    v["alpha"] = _tal("alpha", v["alpha"], minimum=45, maximum=90)
    v["N_Ed"] = _tal("N_Ed", v["N_Ed"])
    v["A_c"] = _positivt("A_c", v["A_c"]) if v["N_Ed"] else None
    if v["z_auto"]:
        if v["N_Ed"] != 0:
            raise ValueError("Vid N_Ed != 0 krävs z_auto=False och ett manuellt z_manuell.")
        v["z_manuell"] = None
    else:
        v["z_manuell"] = _positivt("z_manuell", v["z_manuell"])
        if v["z_manuell"] > v["d"]:
            raise ValueError("z_manuell får inte överstiga d.")
    v["V_Ed"] = _tal("V_Ed", v["V_Ed"], minimum=0) if v["kontrollera_last"] else None
    if v["reducera_tvarkraft"]:
        if not v["kontrollera_last"]:
            raise ValueError("Tvärkraftsreduktion kräver kontrollera_last=True och V_Ed.")
        v["a_v"] = _positivt("a_v", v["a_v"])
        v["m_eff"] = (_tal("m_eff", v["m_eff"], minimum=0, heltal=True)
                      if v["a_v"] <= 2 * v["d"] else 0)
        if v["m_eff"] > 0 and v["n_skar"] == 0:
            raise ValueError("m_eff > 0 kräver bygelarmering (n_skar > 0).")
    else:
        v["a_v"], v["m_eff"] = None, 0
    return v


def _kontroll(namn, last, kapacitet, etikett):
    """Nollkapacitet får aldrig ge godkänt för en positiv last eller NaN/inf."""
    eta = last / kapacitet if kapacitet > 0 else (0.0 if last == 0 else None)
    return [
        _post("eta_" + namn, r"\eta_{\mathrm{" + namn.replace("_", ".") + "}}",
              100 * eta if eta is not None else "Ingen bärförmåga",
              "procent" if eta is not None else "", etikett, decimals=1),
        _post("status_" + namn, "", "Uppfyller" if last <= kapacitet else "Överskriden", "", etikett),
    ]


def Tvärkraft(px):
    r"""Beräknar tvärkraftsbärförmåga enligt EC2 6.2.2 och 6.2.3.

    Kortformat (endast kapacitet, standardinställningar)::

        [b_w, d, f_ck, A_sl, phi_w, n_skar, s, f_ywk]

    Fullformat, även använt av Panel, lägger till i denna ordning::

        [N_Ed, A_c, kontrollera_last, V_Ed, reducera_tvarkraft, a_v, m_eff,
         cot_theta, cot_theta_min, cot_theta_max, alpha, z_auto, z_manuell,
         gamma_c, gamma_s, alpha_cc]

    En dictionary kan användas med de åtta grundindata och valfria namngivna
    tillägg. V_Ed aktiverar då lastkontrollen om inget annat anges uttryckligen.
    Enheter: mm, mm², MPa och kN. N_Ed är positiv vid tryck; V_Ed är ett belopp.
    A_c används endast vid normalkraft, som också kräver manuellt z.
    n_skar=0 anger ingen tvärkraftsarmering. m_eff är det faktiska antalet lika
    byglar som korsar skjuvsprickan inom centrala 0,75a_v, inte antalet skär.

    Rekommenderade EC2-värden för varaktig/tillfällig situation är förvalda;
    ingen svensk nationell bilaga väljs implicit. cot_theta_min/max kan snäva
    in intervallet 1..2,5. V_Rd är min(V_Rd_s, V_Rd_max) utan lastreduktion.
    V_Rd_c_last och V_Rd_s_last är gränser för den OREDUCERADE inmatade lasten
    med vald reduktionsmetod. Kontrollerna eta_6_2_2/eta_6_2_3 redovisas i %.

    Vid reduktion förutsätts hela V_Ed komma från reducerbar last på översidan
    och längsarmeringen vara fullt förankrad. 6.2.3(8) använder (6.19) samt
    oreducerad last mot (6.9), även för lutande byglar enligt hänvisningen där.
    För a_v > 2d används ordinarie tvärkraftsmodell utan reduktion.
    Detaljutformning, minimiarmering, förankringsdimensionering, böjning och
    kontroll av längsarmeringens totala dragkraft ingår inte.
    """
    v = _tolka_px(px)
    try:
        return _berakna(v)
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("Indata ger värden utanför beräkningens numeriska område.") from exc


def _berakna(v):
    bw, d, fck, Asl = (v[n] for n in ("b_w", "d", "f_ck", "A_sl"))
    fcd = v["alpha_cc"] * fck / v["gamma_c"]
    fywd = v["f_ywk"] / v["gamma_s"]
    sigma_cp = 1000 * v["N_Ed"] / v["A_c"] if v["N_Ed"] else 0.0
    if sigma_cp >= 0.2 * fcd:
        raise ValueError("6.2.2 kräver sigma_cp < 0,2 f_cd; högre tryckspänning ingår inte i modellen.")
    k = min(2.0, 1 + math.sqrt(200 / d))
    rho_l_raw = Asl / (bw * d)
    rho_l = min(0.02, rho_l_raw)
    C_Rdc, k1 = 0.18 / v["gamma_c"], 0.15
    vmin = 0.035 * k**1.5 * math.sqrt(fck)
    VRdc_a = (C_Rdc * k * (100 * rho_l * fck)**(1 / 3) + k1 * sigma_cp) * bw * d / 1000
    VRdc_b = (vmin + k1 * sigma_cp) * bw * d / 1000
    VRdc = max(0.0, VRdc_a, VRdc_b)
    z = 0.9 * d if v["z_auto"] else v["z_manuell"]
    Asw = v["n_skar"] * math.pi * v["phi_w"]**2 / 4
    ct = v["cot_theta"]
    sin_alpha = math.sin(math.radians(v["alpha"]))
    cot_alpha = 0.0 if v["alpha"] == 90 else min(1.0, 1 / math.tan(math.radians(v["alpha"])))
    nu = 0.6 * (1 - fck / 250)
    alpha_cw = 1.0  # Ingen förspänning; 6.2.3, anm. 3.
    VRds = Asw / v["s"] * z * fywd * (ct + cot_alpha) * sin_alpha / 1000
    VRdmax = alpha_cw * bw * z * nu * fcd * (ct + cot_alpha) / (1 + ct**2) / 1000
    VRdmax_6_9 = alpha_cw * bw * z * nu * fcd / (ct + 1 / ct) / 1000
    VRd = min(VRds, VRdmax)
    Vlim_6_5 = 0.5 * bw * d * nu * fcd / 1000
    kort_skjuvspann = v["reducera_tvarkraft"] and v["a_v"] <= 2 * d
    beta = min(1.0, max(0.25, v["a_v"] / (2 * d))) if v["reducera_tvarkraft"] else 1.0
    Asw_eff = v["m_eff"] * Asw if kort_skjuvspann else 0.0
    VRd_6_19 = Asw_eff * fywd * sin_alpha / 1000
    Vc_last = min(VRdc / beta, Vlim_6_5) if kort_skjuvspann else VRdc
    Vs_last = min(VRd_6_19 / beta, VRdmax_6_9) if kort_skjuvspann else VRd
    numeric = (fcd, fywd, sigma_cp, rho_l_raw, VRdc_a, VRdc_b, z, Asw, VRds,
               VRdmax, VRdmax_6_9, Vlim_6_5, Asw_eff, VRd_6_19, Vc_last, Vs_last)
    if not all(math.isfinite(x) for x in numeric):
        raise ValueError("Indata ger värden utanför beräkningens numeriska område.")

    # Endast aktiva indata redovisas; d förekommer en gång även vid reduktion.
    metadata = {
        "b_w": (r"b_w", "mm", "gemensam minsta bredd för 6.2.2 och 6.2.3"),
        "d": ("d", "mm", "effektiv höjd"),
        "f_ck": (r"f_{ck}", "MPa", "karakteristisk cylindertryckhållfasthet"),
        "A_sl": (r"A_{sl}", "mm^2", "längsdragarmering som uppfyller figur 6.3"),
        "phi_w": (r"\phi_w", "mm", "bygeldiameter"),
        "n_skar": (r"n", "", "antal verksamma skär per bygel"),
        "s": ("s", "mm", "byglarnas centrumavstånd längs balken"),
        "f_ywk": (r"f_{ywk}", "MPa", "karakteristisk sträckgräns för byglar"),
        "N_Ed": (r"N_{Ed}", "kN", "normalkraft, positiv vid tryck"),
        "A_c": (r"A_c", "mm^2", "betongtvärsnittsarea"),
        "V_Ed": (r"V_{Ed}", "kN", "dimensionerande tvärkraft utan reduktion"),
        "a_v": (r"a_v", "mm", "lastavstånd enligt figur 6.4 och 6.6"),
        "m_eff": (r"m_{eff}", "", "verksamma byglar i centrala 0,75 a_v"),
        "cot_theta": (r"\cot\theta", "", "vald trycksträvelutning"),
        "cot_theta_min": (r"\cot\theta_{min,val}", "", "undre gräns för cot(theta)"),
        "cot_theta_max": (r"\cot\theta_{max,val}", "", "övre gräns för cot(theta)"),
        "alpha": (r"\alpha", "°", "bygelvinkel mot längdaxeln"),
        "z_manuell": (r"z_{man}", "mm", "manuellt angiven inre hävarm"),
        "gamma_c": (r"\gamma_c", "", "partialkoefficient för betong"),
        "gamma_s": (r"\gamma_s", "", "partialkoefficient för armering"),
        "alpha_cc": (r"\alpha_{cc}", "", "koefficient för betongtryckhållfasthet"),
    }
    indata = []
    for name in _PX_NAMN:
        if name in metadata and v[name] is not None and (name != "m_eff" or kort_skjuvspann):
            latex, unit, label = metadata[name]
            indata.append(_post(name, latex, v[name], unit, label))
    indata.extend([
        _post("z_auto", "", "0,9 d" if v["z_auto"] else "Manuell", "", "val av inre hävarm"),
        _post("reducera_tvarkraft", "", "På" if v["reducera_tvarkraft"] else "Av", "", "tvärkraftsreduktion"),
    ])
    mellan = [
        _post("f_cd", r"f_{cd}", fcd, "MPa", "dimensionerande betongtryckhållfasthet"),
        _post("f_ywd", r"f_{ywd}", fywd, "MPa", "dimensionerande sträckgräns"),
        _post("sigma_cp", r"\sigma_{cp}", sigma_cp, "MPa", "normalspänning, positiv vid tryck"),
        _post("sigma_cp_grans", r"0{,}2f_{cd}", 0.2 * fcd, "MPa", "strikt övre tillämpningsgräns"),
        _post("k", "k", k, "", "höjdfaktor, högst 2,0"),
        _post("rho_l_obegransad", r"\rho_{l,obegr}", rho_l_raw, "", "armeringskvot före begränsning", 6),
        _post("rho_l", r"\rho_l", rho_l, "", "medräknad armeringskvot, högst 0,02", 6),
        _post("C_Rd_c", r"C_{Rd,c}", C_Rdc, "", "0,18 / gamma_c"),
        _post("k_1", r"k_1", k1, "", "koefficient för normalspänning"),
        _post("v_min", r"v_{min}", vmin, "MPa", "minsta skjuvhållfasthet före normalkraftsbidrag"),
        _post("V_Rd_c_6_2a", r"V_{Rd,c,a}", VRdc_a, "kN", "uttryck (6.2a)"),
        _post("V_Rd_c_6_2b", r"V_{Rd,c,b}", VRdc_b, "kN", "uttryck (6.2b)"),
        _post("A_sw", r"A_{sw}", Asw, "mm^2", "verksam area per bygel"),
        _post("A_sw_per_m", r"A_{sw}/s", Asw / v["s"] * 1000, "mm^2/m", "tvärkraftsarmering per längdmeter"),
        _post("z", "z", z, "mm", "använd inre hävarm"),
        _post("theta", r"\theta", math.degrees(math.atan(1 / ct)), "°", "trycksträvans vinkel"),
        _post("nu_1", r"\nu_1=\nu", nu, "", "hållfasthetsreduktion enligt (6.6N)"),
        _post("alpha_cw", r"\alpha_{cw}", alpha_cw, "", "ingen förspänning"),
        _post("beta", r"\beta", beta, "", "lastreduktionsfaktor"),
    ]
    resultat = [
        _post("V_Rd_c", r"V_{Rd,c}", VRdc, "kN", "6.2.2, utan beräknad tvärkraftsarmering"),
        _post("V_Rd_s", r"V_{Rd,s}", VRds, "kN", "6.2.3, ordinarie modell, armeringens begränsning"),
        _post("V_Rd_max", r"V_{Rd,max}", VRdmax, "kN", "6.2.3, ordinarie modell, trycksträvans begränsning"),
        _post("V_Rd", r"V_{Rd}", VRd, "kN", "6.2.3, minsta ordinarie bärförmåga före lastreduktion"),
    ]
    if kort_skjuvspann:
        mellan.extend([
            _post("l_eff", r"0{,}75a_v", 0.75 * v["a_v"], "mm", "centralt område för verksamma byglar"),
            _post("A_sw_eff", r"A_{sw,eff}", Asw_eff, "mm^2", "verksam bygelarea för (6.19)"),
        ])
        resultat.extend([
            _post("V_lim_6_5", r"V_{lim,6.5}", Vlim_6_5, "kN", "gräns för oreducerad last enligt (6.5)"),
            _post("V_Rd_6_19", r"V_{Rd,6.19}", VRd_6_19, "kN", "bärförmåga mot reducerad last enligt (6.19)"),
            _post("V_Rd_max_6_9", r"V_{Rd,max,6.9}", VRdmax_6_9, "kN", "gräns för oreducerad last enligt hänvisningen i 6.2.3(8)"),
        ])
    resultat.extend([
        _post("V_Rd_c_last", r"V_{Rd,c,last}", Vc_last, "kN", "6.2.2, gräns för oreducerad inmatad last med vald metod"),
        _post("V_Rd_s_last", r"V_{Rd,s,last}", Vs_last, "kN", "6.2.3, gräns för oreducerad inmatad last med vald metod"),
    ])
    if v["kontrollera_last"]:
        VEd, Vred = v["V_Ed"], beta * v["V_Ed"]
        resultat.append(_post("V_Ed_red", r"V_{Ed,red}", Vred, "kN", "tvärkraft efter vald reduktion"))
        if kort_skjuvspann:
            resultat.extend(_kontroll("c_reducerad", Vred, VRdc, "reducerad tvärkraft mot V_Rd,c"))
            resultat.extend(_kontroll("c_oreducerad", VEd, Vlim_6_5, "oreducerad tvärkraft enligt (6.5)"))
            resultat.extend(_kontroll("s_reducerad", Vred, VRd_6_19, "reducerad tvärkraft enligt (6.19)"))
            resultat.extend(_kontroll("s_oreducerad", VEd, VRdmax_6_9, "oreducerad tvärkraft mot (6.9)"))
        resultat.extend(_kontroll("6_2_2", VEd, Vc_last, "bärförmågekontroll enligt 6.2.2"))
        resultat.extend(_kontroll("6_2_3", VEd, Vs_last, "bärförmågekontroll enligt 6.2.3"))
        mellan.append(_post("Delta_F_td", r"\Delta F_{td}",
                            0.5 * VEd * (ct - cot_alpha), "kN",
                            "dragkraftstillägg enligt (6.18), oreducerad last, utan momentbegränsningen"))

    ekvationer = [
        _ekvation(r"f_{cd}=\alpha_{cc}f_{ck}/\gamma_c,\qquad f_{ywd}=f_{ywk}/\gamma_s", "dimensionerande materialvärden"),
        _ekvation(r"k=\min(1+\sqrt{200/d},2),\quad\rho_l=\min(A_{sl}/(b_wd),0{,}02)", "d i mm, 6.2.2(1)"),
        _ekvation(r"\sigma_{cp}=1000N_{Ed}/A_c<0{,}2f_{cd}", "N_Ed i kN; sigma_cp=0 när N_Ed=0"),
        _ekvation(r"C_{Rd,c}=0{,}18/\gamma_c,\quad k_1=0{,}15,\quad v_{min}=0{,}035k^{3/2}\sqrt{f_{ck}}", "rekommenderade värden i 6.2.2(1), f_ck i MPa"),
        _ekvation(r"V_{Rd,c,a}=[C_{Rd,c}k(100\rho_l f_{ck})^{1/3}+k_1\sigma_{cp}]b_wd/1000", "(6.2a), resultat i kN"),
        _ekvation(r"V_{Rd,c,b}=(v_{min}+k_1\sigma_{cp})b_wd/1000,\quad V_{Rd,c}=\max(0,V_{Rd,c,a},V_{Rd,c,b})", "(6.2b), negativ beräknad bärförmåga ger noll tillgänglig kapacitet"),
        _ekvation(r"A_{sw}=n\pi\phi_w^2/4", "summa verksamma skär i en bygel"),
        _ekvation(r"z=0{,}9d" if v["z_auto"] else r"z=z_{man}", "vald inre hävarm"),
        _ekvation(r"1\leq\cot\theta_{min,val}\leq\cot\theta\leq\cot\theta_{max,val}\leq2{,}5", "vald begränsning inom (6.7N)"),
        _ekvation(r"\nu_1=\nu=0{,}6(1-f_{ck}/250),\quad\alpha_{cw}=1", "(6.6N), ej förspänd betong"),
        _ekvation(r"V_{Rd,s}=\frac{A_{sw}}s zf_{ywd}(\cot\theta+\cot\alpha)\sin\alpha/1000", "(6.13), blir (6.8) för alpha=90 grader"),
        _ekvation(r"V_{Rd,max}=\alpha_{cw}b_wz\nu_1f_{cd}\frac{\cot\theta+\cot\alpha}{1+\cot^2\theta}/1000", "(6.14), blir (6.9) för alpha=90 grader"),
        _ekvation(r"V_{Rd}=\min(V_{Rd,s},V_{Rd,max})", "ordinarie bärförmåga utan lastreduktion; inget tillskott av V_Rd,c"),
    ]
    if v["reducera_tvarkraft"]:
        ekvationer.append(_ekvation(r"\beta=\min(1,\max(0{,}25,a_v/(2d))),\quad V_{Ed,red}=\beta V_{Ed}", "6.2.2(6) och 6.2.3(8)"))
    if kort_skjuvspann:
        ekvationer.extend([
            _ekvation(r"V_{lim,6.5}=0{,}5b_wd\nu f_{cd}/1000,\quad V_{Ed}\leq V_{lim,6.5}", "(6.5), oreducerad tvärkraft"),
            _ekvation(r"A_{sw,eff}=m_{eff}A_{sw},\quad V_{Rd,6.19}=A_{sw,eff}f_{ywd}\sin\alpha/1000", "(6.19), endast verksamma byglar i centrala 0,75a_v"),
            _ekvation(r"V_{Ed,red}\leq V_{Rd,6.19},\quad V_{Rd,max,6.9}=\frac{\alpha_{cw}b_wz\nu_1f_{cd}}{\cot\theta+\tan\theta}/1000", "6.2.3(8), separat kontroll av oreducerad last mot (6.9)"),
            _ekvation(r"V_{Rd,c,last}=\min(V_{Rd,c}/\beta,V_{lim,6.5})", "samlad gräns för oreducerad last, 6.2.2"),
            _ekvation(r"V_{Rd,s,last}=\min(V_{Rd,6.19}/\beta,V_{Rd,max,6.9})", "samlad gräns för oreducerad last, 6.2.3(8)"),
        ])
    if v["kontrollera_last"]:
        ekvationer.extend([
            _ekvation(r"\eta_{6\_2\_2}=100V_{Ed}/V_{Rd,c,last},\quad\eta_{6\_2\_3}=100V_{Ed}/V_{Rd,s,last}", "utnyttjandegrader i procent, respektive bärförmågekontroll"),
            _ekvation(r"\Delta F_{td}=0{,}5V_{Ed}(\cot\theta-\cot\alpha)", "(6.18), ingen kontroll av total längsdragkraft eller begränsning med M_Ed,max/z"),
        ])
    metod = [
        {"rubrik": "Omfattning", "text": (
            "SS-EN 1992-1-1:2005, 6.2.2(1), 6.2.2(6) och 6.2.3. Normalbetong "
            "med konstant tvärsnitt och parallella ramstänger, utan förspänning eller foderrör. "
            "Gemensamt b_w ska uppfylla bredddefinitionerna i båda avsnitten. "
            "Osprucken förspänd betong enligt (6.4) ingår inte. Beräkningen gäller ett angivet snitt."
        )},
        {"rubrik": "Förankring och detaljutformning", "text": (
            "A_sl omfattar endast längsdragarmering som når minst l_bd+d bortom snittet enligt figur 6.3. "
            "Byglarna ska vara verksamma och förankrade. Minimiarmering, bygelavståndsgränser, "
            "förankringsdimensionering, böjning och kontroll av längsarmeringens totala dragkraft ingår inte. "
            "Uppfyller avser enbart respektive redovisad bärförmågekontroll."
        )},
        {"rubrik": "Beräkningsinställningar", "text": (
            "EC2:s rekommenderade värden används för C_Rd,c, k_1, v_min och nu_1, "
            "och alpha_cw=1 för ej förspända bärverk. Ingen svensk nationell bilaga väljs automatiskt. "
            "Materialfaktorer och cot(theta) redovisas med sina använda värden. "
            "Valbara cot-gränser ligger inom 1,0-2,5. Automatiskt z=0,9d gäller endast utan normalkraft."
        )},
        {"rubrik": "Tvärkraftsreduktion", "text": (
            "Aktiverad reduktion förutsätter att hela V_Ed kommer från reducerbar last på översidan, "
            "med lastöverföring enligt figur 6.4/6.6 och fullt förankrad längsarmering vid upplaget. "
            "Andra lastbidrag ingår inte i denna förenklade inmatning. Vid a_v<=2d kontrolleras "
            "reducerad last mot V_Rd,c respektive (6.19), och oreducerad last separat mot (6.5) "
            "respektive (6.9). m_eff är verkligt antal verksamma byglar inom centrala 0,75a_v; "
            "antalet härleds inte från s. Vid a_v>2d används ordinarie modell med beta=1. "
            "V_Rd,c,last och V_Rd,s,last avser gränser för den oreducerade inmatade lasten."
        )},
        {"rubrik": "Enheter", "text": "Mått i mm, areor i mm², hållfastheter i MPa och krafter i kN. Alla hållfasthetsuttryck omvandlas från N till kN genom division med 1000."},
    ]
    for item in indata + mellan + resultat:
        if isinstance(item["value"], (int, float)) and not math.isfinite(item["value"]):
            raise ValueError("Indata ger värden utanför beräkningens numeriska område.")
    return {
        "metodbeskrivning": {"title": "Metodbeskrivning", "items": metod},
        "indata": {"title": "Indata", "items": indata},
        "delresultat": {"title": "Delresultat", "items": mellan},
        "slutresultat": {"title": "Slutresultat", "items": resultat},
        "ekvationer": {"title": "Ekvationer", "items": ekvationer},
    }


def _falt(name, label, default, unit="", symbol="", typ="float", **extra):
    return {"name": name, "type": typ, "label": label, "default": default,
            "unit": unit, "symbol": symbol, **extra}


_LAST = {"field": "kontrollera_last", "equals": True}
_REDUKTION = {"all": [_LAST, {"field": "reducera_tvarkraft", "equals": True}]}

Tvärkraft.panel_schema = {
    "title": "Tvärkraft - EC2 6.2.2 och 6.2.3",
    "px": list(_PX_NAMN),
    "sections": [
        {"title": "Tvärsnitt och längsarmering", "fields": ["b_w", "d", "A_sl", "N_Ed", "A_c"], "columns": 3},
        {"title": "Material", "fields": ["f_ck", "f_ywk"], "columns": 2},
        {"title": "Tvärkraftsarmering", "fields": ["phi_w", "n_skar", "s", "alpha", "m_eff"], "columns": 3},
        {"title": "Last och tvärkraftsreduktion", "fields": ["kontrollera_last", "V_Ed", "reducera_tvarkraft", "a_v"], "columns": 2},
        {"title": "Beräkningsinställningar", "fields": ["cot_theta", "cot_theta_min", "cot_theta_max", "z_auto", "z_manuell", "gamma_c", "gamma_s", "alpha_cc"], "columns": 3, "collapsible": True, "collapsed": True},
    ],
    "fields": [
        _falt("b_w", "Minsta bredd", 300.0, "mm", "<i>b</i><sub>w</sub>"),
        _falt("d", "Effektiv höjd", 500.0, "mm", "<i>d</i>"),
        _falt("f_ck", "Betongens tryckhållfasthet", 30.0, "MPa", "<i>f</i><sub>ck</sub>"),
        _falt("A_sl", "Medräkningsbar längsdragarmering", 2000.0, "mm²", "<i>A</i><sub>sl</sub>"),
        _falt("phi_w", "Bygeldiameter", 8.0, "mm", "φ<sub>w</sub>"),
        _falt("n_skar", "Verksamma skär per bygel (0 = inga)", 2, "", "<i>n</i>", typ="int"),
        _falt("s", "Bygelavstånd", 200.0, "mm", "<i>s</i>"),
        _falt("f_ywk", "Byglarnas sträckgräns", 500.0, "MPa", "<i>f</i><sub>ywk</sub>"),
        _falt("N_Ed", "Normalkraft, tryck positivt", 0.0, "kN", "<i>N</i><sub>Ed</sub>"),
        _falt("A_c", "Betongtvärsnittsarea", 180000.0, "mm²", "<i>A</i><sub>c</sub>", visible_if={"field": "N_Ed", "not_equals": 0}),
        _falt("kontrollera_last", "Kontrollera angiven tvärkraft", False, typ="bool"),
        _falt("V_Ed", "Tvärkraft före reduktion", 100.0, "kN", "<i>V</i><sub>Ed</sub>", visible_if=_LAST),
        _falt("reducera_tvarkraft", "Reducera tvärkraft nära upplag", False, typ="bool", visible_if=_LAST,
              fixed_if={"field": "kontrollera_last", "equals": False, "value": False}),
        _falt("a_v", "Lastavstånd enligt figur 6.4 / 6.6", 300.0, "mm", "<i>a</i><sub>v</sub>", visible_if=_REDUKTION),
        _falt("m_eff", "Verksamma byglar i centrala 0,75 aᵥ", 0, "st", "<i>m</i><sub>eff</sub>", typ="int", visible_if=_REDUKTION),
        _falt("cot_theta", "Vald cot(θ)", 2.5, "", "cot θ"),
        _falt("cot_theta_min", "Minsta tillåtna cot(θ)", 1.0, "", "cot θ<sub>min,val</sub>"),
        _falt("cot_theta_max", "Största tillåtna cot(θ)", 2.5, "", "cot θ<sub>max,val</sub>"),
        _falt("alpha", "Bygelvinkel", 90.0, "°", "α"),
        _falt("z_auto", "Beräkna z = 0,9 d", True, typ="bool",
              fixed_if={"field": "N_Ed", "not_equals": 0, "value": False}),
        _falt("z_manuell", "Manuell inre hävarm", 450.0, "mm", "<i>z</i>", visible_if={"field": "z_auto", "equals": False}),
        _falt("gamma_c", "Partialkoefficient betong", 1.5, "", "γ<sub>c</sub>"),
        _falt("gamma_s", "Partialkoefficient armering", 1.15, "", "γ<sub>s</sub>"),
        _falt("alpha_cc", "Tryckhållfasthetskoefficient", 1.0, "", "α<sub>cc</sub>"),
    ],
}

# ASCII-alias för kod som följer paketets övriga namnkonvention.
tvarkraft = Tvärkraft
