"""Teoretisk geometri for 3-palsfundament innan slagning."""

from __future__ import annotations

import math


MEMBERS = [
    ("N1", "N4"),
    ("N3", "N5"),
    ("N2", "N6"),
    ("N4", "N5"),
    ("N5", "N6"),
    ("N4", "N6"),
]


def _post(namn, latex, value, unit="", etikett=""):
    return {
        "namn": namn,
        "latex": latex,
        "value": value,
        "unit": unit,
        "etikett": etikett,
    }


def _ekvation(latex, etikett):
    return {"latex": latex, "etikett": etikett}


def _as_point(name, value):
    if len(value) != 3:
        raise ValueError(f"{name} måste innehålla 3 koordinater [x, y, z].")
    return [float(value[0]), float(value[1]), float(value[2])]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _distance(a, b):
    v = _sub(a, b)
    return math.sqrt(sum(x * x for x in v))


def _unit_vector(a, b):
    v = _sub(b, a)
    length = math.sqrt(sum(x * x for x in v))
    if length <= 1e-12:
        raise ValueError("Två noder sammanfaller, riktning kan inte beräknas.")
    return [x / length for x in v]


def _angle_deg(v1, v2):
    n1 = math.sqrt(sum(x * x for x in v1))
    n2 = math.sqrt(sum(x * x for x in v2))
    if n1 == 0 or n2 == 0:
        raise ValueError("Vinkel kan inte beräknas för nollvektor.")
    c = sum(a * b for a, b in zip(v1, v2)) / (n1 * n2)
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


def _angle_to_horizontal_deg(v):
    horizontal = math.hypot(v[0], v[1])
    if horizontal <= 1e-12 and abs(v[2]) <= 1e-12:
        raise ValueError("Vinkel mot horisontalplan kan inte beräknas för nollvektor.")
    return math.degrees(math.atan2(abs(v[2]), horizontal))


def _build_bottom_nodes(d45, x_mid, y0, x6, y6, h):
    if d45 <= 0:
        raise ValueError("d45 måste vara > 0.")
    if h <= 0:
        raise ValueError("h måste vara > 0.")

    x4 = x_mid - d45 / 2.0
    x5 = x_mid + d45 / 2.0
    return {
        "N4": [x4, y0, -h],
        "N5": [x5, y0, -h],
        "N6": [x6, y6, -h],
    }


def _compute_angles(nodes):
    n1 = nodes["N1"]
    n2 = nodes["N2"]
    n3 = nodes["N3"]
    n4 = nodes["N4"]
    n5 = nodes["N5"]
    n6 = nodes["N6"]

    s4 = _sub(n1, n4)
    s5 = _sub(n3, n5)
    s6 = _sub(n2, n6)

    return {
        "a45": _angle_deg(s4, _sub(n5, n4)),
        "a46": _angle_deg(s4, _sub(n6, n4)),
        "a54": _angle_deg(s5, _sub(n4, n5)),
        "a56": _angle_deg(s5, _sub(n6, n5)),
        "a64": _angle_deg(s6, _sub(n4, n6)),
        "a65": _angle_deg(s6, _sub(n5, n6)),
    }


def _compute_strut_horizontal_angles(nodes):
    return {
        "alpha14": _angle_to_horizontal_deg(_sub(nodes["N1"], nodes["N4"])),
        "alpha35": _angle_to_horizontal_deg(_sub(nodes["N3"], nodes["N5"])),
        "alpha26": _angle_to_horizontal_deg(_sub(nodes["N2"], nodes["N6"])),
    }


def _det3(m):
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _solve3(a, b):
    det_a = _det3(a)
    if abs(det_a) <= 1e-12:
        raise ValueError("Nodjämvikt kan inte lösas eftersom riktningsmatrisen är singulär.")

    solution = []
    for col in range(3):
        m = [row[:] for row in a]
        for row in range(3):
            m[row][col] = b[row]
        solution.append(_det3(m) / det_a)
    return solution


def _solve_linear(a, b):
    n = len(b)
    m = [list(row) + [float(bi)] for row, bi in zip(a, b)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(m[row][col]))
        if abs(m[pivot][col]) <= 1e-12:
            raise ValueError("Linjärt ekvationssystem är singulärt.")
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]

        pivot_value = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= pivot_value

        for row in range(n):
            if row == col:
                continue
            factor = m[row][col]
            if factor == 0:
                continue
            for j in range(col, n + 1):
                m[row][j] -= factor * m[col][j]

    return [m[row][n] for row in range(n)]


