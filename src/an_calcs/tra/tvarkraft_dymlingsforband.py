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


WOOD_TYPES = {"konstruktionsvirke", "hardtra", "limtra", "kl-tra", "lvl"}
SHEET_TYPES = {"plywood", "osb", "spanskiva"}
STEEL_TYPE = "stal"
VALID_FASTENER_TYPES = {"spik", "skruv", "traskruv"}
VALID_SHEAR_MODELS = {"auto", "spikregler", "skruvregler"}
VALID_CONNECTION_TYPES = {"tra-tra", "stal-tra", "tra-skiva", "skiva-tra"}
VALID_NAIL_TYPES = {"slat", "profilerad"}
VALID_INFASTNING_TYPES = {"sidotra", "andtra"}


@dataclass
class FastenerInput:
    forbindartyp: str
    tvarkraftsmodell: str
    anslutningstyp: str
    materialtyp_1: str
    materialtyp_2: str
    t_1: float
    t_2: float
    rho_k_1: float
    rho_k_2: float
    alpha_1: float
    alpha_2: float
    d: float
    d_h: float
    l: float
    f_u: float
    n_rader: int
    n_per_rad: int
    tvarforskjuten_1d: bool
    forborrad: bool
    infastning_1: str = "sidotra"
    infastning_2: str = "sidotra"
    spiktyp: str | None = None
    l_gang: float | None = None
    slat_hals: bool | None = None
    my_rk_input: float | None = None
    f_ax_k_input: float | None = None
    f_head_k_input: float | None = None
    f_tens_k_input: float | None = None
    rho_a_input: float | None = None
    alpha_ax_input: float | None = None
    normativ_tvarkraftsgren: str | None = None
    normativ_axialgren: str | None = None
    d_eff: float | None = None


def _is_wood(materialtyp):
    return materialtyp in WOOD_TYPES


def _is_sheet(materialtyp):
    return materialtyp in SHEET_TYPES


def _is_steel(materialtyp):
    return materialtyp == STEEL_TYPE


def _sin_deg(vinkel):
    return math.sin(math.radians(vinkel))


def _cos_deg(vinkel):
    return math.cos(math.radians(vinkel))


def _krav_storre_an_noll(namn, value):
    if value <= 0:
        raise ValueError(f"{namn} måste vara > 0.")


def _krav_icke_negativ(namn, value):
    if value < 0:
        raise ValueError(f"{namn} måste vara >= 0.")


def _optional_float(value):
    if value is None:
        return None
    return float(value)


def _normalize_text(value):
    return str(value).strip().lower()


def _validera_gemensamt(data):
    if data.tvarkraftsmodell not in VALID_SHEAR_MODELS:
        raise ValueError("tvarkraftsmodell måste vara 'auto', 'spikregler' eller 'skruvregler'.")
    if data.anslutningstyp not in VALID_CONNECTION_TYPES:
        raise ValueError("anslutningstyp måste vara 'tra-tra', 'stal-tra', 'tra-skiva' eller 'skiva-tra'.")
    if data.materialtyp_1 not in WOOD_TYPES | SHEET_TYPES | {STEEL_TYPE}:
        raise ValueError("materialtyp_1 är ogiltig.")
    if data.materialtyp_2 not in WOOD_TYPES | SHEET_TYPES | {STEEL_TYPE}:
        raise ValueError("materialtyp_2 är ogiltig.")

    _krav_storre_an_noll("t_1", data.t_1)
    _krav_storre_an_noll("t_2", data.t_2)
    _krav_icke_negativ("rho_k_1", data.rho_k_1)
    _krav_icke_negativ("rho_k_2", data.rho_k_2)
    _krav_storre_an_noll("d", data.d)
    _krav_storre_an_noll("d_h", data.d_h)
    _krav_storre_an_noll("l", data.l)
    _krav_storre_an_noll("f_u", data.f_u)
    _krav_storre_an_noll("n_rader", data.n_rader)
    _krav_storre_an_noll("n_per_rad", data.n_per_rad)
    if data.my_rk_input is not None:
        _krav_storre_an_noll("M_y_Rk", data.my_rk_input)
    for namn, value in (
        ("f_ax_k", data.f_ax_k_input),
        ("f_head_k", data.f_head_k_input),
        ("f_tens_k", data.f_tens_k_input),
        ("rho_a", data.rho_a_input),
    ):
        if value is not None:
            _krav_icke_negativ(namn, value)
    if data.alpha_ax_input is not None and (data.alpha_ax_input < 0 or data.alpha_ax_input > 90):
        raise ValueError("alpha_ax måste ligga mellan 0 och 90 grader.")

    for namn, value in (("alpha_1", data.alpha_1), ("alpha_2", data.alpha_2)):
        if value < 0 or value > 360:
            raise ValueError(f"{namn} måste ligga mellan 0 och 360 grader.")

    if data.infastning_1 not in VALID_INFASTNING_TYPES:
        raise ValueError("infastning_1 måste vara 'sidotra' eller 'andtra'.")
    if data.infastning_2 not in VALID_INFASTNING_TYPES:
        raise ValueError("infastning_2 måste vara 'sidotra' eller 'andtra'.")
    if data.infastning_1 == "andtra" and not _is_wood(data.materialtyp_1):
        raise ValueError("infastning_1='andtra' får bara användas för trädel.")
    if data.infastning_2 == "andtra" and not _is_wood(data.materialtyp_2):
        raise ValueError("infastning_2='andtra' får bara användas för trädel.")

    if data.anslutningstyp == "tra-tra":
        if not ((_is_wood(data.materialtyp_1) or _is_sheet(data.materialtyp_1)) and (_is_wood(data.materialtyp_2) or _is_sheet(data.materialtyp_2))):
            raise ValueError("tra-tra kräver två trä- eller skivdelar.")
    elif data.anslutningstyp == "stal-tra":
        if not (_is_steel(data.materialtyp_1) ^ _is_steel(data.materialtyp_2)):
            raise ValueError("stal-tra kräver exakt en ståldel.")
    elif data.anslutningstyp == "tra-skiva":
        if not _is_wood(data.materialtyp_1) or not _is_sheet(data.materialtyp_2):
            raise ValueError("tra-skiva kräver trä i del 1 och skiva i del 2.")
    elif data.anslutningstyp == "skiva-tra":
        if not _is_sheet(data.materialtyp_1) or not _is_wood(data.materialtyp_2):
            raise ValueError("skiva-tra kräver skiva i del 1 och trä i del 2.")


def _tolka_px_spik(px):
    my_rk_input = None
    if len(px) in {20, 21}:
        if len(px) == 21:
            my_rk_input = float(px[-1])
            px = px[:-1]
        (
            forbindartyp,
            tvarkraftsmodell,
            anslutningstyp,
            materialtyp_1,
            materialtyp_2,
            t_1,
            t_2,
            rho_k_1,
            rho_k_2,
            alpha_1,
            alpha_2,
            d,
            d_h,
            l,
            f_u,
            spiktyp,
            n_rader,
            n_per_rad,
            tvarforskjuten_1d,
            forborrad,
        ) = px
        infastning_1 = "sidotra"
        infastning_2 = "sidotra"
    elif len(px) in {22, 23}:
        if len(px) == 23:
            my_rk_input = float(px[-1])
            px = px[:-1]
        (
            forbindartyp,
            tvarkraftsmodell,
            anslutningstyp,
            materialtyp_1,
            materialtyp_2,
            t_1,
            t_2,
            rho_k_1,
            rho_k_2,
            alpha_1,
            alpha_2,
            infastning_1,
            infastning_2,
            d,
            d_h,
            l,
            f_u,
            spiktyp,
            n_rader,
            n_per_rad,
            tvarforskjuten_1d,
            forborrad,
        ) = px
    else:
        raise ValueError("px för spik måste innehålla 20, 21, 22 eller 23 värden.")
    data = FastenerInput(
        forbindartyp=_normalize_text(forbindartyp),
        tvarkraftsmodell=_normalize_text(tvarkraftsmodell),
        anslutningstyp=_normalize_text(anslutningstyp),
        materialtyp_1=_normalize_text(materialtyp_1),
        materialtyp_2=_normalize_text(materialtyp_2),
        t_1=float(t_1),
        t_2=float(t_2),
        rho_k_1=float(rho_k_1),
        rho_k_2=float(rho_k_2),
        alpha_1=float(alpha_1),
        alpha_2=float(alpha_2),
        infastning_1=_normalize_text(infastning_1),
        infastning_2=_normalize_text(infastning_2),
        d=float(d),
        d_h=float(d_h),
        l=float(l),
        f_u=float(f_u),
        my_rk_input=my_rk_input,
        spiktyp=_normalize_text(spiktyp),
        n_rader=int(n_rader),
        n_per_rad=int(n_per_rad),
        tvarforskjuten_1d=bool(tvarforskjuten_1d),
        forborrad=bool(forborrad),
    )
    if data.spiktyp not in VALID_NAIL_TYPES:
        raise ValueError("spiktyp måste vara 'slat' eller 'profilerad'.")
    _validera_gemensamt(data)
    return data


