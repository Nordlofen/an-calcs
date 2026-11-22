"""Betongtvärsnitt: påle, balk och plattremsa med stadium II/III.

Stadium II ger elastisk böjstyvhet. Stadium III ger momentkapacitet vid given normalkraft.
Baserad på användarens leverans 2026-11-21. Se docs/betongtvarsnitt.md.
Beräkningskärnan använder endast standardbiblioteket.
"""

import math
from collections.abc import Mapping

from .bojstyvhet_betongpalar import bojstyvhet_betongpalar, _andligt_tal, _ekvation, _post

__all__ = ["betongtvarsnitt", "berakna_betongtvarsnitt"]

BETONGTVARSNITT_VERSION = "1.1.0"
_PLATTREMSA_BREDD = 1000.0
_BT_DEFAULTS = {
    "geometri": "balk", "stadium": "II", "b": 300.0, "h": 600.0,
    "N_d": 0.0, "M": 100.0, "f_ck": 30.0, "f_cd": 20.0,
    "E_cd": 33000.0, "E_s": 200000.0, "f_yk": 500.0, "gamma_s": 1.15,
    "tryckblock": "rektangel", "sigma_c_lim": None, "epsilon_c_lim": None,
    "armeringsrader": None, "c_nom": 30.0, "phi_b": 8.0, "phi_h": 20.0,
    "c_nom_ok": 35.0, "c_nom_uk": 40.0,
    "n_ok": 2, "n_uk": 4, "phi_ok": 16.0, "phi_uk": 20.0,
    "s_ok": None, "s_uk": None, "extra_lager": None, "c_nom_sida": None,
}


def _bt_tal(name, value, minimum=None, positive=False):
    value = _andligt_tal(name, value)
    if positive and value <= 0:
        raise ValueError(f"{name} måste vara > 0.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} måste vara >= {minimum}.")
    return value


def _bt_val(value, aliases, name):
    key = str(value).strip().casefold()
    if key not in aliases:
        raise ValueError(f"Ogiltigt {name}: {value!r}.")
    return aliases[key]


def _bt_geometri(p, indata):
    """Normalisera geometri och armering för både beräkning och måttskiss."""
    geometry = p["geometri"]
    if "b" not in indata and geometry == "plattremsa":
        p["b"] = _PLATTREMSA_BREDD
    if "h" not in indata and geometry == "plattremsa":
        p["h"] = 260.0
    p["b"] = _bt_tal("b", p["b"], positive=True)
    if geometry == "pale":
        if "h" in indata and not math.isclose(_bt_tal("h", p["h"], positive=True), p["b"], rel_tol=1e-12):
            raise ValueError("Pålvalet avser en kvadratisk påle med h=b.")
        p["h"] = p["b"]
        if p["armeringsrader"] is not None or p["extra_lager"]:
            raise ValueError("Pålvalet använder fyra identiska hörnjärn. Ange pålens täckskikt och diametrar.")
        p["c_nom"] = _bt_tal("c_nom", p["c_nom"], minimum=0)
        p["phi_b"] = _bt_tal("Bygeldiameter", p["phi_b"], minimum=0)
        p["phi_h"] = _bt_tal("Huvudarmeringsdiameter", p["phi_h"], positive=True)
        d0 = p["c_nom"] + p["phi_b"] + p["phi_h"] / 2
        if 2 * d0 + p["phi_h"] > p["h"]:
            raise ValueError("Pålarmeringen ryms inte inom tvärsnittet.")
        rows = [
            {"namn": "Hörnjärn ÖK", "y": d0, "phi": p["phi_h"], "antal": 2},
            {"namn": "Hörnjärn UK", "y": p["h"] - d0, "phi": p["phi_h"], "antal": 2},
        ]
    else:
        p["h"] = _bt_tal("h", p["h"], positive=True)
        if geometry == "balk":
            p["phi_b"] = _bt_tal("Bygeldiameter", p["phi_b"], positive=True)
        if p["armeringsrader"] is not None and p["extra_lager"]:
            raise ValueError("Ange antingen armeringsrader eller extra lager från ÖK och UK.")
        rows = p["armeringsrader"] if p["armeringsrader"] is not None else _bt_fasta_rader(p)
    _bt_normalisera_rader(p, rows)
    _bt_stangavstand(p)
    return p


def _bt_fasta_rader(p):
    stirrup = p["phi_b"] if p["geometri"] == "balk" else 0.0
    for key in ("c_nom_ok", "c_nom_uk"):
        p[key] = _bt_tal(key, p[key], minimum=0)
    inner_height = p["h"] - p["c_nom_ok"] - p["c_nom_uk"] - 2 * stirrup
    if inner_height <= 0:
        raise ValueError("Täckskikten och eventuell bygel måste rymmas inom snitthöjden.")
    extra_layers = p["extra_lager"] if p["extra_lager"] is not None else ()
    if not isinstance(extra_layers, (list, tuple)):
        raise ValueError("Extra armeringslager ska anges som en lista.")
    layers_by_side = {"ok": [], "uk": []}
    for layer in extra_layers:
        if not isinstance(layer, Mapping):
            raise ValueError("Varje extra armeringslager ska vara en dictionary.")
        edge = _bt_val(layer.get("sida"), {"ok": "ok", "ök": "ok", "uk": "uk"}, "sida för armeringslager")
        layers_by_side[edge].append(layer)

    rows = []
    occupied_height = 0.0
    plate = p["geometri"] == "plattremsa"
    for key, name in (("ok", "ÖK"), ("uk", "UK")):
        spacing = p[f"s_{key}"] if plate else None
        if isinstance(spacing, str):
            spacing = spacing.strip().replace(",", ".")
        method = "antal" if spacing in (None, "") else "s"
        first = {"phi": p[f"phi_{key}"], method: p[f"n_{key}"] if method == "antal" else spacing}
        extent = 0.0
        count_active = 0
        for index, layer in enumerate((first, *layers_by_side[key])):
            method = "s" if "s" in layer else "antal"
            if index and (method != ("s" if plate else "antal") or {"s", "antal"} <= layer.keys()):
                raise ValueError(f"Extra lager {name} anges med {'c/c-avstånd' if plate else 'antal järn'}.")
            label = "C/c-avstånd" if method == "s" else "Antal järn"
            amount = _bt_tal(f"{label} {name}", layer.get(method), minimum=0)
            if amount == 0:
                continue
            if method == "antal" and not amount.is_integer():
                raise ValueError(f"Antal järn {name} måste vara ett heltal.")
            phi = _bt_tal(f"Stångdiameter {name}", layer.get("phi"), positive=True)
            if method == "antal" and amount * phi + 2 * stirrup > p["b"]:
                raise ValueError(f"Järnen i {name} ryms inte i breddled.")
            if not index and spacing == "":
                method, amount = "s", p["b"] / amount
            if count_active:
                extent += _bt_tal(f"Fritt lageravstånd {name}", layer.get("a_v", 0), minimum=0)
            distance = p[f"c_nom_{key}"] + stirrup + extent + phi / 2
            y = distance if key == "ok" else p["h"] - distance
            count_active += 1
            layer_name = name if count_active == 1 else f"Lager {count_active} {name}"
            rows.append({"namn": layer_name, "y": y, "phi": phi, method: amount})
            extent += phi
        occupied_height += extent
    if occupied_height > inner_height + 1e-9:
        raise ValueError("Järnen ryms inte i höjdled med angivna täckskikt och diametrar.")
    return rows


def _bt_skissdata(values):
    """Använd samma geometri för skissen som för Panel-beräkningen."""
    inputs = _bt_panel_geometri(dict(values))
    inputs["geometri"] = {1: "pale", 2: "balk", 3: "plattremsa"}[inputs["geometri"]]
    return _bt_geometri({**_BT_DEFAULTS, **inputs}, inputs)


