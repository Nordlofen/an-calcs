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
    if len(px) == 20:
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
    elif len(px) == 22:
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
        raise ValueError("px för spik måste innehålla 20 eller 22 värden.")
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
    if len(px) == 19:
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
    elif len(px) == 21:
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
        raise ValueError("px för skruv måste innehålla 19 eller 21 värden.")
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
        n_rader=int(n_rader),
        n_per_rad=int(n_per_rad),
        tvarforskjuten_1d=bool(tvarforskjuten_1d),
        forborrad=bool(forborrad),
    )
    _validera_gemensamt(data)
    return data


def _tolka_px_traskruv(px):
    if len(px) == 21:
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
    elif len(px) == 23:
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
        raise ValueError("px för traskruv måste innehålla 21 eller 23 värden.")
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


def _yield_moment(data):
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


def _axial_capacity_traskruv(data):
    penetration = min(_fastener_penetration(data), data.l_gang)
    rho = data.rho_k_2 if not _is_steel(data.materialtyp_2) else data.rho_k_1
    # I den här modellen används utdragsmotståndet som karakteristisk axialbärförmåga
    # för linverkan i tvärkraftsberäkningen.
    return 6.5 * data.d * penetration * (rho / 350.0) ** 0.8


def _axial_capacity(data):
    if data.forbindartyp == "spik":
        return _axial_capacity_spik(data)
    if data.forbindartyp == "skruv":
        return _axial_capacity_skruv(data)
    return _axial_capacity_traskruv(data)


def _line_effect(data, base_value, fax_rk):
    contribution = min(fax_rk / 4.0, _line_effect_ratio(data) * base_value)
    return contribution


def _required_min_timber_thickness(data):
    if data.forbindartyp != "spik" or data.forborrad:
        return None
    return 7.0 * data.d


def _min_distance_set(branch, diameter, alpha):
    sin_alpha = _sin_deg(alpha)
    cos_alpha = _cos_deg(alpha)

    if branch == "8.3":
        if diameter < 5.0:
            return {
                "a1_min": (5.0 + 5.0 * cos_alpha) * diameter,
                "a2_min": 5.0 * diameter,
                "a3_t_min": (10.0 + 5.0 * cos_alpha) * diameter,
                "a3_c_min": 10.0 * diameter,
                "a4_t_min": (5.0 + 2.0 * sin_alpha) * diameter,
                "a4_c_min": 5.0 * diameter,
            }
        return {
            "a1_min": (5.0 + 7.0 * cos_alpha) * diameter,
            "a2_min": 5.0 * diameter,
            "a3_t_min": (10.0 + 5.0 * cos_alpha) * diameter,
            "a3_c_min": 10.0 * diameter,
            "a4_t_min": (5.0 + 5.0 * sin_alpha) * diameter,
            "a4_c_min": 5.0 * diameter,
        }

    if branch == "8.5":
        return {
            "a1_min": (4.0 + cos_alpha) * diameter,
            "a2_min": 4.0 * diameter,
            "a3_t_min": max(7.0 * diameter, 80.0),
            "a3_c_min": max((1.0 + 6.0 * sin_alpha) * diameter, 4.0 * diameter),
            "a4_t_min": max((2.0 + 2.0 * sin_alpha) * diameter, 3.0 * diameter),
            "a4_c_min": 3.0 * diameter,
        }

    return {
        "a1_min": (3.0 + 2.0 * cos_alpha) * diameter,
        "a2_min": 3.0 * diameter,
        "a3_t_min": max(7.0 * diameter, 80.0),
        "a3_c_min": max(max(7.0 * diameter, 80.0) * abs(sin_alpha), 3.0 * diameter),
        "a4_t_min": max((2.0 + 2.0 * sin_alpha) * diameter, 3.0 * diameter),
        "a4_c_min": 3.0 * diameter,
    }


def _required_distances(data):
    branch = data.normativ_tvarkraftsgren
    effective_diameter = data.d_eff if data.forbindartyp == "traskruv" and branch in {"8.2", "8.7"} else data.d

    distance_sets = []
    for materialtyp, alpha in ((data.materialtyp_1, data.alpha_1), (data.materialtyp_2, data.alpha_2)):
        if _is_steel(materialtyp):
            continue
        branch_for_distances = branch
        if branch_for_distances == "8.7":
            branch_for_distances = "8.2"
        distance_sets.append(_min_distance_set(branch_for_distances, effective_diameter, alpha))

    result = {}
    for key in ("a1_min", "a2_min", "a3_t_min", "a3_c_min", "a4_t_min", "a4_c_min"):
        result[key] = max(item[key] for item in distance_sets)

    if branch == "8.3" and ((_is_sheet(data.materialtyp_1) and _is_wood(data.materialtyp_2)) or (_is_wood(data.materialtyp_1) and _is_sheet(data.materialtyp_2))):
        result["a1_min"] *= 0.85
        result["a2_min"] *= 0.85

    return result


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


def _timber_side_values(data, fh1, fh2):
    if _is_steel(data.materialtyp_1):
        return fh2, data.t_2, data.t_1
    return fh1, data.t_1, data.t_2