def _tolka_px_skruv(px):
    my_rk_input = None
    if len(px) in {19, 20}:
        if len(px) == 20:
            my_rk_input = float(px[-1])
            px = px[:-1]
        (
            forbindartyp,
            tvarkraftsmodell,
            anslutningstyp,
            materialtyp_1,
            materialtyp_2,
            t_1,
            t_2,
            rho_k_1,
            rho_k_2,
            alpha_1,
            alpha_2,
            d,
            d_h,
            l,
            f_u,
            n_rader,
            n_per_rad,
            tvarforskjuten_1d,
            forborrad,
        ) = px
        infastning_1 = "sidotra"
        infastning_2 = "sidotra"
    elif len(px) in {21, 22}:
        if len(px) == 22:
            my_rk_input = float(px[-1])
            px = px[:-1]
        (
            forbindartyp,
            tvarkraftsmodell,
            anslutningstyp,
            materialtyp_1,
            materialtyp_2,
            t_1,
            t_2,
            rho_k_1,
            rho_k_2,
            alpha_1,
            alpha_2,
            infastning_1,
            infastning_2,
            d,
            d_h,
            l,
            f_u,
            n_rader,
            n_per_rad,
            tvarforskjuten_1d,
            forborrad,
        ) = px
    else:
        raise ValueError("px för skruv måste innehålla 19, 20, 21 eller 22 värden.")
    data = FastenerInput(
        forbindartyp=_normalize_text(forbindartyp),
        tvarkraftsmodell=_normalize_text(tvarkraftsmodell),
        anslutningstyp=_normalize_text(anslutningstyp),
        materialtyp_1=_normalize_text(materialtyp_1),
        materialtyp_2=_normalize_text(materialtyp_2),
        t_1=float(t_1),
        t_2=float(t_2),
        rho_k_1=float(rho_k_1),
        rho_k_2=float(rho_k_2),
        alpha_1=float(alpha_1),
        alpha_2=float(alpha_2),
        infastning_1=_normalize_text(infastning_1),
        infastning_2=_normalize_text(infastning_2),
        d=float(d),
        d_h=float(d_h),
        l=float(l),
        f_u=float(f_u),
        my_rk_input=my_rk_input,
        n_rader=int(n_rader),
        n_per_rad=int(n_per_rad),
        tvarforskjuten_1d=bool(tvarforskjuten_1d),
        forborrad=bool(forborrad),
    )
    _validera_gemensamt(data)
    return data


def _tolka_px_traskruv(px):
    px = list(px)
    axial_props = {}
    if px and isinstance(px[-1], dict):
        axial_props = dict(px.pop())

    my_rk_input = None
    if len(px) in {21, 22}:
        if len(px) == 22:
            my_rk_input = float(px[-1])
            px = px[:-1]
        (
            forbindartyp,
            tvarkraftsmodell,
            anslutningstyp,
            materialtyp_1,
            materialtyp_2,
            t_1,
            t_2,
            rho_k_1,
            rho_k_2,
            alpha_1,
            alpha_2,
            d,
            d_h,
            l,
            l_gang,
            f_u,
            slat_hals,
            n_rader,
            n_per_rad,
            tvarforskjuten_1d,
            forborrad,
        ) = px
        infastning_1 = "sidotra"
        infastning_2 = "sidotra"
    elif len(px) in {23, 24}:
        if len(px) == 24 and not (isinstance(px[-1], str) and isinstance(px[-2], str)):
            my_rk_input = float(px[-1])
            px = px[:-1]
        if isinstance(px[-1], str) and isinstance(px[-2], str):
            (
                forbindartyp,
                tvarkraftsmodell,
                anslutningstyp,
                materialtyp_1,
                materialtyp_2,
                t_1,
                t_2,
                rho_k_1,
                rho_k_2,
                alpha_1,
                alpha_2,
                d,
                d_h,
                l,
                l_gang,
                f_u,
                slat_hals,
                n_rader,
                n_per_rad,
                tvarforskjuten_1d,
                forborrad,
                infastning_1,
                infastning_2,
            ) = px
        else:
            (
                forbindartyp,
                tvarkraftsmodell,
                anslutningstyp,
                materialtyp_1,
                materialtyp_2,
                t_1,
                t_2,
                rho_k_1,
                rho_k_2,
                alpha_1,
                alpha_2,
                infastning_1,
                infastning_2,
                d,
                d_h,
                l,
                l_gang,
                f_u,
                slat_hals,
                n_rader,
                n_per_rad,
                tvarforskjuten_1d,
                forborrad,
            ) = px
    else:
        raise ValueError("px för traskruv måste innehålla 21, 22, 23 eller 24 värden, plus eventuellt en avslutande dict med axialdata.")
    data = FastenerInput(
        forbindartyp=_normalize_text(forbindartyp),
        tvarkraftsmodell=_normalize_text(tvarkraftsmodell),
        anslutningstyp=_normalize_text(anslutningstyp),
        materialtyp_1=_normalize_text(materialtyp_1),
        materialtyp_2=_normalize_text(materialtyp_2),
        t_1=float(t_1),
        t_2=float(t_2),
        rho_k_1=float(rho_k_1),
        rho_k_2=float(rho_k_2),
        alpha_1=float(alpha_1),
        alpha_2=float(alpha_2),
        infastning_1=_normalize_text(infastning_1),
        infastning_2=_normalize_text(infastning_2),
        d=float(d),
        d_h=float(d_h),
        l=float(l),
        l_gang=float(l_gang),
        f_u=float(f_u),
        slat_hals=bool(slat_hals),
        my_rk_input=my_rk_input,
        f_ax_k_input=_optional_float(axial_props["f_ax_k"]) if "f_ax_k" in axial_props else None,
        f_head_k_input=_optional_float(axial_props["f_head_k"]) if "f_head_k" in axial_props else None,
        f_tens_k_input=_optional_float(axial_props["f_tens_k"]) if "f_tens_k" in axial_props else None,
        rho_a_input=_optional_float(axial_props["rho_a"]) if "rho_a" in axial_props else None,
        alpha_ax_input=_optional_float(axial_props["alpha_ax"]) if "alpha_ax" in axial_props else None,
        n_rader=int(n_rader),
        n_per_rad=int(n_per_rad),
        tvarforskjuten_1d=bool(tvarforskjuten_1d),
        forborrad=bool(forborrad),
    )
    _krav_storre_an_noll("l_gang", data.l_gang)
    _validera_gemensamt(data)
    return data


def _tolka_px(px):
    if not isinstance(px, (list, tuple)):
        raise TypeError("px måste vara en lista eller tuple.")
    if not px:
        raise ValueError("px måste innehålla minst ett värde.")

    forbindartyp = _normalize_text(px[0])
    if forbindartyp not in VALID_FASTENER_TYPES:
        raise ValueError("förbindartyp måste vara 'spik', 'skruv' eller 'traskruv'.")

    if forbindartyp == "spik":
        return _tolka_px_spik(px)
    if forbindartyp == "skruv":
        return _tolka_px_skruv(px)
    return _tolka_px_traskruv(px)


def _smooth_penetration_in_tip_member(data):
    if data.forbindartyp != "traskruv" or data.l_gang is None:
        return 0.0
    smooth_length = max(0.0, data.l - data.l_gang)
    return max(0.0, smooth_length - data.t_1)


def _fastener_penetration(data):
    return max(0.0, data.l - data.t_1)


def _effective_thicknesses(data):
    t_1_eff = data.t_1
    t_2_eff = data.t_2
    if data.infastning_2 == "andtra" and not _is_steel(data.materialtyp_2):
        t_2_eff = _fastener_penetration(data)
    return t_1_eff, t_2_eff


def _pick_normative_shear_branch(data):
    if data.tvarkraftsmodell == "spikregler":
        return "8.3"
    if data.tvarkraftsmodell == "skruvregler":
        return "8.5"
    if data.forbindartyp == "spik":
        return "8.3"
    if data.forbindartyp == "skruv":
        return "8.5"

    if data.slat_hals:
        if _smooth_penetration_in_tip_member(data) >= 4.0 * data.d:
            return "8.2"
        if data.d > 6.0:
            return "8.5"
        return "8.3"
    return "8.7"


def _pick_normative_axial_branch(data):
    if data.forbindartyp == "spik":
        return "8.3.2"
    if data.forbindartyp == "skruv":
        return "8.5.2"
    return "8.7.2"


def _effective_diameter(data):
    if data.forbindartyp != "traskruv":
        return data.d
    return 0.8 * data.d


def _k_90(materialtyp, d):
    if materialtyp == "hardtra":
        return 0.90 + 0.015 * d
    if materialtyp == "lvl":
        return 1.30 + 0.015 * d
    return 1.35 + 0.015 * d


def _embedment_strength(materialtyp, rho_k, alpha, d, d_h, t, branch, forborrad, infastning):
    if _is_steel(materialtyp):
        return None

    if infastning == "andtra" and _is_wood(materialtyp):
        factor_endgrain = 1.0 / 3.0 if branch == "8.3" else 0.4
    else:
        factor_endgrain = 1.0

    if branch == "8.3":
        if _is_sheet(materialtyp):
            return 0.11 * max(rho_k, 350.0) * d ** (-0.3)
        if d > 8.0:
            branch = "8.5"
        elif forborrad:
            return factor_endgrain * 0.082 * (1.0 - 0.01 * d) * rho_k
        else:
            return factor_endgrain * 0.082 * rho_k * d ** (-0.3)

    if branch in {"8.5", "8.2", "8.7"}:
        if _is_sheet(materialtyp):
            if materialtyp == "plywood":
                return 0.11 * max(rho_k, 350.0) * (1.0 - 0.01 * d)
            return 0.25 * math.sqrt(max(t, 1.0) / d) * max(10.0, min(rho_k / 10.0, 40.0))
        fh_0_k = 0.082 * (1.0 - 0.01 * d) * rho_k
        return factor_endgrain * fh_0_k / (_k_90(materialtyp, d) * _sin_deg(alpha) ** 2 + _cos_deg(alpha) ** 2)

    raise ValueError("Okänd normativ gren för bäddhållfasthet.")


