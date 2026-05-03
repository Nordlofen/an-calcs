import math
from dataclasses import dataclass


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


SUPPORTED_GANGTYPER = {"slat-hals", "helgangad", "klamskruv"}
SUPPORTED_CONNECTION_TYPES = {"tra-tra"}
FUTURE_CONNECTION_TYPES = {"stal-tra", "skiva-tra"}
VALID_CONNECTION_TYPES = SUPPORTED_CONNECTION_TYPES | FUTURE_CONNECTION_TYPES


@dataclass
class AxialDragTraskruvInput:
    gangtyp: str
    anslutningstyp: str
    andtra: bool
    V_Ed_kN: float
    d: float
    d_h: float
    L: float
    Lg: float | None
    rho_k_1: float
    rho_k_2: float
    t_1: float
    t_2: float
    f_ax_k: float
    f_head_k: float
    f_tens_k: float
    alpha_ax: float
    rho_a: float


def _normalize_text(value):
    return str(value).strip().lower().replace("_", "-")


def _bool(value, namn):
    if isinstance(value, bool):
        return value
    raise ValueError(f"{namn} måste vara bool.")


def _sin_deg(vinkel):
    return math.sin(math.radians(vinkel))


def _cos_deg(vinkel):
    return math.cos(math.radians(vinkel))


def _krav_storre_an_noll(namn, value):
    if value <= 0:
        raise ValueError(f"{namn} måste vara > 0.")


def _optional_float(value):
    if value is None:
        return None
    return float(value)


def _hamta_px(px):
    if not isinstance(px, (list, tuple)):
        raise ValueError("px för axialdrag_traskruv måste vara en lista eller tuple.")
    if len(px) not in {16, 17}:
        raise ValueError("px för axialdrag_traskruv måste innehålla 16 eller 17 värden.")

    (
        gangtyp,
        anslutningstyp,
        andtra,
        V_Ed_kN,
        d,
        d_h,
        L,
        Lg,
        rho_k_1,
        rho_k_2,
        t_1,
        t_2,
        f_ax_k,
        f_head_k,
        f_tens_k,
        alpha_ax,
        *rest,
    ) = px
    rho_a = rest[0] if rest else 350.0

    data = AxialDragTraskruvInput(
        gangtyp=_normalize_text(gangtyp),
        anslutningstyp=_normalize_text(anslutningstyp),
        andtra=_bool(andtra, "andtra"),
        V_Ed_kN=float(V_Ed_kN),
        d=float(d),
        d_h=float(d_h),
        L=float(L),
        Lg=_optional_float(Lg),
        rho_k_1=float(rho_k_1),
        rho_k_2=float(rho_k_2),
        t_1=float(t_1),
        t_2=float(t_2),
        f_ax_k=float(f_ax_k),
        f_head_k=float(f_head_k),
        f_tens_k=float(f_tens_k),
        alpha_ax=float(alpha_ax),
        rho_a=float(rho_a),
    )

    if data.gangtyp not in SUPPORTED_GANGTYPER:
        raise ValueError("gangtyp måste vara 'slat-hals', 'helgangad' eller 'klamskruv'.")
    if data.anslutningstyp not in VALID_CONNECTION_TYPES:
        raise ValueError("anslutningstyp måste vara 'tra-tra', 'stal-tra' eller 'skiva-tra'.")
    if data.anslutningstyp not in SUPPORTED_CONNECTION_TYPES:
        raise NotImplementedError(
            "axialdrag_traskruv är i nuläget endast validerad för anslutningstyp 'tra-tra'. "
            f"'{data.anslutningstyp}' finns kvar som reserverat indatafall för framtida implementation."
        )

    for namn in (
        "V_Ed_kN",
        "d",
        "d_h",
        "L",
        "rho_k_1",
        "rho_k_2",
        "t_1",
        "t_2",
        "f_ax_k",
        "f_head_k",
        "f_tens_k",
        "alpha_ax",
        "rho_a",
    ):
        _krav_storre_an_noll(namn, getattr(data, namn))
    if data.gangtyp in {"slat-hals", "klamskruv"}:
        if data.Lg is None:
            raise ValueError("Lg måste anges för slat-hals och klamskruv.")
        _krav_storre_an_noll("Lg", data.Lg)
    elif data.Lg is not None and data.Lg <= 0:
        raise ValueError("Lg måste vara > 0 om det anges.")

    if data.andtra:
        if data.alpha_ax < 30 or data.alpha_ax > 45:
            raise ValueError("vid andtra=True måste alpha_ax ligga mellan 30 och 45 grader.")
    else:
        alpha = 90.0 - data.alpha_ax
        if alpha < 30 or alpha > 90:
            raise ValueError("vid andtra=False måste alpha_1=alpha_2=90-alpha_ax ligga mellan 30 och 90 grader.")
    return data


