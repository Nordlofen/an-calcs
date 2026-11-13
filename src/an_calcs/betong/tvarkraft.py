"""Tvärkraft enligt SS-EN 1992-1-1:2005, 6.2.2 och 6.2.3 (normalbetong)."""

import math
from collections.abc import Mapping


_GRUNDINDATA = ("b_w", "d", "f_ck", "A_sl", "phi_w", "n_skar", "s", "f_ywk")
_COT_MIN, _COT_MAX = 1.0, 2.5
_METODER = {"bada": "6.2.2 och 6.2.3", "6.2.2": "Endast 6.2.2", "6.2.3": "Endast 6.2.3"}
_LANGSARMERING = {"area": "Area direkt", "jarn": "Antal och diameter", "cc": "cc och diameter"}
_STANDARD = {
    "N_Ed": 0.0, "A_c": None,
    "kontrollera_last": False, "V_Ed": None,
    "reducera_tvarkraft": False, "a_v": None, "m_eff": 0,
    "cot_theta": 2.5, "alpha": 90.0, "z_auto": True, "z_manuell": None,
    "gamma_c": 1.5, "gamma_s": 1.15, "alpha_cc": 1.0,
    "metod": "bada", "A_sl_inmatning": "area", "n_l": None, "phi_l": None,
    "plattstrimla": False,
    "cc_l": None,
}
_PX_NAMN = _GRUNDINDATA + tuple(_STANDARD)
# Tidigare fullformat läses fortfarande; dess två gränsvärden används inte.
_LEGACY_PX_NAMN = _GRUNDINDATA + (
    "N_Ed", "A_c", "kontrollera_last", "V_Ed", "reducera_tvarkraft", "a_v", "m_eff",
    "cot_theta", "cot_theta_min", "cot_theta_max", "alpha", "z_auto", "z_manuell",
    "gamma_c", "gamma_s", "alpha_cc",
)
_COT_HELP = (
    "Högre cot(θ) ökar tvärkraftsarmeringens kapacitet V_Rd,s, men minskar "
    "betongtrycksträvans kapacitet V_Rd,max. Lägre värde ger motsatt effekt. "
    "V_Rd,c enligt 6.2.2 påverkas inte. "
    "1,0 motsvarar 45° och 2,5 motsvarar 21,8°, mätt mot balkens längdaxel."
)


