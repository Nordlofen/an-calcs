"""Släta pelarholkar: EC2 10.9.6.3 och överenskommen kontakt-/konsolmodell."""

import math
from collections.abc import Mapping


_PX_LEGACY = ("typ", "fristaende", "M", "Fv", "Fh", "h", "l", "D", "t_ig",
       "bh", "f_cd_ig", "f_cd_c", "c_nom", "phi", "f_yd", "mu")
_PX_PREVIOUS = tuple(name for name in _PX_LEGACY if name not in ("f_cd_ig", "f_cd_c"))
_PX = _PX_PREVIOUS + ("t_ig_b",)
_SKISSMATT = {"bv", "H", "t_p"}
_DEFAULTS = {"typ": "pelare", "fristaende": True, "mu": 0.3, "t_ig_b": 20.0}


def _tal(name, value, *, positive=False, minimum=None, maximum=None):
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not math.isfinite(number):
            raise ValueError
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} måste vara ett ändligt tal.") from exc
    if positive and number <= 0:
        raise ValueError(f"{name} måste vara > 0.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} måste vara >= {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} måste vara <= {maximum}.")
    return number


def _indata(px):
    if isinstance(px, Mapping):
        unknown = set(px) - set(_PX_LEGACY) - set(_PX) - _SKISSMATT - {"b1", "b2"}
        if unknown:
            raise ValueError(f"Okända indata: {sorted(unknown, key=str)}.")
        given = dict(px)
        # Behåll sparade fältnycklar bh/bv; tillåt även de nya sidobeteckningarna.
        for new, old in (("b1", "bh"), ("b2", "bv")):
            if new in given:
                if old in given and given[old] != given[new]:
                    raise ValueError(f"Ange antingen {new} eller {old}, inte olika värden för samma sidomått.")
                given[old] = given.pop(new)
    elif isinstance(px, (list, tuple)) and len(px) == len(_PX):
        given = dict(zip(_PX, px))
    elif isinstance(px, (list, tuple)) and len(px) == len(_PX_LEGACY):
        given = dict(zip(_PX_LEGACY, px))
    elif isinstance(px, (list, tuple)) and len(px) == len(_PX_PREVIOUS):
        given = dict(zip(_PX_PREVIOUS, px))
    else:
        raise ValueError(f"px ska vara en dictionary eller lista/tuple med {len(_PX)} värden enligt panel_schema['px'].")
    v = {**_DEFAULTS, **given}
    if v["typ"] not in ("pelare", "vagg"):
        raise ValueError("typ måste vara 'pelare' eller 'vagg'.")
    if not isinstance(v["fristaende"], bool):
        raise ValueError("fristaende måste vara True eller False.")
    required = ["M", "Fv", "Fh", "h", "l", "t_ig", "t_ig_b"]
    if v["typ"] == "pelare":
        required.append("D")
    if v["fristaende"]:
        required += ["bh", "c_nom", "phi", "f_yd"]
    missing = [name for name in required if v.get(name) is None]
    if missing:
        raise ValueError(f"Saknade indata: {', '.join(missing)}.")
    for name in ("M", "Fh"):
        v[name] = _tal(name, v[name])
    v["Fv"] = _tal("Fv", v["Fv"], minimum=0)
    v["mu"] = _tal("mu", v["mu"], minimum=0, maximum=0.3)
    for name in ("h", "l", "t_ig", "t_ig_b"):
        v[name] = _tal(name, v[name], positive=True)
    v["D"] = 1000.0 if v["typ"] == "vagg" else _tal("D", v["D"], positive=True)
    if v["fristaende"]:
        for name in ("bh", "phi", "f_yd"):
            v[name] = _tal(name, v[name], positive=True)
        v["c_nom"] = _tal("c_nom", v["c_nom"], minimum=0)
        v["d"] = v["bh"] - v["t_ig"] - v["c_nom"] - v["phi"] / 2
        if v["d"] <= 0:
            raise ValueError("Effektiv höjd d = b1 - t_ig - c_nom - phi/2 måste vara > 0.")
    else:
        for name in ("bh", "c_nom", "phi", "f_yd", "d"):
            v[name] = None
    return v