def _vinklar(data):
    if data.andtra:
        return 90.0, data.alpha_ax
    alpha = 90.0 - data.alpha_ax
    return alpha, alpha


def _effektiva_langder(data):
    cos_alpha = _cos_deg(data.alpha_ax)
    if cos_alpha <= 0:
        raise ValueError("alpha_ax ger ogiltig geometri eftersom cos(alpha_ax) måste vara > 0.")

    l_ef_1_geometri = data.t_1 / cos_alpha - 15.0
    l_ef_2_bas = data.L - data.t_1 / cos_alpha - 15.0
    if data.andtra:
        l_ef_2_geometri = l_ef_2_bas
    else:
        l_ef_2_geometri = min(l_ef_2_bas, data.t_2 / cos_alpha - 15.0)

    l_ef_1 = l_ef_1_geometri
    l_ef_2 = l_ef_2_geometri
    if data.gangtyp == "slat-hals":
        l_ef_2 = min(l_ef_2_geometri, data.Lg)
    elif data.gangtyp == "klamskruv":
        l_ef_1 = min(l_ef_1_geometri, data.Lg)
        l_ef_2 = min(l_ef_2_geometri, data.Lg)

    if l_ef_2 < 6.0 * data.d:
        raise ValueError("l_ef_2 måste vara minst 6d.")
    if data.gangtyp in {"helgangad", "klamskruv"} and l_ef_1 <= 0:
        raise ValueError("l_ef_1 måste vara > 0 för helgängad träskruv och klämskruv.")
    return l_ef_1, l_ef_2, l_ef_2_bas, l_ef_1_geometri, l_ef_2_geometri


def _withdrawal_capacity(f_ax_k, d, l_ef, alpha, rho_k, rho_a):
    alpha_factor = 1.2 * _cos_deg(alpha) ** 2 + _sin_deg(alpha) ** 2
    density_factor = (rho_k / rho_a) ** 0.8
    return f_ax_k * d * l_ef / alpha_factor * density_factor


def _berakna(data):
    alpha_1, alpha_2 = _vinklar(data)
    l_ef_1, l_ef_2, l_ef_2_bas, l_ef_1_geometri, l_ef_2_geometri = _effektiva_langder(data)

    f_t_ed = data.V_Ed_kN * 1000.0 / _sin_deg(data.alpha_ax)
    f_ax_w_1 = None
    if data.gangtyp in {"helgangad", "klamskruv"}:
        f_ax_w_1 = _withdrawal_capacity(data.f_ax_k, data.d, l_ef_1, alpha_1, data.rho_k_1, data.rho_a)
    f_ax_w_2 = _withdrawal_capacity(data.f_ax_k, data.d, l_ef_2, alpha_2, data.rho_k_2, data.rho_a)
    f_ax_h = data.f_head_k * data.d_h**2 * (data.rho_k_1 / data.rho_a) ** 0.8

    if data.gangtyp in {"helgangad", "klamskruv"}:
        f_ax_1 = max(f_ax_w_1, f_ax_h)
        mode_1 = "utdragning del 1" if f_ax_w_1 >= f_ax_h else "huvudgenomdragning"
    else:
        f_ax_1 = f_ax_h
        mode_1 = "huvudgenomdragning"
    f_ax_2 = f_ax_w_2

    active = {
        "del 1": f_ax_1,
        "del 2": f_ax_2,
        "dragbrott skruv": data.f_tens_k,
    }
    controlling_mode = min(active, key=active.get)

    return {
        "alpha_1": alpha_1,
        "alpha_2": alpha_2,
        "l_ef_1": l_ef_1 if data.gangtyp in {"helgangad", "klamskruv"} else None,
        "l_ef_2": l_ef_2,
        "l_ef_2_bas": l_ef_2_bas,
        "l_ef_1_geometri": l_ef_1_geometri,
        "l_ef_2_geometri": l_ef_2_geometri,
        "F_t_Ed": f_t_ed,
        "F_ax_w_1": f_ax_w_1,
        "F_ax_w_2": f_ax_w_2,
        "F_ax_h": f_ax_h,
        "F_ax_1": f_ax_1,
        "F_ax_2": f_ax_2,
        "F_t_Rk": data.f_tens_k,
        "F_ax_Rk": active[controlling_mode],
        "brottmod_del_1": mode_1,
        "brottmod_styrande": controlling_mode,
        "a_1": 7.0 * data.d,
        "a_2": 5.0 * data.d,
        "a_1_CG": 10.0 * data.d,
        "a_2_CG": 4.0 * data.d,
    }