def _embedment_components(materialtyp, rho_k, alpha, d, d_h, t, branch, forborrad, infastning):
    if _is_steel(materialtyp):
        return {
            "fh_k": None,
            "fh_0_k": None,
            "k_90": None,
            "endgrain_factor": None,
            "branch_used": branch,
        }

    if infastning == "andtra" and _is_wood(materialtyp):
        factor_endgrain = 1.0 / 3.0 if branch == "8.3" else 0.4
    else:
        factor_endgrain = 1.0

    if branch == "8.3":
        if _is_sheet(materialtyp):
            fh_k = 0.11 * max(rho_k, 350.0) * d ** (-0.3)
            return {
                "fh_k": fh_k,
                "fh_0_k": fh_k,
                "k_90": None,
                "endgrain_factor": factor_endgrain,
                "branch_used": branch,
            }
        if d > 8.0:
            branch = "8.5"
        elif forborrad:
            fh_0_k = 0.082 * (1.0 - 0.01 * d) * rho_k
            return {
                "fh_k": factor_endgrain * fh_0_k,
                "fh_0_k": fh_0_k,
                "k_90": None,
                "endgrain_factor": factor_endgrain,
                "branch_used": "8.3",
            }
        else:
            fh_0_k = 0.082 * rho_k * d ** (-0.3)
            return {
                "fh_k": factor_endgrain * fh_0_k,
                "fh_0_k": fh_0_k,
                "k_90": None,
                "endgrain_factor": factor_endgrain,
                "branch_used": "8.3",
            }

    if branch in {"8.5", "8.2", "8.7"}:
        if _is_sheet(materialtyp):
            if materialtyp == "plywood":
                fh_k = 0.11 * max(rho_k, 350.0) * (1.0 - 0.01 * d)
            else:
                fh_k = 0.25 * math.sqrt(max(t, 1.0) / d) * max(10.0, min(rho_k / 10.0, 40.0))
            return {
                "fh_k": fh_k,
                "fh_0_k": fh_k,
                "k_90": None,
                "endgrain_factor": factor_endgrain,
                "branch_used": branch,
            }
        fh_0_k = 0.082 * (1.0 - 0.01 * d) * rho_k
        k_90 = _k_90(materialtyp, d)
        fh_k = factor_endgrain * fh_0_k / (k_90 * _sin_deg(alpha) ** 2 + _cos_deg(alpha) ** 2)
        return {
            "fh_k": fh_k,
            "fh_0_k": fh_0_k,
            "k_90": k_90,
            "endgrain_factor": factor_endgrain,
            "branch_used": branch,
        }

    raise ValueError("Okänd normativ gren för bäddhållfasthet.")


def _yield_moment(data):
    if data.my_rk_input is not None:
        return data.my_rk_input
    if data.forbindartyp == "spik" and data.spiktyp == "profilerad":
        return 0.45 * data.f_u * data.d**2.6
    return 0.30 * data.f_u * data.d**2.6


def _timber_timber_shear_candidates(fh1, fh2, t1, t2, diameter, my_rk, line_effect):
    beta = fh2 / fh1

    candidates = {
        "a": fh1 * t1 * diameter,
        "b": fh2 * t2 * diameter,
    }

    root_c = beta + 2.0 * beta**2 * (1.0 + t2 / t1 + (t2 / t1) ** 2) + beta**3 * (t2 / t1) ** 2
    candidates["c"] = (fh1 * t1 * diameter / (1.0 + beta)) * (math.sqrt(root_c) - beta * (1.0 + t2 / t1))

    root_d = 2.0 * beta * (1.0 + beta) + 4.0 * beta * (2.0 + beta) * my_rk / (fh1 * diameter * t1**2)
    candidates["d"] = 1.05 * (fh1 * t1 * diameter / (2.0 + beta)) * (math.sqrt(root_d) - beta)

    root_e = 2.0 * beta**2 * (1.0 + beta) + 4.0 * beta * (1.0 + 2.0 * beta) * my_rk / (fh1 * diameter * t2**2)
    candidates["e"] = 1.05 * (fh1 * t2 * diameter / (1.0 + 2.0 * beta)) * (math.sqrt(root_e) - beta)

    candidates["f"] = 1.15 * math.sqrt((2.0 * beta / (1.0 + beta)) * (2.0 * my_rk * fh1 * diameter))
    return candidates


def _steel_timber_shear_candidates(fh, t_timber, diameter, my_rk, steel_thickness, line_effect):
    if steel_thickness <= 0.5 * diameter:
        candidates = {
            "k": 0.4 * fh * min(t_timber, _fastener_penetration_dummy := t_timber) * diameter,
            "l": 1.15 * math.sqrt(2.0 * my_rk * fh * diameter),
        }
    else:
        candidates = {
            "m": fh * t_timber * diameter,
            "n": 1.15 * math.sqrt(2.0 * my_rk * fh * diameter),
        }
    return candidates


def _line_effect_ratio(data):
    if data.forbindartyp == "traskruv":
        return 1.0
    if data.forbindartyp == "skruv":
        return 0.25
    if data.spiktyp == "profilerad":
        return 0.50
    return 0.25


def _axial_capacity_spik(data):
    if data.infastning_1 == "andtra" or data.infastning_2 == "andtra":
        return 0.0
    penetration = _fastener_penetration(data)
    rho = data.rho_k_2 if not _is_steel(data.materialtyp_2) else data.rho_k_1
    fax_k = 20e-6 * rho**2 if data.spiktyp == "slat" else 30e-6 * rho**2
    fhead_k = 70e-6 * rho**2
    withdrawal = fax_k * data.d * penetration
    pull_through = fhead_k * data.d_h**2
    return min(withdrawal, pull_through)


def _axial_capacity_skruv(data):
    area = math.pi * (max(data.d_h, 3.0 * data.d) ** 2) / 4.0
    fc_90_k = 2.5 if data.materialtyp_1 in WOOD_TYPES | SHEET_TYPES else 0.0
    washer_capacity = 3.0 * fc_90_k * area
    tensile_capacity = 0.9 * data.f_u * math.pi * data.d**2 / 4.0
    return min(tensile_capacity, washer_capacity) if washer_capacity > 0 else tensile_capacity


def _axial_enabled_traskruv(data):
    if data.alpha_ax_input is None:
        return False
    if not (data.f_ax_k_input and data.f_ax_k_input > 0 and data.f_tens_k_input and data.f_tens_k_input > 0):
        return False
    if data.anslutningstyp == "tra-tra" and not (data.f_head_k_input and data.f_head_k_input > 0):
        return False
    return True


def _axial_timber_material(data):
    if not _is_steel(data.materialtyp_2):
        return data.materialtyp_2, data.rho_k_2
    return data.materialtyp_1, data.rho_k_1


def _axial_components_traskruv(data):
    off = {
        "enabled": False,
        "l_ef": min(_fastener_penetration(data), data.l_gang),
        "k_ax": None,
        "k_beta": None,
        "rho_ax": None,
        "rho_a": data.rho_a_input or 350.0,
        "f_ax_k": data.f_ax_k_input,
        "f_head_k": data.f_head_k_input,
        "f_tens_k": data.f_tens_k_input,
        "alpha_ax": data.alpha_ax_input,
        "F_ax_w": 0.0,
        "F_ax_h": None,
        "F_t_Rk": data.f_tens_k_input if data.f_tens_k_input and data.f_tens_k_input > 0 else None,
        "F_ax_Rk": 0.0,
    }
    if not _axial_enabled_traskruv(data):
        return off

    materialtyp_ax, rho_ax = _axial_timber_material(data)
    l_ef = min(_fastener_penetration(data), data.l_gang)
    rho_a = data.rho_a_input or 350.0
    alpha_ax = data.alpha_ax_input
    if materialtyp_ax == "lvl":
        a_const = 0.5
        b_const = 0.5
        k_beta = 1.0
    else:
        a_const = 0.3
        b_const = 0.7
        k_beta = 1.0
    if alpha_ax >= 45.0:
        k_ax = 1.0
    else:
        k_ax = a_const + b_const * alpha_ax / 45.0

    f_ax_w = k_ax * data.f_ax_k_input * data.d * l_ef / k_beta * (rho_ax / rho_a) ** 0.8
    f_ax_h = None
    if data.anslutningstyp == "tra-tra":
        f_ax_h = data.f_head_k_input * data.d_h**2 * (rho_ax / rho_a) ** 0.8
    f_t_rk = data.f_tens_k_input
    active_modes = [f_ax_w, f_t_rk]
    if f_ax_h is not None:
        active_modes.append(f_ax_h)
    return {
        "enabled": True,
        "l_ef": l_ef,
        "k_ax": k_ax,
        "k_beta": k_beta,
        "rho_ax": rho_ax,
        "rho_a": rho_a,
        "f_ax_k": data.f_ax_k_input,
        "f_head_k": data.f_head_k_input,
        "f_tens_k": data.f_tens_k_input,
        "alpha_ax": alpha_ax,
        "F_ax_w": f_ax_w,
        "F_ax_h": f_ax_h,
        "F_t_Rk": f_t_rk,
        "F_ax_Rk": min(active_modes),
    }


def _axial_capacity(data):
    if data.forbindartyp == "spik":
        return _axial_capacity_spik(data)
    if data.forbindartyp == "skruv":
        return _axial_capacity_skruv(data)
    return _axial_components_traskruv(data)["F_ax_Rk"]


def _line_effect(data, base_value, fax_rk):
    contribution = min(fax_rk / 4.0, _line_effect_ratio(data) * base_value)
    return contribution


def _required_min_timber_thickness(data):
    if data.forbindartyp != "spik" or data.forborrad:
        return None
    return 7.0 * data.d


def _alpha_mod_360(alpha):
    return float(alpha) % 360.0


def _rho_class_high(rho_k):
    return rho_k > 420.0


def _min_distance_set(branch, diameter, alpha, rho_k, forborrad):
    alpha_360 = _alpha_mod_360(alpha)
    sin_alpha = abs(_sin_deg(alpha_360))
    cos_alpha = abs(_cos_deg(alpha_360))
    rho_high = _rho_class_high(rho_k)
    d_ge_5 = diameter >= 5.0

    if forborrad:
        a1_min = (4.0 + cos_alpha) * diameter
        a2_min = (3.0 + sin_alpha) * diameter
        a3_t_min = (7.0 + 5.0 * cos_alpha) * diameter
        a3_c_min = 7.0 * diameter
        a4_t_min = (3.0 + (4.0 if d_ge_5 else 2.0) * sin_alpha) * diameter
        a4_c_min = 3.0 * diameter
    else:
        if rho_high:
            a1_min = (7.0 + 8.0 * cos_alpha) * diameter
            a2_min = 7.0 * diameter
            a3_t_min = (15.0 + 5.0 * cos_alpha) * diameter
            a3_c_min = 15.0 * diameter
            a4_t_min = ((7.0 + 5.0 * sin_alpha) if d_ge_5 else (7.0 + 2.0 * sin_alpha)) * diameter
            a4_c_min = 7.0 * diameter
        else:
            a1_min = ((5.0 + 7.0 * cos_alpha) if d_ge_5 else (5.0 + 5.0 * cos_alpha)) * diameter
            a2_min = 5.0 * diameter
            a3_t_min = (10.0 + 5.0 * cos_alpha) * diameter
            a3_c_min = 10.0 * diameter
            a4_t_min = ((5.0 + 5.0 * sin_alpha) if d_ge_5 else (5.0 + 2.0 * sin_alpha)) * diameter
            a4_c_min = 5.0 * diameter

    return {
        "a1_min": a1_min,
        "a2_min": a2_min,
        "a3_t_min": a3_t_min,
        "a3_c_min": a3_c_min,
        "a4_t_min": a4_t_min,
        "a4_c_min": a4_c_min,
    }