def _insticksdjup_ok(values):
    """Gemensam geometrikontroll för redovisning och direkt fältåterkoppling."""
    try:
        l, h = float(values["l"]), float(values["h"])
    except (KeyError, TypeError, ValueError):
        return False
    return math.isfinite(l) and math.isfinite(h) and l > 0 and h > 0 and l >= 1.2*h


def _post(name, latex, value, unit="", label="", decimals=3):
    return {"namn": name, "latex": latex, "value": value, "unit": unit,
            "etikett": label, "decimals": decimals}


def Pelarholk(px):
    r"""Beräkna F1/F2/F3, sidokontakttryck och fristående högerväggs böjarmering.

    Namngivet format rekommenderas. Listformat följer ``panel_schema['px']``.
    Mått: mm; f_yd: dimensionerande sträckgräns i MPa.
    Pelare: Fv/Fh i kN, M i kNm, D = verksamt kontaktdjup ut ur snittet.
    Vägg (typ='vagg'): kN/m och kNm/m; D låses till 1000 mm även vid direktanrop.
    Laster avser holkens överkant: Fv nedåt, Fh åt höger och M medurs positivt.
    Endast kraftspelet i figur 10.7b; negativ kontaktkraft avvisas, inte klipps.

    fristaende=True: M_holk=0.9*l*F1, z=0.9*d, Fs=M_holk/z,
    As_req=Fs/f_yd. d=b1-t_ig-c_nom-phi/2; b1 mäts från elementytan till
    fundamentets högra ytterkant. c_nom avser täckskikt till den aktuella
    dragstångens utsida. Gynnsam lokal friktion försummas i böjberäkningen.
    V_Ed_1=F1 och V_Ed_2=F2 redovisas separat. Vid fristaende=False utelämnas
    böjberäkningen och V_Ed_1; böjindata ignoreras. a_v_2=0.1*l+t_ig_b avser
    endast vänstra väggen: från F2 till underkant bottenigjutning. t_ig_b är
    separat från sidans t_ig, med förval 20 mm även för äldre sparade fall.
    Tvärkraftsreduktion och kapacitet beräknas separat i Tvärkraft().

    Kontaktmodellen är ett projektspecifikt tillägg till EC2:s kraftmodell:
    a_c=0.3*l, triangulärt tryck, spridning t_ig/tan(26.6 grader), oförändrat D.
    Slutresultat visar maxtryck för igjutning och holkbetong, utan utnyttjande-
    grader eller hållfasthetsjämförelse. Enskilda kontakttryck ligger i delresultat.
    Äldre f_cd_ig/f_cd_c accepteras men ignoreras. Positionsformaten med 14
    respektive 16 värden stöds fortsatt. b1/b2 är alias för sparade bh/bv.
    Insticksdjup l < 1,2h ger endast indata och kontrollen Ej uppfyllt, inga
    kraft- eller armeringsresultat. Ekvationerna använder konsekventa enheter.
    Tillgänglig spridningsgeometri måste bedömas separat. F3 redovisas med
    medeltryck, utan kontroll av maximalt bottentryck eller genomstansning.
    Minimiarmering, förankring och övrig detaljutformning ingår inte.
    bv, H och t_p får lämnas i dictionary men är endast skissmått och ignoreras.
    Beräkningsfunktionen läser inga figurer och importerar inget UI-bibliotek.
    """
    v = _indata(px)
    h, l, D, mu = (v[k] for k in ("h", "l", "D", "mu"))
    force_unit = "kN/m" if v["typ"] == "vagg" else "kN"
    moment_unit = "kNm/m" if v["typ"] == "vagg" else "kNm"
    area_unit = "mm²/m" if v["typ"] == "vagg" else "mm²"
    labels = {
        "M": ("M", moment_unit, "Moment vid holkens överkant, medurs positivt"),
        "Fv": (r"F_v", force_unit, "Vertikallast, nedåt positivt"),
        "Fh": (r"F_h", force_unit, "Horisontallast, åt höger positivt"),
        "h": ("h", "mm", "Pelarmått/väggtjocklek"), "l": ("l", "mm", "Insticksdjup"),
        "D": ("D", "mm", "Beräkningsdjup ut ur snittplanet"),
        "t_ig": (r"t_{ig}", "mm", "Igjutningstjocklek vid sidorna"),
        "t_ig_b": (r"t_{ig,b}", "mm", "Igjutningstjocklek under pelarfoten"),
        "mu": (r"\mu", "", "Friktionskoefficient i global jämvikt"),
        "bh": (r"b_1", "mm", "Höger sidomått, inklusive igjutning"),
        "c_nom": (r"c_{nom}", "mm", "Täckskikt till dragstångens utsida"),
        "phi": (r"\phi", "mm", "Dragstångens diameter"),
        "f_yd": (r"f_{yd}", "MPa", "Dimensionerande sträckgräns"),
    }
    inputs = [_post("typ", r"\mathrm{Typ}", "Vägg, 1 m strimla" if v["typ"] == "vagg" else "Pelare", label="Beräkningstyp"),
              _post("fristaende", r"\mathrm{Holktyp}", "Fristående" if v["fristaende"] else "Plattansluten", label="Holktyp")]
    for name, (symbol, unit, label) in labels.items():
        if v.get(name) is not None:
            inputs.append(_post(name, symbol, v[name], unit, label))
    depth_ok = _insticksdjup_ok(v)
    depth_check = {**_post("status_insticksdjup", r"l\geq1{,}2h", "Uppfyllt" if depth_ok else "Ej uppfyllt", label="Insticksdjup"),
                   "show_equals": False}
    if not depth_ok:
        return {"metodbeskrivning": {"title": "Metodbeskrivning", "items": []},
                "indata": {"title": "Indata", "items": inputs},
                "delresultat": {"title": "Delresultat", "items": []},
                "ekvationer": {"title": "Ekvationer", "items": []},
                "slutresultat": {"title": "Slutresultat", "items": [depth_check]}}
    # Eliminering av de tre jämviktsekvationerna; krafter kN och moment kNmm.
    delta = (v["Fh"] + mu * v["Fv"]) / (1 + mu**2)
    A, C = 0.9*l + mu*h/2, mu*h/2 - 0.1*l
    denominator = 0.8*l + mu*h
    moment = 1000*v["M"] + v["Fh"]*l
    F1 = (moment + C*delta) / denominator
    F2 = (moment - A*delta) / denominator
    F3 = v["Fv"] - mu*delta
    for name, force in (("F1", F1), ("F2", F2), ("F3", F3)):
        if not math.isfinite(force):
            raise ValueError("Indata ligger utanför beräkningens numeriska område.")
        if force < 0:
            raise ValueError(f"{name} = {force:.6g} är negativ. Antaget kraftspel enligt figur 10.7b är inte giltigt för dessa laster.")
    ac = 0.3*l
    da = v["t_ig"] / math.tan(math.radians(26.6))
    ac_spr = ac + da
    middle = [
        _post("a1", "a_1", 0.9*l, "mm", "F₁:s höjd över pelarfoten"),
        _post("a2", "a_2", 0.1*l, "mm", "F₂:s höjd över pelarfoten"),
        _post("a_c", "a_c", ac, "mm", "Kontaktzonens höjd"),
        _post("alpha", r"\alpha", 26.6, "°", "Tryckspridningens vinkel mot vertikalen"),
        _post("delta_a", r"\Delta a", da, "mm", "Tillkommande spridningshöjd"),
        _post("a_c_spr", "a_{c,spr}", ac_spr, "mm", "Spridd kontaktzonshöjd"),
        _post("sigma_3_mean", r"\sigma_{3,medel}", 1000*F3/(D*h), "MPa", "Medeltryck under pelarfoten; maxtryck ej kontrollerat"),
    ]
    result = [_post(f"F{i}", f"F_{i}", force, force_unit, "Kontaktkraft") for i, force in enumerate((F1, F2, F3), 1)]
    controlling = 1 if F1 >= F2 else 2
    for material, height, description in (("ig", ac, "igjutning"), ("c", ac_spr, "holkbetong")):
        for i, force in enumerate((F1, F2), 1):
            middle.append(_post(f"sigma_{material}_{i}_max", rf"\sigma_{{{material},{i},max}}",
                                2000*force/(D*height), "MPa", f"Kontakttryck {description}, F{'₁' if i == 1 else '₂'}"))
        result.append(_post(f"sigma_{material}_max", rf"\sigma_{{{material},max}}",
                            2000*max(F1, F2)/(D*height), "MPa", f"Maxtryck {description}, F{'₁' if controlling == 1 else '₂'}"))
    result.append(depth_check)
    if v["fristaende"]:
        result.append(_post("V_Ed_1", "V_{Ed,1}", F1, force_unit, "Högra holkväggens oreducerade tvärkraft"))
    result += [
        _post("V_Ed_2", "V_{Ed,2}", F2, force_unit, "Vänstra holkväggens oreducerade tvärkraft"),
        _post("a_v_2", "a_{v,2}", 0.1*l + v["t_ig_b"], "mm", "Lastavstånd för F₂ till underkant bottenigjutning"),
    ]
    equations = [
        {"latex": r"\sum F_x=F_h-F_1+F_2+\mu F_3=0", "etikett": "Horisontell jämvikt"},
        {"latex": r"\sum F_y=\mu F_1-\mu F_2+F_3-F_v=0", "etikett": "Vertikal jämvikt"},
        {"latex": r"\sum M_{\mathrm{fot}}=M+F_hl-(0{,}9l+\mu h/2)F_1-(\mu h/2-0{,}1l)F_2=0", "etikett": "Moment kring pelarfotens mitt"},
        {"latex": r"a_c=0{,}3l", "etikett": "Triangulär kontaktzon"},
        {"latex": r"\Delta a=t_{ig}/\tan(26{,}6^\circ)", "etikett": "Tillkommande spridningshöjd"},
        {"latex": r"a_{c,spr}=a_c+\Delta a", "etikett": "Spridd kontaktzon"},
        {"latex": r"\sigma_{ig,i,max}=\frac{2F_i}{Da_c}", "etikett": "Maxtryck i igjutning, i = 1, 2"},
        {"latex": r"\sigma_{c,i,max}=\frac{2F_i}{Da_{c,spr}}", "etikett": "Maxtryck i holkbetong, i = 1, 2"},
        {"latex": r"\sigma_{3,medel}=F_3/(Dh)", "etikett": "Endast medeltryck; ingen kontroll av maximalt bottentryck"},
    ]
    if v["fristaende"]:
        equations.append({"latex": r"V_{Ed,1}=F_1", "etikett": "Högra holkväggen, last till Tvärkraft()"})
    equations += [
        {"latex": r"V_{Ed,2}=F_2", "etikett": "Vänstra holkväggen, last till Tvärkraft()"},
        {"latex": r"a_{v,2}=0{,}1l+t_{ig,b}", "etikett": "Lastavstånd till Tvärkraft() för vänstra holkväggen"},
    ]
    if v["fristaende"]:
        d, z = v["d"], 0.9*v["d"]
        M_holk = F1*0.9*l/1000
        Fs = M_holk*1000/z
        middle += [_post("d", "d", d, "mm", "Effektiv höjd i högra holkväggen"),
                   _post("z", "z", z, "mm", "Inre hävarm"),
                   _post("M_holk", "M_{holk}", M_holk, moment_unit, "Konsolmoment i högra holkväggen")]
        result += [_post("Fs", "F_s", Fs, force_unit, "Erforderlig dragkraft i högra holkväggens böjarmering"),
                   _post("As_req", "A_{s,req}", 1000*Fs/v["f_yd"], area_unit, "Erforderlig böjarmering, exklusive minimiarmering")]
        equations += [
            {"latex": r"a_1=0{,}9l", "etikett": "F₁:s hävarm för högra holkväggen"},
            {"latex": r"d=b_1-t_{ig}-c_{nom}-\phi/2", "etikett": "Effektiv höjd i högra holkväggen"},
            {"latex": r"z=0{,}9d", "etikett": "Inre hävarm"},
            {"latex": r"M_{holk}=F_1a_1", "etikett": "Gynnsamt lokalt friktionsbidrag försummas"},
            {"latex": r"F_s=M_{holk}/z", "etikett": "Erforderlig dragkraft i böjarmeringen"},
            {"latex": r"A_{s,req}=F_s/f_{yd}", "etikett": "Erforderlig böjarmeringsarea"},
        ]
    method = [
        {"rubrik": "Kraftmodell", "text": "SS-EN 1992-1-1:2005 (Sv), 10.9.6.3, figur 10.7b. Släta fogytor. F₃ angriper centriskt under pelaren/väggen. Friktionskrafterna ingår i global jämvikt."},
        {"rubrik": "Tryckmodell", "text": "Triangulära sidokontaktzoner med höjden 0,3l och spridning genom igjutningen med 26,6° mot vertikalen enligt projektets handberäkningsmodell; detta är ett tillägg till EC2:s kraftmodell. Verksamt D hålls konstant. Tillgängligt utrymme för tryckspridningen verifieras separat."},
        {"rubrik": "Holktyp", "text": "Fristående: högra väggen beräknas som konsol för F₁, med hävarmen 0,9l och z=0,9d. Gynnsamt lokalt friktionsbidrag utelämnas." if v["fristaende"] else "Plattansluten enligt vald modell: böjarmering beräknas inte. Lastöverföringen till plattan förutsätts verifierad separat."},
        {"rubrik": "Tvärkraft", "text": "Index 1 avser högra väggen och index 2 vänstra. Lastavståndet för F₂ mäts från dess angreppspunkt till underkant bottenigjutning, 0,1l plus bottenigjutningens tjocklek. Kraftreduktion och tillhörande villkor hanteras i Tvärkraft()."},
        {"rubrik": "Enheter och material", "text": f"Krafter i {force_unit}, moment i {moment_unit}, mått i mm och hållfastheter i MPa. Kontakttrycken redovisas utan hållfasthetsjämförelse."},
        {"rubrik": "Avgränsning", "text": "Tvärkraften är oreducerad last till Tvärkraft() med motsvarande beräkningsbredd och enheter. Tvärkraftskapacitet, maximalt bottentryck, genomstansning, minimiarmering, förankring, övrig detaljutformning och pålfördelning ingår inte. B och H används endast i skissen. Ingen fullständig dimensioneringskontroll av hela fundamentet görs."},
    ]
    for item in inputs + middle + result:
        if isinstance(item["value"], (int, float)) and not math.isfinite(item["value"]):
            raise ValueError("Indata ligger utanför beräkningens numeriska område.")
    return {"metodbeskrivning": {"title": "Metodbeskrivning", "items": method},
            "indata": {"title": "Indata", "items": inputs},
            "delresultat": {"title": "Delresultat", "items": middle},
            "slutresultat": {"title": "Slutresultat", "items": result},
            "ekvationer": {"title": "Ekvationer", "items": equations, "notes": [
                {"rubrik": "Enheter", "text": "Formlerna förutsätter konsekventa enheter. Enhetsomräkning sker i beräkningen. För vägg avses en meterstrimla."},
            ]}}