def axialdrag_traskruv(px):
    """
    Beräknar karakteristisk axial dragbärförmåga för träskruv i trä-trä-förband.

    Funktionen avser endast träskruvar belastade i axiellt drag enligt EC5 8.7.
    Tryckbelastade skruvar omfattas inte. Funktionen redovisar även skruvens
    dragkraft ``F_t,Ed`` från användarens dimensionerande upplagsreaktion
    ``V_Ed``, men gör ingen dimensionerande verifiering mot ``F_ax,Rd``.

    Delkonventionen är fast:

    - Del 1 = virkesdel invid skruvhuvudet
    - Del 2 = spetsmottagande virkesdel

    ``px`` ska innehålla 16 eller 17 värden:

    ```python
    [
        gangtyp,        # "slat-hals", "helgangad" eller "klamskruv"
        anslutningstyp, # endast "tra-tra" stöds i nuläget
        andtra,         # bool; True innebär ändträ i del 2 och sidoträ i del 1
        V_Ed_kN,        # dimensionerande upplagsreaktion [kN]
        d,              # ytterdiameter [mm]
        d_h,            # huvuddiameter [mm]
        L,              # skruvlängd längs skruvaxel [mm]
        Lg,             # gängad längd [mm], krävs för slat-hals och klamskruv
        rho_k_1,        # karakteristisk densitet del 1 [kg/m3]
        rho_k_2,        # karakteristisk densitet del 2 [kg/m3]
        t_1,            # tjocklek del 1 [mm]
        t_2,            # tjocklek del 2 [mm]
        f_ax_k,         # utdragshållfasthet [N/mm2]
        f_head_k,       # huvudgenomdragningshållfasthet [N/mm2]
        f_tens_k,       # karakteristisk dragbärförmåga i skruv [N]
        alpha_ax,       # installationsvinkel [deg]
        rho_a,          # valfri referensdensitet [kg/m3], default 350
    ]
    ```

    Vid ``andtra=True`` sätts ``alpha_1=90°`` och ``alpha_2=alpha_ax``.
    Vid ``andtra=False`` sätts ``alpha_1=alpha_2=90°-alpha_ax``.
    ``alpha_1`` och ``alpha_2`` är vinklarna mellan skruvaxel och fiberriktning.

    Funktionen beräknar minimiavstånd enligt EC5 Tabell 8.6 som information,
    men kontrollerar inte faktisk skruvplacering, kantavstånd, ändavstånd eller
    att skruvarna får plats i virket. För enskilda skruvprodukter kan
    tillverkare ange mindre installationsavstånd i ETA/produktdokumentation;
    särskilt anges ``a_2,CG`` ofta som 3d även om EC5-värdet här redovisas som 4d.

    ``Lg`` begränsar effektiv gänglängd för träskruv med slät hals och
    klämskruv. För ``"slat-hals"`` begränsas endast ``l_ef,2``. För
    ``"klamskruv"`` begränsas både ``l_ef,1`` och ``l_ef,2``. För
    ``"helgangad"`` används inte ``Lg`` och kan anges som ``None``.
    """
    data = _hamta_px(px)
    axial = _berakna(data)

    indata_items = [
        _post("gangtyp", r"\mathrm{gangtyp}", data.gangtyp, "-", "träskruvens gängutförande"),
        _post("anslutningstyp", r"\mathrm{anslutning}", data.anslutningstyp, "-", "endast tra-tra stöds i nuläget"),
        _post("andtra", r"\mathrm{andtra}", data.andtra, "-", "True innebär ändträ i del 2 och sidoträ i del 1"),
        _post("del_1", r"\mathrm{del\ 1}", "virkesdel invid skruvhuvudet", "-", "fast delkonvention"),
        _post("del_2", r"\mathrm{del\ 2}", "spetsmottagande virkesdel", "-", "fast delkonvention"),
        _post("V_Ed", r"V_{Ed}", data.V_Ed_kN, "kN", "dimensionerande upplagsreaktion"),
        _post("d", "d", data.d, "mm", "skruvens ytterdiameter"),
        _post("d_h", r"d_h", data.d_h, "mm", "huvuddiameter"),
        _post("L", "L", data.L, "mm", "skruvlängd längs skruvaxel"),
        _post("rho_k_1", r"\rho_{k,1}", data.rho_k_1, "kg/m^3", "karakteristisk densitet i del 1"),
        _post("rho_k_2", r"\rho_{k,2}", data.rho_k_2, "kg/m^3", "karakteristisk densitet i del 2"),
        _post("t_1", r"t_1", data.t_1, "mm", "tjocklek del 1"),
        _post("t_2", r"t_2", data.t_2, "mm", "tjocklek del 2"),
        _post("f_ax_k", r"f_{ax,k}", data.f_ax_k, "N/mm^2", "utdragshållfasthet"),
        _post("f_head_k", r"f_{head,k}", data.f_head_k, "N/mm^2", "huvudgenomdragningshållfasthet"),
        _post("f_tens_k", r"F_{t,Rk}", data.f_tens_k, "N", "karakteristisk dragbärförmåga i skruven"),
        _post("alpha_ax", r"\alpha_{ax}", data.alpha_ax, "deg", "installationsvinkel"),
        _post("rho_a", r"\rho_a", data.rho_a, "kg/m^3", "referensdensitet"),
    ]
    if data.Lg is not None:
        indata_items.insert(9, _post("Lg", r"L_g", data.Lg, "mm", "gängad längd, används för slät hals och klämskruv"))

    delresultat_items = [
        _post("alpha_1", r"\alpha_1", axial["alpha_1"], "deg", "vinkel mellan skruvaxel och fiber i del 1"),
        _post("alpha_2", r"\alpha_2", axial["alpha_2"], "deg", "vinkel mellan skruvaxel och fiber i del 2"),
        _post("F_t_Ed", r"F_{t,Ed}", axial["F_t_Ed"], "N", "dragkraft från V_Ed; ingen verifiering görs"),
    ]
    if axial["l_ef_1"] is not None:
        delresultat_items.append(_post("l_ef_1", r"l_{ef,1}", axial["l_ef_1"], "mm", "effektiv gänglängd i del 1"))
        delresultat_items.append(_post("F_ax_w_1", r"F_{ax,w,1}", axial["F_ax_w_1"], "N", "utdragsbärförmåga i del 1"))
    delresultat_items.extend(
        [
            _post("l_ef_2", r"l_{ef,2}", axial["l_ef_2"], "mm", "effektiv gänglängd i del 2"),
            _post("F_ax_w_2", r"F_{ax,w,2}", axial["F_ax_w_2"], "N", "utdragsbärförmåga i del 2"),
            _post("F_ax_h", r"F_{ax,h}", axial["F_ax_h"], "N", "huvudgenomdragningsbärförmåga i del 1"),
            _post("F_ax_1", r"F_{ax,1}", axial["F_ax_1"], "N", "bärförmåga i del 1"),
            _post("F_ax_2", r"F_{ax,2}", axial["F_ax_2"], "N", "bärförmåga i del 2"),
            _post("F_t_Rk", r"F_{t,Rk}", axial["F_t_Rk"], "N", "karakteristisk dragbärförmåga i skruven"),
            _post("F_ax_Rk", r"F_{ax,Rk}", axial["F_ax_Rk"], "N", "karakteristisk axial dragbärförmåga"),
            _post("brottmod_del_1", r"\mathrm{mode}_1", axial["brottmod_del_1"], "-", "styrande delmodell i del 1"),
            _post("brottmod_styrande", r"\mathrm{mode}", axial["brottmod_styrande"], "-", "styrande brottmod"),
            _post("a_1", r"a_1", axial["a_1"], "mm", "minsta inbördes avstånd parallellt fiberriktning, EC5 Tabell 8.6"),
            _post("a_2", r"a_2", axial["a_2"], "mm", "minsta inbördes avstånd vinkelrätt fiberriktning, EC5 Tabell 8.6"),
            _post("a_1_CG", r"a_{1,CG}", axial["a_1_CG"], "mm", "minsta ändavstånd från tyngdpunkt för gängad del, EC5 Tabell 8.6"),
            _post("a_2_CG", r"a_{2,CG}", axial["a_2_CG"], "mm", "minsta kantavstånd EC5 4d; tillverkare anger ofta 3d i ETA/produktdata"),
        ]
    )

    ekvationer = [
        _ekvation(r"F_{t,Ed} = V_{Ed} / \sin(\alpha_{ax})", "dragkraft i skruv från upplagsreaktion"),
    ]
    if data.gangtyp == "helgangad":
        ekvationer.append(_ekvation(r"l_{ef,1} = \frac{t_1}{\cos(\alpha_{ax})} - 10 - \frac{10}{2}", "effektiv gänglängd i del 1"))
    elif data.gangtyp == "klamskruv":
        ekvationer.append(_ekvation(r"l_{ef,1} = \min\left(\frac{t_1}{\cos(\alpha_{ax})} - 10 - \frac{10}{2},\ L_g\right)", "effektiv gänglängd i del 1 för klämskruv"))
    if data.andtra:
        if data.gangtyp in {"slat-hals", "klamskruv"}:
            ekvationer.append(_ekvation(r"l_{ef,2} = \min\left(L - \frac{t_1}{\cos(\alpha_{ax})} - 10 - \frac{10}{2},\ L_g\right)", "effektiv gänglängd i del 2 vid ändträ"))
        else:
            ekvationer.append(_ekvation(r"l_{ef,2} = L - \frac{t_1}{\cos(\alpha_{ax})} - 10 - \frac{10}{2}", "effektiv gänglängd i del 2 vid ändträ"))
    else:
        if data.gangtyp in {"slat-hals", "klamskruv"}:
            ekvationer.append(
                _ekvation(
                    r"l_{ef,2} = \min\left(L - \frac{t_1}{\cos(\alpha_{ax})} - 10 - \frac{10}{2},\ \frac{t_2}{\cos(\alpha_{ax})} - 10 - \frac{10}{2},\ L_g\right)",
                    "effektiv gänglängd i del 2 vid sidoträ",
                )
            )
        else:
            ekvationer.append(
                _ekvation(
                    r"l_{ef,2} = \min\left(L - \frac{t_1}{\cos(\alpha_{ax})} - 10 - \frac{10}{2},\ \frac{t_2}{\cos(\alpha_{ax})} - 10 - \frac{10}{2}\right)",
                    "effektiv gänglängd i del 2 vid sidoträ",
                )
            )
    ekvationer.extend(
        [
            _ekvation(r"F_{ax,w,i} = \frac{f_{ax,k} d l_{ef,i}}{1.2\cos^2(\alpha_i)+\sin^2(\alpha_i)} \left(\frac{\rho_{k,i}}{\rho_a}\right)^{0.8}", "utdragning, EC5 Eq. (8.40a), n_ef=1"),
            _ekvation(r"F_{ax,h} = f_{head,k} d_h^2 \left(\frac{\rho_{k,1}}{\rho_a}\right)^{0.8}", "huvudgenomdragning, EC5 Eq. (8.40b)"),
            _ekvation(r"F_{ax,2} = F_{ax,w,2}", "bärförmåga i spetsmottagande del"),
            _ekvation(r"F_{ax,Rk} = \min(F_{ax,1}, F_{ax,2}, F_{t,Rk})", "karakteristisk axial dragbärförmåga, EC5 8.7"),
            _ekvation(r"a_1=7d,\ a_2=5d,\ a_{1,CG}=10d,\ a_{2,CG}=4d", "minimiavstånd, EC5 Tabell 8.6"),
        ]
    )
    if data.gangtyp in {"helgangad", "klamskruv"}:
        ekvationer.append(_ekvation(r"F_{ax,1} = \max(F_{ax,w,1}, F_{ax,h})", "bärförmåga i del 1 för helgängad träskruv eller klämskruv"))
    else:
        ekvationer.append(_ekvation(r"F_{ax,1} = F_{ax,h}", "bärförmåga i del 1 för träskruv med slät hals"))

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Funktionen beräknar karakteristisk axial dragbärförmåga för dragbelastad träskruv "
                        "i trä-trä-förband enligt EC5 8.7. Del 1 är virkesdel invid skruvhuvudet och "
                        "del 2 är spetsmottagande virkesdel."
                    ),
                },
                {
                    "rubrik": "Begränsningar",
                    "text": (
                        "Tryckbelastade skruvar, stål-trä och skiva-trä ingår inte. Funktionen kontrollerar "
                        "inte faktisk placering, kantavstånd, ändavstånd eller att skruvarna får plats i virket."
                    ),
                },
            ],
        },
        "indata": {"title": "Indata", "items": indata_items},
        "delresultat": {"title": "Delresultat", "items": delresultat_items},
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("F_ax_Rk", r"F_{ax,Rk}", axial["F_ax_Rk"], "N", "karakteristisk axial dragbärförmåga"),
                _post("F_t_Ed", r"F_{t,Ed}", axial["F_t_Ed"], "N", "dragkraft från V_Ed; ingen verifiering görs"),
                _post("brottmod_styrande", r"\mathrm{mode}", axial["brottmod_styrande"], "-", "styrande brottmod"),
            ],
        },
        "ekvationer": {"title": "Ekvationer", "items": ekvationer},
    }