def _post(namn, latex, value, unit="", etikett="", decimals=3):
    item = {"namn": namn, "latex": latex, "value": value, "unit": unit,
            "etikett": etikett, "decimals": decimals}
    if unit == "kN/m":
        item["sigfigs"] = 3  # Samma precision som kraftposter i kN.
    return item


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
    mapping = isinstance(px, Mapping)
    if mapping:
        if set(px) - set(_PX_NAMN):
            raise ValueError(f"Okända indata: {sorted(set(px) - set(_PX_NAMN), key=str)}.")
        given = dict(px)
    elif isinstance(px, (list, tuple)) and len(px) in (8, len(_LEGACY_PX_NAMN), 26, 27, len(_PX_NAMN)):
        names = _LEGACY_PX_NAMN if len(px) == len(_LEGACY_PX_NAMN) else _PX_NAMN
        given = {name: value for name, value in zip(names, px) if name in _PX_NAMN}
    else:
        raise ValueError("px för Tvärkraft måste vara en dictionary eller lista/tuple med 8, 24, 26, 27 eller 28 värden.")
    v = {**dict.fromkeys(_GRUNDINDATA), **_STANDARD, **given}
    if not isinstance(v["metod"], str) or v["metod"] not in _METODER:
        raise ValueError("metod måste vara 'bada', '6.2.2' eller '6.2.3'.")
    c, s = v["metod"] != "6.2.3", v["metod"] != "6.2.2"
    if c and (not isinstance(v["A_sl_inmatning"], str) or v["A_sl_inmatning"] not in _LANGSARMERING):
        raise ValueError("A_sl_inmatning måste vara 'area', 'jarn' eller 'cc'.")
    if not isinstance(v["plattstrimla"], bool):
        raise ValueError("plattstrimla måste vara True eller False.")
    if v["plattstrimla"]:
        v["b_w"] = 1000.0
    required = ["d", "f_ck"] + ([] if v["plattstrimla"] else ["b_w"])
    if c:
        required += {"area": ["A_sl"], "jarn": ["n_l", "phi_l"], "cc": ["cc_l", "phi_l"]}[v["A_sl_inmatning"]]
    if s:
        required += ["phi_w", "n_skar", "s", "f_ywk"]
    missing = [name for name in required if name not in given or given[name] is None]
    if missing:
        raise ValueError(f"Saknade indata: {', '.join(missing)}.")
    if mapping and "kontrollera_last" not in px and px.get("V_Ed") is not None:
        v["kontrollera_last"] = True
    for name in ("kontrollera_last", "reducera_tvarkraft"):
        if not isinstance(v[name], bool):
            raise ValueError(f"{name} måste vara True eller False.")
    for name in ("b_w", "d"):
        v[name] = _positivt(name, v[name])
    v["f_ck"] = _tal("f_ck", v["f_ck"], minimum=12, maximum=90)
    v["gamma_c"] = _tal("gamma_c", v["gamma_c"], minimum=1)
    v["alpha_cc"] = _tal("alpha_cc", v["alpha_cc"], minimum=0.8, maximum=1)
    v["N_Ed"] = _tal("N_Ed", v["N_Ed"])
    v["A_c"] = _positivt("A_c", v["A_c"]) if c and v["N_Ed"] else None
    if c:
        if v["A_sl_inmatning"] != "area":
            if v["A_sl_inmatning"] == "cc":
                v["cc_l"] = _positivt("cc_l", v["cc_l"])
                v["n_l"] = math.floor(v["b_w"] / v["cc_l"] + 1)
            else:
                v["cc_l"] = None
                v["n_l"] = _tal("n_l", v["n_l"], minimum=0, heltal=True)
            v["phi_l"] = _positivt("phi_l", v["phi_l"])
            v["A_sl"] = v["n_l"] * math.pi * v["phi_l"]**2 / 4
        else:
            v["n_l"], v["phi_l"], v["cc_l"] = None, None, None
        v["A_sl"] = _tal("A_sl", v["A_sl"], minimum=0)
    else:
        for name in ("A_sl_inmatning", "A_sl", "n_l", "phi_l", "cc_l"):
            v[name] = None
    if s:
        for name in ("s", "f_ywk"):
            v[name] = _positivt(name, v[name])
        v["phi_w"] = _tal("phi_w", v["phi_w"], minimum=0)
        v["n_skar"] = _tal("n_skar", v["n_skar"], minimum=0, heltal=True)
        if v["n_skar"] and v["phi_w"] == 0:
            raise ValueError("phi_w måste vara > 0 när n_skar > 0.")
        v["gamma_s"] = _tal("gamma_s", v["gamma_s"], minimum=1)
        v["cot_theta"] = _tal("cot_theta", v["cot_theta"], minimum=_COT_MIN, maximum=_COT_MAX)
        v["alpha"] = _tal("alpha", v["alpha"], minimum=45, maximum=90)
        if not isinstance(v["z_auto"], bool):
            raise ValueError("z_auto måste vara True eller False.")
        if v["z_auto"]:
            if v["N_Ed"] != 0:
                raise ValueError("Vid N_Ed != 0 krävs z_auto=False och ett manuellt z_manuell.")
            v["z_manuell"] = None
        else:
            v["z_manuell"] = _positivt("z_manuell", v["z_manuell"])
            if v["z_manuell"] > v["d"]:
                raise ValueError("z_manuell får inte överstiga d.")
    else:
        for name in ("phi_w", "n_skar", "s", "f_ywk", "gamma_s", "cot_theta", "alpha", "z_auto", "z_manuell"):
            v[name] = None
    v["V_Ed"] = _tal("V_Ed", v["V_Ed"], minimum=0) if v["kontrollera_last"] else None
    if v["reducera_tvarkraft"]:
        if not v["kontrollera_last"]:
            raise ValueError("Tvärkraftsreduktion kräver kontrollera_last=True och V_Ed.")
        v["a_v"] = _positivt("a_v", v["a_v"])
        v["m_eff"] = (_tal("m_eff", v["m_eff"], minimum=0, heltal=True)
                      if s and v["a_v"] <= 2 * v["d"] else None)
        if v["m_eff"] and v["n_skar"] == 0:
            raise ValueError("m_eff > 0 kräver bygelarmering (n_skar > 0).")
    else:
        v["a_v"], v["m_eff"] = None, None
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
    r"""Tvärkraft enligt vald metod: '6.2.2', '6.2.3' eller 'bada' (förval).

    Kortformat (8 värden, båda metoderna)::

        [b_w, d, f_ck, A_sl, phi_w, n_skar, s, f_ywk]

    Panel använder 28 värden; ordningen ges av Tvärkraft.panel_schema["px"].
    Äldre fullformat med 24 och 26 värden stöds utan plattstrimla;
    27-formatet har plattstrimla men inget cc_l. 24-formatets cot-gränser ignoreras.
    Gränserna 1 <= cot_theta <= 2.5 är fasta och kan inte ändras via indata.

    Dictionary rekommenderas vid metodval. Gemensamt krävs b_w, d, f_ck.
    6.2.2 kräver A_sl eller A_sl_inmatning='jarn', n_l och phi_l, varvid
    A_sl=n_l*pi*phi_l**2/4. Alternativt ger A_sl_inmatning='cc', cc_l och
    phi_l antalet n_l=floor(b_w/cc_l+1) och samma areauttryck. cc_l anges i mm.
    6.2.3 kräver phi_w, n_skar, s och f_ywk.
    Inaktiva fält ignoreras. N_Ed != 0 kräver A_c för 6.2.2 och manuellt z
    (z_auto=False, z_manuell) för 6.2.3. V_Ed aktiverar lastkontroll i
    dictionaryformatet om kontrollera_last inte anges uttryckligen.

    Mått i mm, areor i mm², hållfastheter i MPa och krafter i kN.
    plattstrimla=True låser b_w=1000 mm (b_w kan utelämnas). Krafter anges
    och redovisas då i kN/m. Betongarea och armering avser samma strimla.
    n_skar är då skär per bygelrad över strimlans bredd, s radavstånd längs
    strimlan och m_eff antal verksamma rader. Befintliga tal skalas inte om.
    N_Ed är positiv vid tryck, V_Ed är ett belopp. n_skar=0 anger inga byglar.
    m_eff är verkligt antal lika byglar som korsar skjuvsprickan i centrala
    0,75a_v. Det används endast vid reduktion enligt 6.2.3(8).

    Rekommenderade EC2-värden för varaktig/tillfällig situation är förvalda;
    ingen svensk nationell bilaga väljs implicit. V_Rd=min(V_Rd_s,V_Rd_max)
    avser ordinarie modell. Vid reduktion redovisas reducerad och oreducerad
    last mot respektive bärförmåga. Största delutnyttjandet styr slutkontrollen.
    Utnyttjanden ges i %.
    Vid reduktion förutsätts hela V_Ed komma från reducerbar last på översidan
    och längsarmeringen vara fullt förankrad. 6.2.3(8) använder (6.19) samt
    oreducerad last mot (6.9), även vid lutande byglar enligt hänvisningen där.
    a_v>2d ger ordinarie modell. Detaljutformning, minimiarmering, förankrings-
    dimensionering, böjning och total dragkraft i längsarmeringen ingår inte.
    """
    try:
        return _berakna(_tolka_px(px))
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("Indata ger värden utanför beräkningens numeriska område.") from exc