def _bt_indata(indata):
    if not isinstance(indata, Mapping):
        raise ValueError("Nya beräkningar anges som dictionary eller via panel_schema:s px-lista.")
    unknown = set(indata) - set(_BT_DEFAULTS)
    if unknown:
        raise ValueError("Okända indatafält: " + ", ".join(sorted(unknown)))
    p = dict(_BT_DEFAULTS)
    p.update(indata)
    p["geometri"] = _bt_val(p["geometri"], {
        "påle": "pale", "pale": "pale", "1": "pale", "1.0": "pale",
        "balk": "balk", "2": "balk", "2.0": "balk",
        "plattremsa": "plattremsa", "3": "plattremsa", "3.0": "plattremsa",
    }, "geometrival")
    p["stadium"] = _bt_val(p["stadium"], {
        "ii": "II", "2": "II", "2.0": "II", "iii": "III", "3": "III", "3.0": "III",
    }, "stadium")
    p["tryckblock"] = _bt_val(p["tryckblock"], {
        "rektangel": "rektangel", "rektangulart": "rektangel", "0.8x": "rektangel",
        "parabel": "parabel", "parabol_rektangel": "parabel",
    }, "tryckblock")
    for key in ("f_ck", "E_s", "f_yk", "gamma_s"):
        p[key] = _bt_tal(key, p[key], positive=True)
    p["N_d"] = _bt_tal("N_d", p["N_d"], minimum=0)
    p["M"] = _bt_tal("M", p["M"])
    if p["f_ck"] > 50:
        raise ValueError("Betongtvärsnitt stöder f_ck upp till 50 MPa.")
    p["f_yd"] = p["f_yk"] / p["gamma_s"]
    p["epsilon_cu"] = 0.0035
    p["epsilon_c0"] = 0.00175 if p["tryckblock"] == "rektangel" else 0.002
    if p["stadium"] == "II":
        p.pop("f_cd")
        p["E_cd"] = _bt_tal("E_cd", p["E_cd"], positive=True)
        sigma = p["sigma_c_lim"] if p["epsilon_c_lim"] is None else None
        p["sigma_c_lim"] = (0.4 * (p["f_ck"] + 8.0) if sigma is None
                            else _bt_tal("sigma_c_lim", sigma, positive=True))
        if p["epsilon_c_lim"] is None:
            p["epsilon_c_lim"] = p["sigma_c_lim"] / p["E_cd"]
            p["epsilon_c_lim_kalla"] = "sigma_c_lim/E_cd; valt modellkriterium för elastisk analys"
        else:
            p["epsilon_c_lim"] = _bt_tal("epsilon_c_lim", p["epsilon_c_lim"], positive=True)
            p["epsilon_c_lim_kalla"] = "manuellt angiven töjningsgräns"
        if p["epsilon_c_lim"] >= p["epsilon_cu"]:
            raise ValueError("epsilon_c_lim ska vara mindre än 0,0035. Ange värdet dimensionslöst i dictionary-anrop.")
    else:
        for key in ("E_cd", "sigma_c_lim", "epsilon_c_lim"):
            p.pop(key)
        p["f_cd"] = _bt_tal("f_cd", p["f_cd"], positive=True)
        if p["f_cd"] > p["f_ck"]:
            raise ValueError("f_cd får inte överstiga f_ck.")
    return _bt_geometri(p, indata)


def _bt_normalisera_rader(p, rows):
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError("Minst en armeringsrad måste anges.")
    normalized = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"Armeringsrad {i} måste vara en dictionary.")
        extra = set(row) - {"namn", "y", "phi", "antal", "s", "A_s"}
        if extra:
            raise ValueError(f"Okända fält i armeringsrad {i}: {sorted(extra)}")
        y = _bt_tal(f"rad {i}: y", row.get("y"))
        phi = _bt_tal(f"rad {i}: phi", row.get("phi"), positive=True)
        if not phi / 2 <= y <= p["h"] - phi / 2:
            raise ValueError(f"Rad {i}: hela stångdiametern måste ligga inom tvärsnittet.")
        methods = [key for key in ("antal", "s", "A_s") if key in row]
        if len(methods) != 1:
            raise ValueError(f"Rad {i}: ange exakt ett av antal, s eller A_s.")
        method = methods[0]
        value = _bt_tal(f"rad {i}: {method}", row[method], positive=True)
        bar_area = math.pi * phi**2 / 4
        if method == "antal":
            if not value.is_integer():
                raise ValueError("Antal järn måste vara ett heltal; använd s för armering per bredd.")
            area = value * bar_area
        elif method == "s":
            area = p["b"] / value * bar_area
        else:
            area = value
        if area / bar_area * phi > p["b"] + 1e-9:
            raise ValueError(f"Rad {i}: järnen överlappar längs bredden även utan fria avstånd.")
        normalized.append({"namn": str(row.get("namn", f"Armeringsrad {i}")), "y": y,
                           "phi": phi, "A_s": area, "antal_ekv": area / bar_area,
                           "indatametod": method, "indatavarde": value})
    p["rader"] = normalized
    p["A_s"] = sum(row["A_s"] for row in normalized)
    if p["A_s"] >= p["b"] * p["h"]:
        raise ValueError("Armeringsarean måste vara mindre än hela tvärsnittets area.")


def _bt_stangavstand(p):
    rows = p["rader"]
    geometry = p["geometri"]
    if geometry == "pale":
        clear_width = p["b"] - 2 * (p["c_nom"] + p["phi_b"])
    elif geometry == "balk" and p["armeringsrader"] is None:
        bars_width = max(row["antal_ekv"] * row["phi"] for row in rows)
        available = p["b"] - 2 * p["phi_b"] - bars_width
        side_cover = p["c_nom_sida"]
        if isinstance(side_cover, str):
            side_cover = side_cover.strip().replace(",", ".")
        p["c_nom_sida_auto"] = side_cover in (None, "")
        p["c_nom_sida"] = (max(0, min(.09 * p["b"], available / 2)) if p["c_nom_sida_auto"]
                          else _bt_tal("Täckskikt sida", side_cover, minimum=0))
        clear_width = p["b"] - 2 * (p["c_nom_sida"] + p["phi_b"])
        if clear_width < bars_width - 1e-9:
            raise ValueError("Järnen ryms inte mellan bygelns sidor med angivet täckskikt.")
    else:
        clear_width = None

    for row in rows:
        if row["indatametod"] == "s":
            row["a_h"] = row["indatavarde"] - row["phi"]
        elif clear_width is not None and row["indatametod"] == "antal" and row["indatavarde"] > 1:
            count = row["indatavarde"]
            row["a_h"] = max(0, clear_width - count * row["phi"]) / (count - 1)