def _rank(matrix, tol=1e-9):
    rows = [list(row) for row in matrix]
    if not rows:
        return 0

    n_rows = len(rows)
    n_cols = len(rows[0])
    rank = 0
    for col in range(n_cols):
        pivot = max(range(rank, n_rows), key=lambda row: abs(rows[row][col]))
        if abs(rows[pivot][col]) <= tol:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        pivot_value = rows[rank][col]
        for j in range(col, n_cols):
            rows[rank][j] /= pivot_value
        for row in range(n_rows):
            if row == rank:
                continue
            factor = rows[row][col]
            for j in range(col, n_cols):
                rows[row][j] -= factor * rows[rank][j]
        rank += 1
        if rank == n_rows:
            break
    return rank


def _least_squares(a, b):
    n_cols = len(a[0])
    ata = [[sum(row[i] * row[j] for row in a) for j in range(n_cols)] for i in range(n_cols)]
    atb = [sum(row[i] * bi for row, bi in zip(a, b)) for i in range(n_cols)]
    x = _solve_linear(ata, atb)
    residuals = [sum(row[i] * x[i] for i in range(n_cols)) - bi for row, bi in zip(a, b)]
    residual_norm = math.sqrt(sum(r * r for r in residuals))
    return x, residual_norm, _rank(a)


def _parse_pile_loads(px):
    if "pile_loads" in px:
        value = px["pile_loads"]
    elif "Rz" in px:
        value = px["Rz"]
    elif any(name in px for name in ("Rz4", "Rz5", "Rz6")):
        value = {
            "N4": px.get("Rz4", 0.0),
            "N5": px.get("Rz5", 0.0),
            "N6": px.get("Rz6", 0.0),
        }
    else:
        return None

    if isinstance(value, dict):
        return {name: float(value.get(name, value.get(name.lower(), 0.0))) for name in ("N4", "N5", "N6")}
    if isinstance(value, (list, tuple)):
        if len(value) != 3:
            raise ValueError("pile_loads måste innehålla tre värden för N4, N5 och N6.")
        return {"N4": float(value[0]), "N5": float(value[1]), "N6": float(value[2])}

    load = float(value)
    return {"N4": load, "N5": load, "N6": load}


def _nodjamvikt(node, connected_nodes, rz):
    directions = [_unit_vector(node, other) for other in connected_nodes.values()]
    a = [
        [directions[0][0], directions[1][0], directions[2][0]],
        [directions[0][1], directions[1][1], directions[2][1]],
        [directions[0][2], directions[1][2], directions[2][2]],
    ]
    # Positiv Rz ar uppatriktad palreaktion. Stavkrafter definieras positiva i drag.
    b = [0.0, 0.0, -float(rz)]
    return dict(zip(connected_nodes.keys(), _solve3(a, b)))


def _nodjamvikt_all_piles(nodes, pile_loads):
    if pile_loads is None:
        return None
    return {
        "N4": _nodjamvikt(
            nodes["N4"],
            {"N1-N4": nodes["N1"], "N4-N5": nodes["N5"], "N4-N6": nodes["N6"]},
            pile_loads["N4"],
        ),
        "N5": _nodjamvikt(
            nodes["N5"],
            {"N3-N5": nodes["N3"], "N5-N4": nodes["N4"], "N5-N6": nodes["N6"]},
            pile_loads["N5"],
        ),
        "N6": _nodjamvikt(
            nodes["N6"],
            {"N2-N6": nodes["N2"], "N6-N4": nodes["N4"], "N6-N5": nodes["N5"]},
            pile_loads["N6"],
        ),
    }