def _required_distances(data):
    effective_diameter = data.d

    distance_sets = []
    for materialtyp, alpha, rho_k in (
        (data.materialtyp_1, data.alpha_1, data.rho_k_1),
        (data.materialtyp_2, data.alpha_2, data.rho_k_2),
    ):
        if _is_steel(materialtyp):
            continue
        distance_sets.append(_min_distance_set(data.normativ_tvarkraftsgren, effective_diameter, alpha, rho_k, data.forborrad))

    return {
        key: max(item[key] for item in distance_sets)
        for key in ("a1_min", "a2_min", "a3_t_min", "a3_c_min", "a4_t_min", "a4_c_min")
    }


def _k_ef_from_ratio(a1_ratio, forborrad):
    if a1_ratio >= 14.0:
        return 1.0
    if a1_ratio >= 10.0:
        return 0.85 + (a1_ratio - 10.0) * (1.0 - 0.85) / 4.0
    if a1_ratio >= 7.0:
        return 0.70 + (a1_ratio - 7.0) * (0.85 - 0.70) / 3.0
    if forborrad and a1_ratio >= 4.0:
        return 0.50 + (a1_ratio - 4.0) * (0.70 - 0.50) / 3.0
    return 0.70 if not forborrad else 0.50


def _effective_number(data, a1_min):
    n = data.n_per_rad
    if n == 1:
        return 1.0, 1.0

    alpha_avg = min(abs(data.alpha_1), abs(data.alpha_2))
    if alpha_avg >= 90.0:
        return 1.0, float(n)

    if data.normativ_tvarkraftsgren == "8.3":
        if data.tvarforskjuten_1d:
            return 1.0, float(n)
        k_ef = _k_ef_from_ratio(a1_min / data.d, data.forborrad)
        return k_ef, float(n**k_ef)

    if data.normativ_tvarkraftsgren == "8.5":
        if data.d <= 6.0:
            if data.tvarforskjuten_1d:
                return 1.0, float(n)
            k_ef = _k_ef_from_ratio(a1_min / data.d, data.forborrad)
            return k_ef, float(n**k_ef)
        n_ef = min(float(n), (float(n) ** 0.9) * a1_min / (13.0 * data.d))
        return 0.9, n_ef

    if data.normativ_tvarkraftsgren in {"8.2", "8.7"}:
        if data.tvarforskjuten_1d:
            return 1.0, float(n)
        k_ef = _k_ef_from_ratio(a1_min / max(data.d_eff, 1e-9), data.forborrad)
        return k_ef, float(n**k_ef)

    return 1.0, float(n)


def _distance_equations(data):
    diameter_symbol = "d"
    per_side = {}
    if not _is_steel(data.materialtyp_1):
        per_side[1] = _min_distance_set(data.normativ_tvarkraftsgren, data.d, data.alpha_1, data.rho_k_1, data.forborrad)
    if not _is_steel(data.materialtyp_2):
        per_side[2] = _min_distance_set(data.normativ_tvarkraftsgren, data.d, data.alpha_2, data.rho_k_2, data.forborrad)

    def _formula(idx, key):
        alpha = rf"\alpha_{idx}"
        rho_k = data.rho_k_1 if idx == 1 else data.rho_k_2
        rho_high = _rho_class_high(rho_k)
        d_ge_5 = data.d >= 5.0
        if data.forborrad:
            formulas = {
                "a1_min": rf"a_{{1,min}} = (4 + |\cos({alpha})|) \cdot {diameter_symbol}",
                "a2_min": rf"a_{{2,min}} = (3 + |\sin({alpha})|) \cdot {diameter_symbol}",
                "a3_t_min": rf"a_{{3,t,min}} = (7 + 5 \cdot \cos({alpha})) \cdot {diameter_symbol}",
                "a3_c_min": rf"a_{{3,c,min}} = 7 \cdot {diameter_symbol}",
                "a4_t_min": rf"a_{{4,t,min}} = ({3 if d_ge_5 else 3} + {4 if d_ge_5 else 2} \cdot \sin({alpha})) \cdot {diameter_symbol}",
                "a4_c_min": rf"a_{{4,c,min}} = 3 \cdot {diameter_symbol}",
            }
        else:
            if rho_high:
                formulas = {
                    "a1_min": rf"a_{{1,min}} = (7 + 8 \cdot |\cos({alpha})|) \cdot {diameter_symbol}",
                    "a2_min": rf"a_{{2,min}} = 7 \cdot {diameter_symbol}",
                    "a3_t_min": rf"a_{{3,t,min}} = (15 + 5 \cdot \cos({alpha})) \cdot {diameter_symbol}",
                    "a3_c_min": rf"a_{{3,c,min}} = 15 \cdot {diameter_symbol}",
                    "a4_t_min": rf"a_{{4,t,min}} = ({7} + {5 if d_ge_5 else 2} \cdot \sin({alpha})) \cdot {diameter_symbol}",
                    "a4_c_min": rf"a_{{4,c,min}} = 7 \cdot {diameter_symbol}",
                }
            else:
                formulas = {
                    "a1_min": rf"a_{{1,min}} = ({5} + {7 if d_ge_5 else 5} \cdot |\cos({alpha})|) \cdot {diameter_symbol}",
                    "a2_min": rf"a_{{2,min}} = 5 \cdot {diameter_symbol}",
                    "a3_t_min": rf"a_{{3,t,min}} = (10 + 5 \cdot \cos({alpha})) \cdot {diameter_symbol}",
                    "a3_c_min": rf"a_{{3,c,min}} = 10 \cdot {diameter_symbol}",
                    "a4_t_min": rf"a_{{4,t,min}} = ({5} + {5 if d_ge_5 else 2} \cdot \sin({alpha})) \cdot {diameter_symbol}",
                    "a4_c_min": rf"a_{{4,c,min}} = 5 \cdot {diameter_symbol}",
                }
        return formulas[key]

    equations = []
    labels = {
        "a1_min": "a1",
        "a2_min": "a2",
        "a3_t_min": "a3,t",
        "a3_c_min": "a3,c",
        "a4_t_min": "a4,t",
        "a4_c_min": "a4,c",
    }
    for key in ("a1_min", "a2_min", "a3_t_min", "a3_c_min", "a4_t_min", "a4_c_min"):
        governing_idx = max(per_side, key=lambda idx: per_side[idx][key])
        equations.append(_ekvation(_formula(governing_idx, key), f"styrande {labels[key]}, EC5 Tabell 8.2"))
    return equations


def _k_ef_equation(data, a1_min):
    if data.n_per_rad == 1:
        return _ekvation(r"n_{ef} = 1", "effektivt antal för en ensam förbindare i rad, EC5 8.3.1.1(8)")

    if data.tvarforskjuten_1d and data.normativ_tvarkraftsgren in {"8.3", "8.2", "8.7"}:
        return _ekvation(r"n_{ef} = n", "effektivt antal i sicksackrad, EC5 8.3.1.1(8)")

    if data.normativ_tvarkraftsgren == "8.5" and data.d > 6.0:
        return _ekvation(r"n_{ef} = \min(n, n^{0.9} \cdot a_{1,min} / (13 \cdot d))", "effektivt antal i rad, EC5 8.5.1")

    diameter_symbol = r"d_{eff}" if data.normativ_tvarkraftsgren in {"8.2", "8.7"} else "d"
    diameter_value = max(data.d_eff, 1e-9) if data.normativ_tvarkraftsgren in {"8.2", "8.7"} else data.d
    a1_ratio = a1_min / diameter_value

    if a1_ratio >= 14.0:
        k_eq = r"k_{ef} = 1.0"
    elif a1_ratio >= 10.0:
        k_eq = rf"k_{{ef}} = 0.85 + \left(\frac{{a_{{1,min}}}}{{{diameter_symbol}}} - 10\right) \cdot \frac{{1.0 - 0.85}}{{4}}"
    elif a1_ratio >= 7.0:
        k_eq = rf"k_{{ef}} = 0.70 + \left(\frac{{a_{{1,min}}}}{{{diameter_symbol}}} - 7\right) \cdot \frac{{0.85 - 0.70}}{{3}}"
    elif data.forborrad and a1_ratio >= 4.0:
        k_eq = rf"k_{{ef}} = 0.50 + \left(\frac{{a_{{1,min}}}}{{{diameter_symbol}}} - 4\right) \cdot \frac{{0.70 - 0.50}}{{3}}"
    else:
        k_eq = r"k_{ef} = 0.50" if data.forborrad else r"k_{ef} = 0.70"

    return (
        _ekvation(k_eq, "interpolerat k_ef enligt tabell 8.1, EC5 Tabell 8.1"),
        _ekvation(r"n_{ef} = n^{k_{ef}}", "effektivt antal i rad, EC5 8.3.1.1(8)"),
    )


def _timber_side_values(data, fh1, fh2):
    if _is_steel(data.materialtyp_1):
        return fh2, data.t_2, data.t_1
    return fh1, data.t_1, data.t_2