def _bt_bisect(fun, lo, hi, iterations=90):
    flo, fhi = fun(lo), fun(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if flo * fhi > 0:
        raise ValueError("Nollstället är inte inneslutet.")
    for _ in range(iterations):
        mid = (lo + hi) / 2
        fm = fun(mid)
        if fm == 0 or hi - lo < 1e-12 * max(1.0, abs(mid)):
            return mid
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def _bt_resultanthavarm(fc, yfc, steel):
    compression = fc + sum(max(0, r["F"]) for r in steel)
    tension = -sum(min(0, r["F"]) for r in steel)
    yc = ((fc * (yfc or 0.0) + sum(max(0, r["F"]) * r["y"] for r in steel)) / compression
          if compression > 1e-10 else None)
    yt = (-sum(min(0, r["F"]) * r["y"] for r in steel) / tension if tension > 1e-10 else None)
    return {"z": abs(yc - yt) if yc is not None and yt is not None else None,
            "y_Fc": yfc,
            "y_tryckresultant": yc, "y_dragresultant": yt,
            "F_tryck_total": compression}


def _bt_elastisk(p):
    """Exakt integration av linjärt betongtryck; armeringen är punktareor.

    y mäts från ÖK. Tryck är positivt. Positivt M ger tryck i ÖK.
    Egen stångtröghet ingår endast i den ursprungliga nominella pålmodellen.
    """
    b, h, ec, es = p["b"], p["h"], p["E_cd"], p["E_s"]
    rows = p["rader"]
    n, m = p["N_d"] * 1000, p["M"] * 1e6
    alpha = es / ec
    # Fullt tryckt transformerat snitt. Armering ersätter betong.
    area = b * h + sum((alpha - 1) * r["A_s"] for r in rows)
    sq = sum((alpha - 1) * r["A_s"] * (h / 2 - r["y"]) for r in rows)
    iq = b * h**3 / 12 + sum((alpha - 1) * r["A_s"] * (h / 2 - r["y"])**2 for r in rows)
    det = area * iq - sq**2
    if det <= 0:
        raise ValueError("Snittets elastiska styvhetsmatris är inte positivt definit.")
    eps0 = (n * iq - m * sq) / (ec * det)
    curvature = (m * area - n * sq) / (ec * det)
    full = eps0 - abs(curvature) * h / 2 >= -1e-15
    iterations = 0
    if not full:
        candidates = []
        for flip in (False, True):
            oriented = [(h - r["y"] if flip else r["y"], r["A_s"]) for r in rows]
            sign = -1 if flip else 1

            def coefficients(x):
                # N=kappa*nc; M=kappa*mc, med globalt momenttecken.
                nc = ec * b * x**2 / 2
                first = ec * b * x**3 / 6
                for y, a in oriented:
                    force = es * a * (x - y) - ec * a * max(x - y, 0)
                    nc += force
                    first += force * y
                return nc, sign * (nc * h / 2 - first)

            def residual(x):
                nc, mc = coefficients(x)
                return (nc * m - mc * n) / h

            lo, hi = 0.0, h
            if residual(lo) * residual(hi) > 0:
                continue
            x = _bt_bisect(residual, lo, hi)
            nc, mc = coefficients(x)
            denom = nc**2 + (mc / h)**2
            if denom <= 0:
                continue
            k = (nc * n + mc * m / h**2) / denom
            error = math.hypot(nc * k - n, (mc * k - m) / h)
            if k > 0 and error <= 1e-7 * max(1, abs(n), abs(m) / h):
                eps_top = k * (x - h) if flip else k * x
                kg = -k if flip else k
                candidates.append((error, eps_top - kg * h / 2, kg))
        if not candidates:
            raise ValueError("Elastisk N-M-jämvikt kunde inte lösas.")
        _, eps0, curvature = min(candidates)
        iterations = 90
    etop, ebottom = eps0 + curvature * h / 2, eps0 - curvature * h / 2
    # Tryckt betongintervall i de globala koordinaterna.
    if full:
        ya, yb = 0.0, h
    elif curvature > 0:
        ya, yb = 0.0, h / 2 + eps0 / curvature
    else:
        ya, yb = h / 2 + eps0 / curvature, h
    ya, yb = max(0, ya), min(h, yb)
    yc = (ya + yb) / 2
    ac = b * max(0, yb - ya)
    transformed_area = ac
    sy = ac * yc
    for r in rows:
        eps = eps0 + curvature * (h / 2 - r["y"])
        beta = alpha - (1 if eps >= 0 else 0)
        transformed_area += beta * r["A_s"]
        sy += beta * r["A_s"] * r["y"]
    tp = sy / transformed_area
    ic = b * (yb - ya)**3 / 12 + ac * (yc - tp)**2
    i_ii = ic
    for r in rows:
        eps = eps0 + curvature * (h / 2 - r["y"])
        i_ii += (alpha - (1 if eps >= 0 else 0)) * r["A_s"] * (r["y"] - tp)**2
    # Integraler av sigma_c(y)=ec*(eps0+curvature*(h/2-y)).
    aa, bb = ec * (eps0 + curvature * h / 2), -ec * curvature
    fc_gross = b * (aa * (yb - ya) + bb * (yb**2 - ya**2) / 2)
    q_gross = b * (aa * (yb**2 - ya**2) / 2 + bb * (yb**3 - ya**3) / 3)
    fc, qc, steel = fc_gross, q_gross, []
    for r in rows:
        eps = eps0 + curvature * (h / 2 - r["y"])
        sigma = es * eps
        fc -= r["A_s"] * ec * max(eps, 0)
        qc -= r["A_s"] * ec * max(eps, 0) * r["y"]
        steel.append(dict(r, epsilon=eps, sigma=sigma, F=r["A_s"] * sigma))
    n_calc = fc + sum(r["F"] for r in steel)
    m_calc = fc * h / 2 - qc + sum(r["F"] * (h / 2 - r["y"]) for r in steel)
    x = yb - ya
    flip = ebottom > etop
    result = {
        "x": x, "neutralaxel_y": None if abs(curvature) < 1e-25 else h / 2 + eps0 / curvature,
        "x_tp": h - tp if flip else tp, "y_tp": tp, "A_II": transformed_area,
        "I_II": i_ii, "I_c": ic, "EI_II": ec * i_ii / 1e9,
        "epsilon_top": etop, "epsilon_bottom": ebottom,
        "epsilon_c_max": max(0, etop, ebottom), "sigma_c_max": ec * max(0, etop, ebottom),
        "kappa": curvature, "fullt_tryckt": full, "tryckkant": "UK" if flip else "ÖK",
        "rader": steel, "F_c": fc, "F_s_drag": -sum(min(0, r["F"]) for r in steel),
        "F_s_tryck": sum(max(0, r["F"]) for r in steel),
        "N_calc": n_calc, "M_calc": m_calc, "iterationer": iterations,
    }
    result.update(_bt_resultanthavarm(fc, qc / fc if fc > 1e-10 else None, steel))
    return result


def _bt_cirkel_segment(row, depth, y):
    """Betong som undanträngs av en stångrad inom rektangelblocket.

    Exakt cirkelsegment ger kontinuerlig kraft när blockkanten passerar raden.
    A_s/enskild stångarea får vara fraktionellt för armering med s-avstånd.
    """
    radius = row["phi"] / 2
    t = max(-1.0, min(1.0, (depth - y) / radius))
    root = math.sqrt(max(0, 1 - t * t))
    a = radius**2 * (math.asin(t) + math.pi / 2 + t * root)
    q = -2 / 3 * radius**3 * root**3
    factor = row["A_s"] / (math.pi * radius**2)
    return a * factor, (y * a + q) * factor


def _bt_parabel_integraler(h, top, curvature, epsilon_c2):
    """Integraler av sigma/fcd och y*sigma/fcd; inga numeriska fibrer behövs."""
    points = [0.0, h]
    if curvature > 0:
        points.extend(y for y in ((top - epsilon_c2) / curvature, top / curvature) if 0 < y < h)
    points.sort()
    force, first = 0.0, 0.0
    for a, b in zip(points, points[1:]):
        middle = top - curvature * (a + b) / 2
        if middle <= 0:
            continue
        if middle >= epsilon_c2:
            force += b - a
            first += (b * b - a * a) / 2
        else:
            # Integrera i lokala koordinater för att undvika subtraktionsfel.
            length = b - a
            p0 = (top - curvature * a) / epsilon_c2
            q0 = -curvature / epsilon_c2
            c0, c1, c2 = 2 * p0 - p0**2, 2 * q0 * (1 - p0), -q0**2
            integral = c0 * length + c1 * length**2 / 2 + c2 * length**3 / 3
            local_first = c0 * length**2 / 2 + c1 * length**3 / 3 + c2 * length**4 / 4
            force += integral
            first += a * integral + local_first
    return force, first


def _bt_brottprofil(p, u, flip):
    """Beräkna töjningar och snittkrafter för en profil i brottgränstillstånd.

    u=x/h; u=None ger ren jämn tryckning. Vid x>h används EC2:s pivotvillkor.
    Rektangel: eps_c0=1.75 promille, parabel-rektangel: eps_c0=2.0 promille.
    """
    h, b, fcd = p["h"], p["b"], p["f_cd"]
    c0, cu = p["epsilon_c0"], p["epsilon_cu"]
    if u is None:
        x, top, curvature = None, c0, 0.0
    else:
        x = u * h
        pivot = 1 - c0 / cu
        top = cu if u <= 1 else c0 / (1 - pivot / u)
        curvature = top / x
    oriented = [(r, h - r["y"] if flip else r["y"]) for r in p["rader"]]
    if p["tryckblock"] == "rektangel":
        depth = h if x is None else min(h, 0.8 * x)
        fc, qc = b * depth * fcd, b * depth**2 / 2 * fcd
        for row, y in oriented:
            hole, qhole = _bt_cirkel_segment(row, depth, y)
            fc -= fcd * hole
            qc -= fcd * qhole
    else:
        depth = h if x is None else min(h, x)
        integral, first = _bt_parabel_integraler(h, top, curvature, 0.002)
        fc, qc = b * fcd * integral, b * fcd * first
        for row, y in oriented:
            e = max(0, top - curvature * y)
            ratio = min(1.0, e / 0.002)
            sig = fcd * (2 * ratio - ratio**2)
            fc -= row["A_s"] * sig
            qc -= row["A_s"] * sig * y
    steel = []
    for row, y in oriented:
        eps = top - curvature * y
        sig = max(-p["f_yd"], min(p["f_yd"], p["E_s"] * eps))
        steel.append(dict(row, epsilon=eps, sigma=sig, F=row["A_s"] * sig))
    n = fc + sum(r["F"] for r in steel)
    oriented_m = fc * h / 2 - qc + sum(r["F"] * (h / 2 - y)
                                                  for r, (_, y) in zip(steel, oriented))
    result = {"x": x, "x_verksam": h if x is None else min(h, x), "a_block": depth,
            "epsilon_c_max": top, "epsilon_c_min": top - curvature * h,
            "epsilon_top": top - curvature * h if flip else top,
            "epsilon_bottom": top if flip else top - curvature * h,
            "kappa": -curvature if flip else curvature,
            "F_c": fc, "y_Fc_fran_tryckkant": qc / fc if fc > 1e-10 else None,
            "F_s_drag": -sum(min(0, r["F"]) for r in steel),
            "F_s_tryck": sum(max(0, r["F"]) for r in steel),
            "N_calc": n, "M_Rd": -oriented_m if flip else oriented_m,
            "tryckkant": "UK" if flip else "ÖK", "rader": steel}
    yfc = result["y_Fc_fran_tryckkant"]
    result.update(_bt_resultanthavarm(fc, h - yfc if flip and yfc is not None else yfc, steel))
    return result


def _bt_kapacitet(p):
    """Söker båda sidor av N-M-kapacitetsintervallet vid givet N_d.

    Logaritmisk avsökning + inneslutna nollställen. Flera rötter för asymmetrisk
    armering beaktas. Varje publicerad profil måste uppfylla normalkraftsjämvikt.
    """
    target = p["N_d"] * 1000
    tolerance = 1e-8 * max(1, p["b"] * p["h"] * p["f_cd"], target)
    grid = sorted(set([10**(-7 + i * 14 / 420) for i in range(421)] + [1.0, 1.25]))
    candidates = []
    for flip in (False, True):
        uniform = _bt_brottprofil(p, None, flip)
        if abs(uniform["N_calc"] - target) <= tolerance:
            candidates.append(uniform)

        def residual(u):
            return _bt_brottprofil(p, u, flip)["N_calc"] - target

        previous_u, previous_f = grid[0], residual(grid[0])
        for u in grid[1:]:
            f = residual(u)
            if previous_f * f < 0:
                root = _bt_bisect(residual, previous_u, u)
                state = _bt_brottprofil(p, root, flip)
                if abs(state["N_calc"] - target) > tolerance:
                    raise ArithmeticError("Kapacitetsprofilen uppfyller inte N-jämvikten.")
                candidates.append(state)
            elif f == 0 or (abs(f) <= tolerance and u == 1):
                candidates.append(_bt_brottprofil(p, u, flip))
            previous_u, previous_f = u, f
    if not candidates:
        return {"jamvikt": False, "profiler": [], "vald": None,
                "M_Rd_min": None, "M_Rd_max": None, "utnyttjande": None,
                "inom_kapacitetsintervall": False}
    lower = min(candidates, key=lambda r: r["M_Rd"])
    upper = max(candidates, key=lambda r: r["M_Rd"])
    demand = p["M"] * 1e6
    chosen = lower if demand < 0 else upper
    mmin, mmax = lower["M_Rd"], upper["M_Rd"]
    mtol = 1e-8 * max(1, abs(mmin), abs(mmax))
    within = mmin - mtol <= demand <= mmax + mtol
    usable_direction = chosen["M_Rd"] * demand >= 0 and abs(chosen["M_Rd"]) > 1e-12
    utilization = abs(demand / chosen["M_Rd"]) if usable_direction else (0.0 if demand == 0 and within else None)
    return {"jamvikt": True, "profiler": candidates, "vald": chosen,
            "M_Rd_min": mmin, "M_Rd_max": mmax, "utnyttjande": utilization,
            "inom_kapacitetsintervall": within}


def _bt_tillaten_tojning(p, etop, ebottom):
    high, low = max(etop, ebottom, 0), min(etop, ebottom)
    if high <= 0 or low <= 0:
        return p["epsilon_cu"]
    pivot = 1 - p["epsilon_c0"] / p["epsilon_cu"]
    return p["epsilon_c0"] / (1 - pivot + pivot * low / high)


def _bt_varning(code, text, value=None, limit=None, unit="", critical=False):
    return {"kod": code, "niva": "KRITISK" if critical else "VARNING", "text": text,
            "varde": value, "grans": limit, "enhet": unit}


def berakna_betongtvarsnitt(indata):
    """Maskinläsbar analys. Använd betongtvarsnitt(px) för Panel-utskrift.

    Rektangulära snitt, 0 < f_ck <= 50 MPa, N_d >= 0 (tryck), båda M-tecken.
    Laster avser hela den angivna bredden: kN och kNm. Ingen automatisk
    multiplicering av linjelaster med b. För b=1000 mm motsvarar detta en meter.
    Koordinaten y avser armeringscentrum från ÖK. Positivt M ger tryck i ÖK.
    Stadium III redovisar kapacitet vid givet N, inte lastnivåns deformationer.
    """
    p = _bt_indata(indata)
    warnings = []
    ii, iii = None, None
    if p["stadium"] == "II":
        ii = _bt_elastisk(p)
        concrete_limit = _bt_tillaten_tojning(p, ii["epsilon_top"], ii["epsilon_bottom"])
        ii["epsilon_cu_tillaten"] = concrete_limit
        if ii["epsilon_c_max"] > p["epsilon_c_lim"] * (1 + 1e-9):
            warnings.append(_bt_varning("II_EPSILON_C_LIM",
                "Betongens trycktöjning överskrider den elastiska töjningsgränsen.",
                ii["epsilon_c_max"] * 1000, p["epsilon_c_lim"] * 1000, "‰"))
        for index, row in enumerate(ii["rader"], 1):
            if abs(row["sigma"]) > p["f_yd"] * (1 + 1e-9):
                direction = "drag" if row["sigma"] < 0 else "tryck"
                warnings.append(_bt_varning(f"II_STALFLYTNING_{index}",
                    f"Stålspänningen i {row['namn']} överskrider flytgränsen i {direction}.",
                    abs(row["sigma"]), p["f_yd"], "MPa"))
        if ii["epsilon_c_max"] > concrete_limit * (1 + 1e-9):
            warnings.append(_bt_varning("II_BETONG_BROTTTOJNING",
                "Den elastiskt beräknade trycktöjningen överskrider betongens tillåtna stuktöjning.",
                ii["epsilon_c_max"] * 1000, concrete_limit * 1000, "‰", critical=True))
    else:
        iii = _bt_kapacitet(p)
        if not iii["jamvikt"]:
            warnings.append(_bt_varning("III_N_JAMVIKT_SAKNAS",
                "Ingen jämvikt hittades för angiven normalkraft. Momentkapaciteten kunde inte beräknas.",
                critical=True))
        elif not iii["inom_kapacitetsintervall"]:
            warnings.append(_bt_varning("III_MOMENTKAPACITET_OVERSKRIDS",
                "Det inmatade böjmomentet ligger utanför snittets momentkapacitet vid angiven normalkraft.",
                p["M"], (iii["M_Rd_min"] if p["M"] * 1e6 < iii["M_Rd_min"] else iii["M_Rd_max"]) / 1e6,
                "kNm", critical=True))
    return {"version": BETONGTVARSNITT_VERSION, "indata": p, "stadium_II": ii,
            "stadium_III": iii, "varningar": warnings,
            "modellvarning": bool(warnings),
            "kritisk_varning": any(w["niva"] == "KRITISK" for w in warnings)}


def _bt_redovisa_armeringsgrupper(p, state, partial):
    epsilon_y = p["f_yd"] / p["E_s"]
    partial.append(_post("epsilon_sy", r"ε_{sy}", epsilon_y * 1000, "‰", "stålets flyttöjning", 4))
    tension_strain = None
    from_bottom = state["tryckkant"] == "UK"
    for group, sign, depth_name, symbol in (("drag", -1, "d", "d"), ("tryck", 1, "d_prime", "d'")):
        rows = [(i, row) for i, row in enumerate(state["rader"], 1) if sign * row["epsilon"] > 0]
        if not rows:
            continue
        area = sum(row["A_s"] for _, row in rows)
        centroid = sum(row["A_s"] * row["y"] for _, row in rows) / area
        depth = p["h"] - centroid if from_bottom else centroid
        strain = sum(row["A_s"] * sign * row["epsilon"] for _, row in rows) / area
        centroid_label = "areatyngdpunkt"
        if len(rows) > 1:
            for i, row in rows:
                layer_depth = p["h"] - row["y"] if from_bottom else row["y"]
                partial.append(_post(f"{depth_name}_{i}", rf"{symbol}_{{{i}}}", layer_depth, "mm",
                                     f"djup till stångcentrum i {row['namn']} från tryckkanten"))
            centroid_label = "gemensamma areatyngdpunkt"
        partial.extend([
            _post(depth_name, symbol, depth, "mm", f"djup till {group}armeringens {centroid_label} från tryckkanten"),
            _post(f"epsilon_s_{group}", rf"ε_{{s,{group}}}", strain * 1000, "‰", f"töjning vid {group}armeringens areatyngdpunkt", 4),
        ])
        if group == "drag":
            tension_strain = strain
            yielded = sum(row["A_s"] for _, row in rows if -row["epsilon"] >= epsilon_y * (1 - 1e-9))
            partial.append(_post("flytandel_drag", r"\eta_{s,flyt}", 100 * yielded / area, "%",
                                 "andel av dragarmeringsarean som nått flyttöjningen", 1))
    return tension_strain


def _bt_balanspost(tension_strain, epsilon_y, equilibrium):
    label = ""
    if not equilibrium:
        status = "Ej bedömbar"
        label = "normalkraftsjämvikt saknas"
    elif tension_strain is None:
        status = "Ej tillämplig"
        label = "ingen armering ligger i drag"
    else:
        if math.isclose(tension_strain, epsilon_y, rel_tol=1e-9, abs_tol=1e-12):
            status = "Balanserat · Gränsfall"
        elif tension_strain > epsilon_y:
            status = "Underarmerat · Godkänd"
        else:
            status = "Överarmerat · Ej godkänd"
        strain_text = f"{1000 * tension_strain:.4f}".replace(".", ",")
        limit_text = f"{1000 * epsilon_y:.4f}".replace(".", ",")
        label = f"dragtöjning vid d {strain_text} ‰, flyttöjning {limit_text} ‰"
    return _post("balanskontroll", "Balanskontroll", status, etikett=label)


def _bt_panel_resultat(raw):
    p, warnings = raw["indata"], raw["varningar"]
    ii, iii = raw["stadium_II"], raw["stadium_III"]
    geometry = {"pale": "Påle", "balk": "Balk", "plattremsa": "Plattremsa"}[p["geometri"]]
    model = "rektangulärt tryckblock" if p["tryckblock"] == "rektangel" else "parabel–rektangel"
    method_items = [
        {"rubrik": "Beräkning", "text": f"{geometry}, stadium {p['stadium']}. Rektangulärt snitt, enaxlig böjning och normalkraft."},
        {"rubrik": "Tecken och enheter", "text": "I jämviktsekvationerna är tryck positivt. Positivt böjmoment ger tryck i ÖK vid ren böjning. Laster avser hela snittbredden. Armeringsgruppernas töjningar visas som belopp i promille."},
        {"rubrik": "Avgränsning", "text": "Tvärsnittsanalys för f_ck upp till 50 MPa. Förankring, skjuvning, torsion, sprickbredd, fria stångavstånd, rotationsförmåga, instabilitet och andra ordningens moment kontrolleras separat."},
    ]
    if ii is not None:
        method_items.extend([
            {"rubrik": "Stadium II", "text": "N_d och M bestämmer tryckzonen. Betongen i tryckzonen och all längsarmering bidrar till böjstyvheten."},
            {"rubrik": "Varningsgräns i stadium II", "text": "Töjningsgränsen anges direkt eller som sigma_c_lim/E_cd. Automatläget använder 0,4(f_ck+8) MPa som spänningsgräns."},
        ])
    else:
        method_items.append({"rubrik": "Stadium III", "text": f"Momentkapacitet vid angiven normalkraft med {model}. Stålspänningen är konstant efter flytning."})
        method_items.append({"rubrik": "Balanskontroll", "text": "Dragtöjningen vid dragarmeringens areatyngdpunkt jämförs med flyttöjningen vid beräknad momentkapacitet."})
    method_items.extend([
        {"rubrik": "Stuktöjning", "text": f"Vid delvis tryckt snitt gäller {p['epsilon_cu']*1000:g} ‰ i den mest tryckta kanten. Vid helt tryckt snitt beror gränsen på töjningen i båda kanterna. Vid jämn tryckning är gränsen {p['epsilon_c0']*1000:g} ‰."},
        {"rubrik": "Eurokod 2 (EN 1992-1-1:2004)", "text": "Stadium III bygger på betongens tryckmodell i 3.1.7, stålets flytplatå i 3.2.7(2) och antagandena om böjning med normalkraft i 6.1."},
    ])
    data = [
        _post("b", "b", p["b"], "mm", "plattremsans bredd" if p["geometri"] == "plattremsa" else "snittets bredd"),
        _post("h", "h", p["h"], "mm", "tvärsnittets höjd eller plattjocklek"),
        _post("N_d", r"N_d", p["N_d"], "kN", "normalkraft i samma kombination som M, positiv i tryck"),
        _post("M", r"M_{Ed}", p["M"], "kNm", "böjmoment kring snittets mitt"),
    ]
    for key, latex, unit, label in [
        ("f_ck", r"f_{ck}", "MPa", "karakteristisk cylindertryckhållfasthet"),
        ("E_cd", r"E_{cd}", "MPa", "betongens elasticitetsmodul i stadium II"),
        ("sigma_c_lim", r"\sigma_{c,lim}", "MPa", "modellens spänningsgräns för töjningsvarning"),
    ]:
        if key in p and (key != "sigma_c_lim" or not p["epsilon_c_lim_kalla"].startswith("manuellt")):
            data.append(_post(key, latex, p[key], unit, label))
    if ii is not None:
        data.append(_post("epsilon_c_lim", r"ε_{c,lim}", p["epsilon_c_lim"] * 1000, "‰",
            "Definition: " + p["epsilon_c_lim_kalla"], 4))
    if p["geometri"] == "pale":
        data.append(_post("c_nom", r"c_{nom}", p["c_nom"], "mm", "lika täckskikt till bygelns utsida"))
    if p["geometri"] == "pale" or (p["geometri"] == "balk" and p["armeringsrader"] is None):
        data.append(_post("phi_b", r"\phi_b", p["phi_b"], "mm", "bygeldiameter"))
    if p["geometri"] != "pale" and p["armeringsrader"] is None:
        for key, edge in (("ok", "ÖK"), ("uk", "UK")):
            reference = "bygelns utsida" if p["geometri"] == "balk" else "längsarmeringens utsida"
            data.append(_post(f"c_nom_{key}", rf"c_{{nom,{edge}}}", p[f"c_nom_{key}"], "mm", f"täckskikt {edge} till {reference}"))
        if p["geometri"] == "balk":
            label = "automatiskt sidomått till bygelns utsida" if p["c_nom_sida_auto"] else "sidotäckskikt till bygelns utsida"
            data.append(_post("c_nom_sida", r"c_{nom,sida}", p["c_nom_sida"], "mm", label))
    for i, row in enumerate(p["rader"], 1):
        name = row["namn"]
        data.append(_post(f"phi_{i}", rf"\phi_{{{i}}}", row["phi"], "mm", f"stångdiameter {name}"))
        if row["indatametod"] == "s":
            data.append(_post(f"s_{i}", rf"s_{{{i}}}", row["indatavarde"], "mm", f"c/c-avstånd {name}"))
        label = f"armeringsarea {name}"
        if row["indatametod"] == "antal":
            label += f" ({row['indatavarde']:g} järn)"
        data.append(_post(f"As_{i}", rf"A_{{s,{i}}}", row["A_s"], "mm^2", label))
    partial = [
        _post("A_c", r"A_c", p["b"] * p["h"], "mm^2", "snittets bruttoarea"),
        _post("A_s", r"A_s", p["A_s"], "mm^2", "total längsarmeringsarea"),
    ]
    if iii is not None:
        partial.append(_post("f_cd", r"f_{cd}", p["f_cd"], "MPa", "dimensionerande betongtryckhållfasthet"))
    partial.extend([
        _post("E_s", r"E_s", p["E_s"], "MPa", "elasticitetsmodul för armeringen"),
        _post("f_yk", r"f_{yk}", p["f_yk"], "MPa", "karakteristisk flytgräns för stålet"),
        _post("gamma_s", r"\gamma_s", p["gamma_s"], "", "partialkoefficient för armeringsstål"),
        _post("f_yd", r"f_{yd}", p["f_yd"], "MPa", "dimensionerande flytgräns"),
        _post("epsilon_cu", r"ε_{cu}", p["epsilon_cu"] * 1000, "‰",
              "betongens brottöjning vid delvis tryckt snitt (EC2 6.1(3))"),
        _post("epsilon_c0", r"ε_{c,0}", p["epsilon_c0"] * 1000, "‰",
              f"töjningsgräns vid jämn ren tryckning, {model}", 3),
    ])
    for i, row in enumerate(p["rader"], 1):
        if "a_h" in row:
            partial.append(_post(f"a_h_{i}", rf"a_{{h,{i}}}", row["a_h"], "mm", f"fritt stångavstånd i {row['namn']}"))
    ordered_rows = sorted(enumerate(p["rader"], 1), key=lambda item: item[1]["y"])
    for (i, upper), (j, lower) in zip(ordered_rows, ordered_rows[1:]):
        gap = lower["y"] - upper["y"] - (upper["phi"] + lower["phi"]) / 2
        partial.append(_post(f"a_v_{i}_{j}", rf"a_{{v,{i},{j}}}", gap, "mm",
                             f"fritt höjdavstånd mellan {upper['namn']} och {lower['namn']}"))
    final = [_post("stadium", "Stadium", p["stadium"],
                   etikett="elastisk tvärsnittsanalys" if ii is not None else "")]
    equations = [
        _ekvation(r"f_{yd}=f_{yk}/\gamma_s", "dimensionerande flytgräns (EC2 3.2.7(2))"),
        _ekvation(r"\varepsilon_{sy}=f_{yd}/E_s", "stålets flyttöjning"),
    ]
    if any(row["indatametod"] == "s" for row in p["rader"]):
        equations.insert(0, _ekvation(r"A_{s,i}=\frac{b}{s_i}\frac{\pi\phi_i^2}{4}", "armeringsarea från c/c-avstånd"))
    if ii is not None:
        equations.append(_ekvation(r"\varepsilon(y)=\varepsilon_{ÖK}+\frac{y}{h}(\varepsilon_{UK}-\varepsilon_{ÖK})",
                                   "linjär töjning, y från ÖK"))
        if not p["epsilon_c_lim_kalla"].startswith("manuellt"):
            equations.append(_ekvation(r"\varepsilon_{c,lim}=\sigma_{c,lim}/E_{cd}", "automatisk varningsgräns för den elastiska modellen"))
        for key, latex, unit, label, factor in [
            ("x_tp", r"x_{tp}", "mm", "transformerad tyngdpunkt från den mest tryckta kanten", 1),
            ("A_II", r"A_{II}", "mm^2", "transformerat snitts area", 1),
            ("I_II", r"I_{II}", "mm^4", "transformerat snitts tröghetsmoment", 1),
            ("epsilon_c_max", r"ε_{c,max}", "‰", "största trycktöjning i betongen", 1000),
            ("epsilon_top", r"ε_{ÖK}", "‰", "töjning i ÖK", 1000),
            ("epsilon_bottom", r"ε_{UK}", "‰", "töjning i UK", 1000),
            ("epsilon_cu_tillaten", r"ε_{cu,till}", "‰", "tillåten stuktöjning för beräknad töjningsfördelning", 1000),
        ]:
            partial.append(_post(key, latex, ii[key] * factor, unit, label, 4))
        final.extend([
            _post("x", "x", ii["x"], "mm", "tryckzonens höjd"),
            _post("sigma_c_max", r"\sigma_{c,max}", ii["sigma_c_max"], "MPa", "största tryckspänning i betongen"),
        ])
        _bt_redovisa_armeringsgrupper(p, ii, partial)
        final.extend([
            _post("F_c", r"F_c", ii["F_c"] / 1000, "kN", "betongens tryckkraft efter armeringsavdrag"),
            _post("F_s_tryck", r"F'_s", ii["F_s_tryck"] / 1000, "kN", "tryckarmeringens totala kraft"),
            _post("F_s_drag", r"F_{s,drag}", ii["F_s_drag"] / 1000, "kN", "armeringens dragkraft som positivt belopp"),
        ])
        if ii["z"] is not None:
            final.append(_post("z_II", r"z_{II}", ii["z"], "mm", "hävarm mellan tryck- och dragresultanterna"))
        final.append(_post("EI_II", r"EI_{II}", ii["EI_II"], "kN*m^2", "böjstyvhet från tryckzonen och armeringen"))
        equations.extend([
            _ekvation(r"\alpha=\frac{E_s}{E_{cd}}", "modulkvot för stål omräknat till betong"),
            _ekvation(r"\beta_i=\alpha-1\quad\text{om }u_i\leq x", "armering i tryckzonen, med avdrag för undanträngd betong"),
            _ekvation(r"\beta_i=\alpha\quad\text{om }u_i>x", "armeringsrad utanför tryckzonen"),
            _ekvation(r"A_{II}(x)=bx+\sum_i\beta_i A_{s,i}", "transformerad area vid provvärdet x"),
            _ekvation(r"x_{tp}(x)=\frac{bx^2/2+\sum_i\beta_i A_{s,i}u_i}{A_{II}(x)}",
                       "transformerad tyngdpunkt från den mest tryckta kanten"),
            _ekvation(r"I_{II}(x)=\frac{bx^3}{12}+bx\left(\frac{x}{2}-x_{tp}(x)\right)^2+\sum_i\beta_i A_{s,i}\left(u_i-x_{tp}(x)\right)^2",
                       "tröghetsmoment kring tyngdpunkten, med armeringsarean vid stångcentrum"),
            _ekvation(r"M_u=sM", "s = +1 från ÖK och s = −1 från UK"),
            _ekvation(r"M_{tp}(x)=M_u-N_d\left(\frac h2-x_{tp}(x)\right)",
                       "moment flyttat från snittets mitt till den transformerade tyngdpunkten"),
            _ekvation(r"\sigma_{II}(u;x)=\frac{N_d}{A_{II}(x)}-\frac{M_{tp}(x)}{I_{II}(x)}\left(u-x_{tp}(x)\right)",
                       "linjär spänning i det transformerade snittet, med tryck positivt"),
            _ekvation(r"\sigma_{\min}(h)=\min\{\sigma_{II}(0;h),\sigma_{II}(h;h)\}",
                       "lägsta kantspänning när hela snittet prövas"),
            _ekvation(r"x=h\quad\text{om }\sigma_{\min}(h)\geq 0", "hela snitthöjden är verksam"),
            _ekvation(r"\sigma_{II}(x;x)=0\quad\text{om }\sigma_{\min}(h)<0",
                       "lös x med noll spänning vid tryckzonens gräns"),
            _ekvation(r"\sigma_c=E_{cd}\max(\varepsilon_c,0),\quad\sigma_{s,\mathrm{ber}}=E_s\varepsilon_s",
                       "elastiska spänningar med tryck positivt. Överskriden flytgräns ger en varning."),
            _ekvation(r"EI_{II}=E_{cd}I_{II}/10^9", "böjstyvhet i kNm² med E i MPa och I i mm⁴"),
        ])
    if iii is not None:
        tension_strain = None
        if iii["jamvikt"]:
            state = iii["vald"]
            partial.extend([
                _post("a_block_Rd", r"a_{Rd}", state["a_block"], "mm", "tryckblockets höjd" if p["tryckblock"] == "rektangel" else "tryckzonens höjd"),
                _post("epsilon_c_Rd", r"ε_{c,Rd}", state["epsilon_c_max"] * 1000, "‰", "största trycktöjning i betongen"),
                _post("epsilon_top_Rd", r"ε_{ÖK,Rd}", state["epsilon_top"] * 1000, "‰", "töjning i ÖK vid momentkapacitet"),
                _post("epsilon_bottom_Rd", r"ε_{UK,Rd}", state["epsilon_bottom"] * 1000, "‰", "töjning i UK vid momentkapacitet"),
            ])
            final.append(_post("x_Rd_verksam", r"x_{Rd,verksam}", state["x_verksam"], "mm", "tryckzonens höjd inom snittet"))
            if p["tryckblock"] == "rektangel":
                final.append(_post("sigma_c_Rd", r"\sigma_c=f_{cd}", p["f_cd"], "MPa", "betongens tryckspänning i tryckblocket"))
            if state["x"] is not None:
                partial.append(_post("x_Rd", r"x_{Rd}", state["x"], "mm", "djup till neutralaxeln från tryckkanten"))
            tension_strain = _bt_redovisa_armeringsgrupper(p, state, partial)
            final.extend([
                _post("F_c_Rd", "F_c", state["F_c"] / 1000, "kN", "betongens tryckkraft efter armeringsavdrag"),
                _post("F_s_tryck_Rd", r"F'_s", state["F_s_tryck"] / 1000, "kN", "tryckarmeringens totala kraft"),
                _post("F_s_drag_Rd", "F_s", state["F_s_drag"] / 1000, "kN", "armeringens dragkraft"),
            ])
            if state["z"] is not None:
                final.append(_post("z_Rd", "z", state["z"], "mm", "hävarm mellan tryck- och dragresultanterna"))
        final.append(_post("M_Ed", r"M_{Ed}", p["M"], "kNm", "inmatat dimensionerande böjmoment"))
        if iii["jamvikt"]:
            final.append(_post("M_Rd", r"M_{Rd}", state["M_Rd"] / 1e6, "kNm", "momentkapacitet i lastens riktning"))
        final.append(_bt_balanspost(tension_strain, p["f_yd"] / p["E_s"], iii["jamvikt"]))
        moment_status = "Godkänd" if iii["inom_kapacitetsintervall"] else "Ej godkänd"
        moment_label = "" if iii["jamvikt"] else "normalkraftsjämvikt saknas"
        final.append(_post("momentkontroll", "Momentkontroll", moment_status, etikett=moment_label))
        rectangular = p["tryckblock"] == "rektangel"
        capacity = iii["vald"]
        uniform_compression = capacity is not None and capacity["x"] is None
        if uniform_compression:
            equations.append(_ekvation(r"\varepsilon_{s,i}=\varepsilon_{c,0}", "ståltöjning vid jämn tryckning"))
        else:
            fully_compressed = capacity is not None and capacity["x"] > p["h"]
            compression_strain = r"\varepsilon_{c,max}(x)" if fully_compressed else (
                r"\varepsilon_{cu3}" if rectangular else r"\varepsilon_{cu2}")
            equations.append(_ekvation(r"\varepsilon_{s,i}(x)=" + compression_strain + r"\left(1-\frac{u_i}{x}\right)",
                                       "töjning i lager i på djupet u_i från tryckkanten (EC2 6.1(2))"))
            if fully_compressed:
                equations.append(_ekvation(r"\varepsilon_{c,max}(x)=\frac{\varepsilon_{c,0}}{1-(1-\varepsilon_{c,0}/\varepsilon_{cu})h/x}",
                                           "betongens kanttöjning vid helt tryckt snitt (EC2 figur 6.1)"))
        if rectangular:
            block_height = r"a=h" if uniform_compression else r"a=\min(0.8x,h)"
            equations.extend([
                _ekvation(block_height, "tryckblockets höjd (EC2 3.1.7(3))"),
                _ekvation(r"F_c=f_{cd}(ba-A_{s,\mathrm{block}})", "betongens tryckkraft med avdrag för stålets area i blocket"),
            ])
        else:
            equations.append(_ekvation(r"\sigma_c=f_{cd}[1-(1-\varepsilon_c/0.002)^2]", "parabel upp till 2 promille, därefter konstant f_cd till tillämplig brottöjning; dragbetong försummas"))
        equations.extend([
            _ekvation(r"\sigma_{s,\mathrm{ber},i}=\max(-f_{yd},\min(f_{yd},E_s\varepsilon_{s,i}))",
                       "stålspänning i beräkningen med flytplatå (EC2 3.2.7(2)b)"),
            _ekvation(r"F_{s,i}=\sigma_{s,\mathrm{ber},i}A_{s,i}", "kraft i armeringslager i"),
            _ekvation(r"N_{Ed}=F_c+\sum_i F_{s,i}" if uniform_compression else r"N_{Ed}=F_c(x)+\sum_i F_{s,i}(x)",
                       "normalkraftsjämvikt vid jämn tryckning" if uniform_compression else
                       "lös x ur normalkraftsjämvikten. Tryck är positivt och drag negativt."),
            _ekvation(r"M_{Rd,u}=F_c(h/2-u_c)+\sum_i F_{s,i}(h/2-u_i)",
                       "moment kring snittets mitt. u mäts från tryckkanten till respektive kraft."),
            _ekvation(r"M_{Rd}=sM_{Rd,u}", "s = +1 för tryckkant i ÖK och s = −1 för UK"),
        ])
        if rectangular:
            equations.append(_ekvation(r"|M_{Rd}|=F_c z", "förenklad beräkning vid ren böjning utan tryckarmering"))
    for i, warning in enumerate(warnings, 1):
        value_text = ("" if warning["varde"] is None else
                      f" Beräknat {warning['varde']:.6g} {warning['enhet']}. Gräns {warning['grans']:.6g} {warning['enhet']}.")
        heading = "Kritisk varning" if warning["niva"] == "KRITISK" else "Varning"
        shown_by_moment_check = warning["kod"] == "III_MOMENTKAPACITET_OVERSKRIDS"
        method_text = warning["text"] + (value_text if shown_by_moment_check else "")
        method_items.append({"rubrik": heading, "text": method_text})
        if not shown_by_moment_check:
            final.append(_post(f"varning_{i}", rf"\mathrm{{{warning['niva']}}}_{{{i}}}", 1, "",
                               f"{heading}. {warning['text']}{value_text}", 0))
    equation_section = {"title": "Ekvationer", "items": equations}
    if ii is not None:
        equation_section["notes"] = [
            {"rubrik": "Koordinater och enheter", "text": "u och armeringsradens centrumläge u_i räknas från den mest tryckta kanten. N_d och M sätts in i N och Nmm i snittekvationerna. Måtten är i mm."},
            {"rubrik": "Lösning för x", "text": "Programmet anpassar tryckzonen till kraft- och momentjämvikt. Vid delvis tryckt snitt är betongspänningen noll vid tryckzonens gräns."},
        ]
    return {
        "metodbeskrivning": {"title": "Metodbeskrivning", "items": method_items},
        "indata": {"title": "Indata", "items": data},
        "delresultat": {"title": "Delresultat", "items": partial},
        "ekvationer": equation_section,
        "slutresultat": {"title": "Slutresultat", "items": final},
    }


def _bt_panel_geometri(data):
    if data["geometri"] == 1:
        data.pop("h", None)
    elif data["geometri"] == 3:
        data["b"] = _PLATTREMSA_BREDD
    for code, table, method in ((2, "balk_lager", "antal"), (3, "plattremsa_lager", "s")):
        columns = [data.pop(f"{table}_{column}", None) for column in _BT_LAGER_KOLUMNER]
        if data["geometri"] == code and any(column is not None for column in columns):
            data["extra_lager"] = [
                {"sida": edge, "phi": phi, method: amount, "a_v": gap}
                for edge, phi, amount, gap in zip(*columns, strict=True)
            ]
    return data


def _bt_fran_panel(px):
    fields = _BT_PANEL_PX
    if len(px) == len(_BT_ALDRE_PANEL_PX):
        fields = _BT_ALDRE_PANEL_PX
    elif len(px) == len(_BT_ALDRE_PANEL_PX) + 1:
        i = _BT_ALDRE_PANEL_PX.index("gamma_s")
        fields = (*_BT_ALDRE_PANEL_PX[:i], "tryckblock", *_BT_ALDRE_PANEL_PX[i:])
    elif len(px) == len(_BT_PANEL_PX_FORE_LAGER):
        fields = _BT_PANEL_PX_FORE_LAGER
    if len(px) != len(fields):
        raise ValueError(f"Panel-formatet kräver {len(_BT_PANEL_PX)} värden. Äldre pålformat har 12 eller 16 värden.")
    data = _bt_panel_geometri(dict(zip(fields, px)))
    if data["geometri"] == 3:
        data.setdefault("s_ok", "")
        data.setdefault("s_uk", "")
    manual_strain = data.pop("epsilon_c_lim_manuell")
    strain_per_mille = data.pop("epsilon_c_lim_pm")
    auto_stress = data.pop("sigma_c_lim_auto")
    if data["stadium"] == 2:
        if not isinstance(manual_strain, bool) or not isinstance(auto_stress, bool):
            raise ValueError("Varningsgränsernas panelval ska vara booleska.")
        if manual_strain:
            data["epsilon_c_lim"] = _bt_tal("Manuell töjningsgräns", strain_per_mille, positive=True) / 1000
        if auto_stress or manual_strain:
            data.pop("sigma_c_lim")
    return data


def betongtvarsnitt(px):
    """Tvärsnitt i stadium II/III för Panel och CalcBlock.

    Använd namngiven indata enligt ``berakna_betongtvarsnitt`` eller
    ``panel_schema['px']``. Äldre pållistor med 12 eller 16 värden går direkt
    till den befintliga pålfunktionen, med oförändrad redovisning.

    Ange diameter och täckskikt per sida, samt antal för balk eller c/c för
    plattremsa. Extra lager placeras med fritt vertikalt avstånd. Balk har bygel.
    En dictionary kan i stället ange armeringsrader med centrumläge y,
    diameter och exakt ett av antal, s eller A_s.
    Panelens val Analysmodell visar när respektive stadium används.
    Panel använder rektangulärt tryckblock i stadium III. Ett uttryckligt
    materialval från tidigare positions- eller dictionary-anrop läses fortsatt.
    Delresultatet visar enskilda lagerdjup för armeringsgrupper med flera lager.
    Slutresultatet i stadium III visar balanskontroll och momentkontroll.
    """
    if isinstance(px, (list, tuple)):
        if len(px) in (12, 16):
            return bojstyvhet_betongpalar(px)
        px = _bt_fran_panel(px)
    return _bt_panel_resultat(berakna_betongtvarsnitt(px))


def _bt_field(name, label, symbol="", unit="", **extra):
    return {"name": name, "label": label, "symbol": symbol, "unit": unit,
            "type": "float", "default": _BT_DEFAULTS.get(name), **extra}


def _bt_choice(name, label, default, options, **extra):
    return _bt_field(name, label, type="choice", default=default,
                     options=[{"label": label, "value": value} for label, value in options], **extra)


_PALE = {"field": "geometri", "equals": 1}
_BALK = {"field": "geometri", "equals": 2}
_PLATTA = {"field": "geometri", "equals": 3}
_BALK_PLATTA = {"field": "geometri", "in": [2, 3]}
_ELASTISK = {"field": "stadium", "equals": 2}
_ULTIMAT = {"field": "stadium", "equals": 3}
_MANUELL_TOJNING = {"field": "epsilon_c_lim_manuell", "equals": True}
_AUTO_TOJNING = {"field": "epsilon_c_lim_manuell", "equals": False}
_STADIUM_HELP_HTML = (
    '<style>.anp-panel .anp-grid:has(> .anp-field .betongtvarsnitt-stadium-help) '
    '{ align-items: start; }'
    '.betongtvarsnitt-stadium-help > div + div { margin-top: .35em; }</style>'
    '<div class="betongtvarsnitt-stadium-help">'
    '<div><strong>Stadium II.</strong> Beräkna böjstyvhet <i>EI</i><sub>II</sub> vid angiven last, '
    'till exempel som underlag för nedböjningsberäkning.</div>'
    '<div><strong>Stadium III.</strong> Kontrollera om lastmomentet ryms inom snittets momentkapacitet '
    '<i>M</i><sub>Rd</sub> vid angiven normalkraft.</div>'
    '</div>'
)
_CC_HELP = "0 utelämnar lagret. Tomt fält använder c/c från tidigare antal."
_CC_HELP_HTML = (
    '<style>.anp-panel .anp-grid:has(> .anp-field .betongtvarsnitt-cc-help) '
    '{ align-items: start; }</style>'
    f'<span class="betongtvarsnitt-cc-help">{_CC_HELP}</span>'
)

_BT_SKISS_FALT = (
    "geometri", "b", "h", "c_nom", "phi_b", "phi_h",
    "c_nom_ok", "c_nom_uk", "n_ok", "phi_ok", "n_uk", "phi_uk", "s_ok", "s_uk", "c_nom_sida",
)
_BT_FIELDS = [
    _bt_choice("geometri", "Geometri", 2, [("Påle", 1), ("Balk", 2), ("Plattremsa", 3)]),
    _bt_choice("stadium", "Analysmodell", 2, [("Stadium II", 2), ("Stadium III", 3)], help_html=_STADIUM_HELP_HTML),
    _bt_field("b", "Bredd", "<i>b</i>", "mm", presentation_if={**_PALE, "label": "Pålsida"},
              visible_if={"field": "geometri", "not_equals": 3},
              fixed_if={**_PLATTA, "value": _PLATTREMSA_BREDD}),
    _bt_field("h", "Höjd", "<i>h</i>", "mm", visible_if=_BALK_PLATTA,
              presentation_if={**_PLATTA, "label": "Plattjocklek"}),
    _bt_field("c_nom", "Täckskikt", "<i>c</i><sub>nom</sub>", "mm", visible_if=_PALE),
    _bt_field("c_nom_ok", "Täckskikt ÖK", "<i>c</i><sub>nom,ÖK</sub>", "mm", visible_if=_BALK_PLATTA),
    _bt_field("c_nom_uk", "Täckskikt UK", "<i>c</i><sub>nom,UK</sub>", "mm", visible_if=_BALK_PLATTA),
    _bt_field("phi_b", "Bygeldiameter", "Ø<sub>b</sub>", "mm", visible_if={"field": "geometri", "in": [1, 2]}),
    _bt_field("phi_h", "Diameter för fyra hörnjärn", "Ø<sub>h</sub>", "mm", visible_if=_PALE),
    _bt_field("n_ok", "Antal järn", "", "st", type="int", visible_if=_BALK),
    _bt_field("phi_ok", "Stångdiameter", "Ø", "mm", visible_if=_BALK_PLATTA),
    _bt_field("n_uk", "Antal järn", "", "st", type="int", visible_if=_BALK),
    _bt_field("phi_uk", "Stångdiameter", "Ø", "mm", visible_if=_BALK_PLATTA),
    _bt_field("s_ok", "C/c-avstånd", "<i>s</i>", "mm", type="text", default="", visible_if=_PLATTA,
              help=_CC_HELP, help_html=_CC_HELP_HTML),
    _bt_field("s_uk", "C/c-avstånd", "<i>s</i>", "mm", type="text", default="", visible_if=_PLATTA,
              help=_CC_HELP, help_html=_CC_HELP_HTML),
    _bt_field("N_d", "Normalkraft", "<i>N</i><sub>d</sub>", "kN", help="Positiv i tryck. Laster avser hela bredden."),
    _bt_field("M", "Böjmoment", "<i>M</i>", "kNm", help="Positivt moment har trycksidan i ÖK. Laster avser hela bredden."),
    _bt_field("f_ck", "Karakteristisk betongtryckhållfasthet", "<i>f</i><sub>ck</sub>", "MPa", help="Högst 50 MPa."),
    _bt_field("f_cd", "Dimensionerande betongtryckhållfasthet", "<i>f</i><sub>cd</sub>", "MPa", visible_if=_ULTIMAT),
    _bt_field("E_cd", "Betongens elasticitetsmodul", "<i>E</i><sub>cd</sub>", "MPa", visible_if=_ELASTISK,
              help="Används som angiven i stadium II."),
    _bt_field("E_s", "Armeringens elasticitetsmodul", "<i>E</i><sub>s</sub>", "MPa"),
    _bt_field("f_yk", "Armeringens karakteristiska flytgräns", "<i>f</i><sub>yk</sub>", "MPa"),
    _bt_field("gamma_s", "Partialkoefficient för stål", "γ<sub>s</sub>", help="Flytgränsen i beräkningen är fyk / γs."),
    _bt_field("epsilon_c_lim_manuell", "Ange trycktöjningsgränsen manuellt", type="bool", default=False,
              widget="checkbox", visible_if=_ELASTISK),
    _bt_field("epsilon_c_lim_pm", "Manuell trycktöjningsgräns", "ε<sub>c,lim</sub>", "‰", default=15.2 / 33,
              visible_if={"all": [_ELASTISK, _MANUELL_TOJNING]}),
    _bt_field("sigma_c_lim_auto", "Automatisk spänningsnivå", type="bool", default=True, widget="checkbox",
              visible_if={"all": [_ELASTISK, _AUTO_TOJNING]}, help="0,4(fck + 8) MPa. Töjningsgränsen fås genom division med Ecd."),
    _bt_field("sigma_c_lim", "Spänningsnivå för varningsgräns", "σ<sub>c,lim</sub>", "MPa", default=15.2,
              visible_if={"all": [_ELASTISK, _AUTO_TOJNING, {"field": "sigma_c_lim_auto", "equals": False}]}),
    _bt_field("c_nom_sida", "Täckskikt sida", "<i>c</i><sub>nom,sida</sub>", "mm",
              type="text", default="", visible_if=_BALK, help="Till bygelns utsida. Tomt fält använder ett automatiskt sidomått."),
]
_BT_LAGER_KOLUMNER = ("sida", "phi", "mangd", "a_v")


def _bt_lagertabell(name, plate, visible_if):
    columns = [
        _bt_choice("sida", "Kant", "ok", [("ÖK", "ok"), ("UK", "uk")]),
        _bt_field("phi", "Diameter", "Ø", "mm", default=16.0),
        _bt_field("mangd", "C/c-avstånd" if plate else "Antal järn", "<i>s</i>" if plate else "",
                  "mm" if plate else "st", type="float" if plate else "int", default=0),
        _bt_field("a_v", "Fritt lageravstånd", "<i>a</i><sub>v</sub>", "mm", default=25.0),
    ]
    for column in columns:
        column["output"] = f"{name}_{column['name']}"
    return {"name": name, "type": "table", "label": "Extra lager från respektive kant",
            "add_label": "+ Lägg till lager", "visible_if": visible_if, "columns": columns,
            "default_rows": [{}], "outputs": [column["output"] for column in columns]}


_BT_LAGERTABELLER = [_bt_lagertabell("balk_lager", False, _BALK), _bt_lagertabell("plattremsa_lager", True, _PLATTA)]
_BT_LAGERTABELLNAMN = [table["name"] for table in _BT_LAGERTABELLER]
_BT_SKALAR_PX = tuple(field["name"] for field in _BT_FIELDS)
_BT_PANEL_PX_FORE_LAGER = tuple(name for name in _BT_SKALAR_PX if name != "c_nom_sida")
_BT_ALDRE_PANEL_PX = tuple(name for name in _BT_PANEL_PX_FORE_LAGER if name not in {"s_ok", "s_uk"})
_BT_PANEL_PX = (*_BT_SKALAR_PX, *(name for table in _BT_LAGERTABELLER for name in table["outputs"]))

betongtvarsnitt.panel_schema = {
    "title": "Betongtvärsnitt",
    "px": list(_BT_PANEL_PX),
    "fields": [*_BT_FIELDS, *_BT_LAGERTABELLER],
    "blocks": {"ID": {"rader": 40}, "DR": {"rader": 40}, "EKV": {"rader": 40}, "SR": {"rader": 40}},
    "sections": [
        {"title": "Indata", "collapsible": True, "collapsed": False, "columns": 1, "sections": [
            {"fields": ["geometri", "stadium"], "columns": 2},
            {"columns": 2, "sections": [
                {"columns": 1, "sections": [
                    {"title": "Geometri", "fields": ["b", "h"], "columns": 2},
                    {"title": "Täckskikt och diametrar", "fields": ["c_nom", "c_nom_ok", "c_nom_uk", "c_nom_sida", "phi_b", "phi_h"], "columns": 3},
                    {"title": "Längsarmering", "columns": 2, "sections": [
                        {"title": "Överkant", "fields": ["n_ok", "s_ok", "phi_ok"], "columns": 2},
                        {"title": "Underkant", "fields": ["n_uk", "s_uk", "phi_uk"], "columns": 2},
                    ]},
                    {"fields": ["balk_lager"]},
                    {"fields": ["plattremsa_lager"]},
                ]},
                {"figure": {"renderer": "an_calcs.betong._betongtvarsnitt_skiss:render",
                            "fields": list(_BT_SKISS_FALT), "tables": _BT_LAGERTABELLNAMN, "max_width": 480,
                            "caption": "Järnens placering i breddled visas schematiskt."}},
            ]},
            {"columns": 2, "sections": [
                {"title": "Laster", "fields": ["N_d", "M"], "columns": 2},
                {"title": "Material", "fields": ["f_ck", "f_cd", "E_cd", "E_s", "f_yk"], "columns": 2},
            ]},
            {"figure": {"renderer": "an_calcs.betong._betongtvarsnitt_profil:render",
                        "fields": list(_BT_SKALAR_PX), "tables": _BT_LAGERTABELLNAMN,
                        "full_width": True, "max_width": 820}},
        ]},
        {"title": "Beräkningsinställningar", "collapsible": True, "collapsed": True, "columns": 1, "sections": [
            {"title": "Stål", "fields": ["gamma_s"], "columns": 2},
            {"title": "Varningsgräns för stadium II", "columns": 2,
             "fields": ["epsilon_c_lim_manuell", "epsilon_c_lim_pm", "sigma_c_lim_auto", "sigma_c_lim"]},
        ]},
    ],
}