def _global_jamvikt(nodes, pile_loads):
    if pile_loads is None:
        return None

    unknowns = [
        "N14",
        "N35",
        "N26",
        "N45",
        "N56",
        "N46",
        "R1x",
        "R1y",
        "R1z",
        "R2x",
        "R2y",
        "R2z",
        "R3x",
        "R3y",
        "R3z",
    ]
    members = {
        "N14": ("N1", "N4"),
        "N35": ("N3", "N5"),
        "N26": ("N2", "N6"),
        "N45": ("N4", "N5"),
        "N56": ("N5", "N6"),
        "N46": ("N4", "N6"),
    }
    support_reactions = {
        "R1x": ("N1", 0),
        "R1y": ("N1", 1),
        "R1z": ("N1", 2),
        "R2x": ("N2", 0),
        "R2y": ("N2", 1),
        "R2z": ("N2", 2),
        "R3x": ("N3", 0),
        "R3y": ("N3", 1),
        "R3z": ("N3", 2),
    }

    rows = []
    rhs = []
    for node in ("N1", "N2", "N3", "N4", "N5", "N6"):
        for axis in range(3):
            row = [0.0] * len(unknowns)

            for force_name, (start, end) in members.items():
                idx = unknowns.index(force_name)
                if node == start:
                    row[idx] += _unit_vector(nodes[start], nodes[end])[axis]
                elif node == end:
                    row[idx] += _unit_vector(nodes[end], nodes[start])[axis]

            for reaction_name, (reaction_node, reaction_axis) in support_reactions.items():
                if node == reaction_node and axis == reaction_axis:
                    row[unknowns.index(reaction_name)] = 1.0

            external = 0.0
            if node in pile_loads and axis == 2:
                external = pile_loads[node]

            rows.append(row)
            rhs.append(-external)

    values, residual_norm, rank = _least_squares(rows, rhs)
    result = dict(zip(unknowns, values))
    return {
        "member_forces": {name: result[name] for name in ("N14", "N35", "N26", "N45", "N56", "N46")},
        "top_reactions": {name: result[name] for name in ("R1x", "R1y", "R1z", "R2x", "R2y", "R2z", "R3x", "R3y", "R3z")},
        "rank": rank,
        "residual_norm": residual_norm,
    }


def _move_node(nodes, move_node, delta_x, delta_y):
    if move_node is None:
        return {name: point[:] for name, point in nodes.items()}
    if move_node not in ("N4", "N5", "N6"):
        raise ValueError("move_node måste vara None, 'N4', 'N5' eller 'N6'.")

    moved = {name: point[:] for name, point in nodes.items()}
    moved[move_node] = [
        moved[move_node][0] + delta_x,
        moved[move_node][1] + delta_y,
        moved[move_node][2],
    ]
    return moved


def _node_set_from_params(data, params):
    x_mid, y0, x6, y6, h = params
    nodes = {
        "N1": data["N1"],
        "N2": data["N2"],
        "N3": data["N3"],
    }
    nodes.update(_build_bottom_nodes(data["d45"], x_mid, y0, x6, y6, h))
    return nodes


def _target_residuals(data, params):
    nodes = _node_set_from_params(data, params)
    angles = _compute_angles(nodes)
    return [angles[name] - data["alpha_target"] for name in ("a45", "a46", "a54", "a56", "a64", "a65")]


def _objective(data, params):
    if params[4] <= 0:
        return float("inf")
    try:
        residuals = _target_residuals(data, params)
    except ValueError:
        return float("inf")
    return sum(r * r for r in residuals)


def _initial_params(data):
    n1 = data["N1"]
    n2 = data["N2"]
    n3 = data["N3"]
    target_rad = math.radians(data["alpha_target"])
    h0 = max(data["d45"] * math.tan(target_rad) / 2.0, data["d45"] * 0.25, 1.0)
    return [
        (n1[0] + n3[0]) / 2.0,
        (n1[1] + n3[1]) / 2.0,
        n2[0],
        n2[1],
        h0,
    ]


def _nelder_mead(data, start, max_iter=900, tol=1e-8):
    n = len(start)
    scale = max(data["d45"], max(abs(v) for point in (data["N1"], data["N2"], data["N3"]) for v in point), 1.0)
    steps = [0.25 * scale, 0.25 * scale, 0.25 * scale, 0.25 * scale, 0.25 * scale]
    simplex = [start[:]]
    for i, step in enumerate(steps):
        point = start[:]
        point[i] += step
        simplex.append(point)

    values = [_objective(data, point) for point in simplex]

    for _ in range(max_iter):
        order = sorted(range(n + 1), key=lambda i: values[i])
        simplex = [simplex[i] for i in order]
        values = [values[i] for i in order]

        spread = max(abs(values[i] - values[0]) for i in range(1, n + 1))
        size = max(math.sqrt(sum((simplex[i][j] - simplex[0][j]) ** 2 for j in range(n))) for i in range(1, n + 1))
        if spread < tol and size < tol:
            break

        centroid = [sum(simplex[i][j] for i in range(n)) / n for j in range(n)]
        worst = simplex[-1]

        reflected = [centroid[j] + (centroid[j] - worst[j]) for j in range(n)]
        reflected[4] = max(reflected[4], 1e-9)
        reflected_value = _objective(data, reflected)

        if values[0] <= reflected_value < values[-2]:
            simplex[-1] = reflected
            values[-1] = reflected_value
            continue

        if reflected_value < values[0]:
            expanded = [centroid[j] + 2.0 * (reflected[j] - centroid[j]) for j in range(n)]
            expanded[4] = max(expanded[4], 1e-9)
            expanded_value = _objective(data, expanded)
            if expanded_value < reflected_value:
                simplex[-1] = expanded
                values[-1] = expanded_value
            else:
                simplex[-1] = reflected
                values[-1] = reflected_value
            continue

        contracted = [centroid[j] + 0.5 * (worst[j] - centroid[j]) for j in range(n)]
        contracted[4] = max(contracted[4], 1e-9)
        contracted_value = _objective(data, contracted)
        if contracted_value < values[-1]:
            simplex[-1] = contracted
            values[-1] = contracted_value
            continue

        best = simplex[0]
        for i in range(1, n + 1):
            simplex[i] = [best[j] + 0.5 * (simplex[i][j] - best[j]) for j in range(n)]
            simplex[i][4] = max(simplex[i][4], 1e-9)
            values[i] = _objective(data, simplex[i])

    best_i = min(range(n + 1), key=lambda i: values[i])
    return simplex[best_i], values[best_i]