def _field(name, label, default, unit="", symbol="", **extra):
    return {"name": name, "type": "float", "label": label, "default": default,
            "unit": unit, "symbol": symbol, **extra}


_WALL = {"field": "typ", "equals": "vagg"}
_FREE = {"field": "fristaende", "equals": True}
Pelarholk.panel_schema = {
    "title": "Pelarholk – släta fogytor, EC2 10.9.6.3",
    "px": list(_PX),
    "preserve_state_fields": ["f_cd_ig", "f_cd_c"],
    "blocks": {"ID": {"rader": 25}, "DR": {"rader": 20},
               "SR": {"rader": 30}, "EKV": {"rader": 20}},
    "sections": [
        {"title": "Indata", "collapsible": True, "collapsed": False, "columns": 1, "sections": [
            {"fields": ["typ", "fristaende"], "columns": 2},
            {"title": "Geometri", "fields": ["h", "l", "bv", "bh", "H", "t_ig", "D", "t_ig_b", "t_p"], "columns": 2,
             "figure": {"renderer": "an_calcs.betong._pelarholk_skiss:render", "max_width": 460,
                        "fields": ["typ", "fristaende", "h", "l", "bv", "bh", "H", "t_ig", "D", "t_ig_b", "t_p"],
                        "caption": "Måttsättning · samma skala i höjd och bredd, igjutning schematiskt förstärkt.",
                        "alt": "Dynamisk måttskiss av pelarholken."}},
            {"title": "Lasteffekter vid holkens överkant", "fields": ["M", "Fv", "Fh"], "columns": 3},
            {"title": "Böjarmering i högra holkväggen", "fields": ["c_nom", "phi", "f_yd"], "columns": 3},
            {"title": "Friläggning för böjarmering", "collapsible": True, "collapsed": True,
             "figure": {"package": "an_calcs.betong", "resource": "figures/pelarholk-bojarmering-kompakt.svg", "full_width": True, "max_width": 560,
                        "visible_if": _FREE,
                        "caption": "Frilagd högra holkvägg · a1 = 0,9l och z = 0,9d. Principskiss, ej skalenlig.",
                        "caption_html": "Frilagd högra holkvägg · <i>a</i><sub>1</sub> = 0,9<i>l</i> och <i>z</i> = 0,9<i>d</i>. Principskiss, ej skalenlig.",
                        "alt": "Frilagd högra holkvägg med F₁, snittets tvärkraft, dragkraft Fₛ och betongtryckkraft i betongen. Måttdetalj för högra sidomåttet, igjutning, täckskikt, d och z.",
                        "source": "Projektets konsolmodell. Gynnsam lokal friktion utelämnas; F₁ tas från global jämvikt med friktion."}},
            {"title": "Kontaktzoner och tryckspridning", "collapsible": True, "collapsed": True,
             "figure": {"package": "an_calcs.betong", "resource": "figures/pelarholk-kontaktzoner.png", "full_width": True, "max_width": 780,
                        "caption": "Principskiss · ej skalenlig. B och H är skissmått; D är beräkningsdjupet.",
                        "alt": "Triangulära kontaktzoner för F₁ och F₂, kraftlägen och tryckspridning genom igjutningen.",
                        "source": "Projektets kontaktmodell, baserad på handberäkningen. Kraftlägen enligt EC2 figur 10.7b."}},
            {"title": "Lastavstånd för vänstra holkväggen", "collapsible": True, "collapsed": True,
             "figure": {"package": "an_calcs.betong", "resource": "figures/pelarholk-lastavstand.svg", "full_width": True, "max_width": 560,
                        "caption": "a_v,2 = 0,1l + t_ig,b · detalj vid pelarfoten, ej skalenlig.",
                        "caption_html": "<i>a</i><sub>v,2</sub> = 0,1<i>l</i> + <i>t</i><sub>ig,b</sub> · detalj vid pelarfoten, ej skalenlig.",
                        "alt": "Vänstra holkväggens lastavstånd från F₂ till underkant bottenigjutning, med delmåtten 0,1l och bottenigjutningens tjocklek.",
                        "source": "Projektets modell. F₂ verkar här på holkväggen. Holkbotten avser underkant bottenigjutning."}},
            {"title": "EC2 · figur 10.7", "collapsible": True, "collapsed": True,
             "figure": {"package": "an_calcs.betong", "resource": "figures/ec2-figure-10-7.png", "full_width": True, "max_width": 560,
                        "caption": "Figur 10.7 · Fundament med pelarholkar. Högra delfiguren gäller släta fogytor (10.7b i standardtexten).",
                        "alt": "EC2:s originalfigur med profilerad respektive slät fogyta och tillhörande kraftspel.",
                        "source": "SS-EN 1992-1-1:2005 (Sv), s. 181. Originalets dubbla märkning (a) är bevarad."}},
        ]},
        {"title": "Beräkningsinställningar", "fields": ["mu"], "collapsible": True, "collapsed": True},
    ],
    "fields": [
        _field("typ", "Beräkningstyp", "vagg", type="choice", options=[{"label": "Långsträckt vägg · per meter", "value": "vagg"}, {"label": "Pelare", "value": "pelare"}],
               help="Talvärden behålls vid byte. Anpassa lasterna till kN/kNm eller kN/m och kNm/m."),
        _field("fristaende", "Fristående holk", True, type="bool", help="På: böjarmering i högra väggen samt V_Ed,1 och V_Ed,2. Av: plattansluten, endast V_Ed,2 till tvärkraftskontroll.",
               help_html="På: böjarmering i högra väggen samt <i>V</i><sub>Ed,1</sub> och <i>V</i><sub>Ed,2</sub>. Av: plattansluten, endast <i>V</i><sub>Ed,2</sub> till tvärkraftskontroll."),
        _field("M", "Moment, medurs positivt", 100.0, "kNm", "<i>M</i>", presentation_if={**_WALL, "unit": "kNm/m"}),
        _field("Fv", "Vertikallast, nedåt positivt", 500.0, "kN", "<i>F</i><sub>v</sub>", presentation_if={**_WALL, "unit": "kN/m"}),
        _field("Fh", "Horisontallast, åt höger positivt", 30.0, "kN", "<i>F</i><sub>h</sub>", presentation_if={**_WALL, "unit": "kN/m"}),
        _field("h", "Pelarmått / väggtjocklek", 200.0, "mm", "<i>h</i>"),
        _field("l", "Insticksdjup", 350.0, "mm", "<i>l</i>", help="Från holköverkant till pelarfot. Modellen kräver l ≥ 1,2 h.",
               help_html="Från holköverkant till pelarfot. Modellen kräver <i>l</i> ≥ 1,2<i>h</i>.",
               help_check={"validator": "an_calcs.betong.pelarholk:_insticksdjup_ok", "fields": ["l", "h"]}),
        _field("D", "Beräkningsdjup ut ur snittet", 600.0, "mm", "<i>D</i>", fixed_if={**_WALL, "value": 1000.0}, presentation_if={**_WALL, "label": "Beräkningsdjup · 1 m strimla"}),
        _field("bv", "Vänster sidomått (skiss)", 300.0, "mm", "<i>b</i><sub>2</sub>", help="Från elementytan till fundamentkanten, inklusive igjutning."),
        _field("bh", "Höger sidomått", 500.0, "mm", "<i>b</i><sub>1</sub>", help="Inklusive igjutning. Används även för d vid fristående holk. B = b2 + h + b1.",
               help_html="Inklusive igjutning. Används även för <i>d</i> vid fristående holk. <i>B</i> = <i>b</i><sub>2</sub> + <i>h</i> + <i>b</i><sub>1</sub>."),
        _field("H", "Fundamenthöjd (skiss)", 650.0, "mm", "<i>H</i>"),
        _field("t_ig", "Igjutningstjocklek vid sidorna", 20.0, "mm", "<i>t</i><sub>ig</sub>"),
        _field("t_ig_b", "Igjutningstjocklek under pelarfoten", 20.0, "mm", "<i>t</i><sub>ig,b</sub>",
               help="Från pelarfoten till holkbotten. Används för vänstra väggens lastavstånd.",
               help_html="Från pelarfoten till holkbotten. <i>a</i><sub>v,2</sub> = 0,1<i>l</i> + <i>t</i><sub>ig,b</sub>."),
        _field("t_p", "Plattjocklek (skiss)", 150.0, "mm", "<i>t</i><sub>p</sub>", visible_if={"field": "fristaende", "equals": False}),
        _field("c_nom", "Täckskikt till dragstångens utsida", 35.0, "mm", "<i>c</i><sub>nom</sub>", visible_if=_FREE),
        _field("phi", "Dragstångens diameter", 16.0, "mm", "φ", visible_if=_FREE),
        _field("f_yd", "Dimensionerande sträckgräns", 500/1.15, "MPa", "<i>f</i><sub>yd</sub>", visible_if=_FREE),
        _field("mu", "Friktionskoefficient", 0.3, "", "μ", help="0 ≤ μ ≤ 0,3. Ingår i global jämvikt. Gynnsam lokal friktion försummas för holkväggens böjarmering."),
    ],
}

pelarholk = Pelarholk