def _berakna(v):
    c, s = v["metod"] != "6.2.3", v["metod"] != "6.2.2"
    strimla = v["plattstrimla"]
    kraftenhet = "kN/m" if strimla else "kN"
    byglar = "bygelrader" if strimla else "byglar"
    bygel = "bygelrad i 1 m strimla" if strimla else "bygel"
    bw, d, fck = (v[n] for n in ("b_w", "d", "f_ck"))
    fcd = v["alpha_cc"] * fck / v["gamma_c"]
    nu = 0.6 * (1 - fck / 250)
    kort_skjuvspann = v["reducera_tvarkraft"] and v["a_v"] <= 2 * d
    beta = min(1.0, max(0.25, v["a_v"] / (2 * d))) if v["reducera_tvarkraft"] else 1.0
    if c:
        sigma_cp = 1000 * v["N_Ed"] / v["A_c"] if v["N_Ed"] else 0.0
        if sigma_cp >= 0.2 * fcd:
            raise ValueError("6.2.2 kräver sigma_cp < 0,2 f_cd; högre tryckspänning ingår inte i modellen.")
        k = min(2.0, 1 + math.sqrt(200 / d))
        rho_l_raw = v["A_sl"] / (bw * d)
        rho_l = min(0.02, rho_l_raw)
        C_Rdc, k1 = 0.18 / v["gamma_c"], 0.15
        vmin = 0.035 * k**1.5 * math.sqrt(fck)
        VRdc_a = (C_Rdc * k * (100 * rho_l * fck)**(1 / 3) + k1 * sigma_cp) * bw * d / 1000
        VRdc_b = (vmin + k1 * sigma_cp) * bw * d / 1000
        VRdc = max(0.0, VRdc_a, VRdc_b)
        Vlim_6_5 = 0.5 * bw * d * nu * fcd / 1000
        # Intern ekvivalent lastgräns för slutkontrollen; redovisas inte som kapacitet.
        Vc_last = min(VRdc / beta, Vlim_6_5) if kort_skjuvspann else VRdc
    if s:
        fywd = v["f_ywk"] / v["gamma_s"]
        z = 0.9 * d if v["z_auto"] else v["z_manuell"]
        Asw = v["n_skar"] * math.pi * v["phi_w"]**2 / 4
        ct = v["cot_theta"]
        sin_alpha = math.sin(math.radians(v["alpha"]))
        cot_alpha = 0.0 if v["alpha"] == 90 else min(1.0, 1 / math.tan(math.radians(v["alpha"])))
        alpha_cw = 1.0  # Ingen förspänning; 6.2.3, anm. 3.
        VRds = Asw / v["s"] * z * fywd * (ct + cot_alpha) * sin_alpha / 1000
        VRdmax = alpha_cw * bw * z * nu * fcd * (ct + cot_alpha) / (1 + ct**2) / 1000
        VRdmax_6_9 = alpha_cw * bw * z * nu * fcd / (ct + 1 / ct) / 1000
        VRd = min(VRds, VRdmax)
        Asw_eff = v["m_eff"] * Asw if kort_skjuvspann else 0.0
        VRd_6_19 = Asw_eff * fywd * sin_alpha / 1000
        Vs_last = min(VRd_6_19 / beta, VRdmax_6_9) if kort_skjuvspann else VRd

    # Endast aktiva indata redovisas; d förekommer en gång även vid reduktion.
    metadata = {
        "n_l": (r"n_l", "st", "antal medräkningsbara längsarmeringsjärn"),
        "cc_l": (r"\mathrm{cc}", "mm", "längsarmeringens centrumavstånd"),
        "phi_l": (r"\phi_l", "mm", "längsarmeringens stångdiameter"),
        "b_w": (r"b_w", "mm", "minsta bredd enligt vald metod"),
        "d": ("d", "mm", "effektiv höjd"),
        "f_ck": (r"f_{ck}", "MPa", "karakteristisk cylindertryckhållfasthet"),
        "A_sl": (r"A_{sl}", "mm^2", "längsdragarmering som uppfyller figur 6.3"),
        "phi_w": (r"\phi_w", "mm", "bygeldiameter"),
        "n_skar": (r"n", "", f"antal verksamma skär per {bygel}"),
        "s": ("s", "mm", "bygelradernas avstånd längs strimlan" if strimla else "byglarnas centrumavstånd längs balken"),
        "f_ywk": (r"f_{ywk}", "MPa", "karakteristisk sträckgräns för byglar"),
        "N_Ed": (r"N_{Ed}", kraftenhet, "normalkraft, positiv vid tryck"),
        "A_c": (r"A_c", "mm^2", "betongtvärsnittsarea"),
        "V_Ed": (r"V_{Ed}", kraftenhet, "dimensionerande tvärkraft utan reduktion"),
        "a_v": (r"a_v", "mm", "lastavstånd enligt figur 6.4 och 6.6"),
        "m_eff": (r"m_{eff}", "", f"verksamma {byglar} i centrala 0,75 a_v"),
        "cot_theta": (r"\cot\theta", "", "vald trycksträvelutning"),
        "alpha": (r"\alpha", "°", "bygelvinkel mot längdaxeln"),
        "z_manuell": (r"z_{man}", "mm", "manuellt angiven inre hävarm"),
        "gamma_c": (r"\gamma_c", "", "partialkoefficient för betong"),
        "gamma_s": (r"\gamma_s", "", "partialkoefficient för armering"),
        "alpha_cc": (r"\alpha_{cc}", "", "koefficient för betongtryckhållfasthet"),
    }
    if strimla:
        for name in ("A_sl", "A_c", "n_l"):
            latex, unit, label = metadata[name]
            metadata[name] = (latex, unit, label + " i 1 m strimla")
        metadata["b_w"] = (r"b_w", "mm", "fast bredd för 1 m strimla")
    indata = [_post("metod", "", _METODER[v["metod"]], "", "vald beräkningsmetod"),
              _post("plattstrimla", "", "b_w-1m strimla" if strimla else "Angiven bredd", "", "beräkningsbredd")]
    for name in _PX_NAMN:
        if name == "A_sl" and v["A_sl_inmatning"] in ("jarn", "cc"):
            continue
        if name == "n_l" and v["A_sl_inmatning"] == "cc":
            continue
        if name in metadata and v[name] is not None:
            latex, unit, label = metadata[name]
            indata.append(_post(name, latex, v[name], unit, label))
    if c:
        indata.append(_post("A_sl_inmatning", "", _LANGSARMERING[v["A_sl_inmatning"]], "", "inmatning av längsarmering"))
    if s:
        indata.append(_post("z_auto", "", "0,9 d" if v["z_auto"] else "Manuell", "", "val av inre hävarm"))
    indata.append(_post("reducera_tvarkraft", "", "På" if v["reducera_tvarkraft"] else "Av", "", "tvärkraftsreduktion"))
    mellan = [
        _post("f_cd", r"f_{cd}", fcd, "MPa", "dimensionerande betongtryckhållfasthet"),
        _post("beta", r"\beta", beta, "", "lastreduktionsfaktor"),
    ]
    resultat = []
    if c:
        if v["A_sl_inmatning"] == "cc":
            mellan.append(_post("n_l", r"n_l", v["n_l"], "st", "beräknat antal längsarmeringsjärn, avrundat nedåt", decimals=0))
        if v["A_sl_inmatning"] in ("jarn", "cc"):
            mellan.append(_post("A_sl", r"A_{sl}", v["A_sl"], "mm^2", "beräknad medräkningsbar längsdragarmering" + (" i 1 m strimla" if strimla else "")))
        mellan.extend([
            _post("sigma_cp", r"\sigma_{cp}", sigma_cp, "MPa", "normalspänning, positiv vid tryck"),
            _post("sigma_cp_grans", r"0{,}2f_{cd}", 0.2 * fcd, "MPa", "strikt övre tillämpningsgräns för 6.2.2"),
            _post("k", "k", k, "", "höjdfaktor, högst 2,0"),
            _post("rho_l_obegransad", r"\rho_{l,obegr}", rho_l_raw, "", "armeringskvot före begränsning", 6),
            _post("rho_l", r"\rho_l", rho_l, "", "medräknad armeringskvot, högst 0,02", 6),
            _post("C_Rd_c", r"C_{Rd,c}", C_Rdc, "", "0,18 / gamma_c"),
            _post("k_1", r"k_1", k1, "", "koefficient för normalspänning"),
            _post("v_min", r"v_{min}", vmin, "MPa", "minsta skjuvhållfasthet före normalkraftsbidrag"),
            _post("V_Rd_c_6_2a", r"V_{Rd,c,a}", VRdc_a, kraftenhet, "uttryck (6.2a)"),
            _post("V_Rd_c_6_2b", r"V_{Rd,c,b}", VRdc_b, kraftenhet, "uttryck (6.2b)"),
        ])
        resultat.append(_post("V_Rd_c", r"V_{Rd,c}", VRdc, kraftenhet, "6.2.2, utan beräknad tvärkraftsarmering"))
        if kort_skjuvspann:
            resultat.append(_post("V_lim_6_5", r"V_{lim,6.5}", Vlim_6_5, kraftenhet, "gräns för oreducerad last enligt (6.5)"))
    if s:
        mellan.extend([
            _post("f_ywd", r"f_{ywd}", fywd, "MPa", "dimensionerande sträckgräns"),
            _post("A_sw", r"A_{sw}", Asw, "mm^2", f"verksam area per {bygel}"),
            _post("A_sw_per_m", r"A_{sw}/s", Asw / v["s"] * 1000, "mm^2/m", "tvärkraftsarmering per längdmeter"),
            _post("z", "z", z, "mm", "använd inre hävarm"),
            _post("theta", r"\theta", math.degrees(math.atan(1 / ct)), "°", "trycksträvans vinkel"),
            _post("alpha_cw", r"\alpha_{cw}", alpha_cw, "", "ingen förspänning"),
        ])
        resultat.extend([
            _post("V_Rd_s", r"V_{Rd,s}", VRds, kraftenhet, "6.2.3, ordinarie modell, armeringens begränsning"),
            _post("V_Rd_max", r"V_{Rd,max}", VRdmax, kraftenhet, "6.2.3, ordinarie modell, trycksträvans begränsning"),
            _post("V_Rd", r"V_{Rd}", VRd, kraftenhet, "6.2.3, minsta ordinarie bärförmåga före lastreduktion"),
        ])
        if kort_skjuvspann:
            mellan.extend([
                _post("l_eff", r"0{,}75a_v", 0.75 * v["a_v"], "mm", f"centralt område för verksamma {byglar}"),
                _post("A_sw_eff", r"A_{sw,eff}", Asw_eff, "mm^2", "verksam bygelarea för (6.19)"),
            ])
            resultat.extend([
                _post("V_Rd_6_19", r"V_{Rd,6.19}", VRd_6_19, kraftenhet, "bärförmåga mot reducerad last enligt (6.19)"),
                _post("V_Rd_max_6_9", r"V_{Rd,max,6.9}", VRdmax_6_9, kraftenhet, "gräns för oreducerad last enligt hänvisningen i 6.2.3(8)"),
            ])
    if s or kort_skjuvspann:
        mellan.append(_post("nu_1" if s else "nu", r"\nu_1" if s else r"\nu", nu, "", "hållfasthetsreduktion enligt (6.6N)"))
    if v["kontrollera_last"]:
        VEd, Vred = v["V_Ed"], beta * v["V_Ed"]
        resultat.append(_post("V_Ed_red", r"V_{Ed,red}", Vred, kraftenhet, "tvärkraft efter vald reduktion"))
        if c:
            if kort_skjuvspann:
                resultat.extend(_kontroll("c_reducerad", Vred, VRdc, "reducerad tvärkraft mot V_Rd,c"))
                resultat.extend(_kontroll("c_oreducerad", VEd, Vlim_6_5, "oreducerad tvärkraft enligt (6.5)"))
            resultat.extend(_kontroll("6_2_2", VEd, Vc_last, "bärförmågekontroll enligt 6.2.2"))
        if s:
            if kort_skjuvspann:
                resultat.extend(_kontroll("s_reducerad", Vred, VRd_6_19, "reducerad tvärkraft enligt (6.19)"))
                resultat.extend(_kontroll("s_oreducerad", VEd, VRdmax_6_9, "oreducerad tvärkraft mot (6.9)"))
            resultat.extend(_kontroll("6_2_3", VEd, Vs_last, "bärförmågekontroll enligt 6.2.3"))
            mellan.append(_post("Delta_F_td", r"\Delta F_{td}", 0.5 * VEd * (ct - cot_alpha), kraftenhet,
                                "dragkraftstillägg enligt (6.18), oreducerad last, utan momentbegränsningen"))

    ekvationer = [_ekvation(r"f_{cd}=\alpha_{cc}f_{ck}/\gamma_c", "dimensionerande betongtryckhållfasthet")]
    if c:
        if v["A_sl_inmatning"] == "cc":
            ekvationer.append(_ekvation(r"n_l=\mathrm{floor}(b_w/\mathrm{cc}+1)", "avrundning nedåt till heltal"))
        if v["A_sl_inmatning"] in ("jarn", "cc"):
            ekvationer.append(_ekvation(r"A_{sl}=n_l\pi\phi_l^2/4", "area från antal och stångdiameter"))
        ekvationer.extend([
            _ekvation(r"k=\min(1+\sqrt{200/d},2)", "d i mm, 6.2.2(1)"),
            _ekvation(r"\rho_l=\min(A_{sl}/(b_wd),0{,}02)", "medräknad längsarmeringskvot"),
            _ekvation(r"\sigma_{cp}=1000N_{Ed}/A_c" if v["N_Ed"] else r"\sigma_{cp}=0",
                      f"Krav: sigma_cp < 0,2 f_cd. N_Ed i {kraftenhet}."),
            _ekvation(r"C_{Rd,c}=0{,}18/\gamma_c", "rekommenderat värde i 6.2.2(1)"),
            _ekvation(r"k_1=0{,}15", "rekommenderat värde i 6.2.2(1)"),
            _ekvation(r"v_{min}=0{,}035k^{3/2}\sqrt{f_{ck}}", "(6.3N), f_ck i MPa"),
            _ekvation(r"V_{Rd,c,a}=[C_{Rd,c}k(100\rho_l f_{ck})^{1/3}+k_1\sigma_{cp}]b_wd/1000", f"(6.2a), resultat i {kraftenhet}"),
            _ekvation(r"V_{Rd,c,b}=(v_{min}+k_1\sigma_{cp})b_wd/1000", f"(6.2b), resultat i {kraftenhet}"),
            _ekvation(r"V_{Rd,c}=\max(0,V_{Rd,c,a},V_{Rd,c,b})", "negativ beräknad bärförmåga ger noll tillgänglig kapacitet"),
        ])
    if s or kort_skjuvspann:
        ekvationer.append(_ekvation(
            r"\nu_1=\nu=0{,}6(1-f_{ck}/250)" if s else r"\nu=0{,}6(1-f_{ck}/250)",
            "(6.6N), även nu_1 enligt grundmodellen i 6.2.3" if s else "(6.6N)",
        ))
    if s:
        cot_value = format(ct, ".12g").replace(".", "{,}")
        ekvationer.extend([
            _ekvation(r"f_{ywd}=f_{ywk}/\gamma_s", "dimensionerande sträckgräns"),
            _ekvation(r"A_{sw}=n\pi\phi_w^2/4", f"summa verksamma skär i en {bygel}"),
            _ekvation(r"z=0{,}9d" if v["z_auto"] else r"z=z_{man}", "vald inre hävarm"),
            _ekvation(r"\cot\theta=" + cot_value, "Tillåtet intervall: 1,0-2,5 enligt (6.7N)"),
            _ekvation(r"\alpha_{cw}=1", "ej förspänd betong"),
            _ekvation(r"V_{Rd,s}=\frac{A_{sw}}s zf_{ywd}(\cot\theta+\cot\alpha)\sin\alpha/1000", "(6.13), blir (6.8) för alpha=90 grader"),
            _ekvation(r"V_{Rd,max}=\alpha_{cw}b_wz\nu_1 f_{cd}\frac{\cot\theta+\cot\alpha}{1+\cot^2\theta}/1000", "(6.14), blir (6.9) för alpha=90 grader"),
            _ekvation(r"V_{Rd}=\min(V_{Rd,s},V_{Rd,max})", "ordinarie bärförmåga utan lastreduktion"),
        ])
    if v["reducera_tvarkraft"]:
        ekvationer.extend([
            _ekvation(r"\beta=\min(1,\max(0{,}25,a_v/(2d)))", "6.2.2(6)" if not s else "6.2.3(8)" if not c else "6.2.2(6) och 6.2.3(8)"),
            _ekvation(r"V_{Ed,red}=\beta V_{Ed}", "reducerad tvärkraft"),
        ])
    if kort_skjuvspann:
        if c:
            ekvationer.append(_ekvation(r"V_{lim,6.5}=0{,}5b_wd\nu f_{cd}/1000", "(6.5), gräns för oreducerad tvärkraft"))
        if s:
            ekvationer.extend([
                _ekvation(r"A_{sw,eff}=m_{eff}A_{sw}", f"endast verksamma {byglar} i centrala 0,75a_v"),
                _ekvation(r"V_{Rd,6.19}=A_{sw,eff}f_{ywd}\sin\alpha/1000", "(6.19), gräns för reducerad tvärkraft"),
                _ekvation(r"V_{Rd,max,6.9}=\frac{\alpha_{cw}b_wz\nu_1 f_{cd}}{\cot\theta+\tan\theta}/1000", "6.2.3(8), gräns för oreducerad last enligt (6.9)"),
            ])
    if v["kontrollera_last"]:
        if c:
            if kort_skjuvspann:
                ekvationer.extend([
                    _ekvation(r"\eta_{\mathrm{c.reducerad}}=100V_{Ed,red}/V_{Rd,c}\leq100", "procent, reducerad tvärkraft mot V_Rd,c"),
                    _ekvation(r"\eta_{\mathrm{c.oreducerad}}=100V_{Ed}/V_{lim,6.5}\leq100", "procent, oreducerad tvärkraft enligt (6.5)"),
                    _ekvation(r"\eta_{6.2.2}=\max(\eta_{\mathrm{c.reducerad}},\eta_{\mathrm{c.oreducerad}})", "största delutnyttjandet styr, procent"),
                ])
            else:
                ekvationer.append(_ekvation(r"\eta_{6.2.2}=100V_{Ed}/V_{Rd,c}\leq100", "utnyttjandegrad i procent, 6.2.2"))
        if s:
            if kort_skjuvspann:
                ekvationer.extend([
                    _ekvation(r"\eta_{\mathrm{s.reducerad}}=100V_{Ed,red}/V_{Rd,6.19}\leq100", "procent, reducerad tvärkraft enligt (6.19)"),
                    _ekvation(r"\eta_{\mathrm{s.oreducerad}}=100V_{Ed}/V_{Rd,max,6.9}\leq100", "procent, oreducerad tvärkraft mot (6.9)"),
                    _ekvation(r"\eta_{6.2.3}=\max(\eta_{\mathrm{s.reducerad}},\eta_{\mathrm{s.oreducerad}})", "största delutnyttjandet styr, procent"),
                ])
            else:
                ekvationer.append(_ekvation(r"\eta_{6.2.3}=100V_{Ed}/V_{Rd}\leq100", "utnyttjandegrad i procent, 6.2.3"))
            ekvationer.append(_ekvation(r"\Delta F_{td}=0{,}5V_{Ed}(\cot\theta-\cot\alpha)", "(6.18), ingen kontroll av total längsdragkraft eller begränsning med M_Ed,max/z"))
    metod = [
        {"rubrik": "Vald metod", "text": _METODER[v["metod"]] + " enligt SS-EN 1992-1-1:2005. Endast vald metod beräknas och redovisas."},
        {"rubrik": "Omfattning", "text": (
            "Normalbetong med konstant tvärsnitt och parallella ramstänger, utan förspänning eller foderrör. "
            "b_w ska uppfylla bredddefinitionen för vald metod. Beräkningen gäller ett angivet snitt. "
            "Osprucken förspänd betong enligt (6.4) ingår inte."
        )},
        {"rubrik": "Förankring och detaljutformning", "text": (
            ("A_sl omfattar endast längsdragarmering som når minst l_bd+d bortom snittet enligt figur 6.3. " if c else "")
            + ("Byglarna ska vara verksamma och förankrade. " if s else "")
            + "Minimiarmering, bygelavståndsgränser, förankringsdimensionering, böjning och total dragkraft "
            "i längsarmeringen ingår inte. Uppfyller avser enbart respektive redovisad bärförmågekontroll."
        )},
        {"rubrik": "Beräkningsinställningar", "text": (
            "EC2:s rekommenderade koefficienter används. Ingen svensk nationell bilaga väljs automatiskt. "
            "Materialfaktorer redovisas med sina använda värden. "
            + ("Gränserna för cot(theta) är fasta: 1,0-2,5. Automatiskt z=0,9d gäller endast utan normalkraft. " + _COT_HELP if s else "")
        )},
        {"rubrik": "Enheter", "text": f"Mått i mm, areor i mm², hållfastheter i MPa och krafter i {kraftenhet}. Hållfasthetsuttrycken omvandlas från N till kN genom division med 1000."},
    ]
    if strimla:
        metod.append({"rubrik": "b_w-1m strimla", "text": (
            "b_w är låst till 1000 mm. Laster, betongarea och längsarmering avser denna strimla. "
            "Krafter och bärförmågor för strimlan redovisas per meter bredd i kN/m. "
            + ("n är summan av verksamma skär per bygelrad över strimlans bredd; s är radavståndet "
               "längs strimlan. A_sw/s avser tvärkraftsarmering per längdmeter i denna strimla. " if s else "")
            + "Indata tolkas för strimlan och skalas inte om från någon tidigare angiven bredd."
        )})
    if v["reducera_tvarkraft"]:
        metod.append({"rubrik": "Tvärkraftsreduktion", "text": (
            "Hela V_Ed förutsätts komma från reducerbar last på översidan, med lastöverföring enligt "
            "figur 6.4/6.6 och fullt förankrad längsarmering vid upplaget. Andra lastbidrag ingår inte. "
            + ("För 6.2.2 kontrolleras reducerad last mot V_Rd,c och oreducerad last mot (6.5). " if c else "")
            + ("För 6.2.3 kontrolleras reducerad last mot (6.19) och oreducerad last mot (6.9). "
               f"m_eff är verkligt antal verksamma {byglar} inom centrala 0,75a_v; antalet härleds inte från s. " if s else "")
            + "Största utnyttjandet av kontrollen med reducerad respektive oreducerad last styr "
            "slutkontrollen för varje metod. Vid a_v>2d används ordinarie modell med beta=1."
        )})
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
_C = {"field": "metod", "in": ["bada", "6.2.2"]}
_S = {"field": "metod", "in": ["bada", "6.2.3"]}
_REDUKTION = {"all": [_LAST, {"field": "reducera_tvarkraft", "equals": True}]}
_JARN = {"all": [_C, {"field": "A_sl_inmatning", "equals": "jarn"}]}
_CC = {"all": [_C, {"field": "A_sl_inmatning", "equals": "cc"}]}
_DIAMETER = {"all": [_C, {"field": "A_sl_inmatning", "in": ["jarn", "cc"]}]}
_STRIMLA = {"field": "plattstrimla", "equals": True}