def _optimize_bottom_params(data):
    start = _initial_params(data)

    try:
        from scipy.optimize import least_squares
    except ImportError:
        params, error = _nelder_mead(data, start)
        return params, "nelder-mead", error

    def residuals(params):
        if params[4] <= 0:
            return [1e6 + abs(params[4])] * 6
        return _target_residuals(data, list(params))

    result = least_squares(residuals, start, bounds=([-math.inf, -math.inf, -math.inf, -math.inf, 1e-9], math.inf))
    params = [float(value) for value in result.x]
    return params, "scipy.least_squares", sum(r * r for r in residuals(params))


def _parse_px(px):
    if px is None:
        raise ValueError("px måste anges.")

    if isinstance(px, dict):
        direct_geometry = all(name in px for name in ("x_mid", "y0", "x6", "y6", "h"))
        required = ("N1", "N2", "N3", "d45") + (() if direct_geometry else ("alpha_target",))
        missing = [name for name in required if name not in px]
        if missing:
            raise ValueError(f"px saknar värden: {', '.join(missing)}.")
        return {
            "N1": _as_point("N1", px["N1"]),
            "N2": _as_point("N2", px["N2"]),
            "N3": _as_point("N3", px["N3"]),
            "d45": float(px["d45"]),
            "alpha_target": None if direct_geometry else float(px["alpha_target"]),
            "x_mid": float(px["x_mid"]) if direct_geometry else None,
            "y0": float(px["y0"]) if direct_geometry else None,
            "x6": float(px["x6"]) if direct_geometry else None,
            "y6": float(px["y6"]) if direct_geometry else None,
            "h": float(px["h"]) if direct_geometry else None,
            "move_node": px.get("move_node"),
            "delta_x": float(px.get("delta_x", px.get("Delta_x", 0.0))),
            "delta_y": float(px.get("delta_y", px.get("Delta_y", 0.0))),
            "pile_loads": _parse_pile_loads(px),
            "direct_geometry": direct_geometry,
        }

    if len(px) in (5, 8):
        n1, n2, n3, d45, alpha_target = px[:5]
        move_node, delta_x, delta_y = (None, 0.0, 0.0) if len(px) == 5 else px[5:8]
        return {
            "N1": _as_point("N1", n1),
            "N2": _as_point("N2", n2),
            "N3": _as_point("N3", n3),
            "d45": float(d45),
            "alpha_target": float(alpha_target),
            "x_mid": None,
            "y0": None,
            "x6": None,
            "y6": None,
            "h": None,
            "move_node": move_node,
            "delta_x": float(delta_x),
            "delta_y": float(delta_y),
            "pile_loads": None,
            "direct_geometry": False,
        }

    if len(px) not in (9, 12):
        raise ValueError(
            "px måste innehålla 5, 8, 9 eller 12 värden: "
            "[N1, N2, N3, d45, alpha_target], "
            "[N1, N2, N3, d45, alpha_target, move_node, delta_x, delta_y], "
            "[N1, N2, N3, d45, x_mid, y0, x6, y6, h] eller "
            "[N1, N2, N3, d45, x_mid, y0, x6, y6, h, move_node, delta_x, delta_y]."
        )

    n1, n2, n3, d45, x_mid, y0, x6, y6, h = px[:9]
    move_node, delta_x, delta_y = (None, 0.0, 0.0) if len(px) == 9 else px[9:12]
    return {
        "N1": _as_point("N1", n1),
        "N2": _as_point("N2", n2),
        "N3": _as_point("N3", n3),
        "d45": float(d45),
        "alpha_target": None,
        "x_mid": float(x_mid),
        "y0": float(y0),
        "x6": float(x6),
        "y6": float(y6),
        "h": float(h),
        "move_node": move_node,
        "delta_x": float(delta_x),
        "delta_y": float(delta_y),
        "pile_loads": None,
        "direct_geometry": True,
    }