def tvarkraft_dymlingsforband(px):
    """
    Beräknar karakteristisk tvärkraftsbärförmåga för dymlingsförband enligt
    EN 1995-1-1 kapitel 8 för ``spik``, ``skruv`` och ``traskruv``.

    Funktionen tar en enda lista ``px`` som indata. Listans första värde
    avgör vilket indataformat som används:

    - ``"spik"`` -> spikformat
    - ``"skruv"`` -> skruvformat
    - ``"traskruv"`` -> träskruvsformat

    Returvärdet är en standardiserad ``details``-dictionary med sektionerna:

    - ``metodbeskrivning``
    - ``indata``
    - ``delresultat``
    - ``slutresultat``
    - ``ekvationer``

    Gemensamma begrepp
    ------------------
    ``tvarkraftsmodell``:
    - ``"auto"``: funktionen väljer normgren automatiskt
    - ``"spikregler"``: tvinga tvärkraftsdelen till spikgren
    - ``"skruvregler"``: tvinga tvärkraftsdelen till skruvgren

    ``anslutningstyp``:
    - ``"tra-tra"``
    - ``"stal-tra"``
    - ``"tra-skiva"``
    - ``"skiva-tra"``

    ``materialtyp_1`` och ``materialtyp_2``:
    - trä: ``"konstruktionsvirke"``, ``"hardtra"``, ``"limtra"``, ``"kl-tra"``, ``"lvl"``
    - skiva: ``"plywood"``, ``"osb"``, ``"spanskiva"``
    - stål: ``"stal"``

    ``alpha_1`` och ``alpha_2``:
    - vinkel i grader mellan kraftens riktning i förbandsplanet och
      fiberriktningen i respektive materialdel

    ``infastning_1`` och ``infastning_2``:
    - ``"sidotra"`` eller ``"andtra"``
    - om ändträ används reduceras bäddhållfastheten för den delen enligt den
      modell som används i funktionen

    ``n_rader`` och ``n_per_rad``:
    - ``n_rader`` = antal rader vinkelrätt fiberriktningen
    - ``n_per_rad`` = antal förbindare i rad parallellt fiberriktningen

    ``tvarforskjuten_1d``:
    - ``True`` om raden är tvärförskjuten minst 1d
    - används i gruppverkan/effektivt antal

    ``forborrad``:
    - ``True`` eller ``False``

    Valfritt sista värde:
    - ``M_y_Rk`` [Nmm]
    - om detta anges sist i respektive ``px``-format används det direkt som
      karakteristiskt flytmoment
    - om det inte anges beräknas ``M_y,Rk`` av funktionen

    px-format för spik
    ------------------
    Kortformat utan ``infastning_1`` och ``infastning_2``:

    ``[
        "spik",
        tvarkraftsmodell,
        anslutningstyp,
        materialtyp_1, materialtyp_2,
        t_1, t_2,
        rho_k_1, rho_k_2,
        alpha_1, alpha_2,
        d, d_h, l, f_u,
        spiktyp,
        n_rader, n_per_rad,
        tvarforskjuten_1d, forborrad
    ]``

    Samma format kan utökas med ett sista värde ``M_y_Rk``:

    ``[
        ...,
        tvarforskjuten_1d, forborrad,
        M_y_Rk
    ]``

    Utökat format med ``infastning_1`` och ``infastning_2``:

    ``[
        "spik",
        tvarkraftsmodell,
        anslutningstyp,
        materialtyp_1, materialtyp_2,
        t_1, t_2,
        rho_k_1, rho_k_2,
        alpha_1, alpha_2,
        infastning_1, infastning_2,
        d, d_h, l, f_u,
        spiktyp,
        n_rader, n_per_rad,
        tvarforskjuten_1d, forborrad
    ]``

    Samma utökade format kan kompletteras med ``M_y_Rk`` sist:

    ``[
        ...,
        tvarforskjuten_1d, forborrad,
        M_y_Rk
    ]``

    där ``spiktyp`` är:
    - ``"slat"``
    - ``"profilerad"``

    px-format för skruv
    -------------------
    Kortformat:

    ``[
        "skruv",
        tvarkraftsmodell,
        anslutningstyp,
        materialtyp_1, materialtyp_2,
        t_1, t_2,
        rho_k_1, rho_k_2,
        alpha_1, alpha_2,
        d, d_h, l, f_u,
        n_rader, n_per_rad,
        tvarforskjuten_1d, forborrad
    ]``

    Samma format kan utökas med ett sista värde ``M_y_Rk``:

    ``[
        ...,
        tvarforskjuten_1d, forborrad,
        M_y_Rk
    ]``

    Utökat format:

    ``[
        "skruv",
        tvarkraftsmodell,
        anslutningstyp,
        materialtyp_1, materialtyp_2,
        t_1, t_2,
        rho_k_1, rho_k_2,
        alpha_1, alpha_2,
        infastning_1, infastning_2,
        d, d_h, l, f_u,
        n_rader, n_per_rad,
        tvarforskjuten_1d, forborrad
    ]``

    Samma utökade format kan kompletteras med ``M_y_Rk`` sist:

    ``[
        ...,
        tvarforskjuten_1d, forborrad,
        M_y_Rk
    ]``

    px-format för träskruv
    ----------------------
    Kortformat:

    ``[
        "traskruv",
        tvarkraftsmodell,
        anslutningstyp,
        materialtyp_1, materialtyp_2,
        t_1, t_2,
        rho_k_1, rho_k_2,
        alpha_1, alpha_2,
        d, d_h, l, l_gang, f_u,
        slat_hals,
        n_rader, n_per_rad,
        tvarforskjuten_1d, forborrad
    ]``

    Samma format kan utökas med ett sista värde ``M_y_Rk``:

    ``[
        ...,
        tvarforskjuten_1d, forborrad,
        M_y_Rk
    ]``

    Utökat format:

    ``[
        "traskruv",
        tvarkraftsmodell,
        anslutningstyp,
        materialtyp_1, materialtyp_2,
        t_1, t_2,
        rho_k_1, rho_k_2,
        alpha_1, alpha_2,
        d, d_h, l, l_gang, f_u,
        slat_hals,
        n_rader, n_per_rad,
        tvarforskjuten_1d, forborrad,
        infastning_1, infastning_2
    ]``

    Samma utökade format kan kompletteras med ``M_y_Rk`` sist:

    ``[
        ...,
        tvarforskjuten_1d, forborrad,
        infastning_1, infastning_2,
        M_y_Rk
    ]``

    Valfritt kan träskruvsformatet också avslutas med en dict för axiella
    produktparametrar. Denna används bara för att beräkna ``F_ax,Rk`` enligt
    träskruvsgrenen; om dict saknas, eller parametrarna sätts till ``None`` eller
    ``0``, sätts ``F_ax,Rk = 0`` och linverkan stängs av.

    ``{
        "f_ax_k": ...,
        "f_head_k": ...,
        "f_tens_k": ...,
        "alpha_ax": ...,
        "rho_a": ...   # valfritt, standard 350
    }``

    Exempel med både ``M_y_Rk`` och axialdata:

    ``[
        ...,
        infastning_1, infastning_2,
        M_y_Rk,
        {
            "f_ax_k": 21.67,
            "f_head_k": 13.3,
            "f_tens_k": 12300.0,
            "alpha_ax": 0.0
        }
    ]``

    där:
    - ``d`` = diameter [mm]
    - ``d_h`` = huvuddiameter [mm]
    - ``l`` = total längd [mm]
    - ``l_gang`` = gänglängd [mm]
    - ``slat_hals`` = ``True`` eller ``False``

    Exempel
    -------
    Träskruv, skiva mot trä:

    ```python
    from an_calcs.tra import tvarkraft_dymlingsforband

    px = [
        "traskruv",
        "auto",
        "skiva-tra",
        "spanskiva",
        "konstruktionsvirke",
        22.0,
        80.0,
        350.0,
        350.0,
        0.0,
        0.0,
        6.0,
        12.0,
        60.0,
        40.0,
        800.0,
        False,
        1,
        1,
        False,
        False,
    ]

    details = tvarkraft_dymlingsforband(px)
    ```

    Träskruv i ändträ, benchmarklikt fall:

    ```python
    from an_calcs.tra import tvarkraft_dymlingsforband

    px = [
        "traskruv",
        "skruvregler",
        "tra-tra",
        "lvl",
        "konstruktionsvirke",
        90.0,
        45.0,
        350.0,
        350.0,
        0.0,
        0.0,
        6.0,
        14.0,
        220.0,
        70.0,
        331.79878651746606,
        False,
        6,
        1,
        False,
        True,
        "sidotra",
        "andtra",
        {
            "f_ax_k": 21.6666666667,
            "f_head_k": 13.3,
            "f_tens_k": 12300.0,
            "alpha_ax": 0.0,
        },
    ]

    details = tvarkraft_dymlingsforband(px)
    ```

    Skruv i stål-trä:

    ```python
    from an_calcs.tra import tvarkraft_dymlingsforband

    px = [
        "skruv",
        "auto",
        "stal-tra",
        "stal",
        "konstruktionsvirke",
        2.0,
        80.0,
        0.0,
        350.0,
        0.0,
        0.0,
        8.0,
        24.0,
        100.0,
        400.0,
        1,
        1,
        False,
        True,
    ]

    details = tvarkraft_dymlingsforband(px)
    ```

    Skruv med manuellt inmatat flytmoment:

    ```python
    from an_calcs.tra import tvarkraft_dymlingsforband

    px = [
        "skruv",
        "auto",
        "tra-tra",
        "konstruktionsvirke",
        "konstruktionsvirke",
        45.0,
        95.0,
        350.0,
        350.0,
        0.0,
        0.0,
        12.0,
        36.0,
        160.0,
        400.0,
        2,
        3,
        False,
        True,
        12345.0,  # M_y_Rk [Nmm]
    ]

    details = tvarkraft_dymlingsforband(px)
    ```

    Viktiga slutresultat
    --------------------
    I ``details["slutresultat"]["items"]`` redovisas bland annat:

    - ``F_v_Rk_enkel``: karakteristisk tvärkraftsbärförmåga per förbindare
    - ``F_v_Rk_total``: karakteristisk tvärkraftsbärförmåga för grupp
    - ``F_ax_Rk``: karakteristisk axialbärförmåga
    - ``brottmod_styrande``: styrande brottmod
    """
    data = _tolka_px(px)
    data.normativ_tvarkraftsgren = _pick_normative_shear_branch(data)
    data.normativ_axialgren = _pick_normative_axial_branch(data)
    data.d_eff = _effective_diameter(data)
    t_1_eff, t_2_eff = _effective_thicknesses(data)

    d_for_calc = data.d_eff if data.forbindartyp == "traskruv" and data.normativ_tvarkraftsgren in {"8.2", "8.7"} else data.d

    fh_1_data = _embedment_components(
        data.materialtyp_1,
        data.rho_k_1,
        data.alpha_1,
        d_for_calc,
        data.d_h,
        t_1_eff,
        data.normativ_tvarkraftsgren,
        data.forborrad,
        data.infastning_1,
    )
    fh_2_data = _embedment_components(
        data.materialtyp_2,
        data.rho_k_2,
        data.alpha_2,
        d_for_calc,
        data.d_h,
        t_2_eff,
        data.normativ_tvarkraftsgren,
        data.forborrad,
        data.infastning_2,
    )
    fh_1_k = fh_1_data["fh_k"]
    fh_2_k = fh_2_data["fh_k"]

    my_rk = _yield_moment(data)
    axial_traskruv = _axial_components_traskruv(data) if data.forbindartyp == "traskruv" else None
    f_ax_rk = axial_traskruv["F_ax_Rk"] if axial_traskruv is not None else _axial_capacity(data)
    line_effect_active = f_ax_rk > 0.0
    c_rope = _line_effect_ratio(data)
    l_pen = None
    rho_ax = None
    if data.forbindartyp == "traskruv":
        l_pen = axial_traskruv["l_ef"]
        rho_ax = axial_traskruv["rho_ax"]
    elif data.forbindartyp == "spik":
        l_pen = _fastener_penetration(data)
        rho_ax = data.rho_k_2 if not _is_steel(data.materialtyp_2) else data.rho_k_1

    if data.anslutningstyp == "stal-tra":
        fh_timber, timber_thickness, steel_thickness = _timber_side_values(data, fh_1_k, fh_2_k)
        base_candidates = _steel_timber_shear_candidates(fh_timber, timber_thickness, d_for_calc, my_rk, steel_thickness, 0.0)
    else:
        base_candidates = _timber_timber_shear_candidates(fh_1_k, fh_2_k, t_1_eff, t_2_eff, d_for_calc, my_rk, 0.0)

    beta = None
    r_t = None
    if data.anslutningstyp != "stal-tra" and fh_1_k and fh_2_k:
        beta = fh_2_k / fh_1_k
        if t_1_eff > 0:
            r_t = t_2_eff / t_1_eff

    line_effect_modes = {"c", "d", "e", "f", "l", "n"}
    candidates = {}
    for namn, value in base_candidates.items():
        if namn in line_effect_modes:
            candidates[namn] = value + _line_effect(data, value, f_ax_rk)
        else:
            candidates[namn] = value
    brottmod_styrande = min(candidates, key=candidates.get)
    f_v_rk_enkel = candidates[brottmod_styrande]

    min_distances = _required_distances(data)
    k_ef, n_ef_rad = _effective_number(data, min_distances["a1_min"])
    n_eff_total = data.n_rader * n_ef_rad
    f_v_rk_total = f_v_rk_enkel * n_eff_total

    min_tjocklek = _required_min_timber_thickness(data)

    indata_items = [
        _post("forbindartyp", r"\mathrm{typ}", data.forbindartyp, "-", "vald EC5-kategori"),
        _post("tvarkraftsmodell", r"\mathrm{modell}", data.tvarkraftsmodell, "-", "vald tvärkraftsmodell"),
        _post("anslutningstyp", r"\mathrm{anslutning}", data.anslutningstyp, "-", "valt anslutningsfall"),
        _post("materialtyp_1", r"\mathrm{mat}_1", data.materialtyp_1, "-", "materialdel 1"),
        _post("materialtyp_2", r"\mathrm{mat}_2", data.materialtyp_2, "-", "materialdel 2"),
        _post("t_1", "t_1", data.t_1, "mm", "tjocklek del 1"),
        _post("t_2", "t_2", data.t_2, "mm", "tjocklek del 2"),
        _post("rho_k_1", r"\rho_{k,1}", data.rho_k_1, "kg/m^3", "karakteristisk densitet del 1"),
        _post("rho_k_2", r"\rho_{k,2}", data.rho_k_2, "kg/m^3", "karakteristisk densitet del 2"),
        _post("alpha_1", r"\alpha_1", data.alpha_1, "deg", "vinkel mellan kraft och fiberriktning i del 1"),
        _post("alpha_2", r"\alpha_2", data.alpha_2, "deg", "vinkel mellan kraft och fiberriktning i del 2"),
        _post("infastning_1", r"\mathrm{inf}_1", data.infastning_1, "-", "sidoträ eller ändträ i del 1"),
        _post("infastning_2", r"\mathrm{inf}_2", data.infastning_2, "-", "sidoträ eller ändträ i del 2"),
        _post("d", "d", data.d, "mm", "förbindarens diameter"),
        _post("d_h", r"d_h", data.d_h, "mm", "huvuddiameter"),
        _post("l", "l", data.l, "mm", "total längd"),
        _post("f_u", r"f_u", data.f_u, "MPa", "draghållfasthet"),
        _post("n_rader", r"n_r", data.n_rader, "", "antal rader vinkelrätt fiberriktningen"),
        _post("n_per_rad", r"n_p", data.n_per_rad, "", "antal förbindare i rad parallellt fiberriktningen"),
        _post("tvarforskjuten_1d", r"\mathrm{zigzag}", data.tvarforskjuten_1d, "-", "tvärförskjuten minst 1d"),
        _post("forborrad", r"\mathrm{pre}", data.forborrad, "-", "förborrad"),
    ]

    if data.forbindartyp == "spik":
        indata_items.append(_post("spiktyp", r"\mathrm{spiktyp}", data.spiktyp, "-", "typ av spik"))
    if data.forbindartyp == "traskruv":
        indata_items.extend(
            [
                _post("l_gang", r"l_{gang}", data.l_gang, "mm", "gänglängd"),
                _post("slat_hals", r"\mathrm{slat\_hals}", data.slat_hals, "-", "träskruv med slät hals"),
            ]
        )
        if (
            data.f_ax_k_input is not None
            or data.f_head_k_input is not None
            or data.f_tens_k_input is not None
            or data.alpha_ax_input is not None
            or data.rho_a_input is not None
        ):
            indata_items.extend(
                [
                    _post("f_ax_k_input", r"f_{ax,k}", data.f_ax_k_input, "N/mm^2", "inmatad utdragshållfasthet"),
                    _post("f_head_k_input", r"f_{head,k}", data.f_head_k_input, "N/mm^2", "inmatad genomdragningshållfasthet"),
                    _post("f_tens_k_input", r"F_{t,Rk}", data.f_tens_k_input, "N", "inmatad dragbärförmåga"),
                    _post("alpha_ax_input", r"\alpha_{ax}", data.alpha_ax_input, "deg", "inmatad axelvinkel mot fiberriktning"),
                    _post("rho_a_input", r"\rho_a", data.rho_a_input, "kg/m^3", "referensdensitet för axialdata"),
                ]
            )
    if data.my_rk_input is not None:
        indata_items.append(_post("M_y_Rk_input", r"M_{y,Rk}", data.my_rk_input, "Nmm", "inmatat flytmoment"))

    delresultat_items = [
        _post("normativ_tvarkraftsgren", r"\mathrm{gren}_v", data.normativ_tvarkraftsgren, "-", "vald tvärkraftsgren"),
        _post("normativ_axialgren", r"\mathrm{gren}_{ax}", data.normativ_axialgren, "-", "vald axialgren"),
    ]

    delresultat_items.append(_post("d_eff", r"d_{eff}", data.d_eff, "mm", "effektiv diameter"))

    delresultat_items.extend(
        [
            _post("t_1_eff", r"t_{1,eff}", t_1_eff, "mm", "effektiv tjocklek del 1"),
            _post("t_2_eff", r"t_{2,eff}", t_2_eff, "mm", "effektiv tjocklek del 2"),
        ]
    )

    def _append_fh_data(idx, fh_data, fh_k):
        if fh_data["fh_0_k"] is not None:
            delresultat_items.append(_post(f"f_h_{idx}_0_k", rf"f_{{h,0,{idx},k}}", fh_data["fh_0_k"], "N/mm^2", f"oreducerad bäddhållfasthet del {idx}"))
        if fh_data["k_90"] is not None:
            delresultat_items.append(_post(f"k_90_{idx}", rf"k_{{90,{idx}}}", fh_data["k_90"], "-", f"k90-värde del {idx}"))
        if fh_data["endgrain_factor"] not in {None, 1.0}:
            delresultat_items.append(_post(f"eta_endtra_{idx}", rf"\eta_{{end,{idx}}}", fh_data["endgrain_factor"], "-", f"ändträfaktor del {idx}"))
        if fh_k is not None:
            delresultat_items.append(_post(f"f_h_{idx}_k", rf"f_{{h,{idx},k}}", fh_k, "N/mm^2", f"bäddhållfasthet del {idx}"))

    _append_fh_data(1, fh_1_data, fh_1_k)
    _append_fh_data(2, fh_2_data, fh_2_k)

    if fh_1_data["endgrain_factor"] not in {None, 1.0} or fh_2_data["endgrain_factor"] not in {None, 1.0}:
        delresultat_items.append(
            _post("andtra_reduktion_info", r"\mathrm{andtra}", "1/3 i spikgrenen, 0.4 i denna skruvmodell", "-", "synlig info om ändträmodell")
        )

    delresultat_items.append(_post("M_y_Rk", r"M_{y,Rk}", my_rk, "Nmm", "karakteristiskt flytmoment"))

    if data.forbindartyp == "traskruv":
        delresultat_items.append(
            _post("axialdata_aktiv", r"\mathrm{axial}", axial_traskruv["enabled"], "-", "axialdata aktiv för träskruv")
        )
        delresultat_items.append(_post("l_ef", r"l_{ef}", axial_traskruv["l_ef"], "mm", "effektiv gänginträngning"))
        if axial_traskruv["rho_ax"] is not None:
            delresultat_items.append(_post("rho_ax", r"\rho_{ax}", axial_traskruv["rho_ax"], "kg/m^3", "densitet i axialmodell"))
        delresultat_items.append(_post("rho_a", r"\rho_a", axial_traskruv["rho_a"], "kg/m^3", "referensdensitet i axialmodell"))
        if axial_traskruv["alpha_ax"] is not None:
            delresultat_items.append(_post("alpha_ax", r"\alpha_{ax}", axial_traskruv["alpha_ax"], "deg", "vinkel mellan skruvaxel och fiberriktning"))
        if axial_traskruv["k_ax"] is not None:
            delresultat_items.append(_post("k_ax", r"k_{ax}", axial_traskruv["k_ax"], "-", "vinkelfaktor för axial utdragning"))
        if axial_traskruv["k_beta"] is not None:
            delresultat_items.append(_post("k_beta", r"k_{\beta}", axial_traskruv["k_beta"], "-", "korrektionsfaktor för axial utdragning"))
        if axial_traskruv["f_ax_k"] is not None:
            delresultat_items.append(_post("f_ax_k", r"f_{ax,k}", axial_traskruv["f_ax_k"], "N/mm^2", "utdragshållfasthet för gängad del"))
        if axial_traskruv["f_head_k"] is not None:
            delresultat_items.append(_post("f_head_k", r"f_{head,k}", axial_traskruv["f_head_k"], "N/mm^2", "genomdragningshållfasthet för huvud"))
        if axial_traskruv["F_t_Rk"] is not None:
            delresultat_items.append(_post("F_t_Rk", r"F_{t,Rk}", axial_traskruv["F_t_Rk"], "N", "dragbärförmåga i skruven"))
        delresultat_items.append(_post("F_ax_w", r"F_{ax,w}", axial_traskruv["F_ax_w"], "N", "axiell bärförmåga för utdragning"))
        if axial_traskruv["F_ax_h"] is not None:
            delresultat_items.append(_post("F_ax_h", r"F_{ax,h}", axial_traskruv["F_ax_h"], "N", "axiell bärförmåga för genomdragning huvud"))
        delresultat_items.append(_post("F_ax_Rk", r"F_{ax,Rk}", f_ax_rk, "N", "karakteristisk axialbärförmåga"))
        if not axial_traskruv["enabled"]:
            delresultat_items.append(
                _post("axialdata_info", r"\mathrm{axial\_info}", "axialdata saknas eller är avstängda", "-", "ingen linverkan tillgodoräknas")
            )
    else:
        delresultat_items.append(_post("F_ax_Rk", r"F_{ax,Rk}", f_ax_rk, "N", "karakteristisk axialbärförmåga"))

    if line_effect_active:
        delresultat_items.append(_post("c_rope", r"c_{rope}", c_rope, "-", "linverkskoefficient"))
    if l_pen is not None:
        delresultat_items.append(_post("l_pen", r"l_{pen}", l_pen, "mm", "inträngningslängd i axialmodell"))
    if beta is not None:
        delresultat_items.append(_post("beta", r"\beta", beta, "-", "kvot mellan bäddhållfastheter"))
    if r_t is not None:
        delresultat_items.append(_post("R_t", r"R_t", r_t, "-", "kvot mellan effektiva tjocklekar"))

    delresultat_items.extend(
        [
            _post("k_ef", r"k_{ef}", k_ef, "-", "exponent för effektivt antal i rad"),
            _post("a1_for_nef", r"a_{1,\mathrm{nef}}", min_distances["a1_min"], "mm", "a1-värde som används vid beräkning av effektivt antal"),
            _post("n_ef_rad", r"n_{ef}", n_ef_rad, "", "effektivt antal förbindare i rad"),
            _post("n_eff_total", r"n_{tot,ef}", n_eff_total, "", "effektivt totalt antal förbindare"),
            _post("a1_min", r"a_{1,min}", min_distances["a1_min"], "mm", "erforderligt minsta avstånd parallellt fiberriktningen"),
            _post("a2_min", r"a_{2,min}", min_distances["a2_min"], "mm", "erforderligt minsta avstånd vinkelrätt fiberriktningen"),
            _post("a3_t_min", r"a_{3,t,min}", min_distances["a3_t_min"], "mm", "erforderligt minsta avstånd till belastad ände"),
            _post("a3_c_min", r"a_{3,c,min}", min_distances["a3_c_min"], "mm", "erforderligt minsta avstånd till obelastad ände"),
            _post("a4_t_min", r"a_{4,t,min}", min_distances["a4_t_min"], "mm", "erforderligt minsta kantavstånd belastad kant"),
            _post("a4_c_min", r"a_{4,c,min}", min_distances["a4_c_min"], "mm", "erforderligt minsta kantavstånd obelastad kant"),
        ]
    )

    if min_tjocklek is not None:
        delresultat_items.append(
            _post("t_min_utan_forborrning", r"t_{min}", min_tjocklek, "mm", "minsta virkestjocklek utan förborrning")
        )

    for namn in sorted(candidates):
        delresultat_items.append(
            _post(f"brottmod_{namn}", rf"F_{{v,Rk,{namn}}}", candidates[namn], "N", f"bärförmåga för brottmod {namn}")
        )
    delresultat_items.append(_post("F_v_Rk_min", r"\min F_{v,Rk}", f_v_rk_enkel, "N", "minsta karakteristiska tvärkraftsbärförmåga"))

    ekvationer = []

    if data.infastning_2 == "andtra" and not _is_steel(data.materialtyp_2):
        ekvationer.append(_ekvation(r"t_{2,eff} = l - t_1", "effektiv tjocklek del 2 vid ändträ, EC5 8.2.2"))

    if data.forbindartyp == "traskruv" and data.normativ_tvarkraftsgren in {"8.2", "8.7"}:
        ekvationer.append(_ekvation(r"d_{eff} = 0.8 \cdot d", "effektiv diameter för träskruv, EC5 8.7.1"))

    def _k90_eq(materialtyp, idx):
        if materialtyp == "hardtra":
            return _ekvation(rf"k_{{90,{idx}}} = 0.90 + 0.015 \cdot d", f"k90 för del {idx}, EC5 8.5.1")
        if materialtyp == "lvl":
            return _ekvation(rf"k_{{90,{idx}}} = 1.30 + 0.015 \cdot d", f"k90 för del {idx}, EC5 8.5.1")
        return _ekvation(rf"k_{{90,{idx}}} = 1.35 + 0.015 \cdot d", f"k90 för del {idx}, EC5 8.5.1")

    def _fh0_eq(data_item, idx):
        branch_used = data_item["branch_used"]
        if data_item["fh_0_k"] is None:
            return []
        if branch_used == "8.3":
            if (idx == 1 and _is_sheet(data.materialtyp_1)) or (idx == 2 and _is_sheet(data.materialtyp_2)):
                return [_ekvation(rf"f_{{h,0,{idx},k}} = 0.11 \cdot \rho_{{k,{idx}}} \cdot d^{{-0.3}}", f"oreducerad bäddhållfasthet del {idx}, EC5 8.3.1.2(2)")]
            if data.forborrad:
                return [_ekvation(rf"f_{{h,0,{idx},k}} = 0.082 \cdot (1 - 0.01 \cdot d) \cdot \rho_{{k,{idx}}}", f"oreducerad bäddhållfasthet del {idx}, EC5 8.3.1.2(2)")]
            return [_ekvation(rf"f_{{h,0,{idx},k}} = 0.082 \cdot \rho_{{k,{idx}}} \cdot d^{{-0.3}}", f"oreducerad bäddhållfasthet del {idx}, EC5 8.3.1.2(2)")]
        if (idx == 1 and _is_sheet(data.materialtyp_1)) or (idx == 2 and _is_sheet(data.materialtyp_2)):
            if (idx == 1 and data.materialtyp_1 == "plywood") or (idx == 2 and data.materialtyp_2 == "plywood"):
                return [_ekvation(rf"f_{{h,0,{idx},k}} = 0.11 \cdot \rho_{{k,{idx}}} \cdot (1 - 0.01 \cdot d)", f"oreducerad bäddhållfasthet del {idx}, EC5 8.5.1")]
            return [_ekvation(rf"f_{{h,0,{idx},k}} = 0.25 \cdot \sqrt{{t_{{{idx},eff}} / d_{{eff}}}} \cdot c_{{board,{idx}}}", f"oreducerad bäddhållfasthet del {idx}, EC5 8.5.1")]
        return [_ekvation(rf"f_{{h,0,{idx},k}} = 0.082 \cdot (1 - 0.01 \cdot d_{{eff}}) \cdot \rho_{{k,{idx}}}", f"oreducerad bäddhållfasthet del {idx}, EC5 8.5.1")]

    def _fh_eq(data_item, idx):
        equations = []
        materialtyp = data.materialtyp_1 if idx == 1 else data.materialtyp_2
        if data_item["fh_k"] is None:
            return equations
        if data_item["k_90"] is not None:
            equations.append(_k90_eq(materialtyp, idx))
        equations.extend(_fh0_eq(data_item, idx))
        if data_item["endgrain_factor"] not in {None, 1.0}:
            factor_text = r"\frac{1}{3}" if abs(data_item["endgrain_factor"] - (1.0 / 3.0)) < 1e-9 else "0.4"
            equations.append(_ekvation(rf"\eta_{{end,{idx}}} = {factor_text}", f"ändträfaktor del {idx}, EC5 8.3.1.2(4)"))
        if data_item["k_90"] is not None:
            side_expr = rf"\frac{{f_{{h,0,{idx},k}}}}{{k_{{90,{idx}}} \cdot \sin^2(\alpha_{idx}) + \cos^2(\alpha_{idx})}}"
        else:
            side_expr = rf"f_{{h,0,{idx},k}}"
        if data_item["endgrain_factor"] not in {None, 1.0}:
            equations.append(_ekvation(rf"f_{{h,{idx},k}} = \eta_{{end,{idx}}} \cdot {side_expr}", f"bäddhållfasthet del {idx}, EC5 {data.normativ_tvarkraftsgren}"))
        else:
            equations.append(_ekvation(rf"f_{{h,{idx},k}} = {side_expr}", f"bäddhållfasthet del {idx}, EC5 {data.normativ_tvarkraftsgren}"))
        return equations

    ekvationer.extend(_fh_eq(fh_1_data, 1))
    ekvationer.extend(_fh_eq(fh_2_data, 2))

    if beta is not None:
        ekvationer.append(_ekvation(r"\beta = \frac{f_{h,2,k}}{f_{h,1,k}}", "kvot mellan bäddhållfastheter, EC5 8.2.3"))
    if r_t is not None:
        ekvationer.append(_ekvation(r"R_t = \frac{t_{2,eff}}{t_{1,eff}}", "kvot mellan effektiva tjocklekar, EC5 8.2.3"))

    if data.my_rk_input is not None:
        ekvationer.append(_ekvation(r"M_{y,Rk} = \mathrm{inmatat\ värde}", "karakteristiskt flytmoment, EC5 8.5.1"))
    elif data.forbindartyp == "spik" and data.spiktyp == "profilerad":
        ekvationer.append(_ekvation(r"M_{y,Rk} = 0.45 \cdot f_u \cdot d^{2.6}", "karakteristiskt flytmoment, EC5 8.5.1"))
    else:
        ekvationer.append(_ekvation(r"M_{y,Rk} = 0.30 \cdot f_u \cdot d^{2.6}", "karakteristiskt flytmoment, EC5 8.5.1"))

    if data.forbindartyp == "spik":
        if data.infastning_1 == "andtra" or data.infastning_2 == "andtra":
            ekvationer.append(_ekvation(r"F_{ax,Rk} = 0", "spik i ändträ antas inte ta axiell last, EC5 8.3.2"))
        else:
            ekvationer.append(_ekvation(r"F_{ax,Rk} = \min(F_{ax,withdrawal}, F_{head})", "karakteristisk axialbärförmåga, EC5 8.3.2"))
    elif data.forbindartyp == "skruv":
        ekvationer.append(_ekvation(r"F_{ax,Rk} = \min(F_{tensile}, F_{washer})", "karakteristisk axialbärförmåga, EC5 8.5.2"))
    else:
        if axial_traskruv["enabled"]:
            ekvationer.extend(
                [
                    _ekvation(r"F_{ax,w} = k_{ax} \cdot f_{ax,k} \cdot d \cdot l_{ef} / k_{\beta} \cdot \left(\frac{\rho_{ax}}{\rho_a}\right)^{0.8}", "axiell bärförmåga utdragning, EC5 8.7.2"),
                    _ekvation(r"F_{t,Rk} = f_{tens,k}", "dragbärförmåga i skruven, EC5 8.7.2"),
                ]
            )
            if data.anslutningstyp == "tra-tra":
                ekvationer.append(_ekvation(r"F_{ax,h} = f_{head,k} \cdot d_h^2 \cdot \left(\frac{\rho_{ax}}{\rho_a}\right)^{0.8}", "axiell bärförmåga genomdragning huvud, EC5 8.7.2"))
                ekvationer.append(_ekvation(r"F_{ax,Rk} = \min(F_{ax,w}, F_{ax,h}, F_{t,Rk})", "karakteristisk axialbärförmåga, EC5 8.7.2"))
            else:
                ekvationer.append(_ekvation(r"F_{ax,Rk} = \min(F_{ax,w}, F_{t,Rk})", "karakteristisk axialbärförmåga, EC5 8.7.2"))
        else:
            ekvationer.append(_ekvation(r"F_{ax,Rk} = 0", "axialdata saknas, linverkan avstängd, EC5 8.7.2"))

    ekvationer.extend(_distance_equations(data))

    if data.anslutningstyp == "stal-tra":
        if data.t_1 <= 0.5 * d_for_calc or data.t_2 <= 0.5 * d_for_calc:
            ekvationer.extend(
                [
                    _ekvation(r"F_{v,Rk,1} = 0.4 \cdot f_{h,k} \cdot t_{timber} \cdot d_{eff}", "brottmod k, EC5 8.2.3"),
                    _ekvation(r"F_{v,Rk,2} = 1.15 \cdot \sqrt{2 \cdot M_{y,Rk} \cdot f_{h,k} \cdot d_{eff}} + F_{rope}", "brottmod l, EC5 8.2.3"),
                ]
            )
        else:
            ekvationer.extend(
                [
                    _ekvation(r"F_{v,Rk,1} = f_{h,k} \cdot t_{timber} \cdot d_{eff}", "brottmod m, EC5 8.2.3"),
                    _ekvation(r"F_{v,Rk,2} = 1.15 \cdot \sqrt{2 \cdot M_{y,Rk} \cdot f_{h,k} \cdot d_{eff}} + F_{rope}", "brottmod n, EC5 8.2.3"),
                ]
            )
    else:
        ekvationer.extend(
            [
                _ekvation(r"F_{v,Rk,1} = f_{h,1,k} \cdot t_{1,eff} \cdot d_{eff}", "brottmod a, EC5 8.2.3"),
                _ekvation(r"F_{v,Rk,2} = f_{h,2,k} \cdot t_{2,eff} \cdot d_{eff}", "brottmod b, EC5 8.2.3"),
                _ekvation(
                    r"F_{v,Rk,3} = \frac{f_{h,1,k} \cdot t_{1,eff} \cdot d_{eff}}{1 + \beta} \cdot \left(\sqrt{\beta + 2 \beta^2 (1 + R_t + R_t^2) + \beta^3 R_t^2} - \beta (1 + R_t)\right) + F_{rope}",
                    "brottmod c, EC5 8.2.3",
                ),
                _ekvation(
                    r"F_{v,Rk,4} = 1.05 \cdot \frac{f_{h,1,k} \cdot t_{1,eff} \cdot d_{eff}}{2 + \beta} \cdot \left(\sqrt{2 \beta (1 + \beta) + \frac{4 \beta (2 + \beta) M_{y,Rk}}{f_{h,1,k} \cdot d_{eff} \cdot t_{1,eff}^2}} - \beta\right) + F_{rope}",
                    "brottmod d, EC5 8.2.3",
                ),
                _ekvation(
                    r"F_{v,Rk,5} = 1.05 \cdot \frac{f_{h,1,k} \cdot t_{2,eff} \cdot d_{eff}}{1 + 2 \beta} \cdot \left(\sqrt{2 \beta^2 (1 + \beta) + \frac{4 \beta (1 + 2 \beta) M_{y,Rk}}{f_{h,1,k} \cdot d_{eff} \cdot t_{2,eff}^2}} - \beta\right) + F_{rope}",
                    "brottmod e, EC5 8.2.3",
                ),
                _ekvation(
                    r"F_{v,Rk,6} = 1.15 \cdot \sqrt{\frac{2 \beta}{1 + \beta} \cdot (2 \cdot M_{y,Rk} \cdot f_{h,1,k} \cdot d_{eff})} + F_{rope}",
                    "brottmod f, EC5 8.2.3",
                ),
            ]
        )

    if line_effect_active:
        ekvationer.append(_ekvation(r"F_{rope} = \min(F_{ax,Rk}/4, c_{rope} \cdot F_{Johansen})", "begränsad linverkan i aktuella brottmoder, EC5 8.2.2(2)"))

    ekvationer.append(_ekvation(r"F_{v,Rk} = \min(F_{v,Rk,i})", "styrande karakteristisk tvärkraftsbärförmåga, EC5 8.2.3"))

    k_ef_eq = _k_ef_equation(data, min_distances["a1_min"])
    if isinstance(k_ef_eq, tuple):
        ekvationer.extend(k_ef_eq)
    else:
        ekvationer.append(k_ef_eq)

    ekvationer.append(_ekvation(r"F_{v,Rk,total} = F_{v,Rk,enkel} \cdot n_{tot,ef}", "total karakteristisk tvärkraftsbärförmåga, EC5 8.3.1.1(8)"))

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Funktionen beräknar karakteristisk tvärkraftsbärförmåga för dymlingsförband enligt "
                        "Eurokod 5 kapitel 8 för spik, skruv och träskruv. Beräkningen visar både kapacitet per "
                        "förbindare och total gruppkapacitet med effektivt antal där relevant."
                    ),
                },
                {
                    "rubrik": "Regelval",
                    "text": (
                        "Förbindartypen tolkas som EC5-kategori. Tvärkraftsgrenen kan väljas automatiskt eller "
                        "overridas med spik- eller skruvregler. Träskruvar redovisar dessutom effektiv diameter."
                    ),
                },
                {
                    "rubrik": "Geometri",
                    "text": (
                        "Funktionen beräknar erforderliga minimiavstånd enligt relevant EC5-gren men verifierar "
                        "inte dessa mot några separat inmatade verkliga avstånd."
                    ),
                },
                {
                    "rubrik": "Ändträ",
                    "text": (
                        "Om en trädel anges som ändträ reduceras bäddhållfastheten i just den delen till en tredjedel "
                        "av motsvarande sidoträvärde enligt valt modellantagande."
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
            "items": [
                _post("F_v_Rk_enkel", r"F_{v,Rk,enkel}", f_v_rk_enkel, "N", "karakteristisk tvärkraftsbärförmåga per förbindare"),
                _post("F_v_Rk_total", r"F_{v,Rk,total}", f_v_rk_total, "N", "karakteristisk tvärkraftsbärförmåga för grupp"),
                _post("F_ax_Rk", r"F_{ax,Rk}", f_ax_rk, "N", "karakteristisk axialbärförmåga"),
                _post("brottmod_styrande", r"\mathrm{mode}", brottmod_styrande, "-", "styrande brottmod"),
                _post("tvarkraftsgren", r"\mathrm{gren}", data.normativ_tvarkraftsgren, "-", "använd tvärkraftsgren"),
                _post("linverkan_aktiv", r"\mathrm{rope}", line_effect_active, "-", "linverkan används i aktuell brottmod"),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": ekvationer,
        },
    }