def tvarkraft_dymlingsforband(px):
    """
    Beräknar karakteristisk tvärkraftsbärförmåga för dymlingsförband enligt
    EN 1995-1-1 kapitel 8 för spik, skruv och träskruv.

    Funktionen accepterar olika ``px``-format beroende på ``förbindartyp`` och
    returnerar en standardiserad ``details``-dictionary med både indata,
    delresultat och slutresultat.
    """
    data = _tolka_px(px)
    data.normativ_tvarkraftsgren = _pick_normative_shear_branch(data)
    data.normativ_axialgren = _pick_normative_axial_branch(data)
    data.d_eff = _effective_diameter(data)
    t_1_eff, t_2_eff = _effective_thicknesses(data)

    d_for_calc = data.d_eff if data.forbindartyp == "traskruv" and data.normativ_tvarkraftsgren in {"8.2", "8.7"} else data.d

    fh_1_k = _embedment_strength(
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
    fh_2_k = _embedment_strength(
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

    my_rk = _yield_moment(data)
    f_ax_rk = _axial_capacity(data)
    line_effect_active = f_ax_rk > 0.0

    if data.anslutningstyp == "stal-tra":
        fh_timber, timber_thickness, steel_thickness = _timber_side_values(data, fh_1_k, fh_2_k)
        base_candidates = _steel_timber_shear_candidates(fh_timber, timber_thickness, d_for_calc, my_rk, steel_thickness, 0.0)
    else:
        base_candidates = _timber_timber_shear_candidates(fh_1_k, fh_2_k, t_1_eff, t_2_eff, d_for_calc, my_rk, 0.0)

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

    delresultat_items = [
        _post("normativ_tvarkraftsgren", r"\mathrm{gren}_v", data.normativ_tvarkraftsgren, "-", "vald tvärkraftsgren"),
        _post("normativ_axialgren", r"\mathrm{gren}_{ax}", data.normativ_axialgren, "-", "vald axialgren"),
        _post("d_eff", r"d_{eff}", data.d_eff, "mm", "effektiv diameter"),
        _post("f_h_1_k", r"f_{h,1,k}", fh_1_k, "N/mm^2", "bäddhållfasthet del 1"),
        _post("f_h_2_k", r"f_{h,2,k}", fh_2_k, "N/mm^2", "bäddhållfasthet del 2"),
        _post("t_1_eff", r"t_{1,eff}", t_1_eff, "mm", "effektiv tjocklek del 1"),
        _post("t_2_eff", r"t_{2,eff}", t_2_eff, "mm", "effektiv tjocklek del 2"),
        _post("M_y_Rk", r"M_{y,Rk}", my_rk, "Nmm", "karakteristiskt flytmoment"),
        _post("F_ax_Rk", r"F_{ax,Rk}", f_ax_rk, "N", "karakteristisk axialbärförmåga"),
        _post("n_ef_rad", r"n_{ef}", n_ef_rad, "", "effektivt antal förbindare i rad"),
        _post("n_eff_total", r"n_{tot,ef}", n_eff_total, "", "effektivt totalt antal förbindare"),
        _post("a1_min", r"a_{1,min}", min_distances["a1_min"], "mm", "erforderligt minsta avstånd parallellt fiberriktningen"),
        _post("a2_min", r"a_{2,min}", min_distances["a2_min"], "mm", "erforderligt minsta avstånd vinkelrätt fiberriktningen"),
        _post("a3_t_min", r"a_{3,t,min}", min_distances["a3_t_min"], "mm", "erforderligt minsta avstånd till belastad ände"),
        _post("a3_c_min", r"a_{3,c,min}", min_distances["a3_c_min"], "mm", "erforderligt minsta avstånd till obelastad ände"),
        _post("a4_t_min", r"a_{4,t,min}", min_distances["a4_t_min"], "mm", "erforderligt minsta kantavstånd belastad kant"),
        _post("a4_c_min", r"a_{4,c,min}", min_distances["a4_c_min"], "mm", "erforderligt minsta kantavstånd obelastad kant"),
    ]

    if min_tjocklek is not None:
        delresultat_items.append(
            _post("t_min_utan_forborrning", r"t_{min}", min_tjocklek, "mm", "minsta virkestjocklek utan förborrning")
        )

    for namn, value in sorted(base_candidates.items()):
        delresultat_items.append(
            _post(f"brottmod_{namn}", rf"F_{{v,Rk,{namn}}}", candidates[namn], "N", f"kandidat för brottmod {namn}")
        )

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
                _post("linverkan_aktiv", r"\mathrm{rope}", line_effect_active, "-", "linverkan används i kandidaten"),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"F_{v,Rk,total} = F_{v,Rk,enkel} \, n_{tot,ef}", "total tvärkraftsbärförmåga"),
                _ekvation(r"d_{eff} = 0.8\,d", "effektiv diameter för träskruv i denna modell"),
                _ekvation(r"M_{y,Rk} = 0.30 \, f_u \, d^{2.6}", "flytmoment för rund spik och skruv"),
                _ekvation(r"M_{y,Rk} = 0.45 \, f_u \, d^{2.6}", "flytmoment för profilerad spik"),
                _ekvation(r"f_{h,k} = 0.082 \, \rho_k \, d^{-0.3}", "bäddhållfasthet för spik i trä utan förborrning"),
                _ekvation(r"f_{h,k} = 0.082 \, (1-0.01d)\,\rho_k", "bäddhållfasthet för spik i trä med förborrning"),
                _ekvation(r"f_{h,\alpha,k} = \frac{f_{h,0,k}}{k_{90}\sin^2\alpha + \cos^2\alpha}", "bäddhållfasthet för skruv i trä"),
                _ekvation(r"n_{ef} = n^{k_{ef}}", "effektivt antal för spikrad eller skruvrad med liten diameter"),
                _ekvation(r"n_{ef} = \min\left(n, n^{0.9}\frac{a_1}{13d}\right)", "effektivt antal för skruvar med diameter större än 6 mm"),
                _ekvation(r"F_{rope} = \min\left(\frac{F_{ax,Rk}}{4}, c_{rope}F_{Johansen}\right)", "begränsad linverkan"),
                _ekvation(r"f_{h,endtra,k} = \frac{1}{3}f_{h,sidotra,k}", "modellantagande för ändträ"),
            ],
        },
    }