def trepalsfundament_teoretiskt_innan_slagning(px):
    """
    Beräknar teoretisk 3D-geometri och nodvinklar for ett 3-palsfundament
    innan slagning, med valfri felslagning av en nedre nod.

    Modellen är en geometrisk STM-/fackverksmodell med tre övre noder och tre
    nedre noder:

        - N1, N2 och N3 är övre noder.
        - N4, N5 och N6 är nedre pål-/dragbandsnoder.
        - Stavar skapas mellan N1-N4, N3-N5, N2-N6, N4-N5, N5-N6 och N4-N6.

    Normal indata är de tre övre noderna, målvinkeln ``alpha_target`` och det
    kända avståndet ``d45`` mellan N4 och N5. Funktionen optimerar då
    bottennoderna så att de sex nodvinklarna hamnar så nära målvinkeln som
    möjligt. N4 och N5 byggs symmetriskt kring en optimerad ``x_mid`` med
    avståndet ``d45`` mellan noderna. N4, N5 och N6 placeras i samma
    bottenplan ``z = -h``.

    Funktionen beräknar vinklarna mellan respektive trycksträva och dragbanden
    i bottenplanet:

        - a45 och a46 vid N4
        - a54 och a56 vid N5
        - a64 och a65 vid N6

    Om ``move_node`` anges flyttas vald nedre nod efter att den teoretiska
    geometrin byggts. ``delta_x`` och ``delta_y`` appliceras bara på vald nod.
    Ursprunglig geometri sparas i ``details["geometri"]["original_nodes"]``.
    Vinkelförändringar relativt ursprungsgeometrin sparas som ``angle_deltas``.

    Rekommenderat parameterformat utan felslagning:
        px = [N1, N2, N3, d45, alpha_target]

    Rekommenderat parameterformat med felslagning:
        px = [N1, N2, N3, d45, alpha_target, move_node, delta_x, delta_y]

    Alternativt kan px vara en dict:
        px = {
            "N1": [x1, y1, z1],
            "N2": [x2, y2, z2],
            "N3": [x3, y3, z3],
            "d45": avstand_mellan_N4_och_N5,
            "alpha_target": malvinkel,
            "move_node": "N4",
            "Delta_x": -100.0,
            "Delta_y": 0.0,
            "pile_loads": {"N4": Rz4, "N5": Rz5, "N6": Rz6},
        }

    Pålasterna är valfria. Om de anges beräknas lokal nodjämvikt i N4, N5
    och N6. ``Rz`` kan anges som en gemensam uppåtriktad pålreaktion för alla
    tre pålar, eller ``pile_loads`` som dict/lista med separata värden.
    Krafttecken: positiv normalkraft = drag, negativ normalkraft = tryck.

    Äldre direktgeometriformat stöds fortfarande:
        px = [N1, N2, N3, d45, x_mid, y0, x6, y6, h]

    Äldre direktgeometriformat med felslagning:
        px = [N1, N2, N3, d45, x_mid, y0, x6, y6, h, move_node, delta_x, delta_y]

    ``move_node`` kan vara "N4", "N5" eller "N6". ``delta_x``/``Delta_x``
    och ``delta_y``/``Delta_y`` anges i mm.

    Enhetskonvention:
        - koordinater och avstånd i mm
        - vinklar i grader
        - pålaster och stavkrafter i kN

    Returvärde:
        dict
            Standardiserad details-dictionary med extra sektionen ``geometri``,
            avsedd att skickas vidare till ``plot_trepalsfundament_3d``.

    Exempel:
        >>> px = {
        ...     "N1": [0.0, 0.0, 0.0],
        ...     "N2": [1000.0, 2000.0, 0.0],
        ...     "N3": [2000.0, 0.0, 0.0],
        ...     "d45": 1080.0,
        ...     "alpha_target": 58.0,
        ...     "move_node": "N4",
        ...     "Delta_x": -100.0,
        ...     "Delta_y": 0.0,
        ...     "Rz": 1000.0,
        ... }
        >>> details = trepalsfundament_teoretiskt_innan_slagning(px)
        >>> fig = plot_trepalsfundament_3d(details)
        >>> fig.show()
    """
    data = _parse_px(px)

    if data["direct_geometry"]:
        params = [data["x_mid"], data["y0"], data["x6"], data["y6"], data["h"]]
        optimizer = "direkt geometri"
        opt_error = None
    else:
        if not (0 < data["alpha_target"] < 90):
            raise ValueError("alpha_target måste vara > 0 och < 90 grader.")
        params, optimizer, opt_error = _optimize_bottom_params(data)
        data["x_mid"], data["y0"], data["x6"], data["y6"], data["h"] = params

    original_nodes = _node_set_from_params(data, params)

    nodes = _move_node(original_nodes, data["move_node"], data["delta_x"], data["delta_y"])
    original_angles = _compute_angles(original_nodes)
    angles = _compute_angles(nodes)
    strut_horizontal_angles = _compute_strut_horizontal_angles(nodes)
    angle_deltas = {name: angles[name] - original_angles[name] for name in angles}
    lengths = {f"{a}{b}": _distance(nodes[a], nodes[b]) for a, b in MEMBERS}
    original_lengths = {f"{a}{b}": _distance(original_nodes[a], original_nodes[b]) for a, b in MEMBERS}
    forces = _nodjamvikt_all_piles(nodes, data["pile_loads"])
    global_forces = _global_jamvikt(nodes, data["pile_loads"])

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Funktionen bygger en idealiserad 3D-modell av ett "
                        "3-pålsfundament med tre övre noder, tre nedre "
                        "pål-/dragbandsnoder och sex stavar."
                    ),
                },
                {
                    "rubrik": "Vinkeldefinition",
                    "text": (
                        "Vinklarna beräknas mellan trycksträvan från respektive "
                        "övre nod och dragbanden i bottenplanet."
                    ),
                },
                {
                    "rubrik": "Begränsning",
                    "text": (
                        "Modellen är geometrisk. Den dimensionerar inte betong, "
                        "armering, pålar eller knutpunkter."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("N1", r"N_1", nodes["N1"], "mm", "övre nod 1"),
                _post("N2", r"N_2", nodes["N2"], "mm", "övre nod 2"),
                _post("N3", r"N_3", nodes["N3"], "mm", "övre nod 3"),
                _post("d45", r"d_{45}", data["d45"], "mm", "låst avstånd mellan N4 och N5"),
                _post("alpha_target", r"\alpha_{target}", data["alpha_target"], "deg", "målvinkel"),
                _post("move_node", r"N_{flytt}", data["move_node"], "", "felslagen nod"),
                _post("delta_x", r"\Delta x", data["delta_x"], "mm", "felslagning i x-led"),
                _post("delta_y", r"\Delta y", data["delta_y"], "mm", "felslagning i y-led"),
                _post("pile_loads", r"R_z", data["pile_loads"], "kN", "uppåtriktade pålreaktioner"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("N4", r"N_4", nodes["N4"], "mm", "nedre nod 4"),
                _post("N5", r"N_5", nodes["N5"], "mm", "nedre nod 5"),
                _post("N6", r"N_6", nodes["N6"], "mm", "nedre nod 6"),
                _post("N4_orig", r"N_{4,orig}", original_nodes["N4"], "mm", "ursprunglig nedre nod 4"),
                _post("N5_orig", r"N_{5,orig}", original_nodes["N5"], "mm", "ursprunglig nedre nod 5"),
                _post("N6_orig", r"N_{6,orig}", original_nodes["N6"], "mm", "ursprunglig nedre nod 6"),
                _post("x_mid", r"x_{mid}", data["x_mid"], "mm", "beräknad mittkoordinat för N4-N5"),
                _post("y0", r"y_0", data["y0"], "mm", "beräknad y-koordinat för N4 och N5"),
                _post("x6", r"x_6", data["x6"], "mm", "beräknad x-koordinat för N6"),
                _post("y6", r"y_6", data["y6"], "mm", "beräknad y-koordinat för N6"),
                _post("h", r"h", data["h"], "mm", "beräknat djup till bottenplanet"),
                _post("optimizer", r"\mathrm{optimizer}", optimizer, "", "metod för bottengeometri"),
                _post("opt_error", r"e_{opt}", opt_error, "deg^2", "summerat kvadratiskt vinkelfel"),
                *[
                    _post(name, name, value, "mm", f"stavlängd {name}")
                    for name, value in lengths.items()
                ],
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("a45", r"\alpha_{45}", angles["a45"], "deg", "vinkel vid N4 mot N5"),
                _post("a46", r"\alpha_{46}", angles["a46"], "deg", "vinkel vid N4 mot N6"),
                _post("a54", r"\alpha_{54}", angles["a54"], "deg", "vinkel vid N5 mot N4"),
                _post("a56", r"\alpha_{56}", angles["a56"], "deg", "vinkel vid N5 mot N6"),
                _post("a64", r"\alpha_{64}", angles["a64"], "deg", "vinkel vid N6 mot N4"),
                _post("a65", r"\alpha_{65}", angles["a65"], "deg", "vinkel vid N6 mot N5"),
                _post("alpha14", r"\alpha_{14}", strut_horizontal_angles["alpha14"], "deg", "sträva N1-N4 mot horisontalplan"),
                _post("alpha35", r"\alpha_{35}", strut_horizontal_angles["alpha35"], "deg", "sträva N3-N5 mot horisontalplan"),
                _post("alpha26", r"\alpha_{26}", strut_horizontal_angles["alpha26"], "deg", "sträva N2-N6 mot horisontalplan"),
                _post("da45", r"\Delta\alpha_{45}", angle_deltas["a45"], "deg", "vinkelförändring a45"),
                _post("da46", r"\Delta\alpha_{46}", angle_deltas["a46"], "deg", "vinkelförändring a46"),
                _post("da54", r"\Delta\alpha_{54}", angle_deltas["a54"], "deg", "vinkelförändring a54"),
                _post("da56", r"\Delta\alpha_{56}", angle_deltas["a56"], "deg", "vinkelförändring a56"),
                _post("da64", r"\Delta\alpha_{64}", angle_deltas["a64"], "deg", "vinkelförändring a64"),
                _post("da65", r"\Delta\alpha_{65}", angle_deltas["a65"], "deg", "vinkelförändring a65"),
                *(
                    []
                    if forces is None
                    else [
                        _post("N1-N4", r"N_{14}", forces["N4"]["N1-N4"], "kN", "trycksträva N1-N4, positiv = drag"),
                        _post("N3-N5", r"N_{35}", forces["N5"]["N3-N5"], "kN", "trycksträva N3-N5, positiv = drag"),
                        _post("N2-N6", r"N_{26}", forces["N6"]["N2-N6"], "kN", "trycksträva N2-N6, positiv = drag"),
                        _post("N4-N5_vid_N4", r"N_{45,N4}", forces["N4"]["N4-N5"], "kN", "dragband N4-N5 från jämvikt i N4"),
                        _post("N4-N6_vid_N4", r"N_{46,N4}", forces["N4"]["N4-N6"], "kN", "dragband N4-N6 från jämvikt i N4"),
                        _post("N5-N4_vid_N5", r"N_{54,N5}", forces["N5"]["N5-N4"], "kN", "dragband N5-N4 från jämvikt i N5"),
                        _post("N5-N6_vid_N5", r"N_{56,N5}", forces["N5"]["N5-N6"], "kN", "dragband N5-N6 från jämvikt i N5"),
                        _post("N6-N4_vid_N6", r"N_{64,N6}", forces["N6"]["N6-N4"], "kN", "dragband N6-N4 från jämvikt i N6"),
                        _post("N6-N5_vid_N6", r"N_{65,N6}", forces["N6"]["N6-N5"], "kN", "dragband N6-N5 från jämvikt i N6"),
                    ]
                ),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(
                    r"\alpha = \arccos\left(\frac{\vec{u}\cdot\vec{v}}{|\vec{u}|\,|\vec{v}|}\right)",
                    "vinkel mellan två vektorer",
                ),
                _ekvation(r"N_4=(x_{mid}-d_{45}/2,\ y_0,\ -h)", "nedre nod N4"),
                _ekvation(r"N_5=(x_{mid}+d_{45}/2,\ y_0,\ -h)", "nedre nod N5"),
                _ekvation(r"N_6=(x_6,\ y_6,\ -h)", "nedre nod N6"),
                _ekvation(r"\sum \vec{F}_{nod}=0", "lokal nodjämvikt i pålnod"),
            ],
        },
        "geometri": {
            "nodes": nodes,
            "original_nodes": original_nodes,
            "members": [list(member) for member in MEMBERS],
            "angles": angles,
            "original_angles": original_angles,
            "strut_horizontal_angles": strut_horizontal_angles,
            "angle_deltas": angle_deltas,
            "lengths": lengths,
            "original_lengths": original_lengths,
            "move_node": data["move_node"],
            "delta_x": data["delta_x"],
            "delta_y": data["delta_y"],
            "alpha_target": data["alpha_target"],
            "optimizer": optimizer,
            "opt_error": opt_error,
        },
        "krafter": {
            "pile_loads": data["pile_loads"],
            "member_forces": forces,
            "global_equilibrium": global_forces,
            "sign_convention": "positiv = drag, negativ = tryck",
        },
    }