Tvärkraft.panel_schema = {
    "title": "Tvärkraft - EC2 6.2.2 och 6.2.3",
    "px": list(_PX_NAMN),
    "sections": [
        {"fields": ["metod", "plattstrimla"], "columns": 1},
        {"title": "Tvärsnitt och längsarmering", "fields": ["b_w", "d", "N_Ed", "A_c", "A_sl_inmatning", "A_sl", "n_l", "cc_l", "phi_l"], "columns": 3},
        {"title": "Material", "fields": ["f_ck", "f_ywk"], "columns": 2},
        {"title": "Tvärkraftsarmering", "fields": ["phi_w", "n_skar", "s", "alpha", "m_eff"], "columns": 3},
        {"title": "Last och tvärkraftsreduktion", "fields": ["kontrollera_last", "V_Ed", "reducera_tvarkraft", "a_v"], "columns": 2},
        {"title": "Beräkningsinställningar", "fields": ["cot_theta", "z_auto", "z_manuell", "gamma_c", "gamma_s", "alpha_cc"], "columns": 3, "collapsible": True, "collapsed": True},
    ],
    "fields": [
        _falt("metod", "Beräkningsmetod", "bada", typ="choice", options=[
            {"label": label, "value": value} for value, label in _METODER.items()
        ]),
        _falt("plattstrimla", r"\(b_w\)-1m strimla", False, typ="bool",
              # Widgetens HTML-filter tillåter span, men tar bort sub-taggar.
              label_html="<i>b</i><span style='vertical-align:sub;font-size:smaller'>w</span>-1m strimla",
              help="Aktivt läge använder 1 000 mm bredd. Laster och armering anges för denna strimla; befintliga värden behålls vid byte av läge."),
        _falt("b_w", "Minsta bredd", 300.0, "mm", "<i>b</i><sub>w</sub>",
              fixed_if={**_STRIMLA, "value": 1000.0},
              presentation_if={**_STRIMLA, "label": "Strimlans bredd (fast)"}),
        _falt("d", "Effektiv höjd", 500.0, "mm", "<i>d</i>"),
        _falt("f_ck", "Betongens tryckhållfasthet", 30.0, "MPa", "<i>f</i><sub>ck</sub>"),
        _falt("A_sl_inmatning", "Ange längsarmering som", "area", typ="choice", visible_if=_C, options=[
            {"label": label, "value": value} for value, label in _LANGSARMERING.items()
        ]),
        _falt("A_sl", "Medräkningsbar längsdragarmering", 2000.0, "mm²", "<i>A</i><sub>sl</sub>",
              visible_if={"all": [_C, {"field": "A_sl_inmatning", "equals": "area"}]},
              presentation_if={**_STRIMLA, "label": "Medräkningsbar längsdragarmering i 1 m strimla"}),
        _falt("n_l", "Antal längsarmeringsjärn", 4, "st", "<i>n</i><sub>l</sub>", typ="int", visible_if=_JARN,
              presentation_if={**_STRIMLA, "label": "Antal längsarmeringsjärn i 1 m strimla"}),
        _falt("cc_l", "Längsarmeringens centrumavstånd", 200.0, "mm", "cc", visible_if=_CC),
        _falt("phi_l", "Längsarmeringens diameter", 25.0, "mm", "φ<sub>l</sub>", visible_if=_DIAMETER),
        _falt("phi_w", "Bygeldiameter", 8.0, "mm", "φ<sub>w</sub>", visible_if=_S),
        _falt("n_skar", "Verksamma skär per bygel (0 = inga)", 2, "", "<i>n</i>", typ="int", visible_if=_S,
              presentation_if={**_STRIMLA, "label": "Skär per bygelrad över 1 m bredd (0 = inga)"}),
        _falt("s", "Bygelavstånd", 200.0, "mm", "<i>s</i>", visible_if=_S,
              presentation_if={**_STRIMLA, "label": "Radavstånd längs strimlan"}),
        _falt("f_ywk", "Byglarnas sträckgräns", 500.0, "MPa", "<i>f</i><sub>ywk</sub>", visible_if=_S),
        _falt("N_Ed", "Normalkraft, tryck positivt", 0.0, "kN", "<i>N</i><sub>Ed</sub>",
              presentation_if={**_STRIMLA, "unit": "kN/m"}),
        _falt("A_c", "Betongtvärsnittsarea", 180000.0, "mm²", "<i>A</i><sub>c</sub>",
              visible_if={"all": [_C, {"field": "N_Ed", "not_equals": 0}]},
              presentation_if={**_STRIMLA, "label": "Betongarea i 1 m strimla"}),
        _falt("kontrollera_last", "Kontrollera angiven tvärkraft", False, typ="bool"),
        _falt("V_Ed", "Tvärkraft före reduktion", 100.0, "kN", "<i>V</i><sub>Ed</sub>", visible_if=_LAST,
              presentation_if={**_STRIMLA, "unit": "kN/m"}),
        _falt("reducera_tvarkraft", "Reducera tvärkraft nära upplag", False, typ="bool", visible_if=_LAST,
              fixed_if={"field": "kontrollera_last", "equals": False, "value": False}),
        _falt("a_v", "Lastavstånd enligt figur 6.4 / 6.6", 300.0, "mm", "<i>a</i><sub>v</sub>", visible_if=_REDUKTION),
        _falt("m_eff", "Verksamma byglar i centrala 0,75 aᵥ", 0, "st", "<i>m</i><sub>eff</sub>", typ="int",
              visible_if={"all": [_S, _REDUKTION]},
              presentation_if={**_STRIMLA, "label": "Verksamma bygelrader i centrala 0,75 aᵥ"}),
        _falt("cot_theta", "Vald cot(θ)", 2.5, "", "cot θ", visible_if=_S, span=3, help=_COT_HELP),
        _falt("alpha", "Bygelvinkel", 90.0, "°", "α", visible_if=_S),
        _falt("z_auto", "Beräkna z = 0,9 d", True, typ="bool", visible_if=_S,
              fixed_if={"field": "N_Ed", "not_equals": 0, "value": False}),
        _falt("z_manuell", "Manuell inre hävarm", 450.0, "mm", "<i>z</i>",
              visible_if={"all": [_S, {"field": "z_auto", "equals": False}]}),
        _falt("gamma_c", "Partialkoefficient betong", 1.5, "", "γ<sub>c</sub>"),
        _falt("gamma_s", "Partialkoefficient armering", 1.15, "", "γ<sub>s</sub>", visible_if=_S),
        _falt("alpha_cc", "Tryckhållfasthetskoefficient", 1.0, "", "α<sub>cc</sub>"),
    ],
}

# ASCII-alias för kod som följer paketets övriga namnkonvention.
tvarkraft = Tvärkraft