def plot_trepalsfundament_3d(details, title="3-pålsfundament - teoretiskt innan slagning"):
    """Skapar en Plotly-figur från details från huvudfunktionen."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError("plot_trepalsfundament_3d kräver paketet plotly.") from exc

    geometri = details["geometri"]
    nodes = geometri["nodes"]
    original_nodes = geometri.get("original_nodes", nodes)
    members = geometri["members"]
    angles = geometri["angles"]
    angle_deltas = geometri.get("angle_deltas", {})
    move_node = geometri.get("move_node")
    delta_x = geometri.get("delta_x", 0.0)
    delta_y = geometri.get("delta_y", 0.0)

    if move_node is not None and title == "3-pålsfundament - teoretiskt innan slagning":
        title = f"3-pålsfundament - efter felslagning ({move_node}, dx={delta_x:g} mm, dy={delta_y:g} mm)"

    fig = go.Figure()

    for i, j in members:
        p = nodes[i]
        q = nodes[j]
        fig.add_trace(
            go.Scatter3d(
                x=[p[0], q[0]],
                y=[p[1], q[1]],
                z=[p[2], q[2]],
                mode="lines",
                line=dict(width=6),
                name=f"{i}-{j}",
            )
        )

    for name, p in nodes.items():
        fig.add_trace(
            go.Scatter3d(
                x=[p[0]],
                y=[p[1]],
                z=[p[2]],
                mode="markers+text",
                marker=dict(size=6),
                text=[name],
                textposition="top center",
                showlegend=False,
            )
        )

    if move_node is not None:
        p0 = original_nodes[move_node]
        p1 = nodes[move_node]
        fig.add_trace(
            go.Scatter3d(
                x=[p0[0]],
                y=[p0[1]],
                z=[p0[2]],
                mode="markers+text",
                marker=dict(size=7, symbol="circle-open"),
                text=[f"{move_node}_orig"],
                textposition="top center",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter3d(
                x=[p0[0], p1[0]],
                y=[p0[1], p1[1]],
                z=[p0[2], p1[2]],
                mode="lines",
                line=dict(width=4, dash="dash"),
                name=f"{move_node} felslagning",
                showlegend=False,
            )
        )

    angle_text = {
        "N4": f"a45={angles['a45']:.1f}°<br>a46={angles['a46']:.1f}°",
        "N5": f"a54={angles['a54']:.1f}°<br>a56={angles['a56']:.1f}°",
        "N6": f"a64={angles['a64']:.1f}°<br>a65={angles['a65']:.1f}°",
    }
    if move_node is not None and angle_deltas:
        angle_text = {
            "N4": (
                f"a45={angles['a45']:.1f}° ({angle_deltas['a45']:+.1f})<br>"
                f"a46={angles['a46']:.1f}° ({angle_deltas['a46']:+.1f})"
            ),
            "N5": (
                f"a54={angles['a54']:.1f}° ({angle_deltas['a54']:+.1f})<br>"
                f"a56={angles['a56']:.1f}° ({angle_deltas['a56']:+.1f})"
            ),
            "N6": (
                f"a64={angles['a64']:.1f}° ({angle_deltas['a64']:+.1f})<br>"
                f"a65={angles['a65']:.1f}° ({angle_deltas['a65']:+.1f})"
            ),
        }
    for name, text in angle_text.items():
        p = nodes[name]
        fig.add_trace(
            go.Scatter3d(
                x=[p[0]],
                y=[p[1]],
                z=[p[2]],
                mode="text",
                text=[text],
                textposition="bottom center",
                showlegend=False,
            )
        )

    fig.update_layout(
        title=title,
        height=700,
        scene=dict(
            aspectmode="data",
            xaxis=dict(title="X [mm]", showticklabels=False, showgrid=True, gridcolor="black", showbackground=False),
            yaxis=dict(title="Y [mm]", showticklabels=False, showgrid=True, gridcolor="black", showbackground=False),
            zaxis=dict(title="Z [mm]", showticklabels=False, showgrid=True, gridcolor="black", showbackground=False),
        ),
    )

    return fig


from .palsfundament import (
    plot_palsfundament_3d as plot_trepalsfundament_3d,
    print_palsfundament_resultat as print_trepalsfundament_resultat,
)
