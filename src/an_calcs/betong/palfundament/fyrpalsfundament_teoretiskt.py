"""Teoretisk geometri for 4-palsfundament innan slagning."""

from __future__ import annotations

import math

from .trepalsfundament_teoretiskt import (
    _angle_deg,
    _angle_to_horizontal_deg,
    _as_point,
    _distance,
    _ekvation,
    _least_squares,
    _post,
    _sub,
    _unit_vector,
)


BOTTOM_NODES = ("N5", "N6", "N7", "N8")
TOP_NODES = ("N1", "N2", "N3", "N4")
STRUTS = [("N1", "N5"), ("N2", "N6"), ("N3", "N7"), ("N4", "N8")]
TIES = [("N5", "N6"), ("N6", "N7"), ("N7", "N8"), ("N8", "N5")]
MEMBERS = STRUTS + TIES


def _build_bottom_nodes(d, cx, cy, theta_deg, h):
    if d <= 0:
        raise ValueError("d måste vara > 0.")
    if h <= 0:
        raise ValueError("h måste vara > 0.")

    half = d / 2.0
    theta = math.radians(theta_deg)
    c = math.cos(theta)
    s = math.sin(theta)
    local = {
        "N5": [-half, -half],
        "N6": [half, -half],
        "N7": [half, half],
        "N8": [-half, half],
    }

    nodes = {}
    for name, (x, y) in local.items():
        nodes[name] = [cx + c * x - s * y, cy + s * x + c * y, -h]
    return nodes


def _node_set_from_params(data, params):
    cx, cy, theta_deg, h = params
    nodes = {name: data[name] for name in TOP_NODES}
    nodes.update(_build_bottom_nodes(data["d"], cx, cy, theta_deg, h))
    return nodes


def _compute_angles(nodes):
    return {
        "a56": _angle_deg(_sub(nodes["N1"], nodes["N5"]), _sub(nodes["N6"], nodes["N5"])),
        "a58": _angle_deg(_sub(nodes["N1"], nodes["N5"]), _sub(nodes["N8"], nodes["N5"])),
        "a65": _angle_deg(_sub(nodes["N2"], nodes["N6"]), _sub(nodes["N5"], nodes["N6"])),
        "a67": _angle_deg(_sub(nodes["N2"], nodes["N6"]), _sub(nodes["N7"], nodes["N6"])),
        "a76": _angle_deg(_sub(nodes["N3"], nodes["N7"]), _sub(nodes["N6"], nodes["N7"])),
        "a78": _angle_deg(_sub(nodes["N3"], nodes["N7"]), _sub(nodes["N8"], nodes["N7"])),
        "a87": _angle_deg(_sub(nodes["N4"], nodes["N8"]), _sub(nodes["N7"], nodes["N8"])),
        "a85": _angle_deg(_sub(nodes["N4"], nodes["N8"]), _sub(nodes["N5"], nodes["N8"])),
    }


def _compute_strut_horizontal_angles(nodes):
    return {
        "alpha15": _angle_to_horizontal_deg(_sub(nodes["N1"], nodes["N5"])),
        "alpha26": _angle_to_horizontal_deg(_sub(nodes["N2"], nodes["N6"])),
        "alpha37": _angle_to_horizontal_deg(_sub(nodes["N3"], nodes["N7"])),
        "alpha48": _angle_to_horizontal_deg(_sub(nodes["N4"], nodes["N8"])),
    }


def _target_residuals(data, params):
    nodes = _node_set_from_params(data, params)
    angles = _compute_angles(nodes)
    return [angles[name] - data["alpha_target"] for name in ("a56", "a58", "a65", "a67", "a76", "a78", "a87", "a85")]


def _objective(data, params):
    if params[3] <= 0:
        return float("inf")
    try:
        residuals = _target_residuals(data, params)
    except ValueError:
        return float("inf")
    return sum(r * r for r in residuals)


def _initial_params(data):
    cx = sum(data[name][0] for name in TOP_NODES) / 4.0
    cy = sum(data[name][1] for name in TOP_NODES) / 4.0
    h0 = max(data["d"] * math.tan(math.radians(data["alpha_target"])) / 2.0, data["d"] * 0.25, 1.0)
    return [cx, cy, 0.0, h0]


def _nelder_mead(data, start, max_iter=800, tol=1e-8):
    n = len(start)
    scale = max(data["d"], max(abs(v) for name in TOP_NODES for v in data[name]), 1.0)
    steps = [0.25 * scale, 0.25 * scale, 10.0, 0.25 * scale]
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
        reflected[3] = max(reflected[3], 1e-9)
        reflected_value = _objective(data, reflected)

        if values[0] <= reflected_value < values[-2]:
            simplex[-1] = reflected
            values[-1] = reflected_value
            continue
        if reflected_value < values[0]:
            expanded = [centroid[j] + 2.0 * (reflected[j] - centroid[j]) for j in range(n)]
            expanded[3] = max(expanded[3], 1e-9)
            expanded_value = _objective(data, expanded)
            simplex[-1], values[-1] = (expanded, expanded_value) if expanded_value < reflected_value else (reflected, reflected_value)
            continue

        contracted = [centroid[j] + 0.5 * (worst[j] - centroid[j]) for j in range(n)]
        contracted[3] = max(contracted[3], 1e-9)
        contracted_value = _objective(data, contracted)
        if contracted_value < values[-1]:
            simplex[-1] = contracted
            values[-1] = contracted_value
            continue

        best = simplex[0]
        for i in range(1, n + 1):
            simplex[i] = [best[j] + 0.5 * (simplex[i][j] - best[j]) for j in range(n)]
            simplex[i][3] = max(simplex[i][3], 1e-9)
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
        if params[3] <= 0:
            return [1e6 + abs(params[3])] * 8
        return _target_residuals(data, list(params))

    result = least_squares(residuals, start, bounds=([-math.inf, -math.inf, -math.inf, 1e-9], math.inf))
    params = [float(value) for value in result.x]
    return params, "scipy.least_squares", sum(r * r for r in residuals(params))


def _parse_pile_loads(px):
    if "pile_loads" in px:
        value = px["pile_loads"]
    elif "Rz" in px:
        value = px["Rz"]
    elif any(name in px for name in ("Rz5", "Rz6", "Rz7", "Rz8")):
        value = {"N5": px.get("Rz5", 0.0), "N6": px.get("Rz6", 0.0), "N7": px.get("Rz7", 0.0), "N8": px.get("Rz8", 0.0)}
    else:
        return None

    if isinstance(value, dict):
        return {name: float(value.get(name, value.get(name.lower(), 0.0))) for name in BOTTOM_NODES}
    if isinstance(value, (list, tuple)):
        if len(value) != 4:
            raise ValueError("pile_loads måste innehålla fyra värden för N5, N6, N7 och N8.")
        return {name: float(value[i]) for i, name in enumerate(BOTTOM_NODES)}

    load = float(value)
    return {name: load for name in BOTTOM_NODES}


def _move_node(nodes, move_node, delta_x, delta_y):
    if move_node is None:
        return {name: point[:] for name, point in nodes.items()}
    if move_node not in BOTTOM_NODES:
        raise ValueError("move_node måste vara None, 'N5', 'N6', 'N7' eller 'N8'.")
    moved = {name: point[:] for name, point in nodes.items()}
    moved[move_node] = [moved[move_node][0] + delta_x, moved[move_node][1] + delta_y, moved[move_node][2]]
    return moved


def _translate_to_origin_xy(nodes, origin_node):
    if origin_node is None:
        return {name: point[:] for name, point in nodes.items()}, [0.0, 0.0, 0.0]
    if origin_node not in nodes:
        raise ValueError("origin_node måste vara en nod som finns i modellen.")

    shift = [-nodes[origin_node][0], -nodes[origin_node][1], 0.0]
    return (
        {
            name: [point[0] + shift[0], point[1] + shift[1], point[2]]
            for name, point in nodes.items()
        },
        shift,
    )


def _apply_xy_shift(nodes, shift):
    return {
        name: [point[0] + shift[0], point[1] + shift[1], point[2]]
        for name, point in nodes.items()
    }


def _origin_shift(nodes, original_nodes, origin_node, origin_mode):
    if origin_node is None:
        return [0.0, 0.0, 0.0]
    if origin_mode not in ("current", "original"):
        raise ValueError("origin_mode måste vara 'current' eller 'original'.")

    reference_nodes = original_nodes if origin_mode == "original" else nodes
    if origin_node not in reference_nodes:
        raise ValueError("origin_node måste vara en nod som finns i modellen.")
    return [-reference_nodes[origin_node][0], -reference_nodes[origin_node][1], 0.0]


def _solve_local_node(node, connected_nodes, rz):
    directions = [_unit_vector(node, other) for other in connected_nodes.values()]
    a = [
        [directions[0][0], directions[1][0], directions[2][0]],
        [directions[0][1], directions[1][1], directions[2][1]],
        [directions[0][2], directions[1][2], directions[2][2]],
    ]
    # Cramers regel via importerad 3-palsfunktion hade varit privat i privat; lös med least squares exakt 3x3.
    values, _, _ = _least_squares(a, [0.0, 0.0, -float(rz)])
    return dict(zip(connected_nodes.keys(), values))


def _local_equilibrium(nodes, pile_loads):
    if pile_loads is None:
        return None
    return {
        "N5": _solve_local_node(nodes["N5"], {"N1-N5": nodes["N1"], "N5-N6": nodes["N6"], "N5-N8": nodes["N8"]}, pile_loads["N5"]),
        "N6": _solve_local_node(nodes["N6"], {"N2-N6": nodes["N2"], "N6-N5": nodes["N5"], "N6-N7": nodes["N7"]}, pile_loads["N6"]),
        "N7": _solve_local_node(nodes["N7"], {"N3-N7": nodes["N3"], "N7-N6": nodes["N6"], "N7-N8": nodes["N8"]}, pile_loads["N7"]),
        "N8": _solve_local_node(nodes["N8"], {"N4-N8": nodes["N4"], "N8-N7": nodes["N7"], "N8-N5": nodes["N5"]}, pile_loads["N8"]),
    }


def _global_equilibrium(nodes, pile_loads):
    if pile_loads is None:
        return None

    unknowns = ["N15", "N26", "N37", "N48", "N56", "N67", "N78", "N85"]
    unknowns += [f"R{i}{axis}" for i in range(1, 5) for axis in ("x", "y", "z")]
    members = {
        "N15": ("N1", "N5"),
        "N26": ("N2", "N6"),
        "N37": ("N3", "N7"),
        "N48": ("N4", "N8"),
        "N56": ("N5", "N6"),
        "N67": ("N6", "N7"),
        "N78": ("N7", "N8"),
        "N85": ("N8", "N5"),
    }

    rows = []
    rhs = []
    for node in TOP_NODES + BOTTOM_NODES:
        for axis in range(3):
            row = [0.0] * len(unknowns)
            for force_name, (start, end) in members.items():
                idx = unknowns.index(force_name)
                if node == start:
                    row[idx] += _unit_vector(nodes[start], nodes[end])[axis]
                elif node == end:
                    row[idx] += _unit_vector(nodes[end], nodes[start])[axis]
            for i, top_node in enumerate(TOP_NODES, start=1):
                if node == top_node:
                    for axis_name, axis_index in (("x", 0), ("y", 1), ("z", 2)):
                        if axis == axis_index:
                            row[unknowns.index(f"R{i}{axis_name}")] = 1.0
            external = pile_loads[node] if node in pile_loads and axis == 2 else 0.0
            rows.append(row)
            rhs.append(-external)

    values, residual_norm, rank = _least_squares(rows, rhs)
    result = dict(zip(unknowns, values))
    return {
        "member_forces": {name: result[name] for name in ("N15", "N26", "N37", "N48", "N56", "N67", "N78", "N85")},
        "top_reactions": {name: result[name] for name in unknowns if name.startswith("R")},
        "rank": rank,
        "residual_norm": residual_norm,
    }


def _parse_px(px):
    if px is None:
        raise ValueError("px måste anges.")
    if not isinstance(px, dict):
        raise ValueError("4-pålsfunktionen förväntar px som dict.")

    direct_geometry = all(name in px for name in ("cx", "cy", "theta", "h"))
    d_value = px.get("d", px.get("d56"))
    required = ("N1", "N2", "N3", "N4") + (() if d_value is not None else ("d",)) + (() if direct_geometry else ("alpha_target",))
    missing = [name for name in required if name not in px]
    if missing:
        raise ValueError(f"px saknar värden: {', '.join(missing)}.")

    return {
        "N1": _as_point("N1", px["N1"]),
        "N2": _as_point("N2", px["N2"]),
        "N3": _as_point("N3", px["N3"]),
        "N4": _as_point("N4", px["N4"]),
        "d": float(d_value),
        "alpha_target": None if direct_geometry else float(px["alpha_target"]),
        "cx": float(px["cx"]) if direct_geometry else None,
        "cy": float(px["cy"]) if direct_geometry else None,
        "theta": float(px["theta"]) if direct_geometry else None,
        "h": float(px["h"]) if direct_geometry else None,
        "move_node": px.get("move_node"),
        "delta_x": float(px.get("delta_x", px.get("Delta_x", 0.0))),
        "delta_y": float(px.get("delta_y", px.get("Delta_y", 0.0))),
        "origin_node": px.get("origin_node"),
        "origin_mode": px.get("origin_mode", "current"),
        "pile_loads": _parse_pile_loads(px),
        "direct_geometry": direct_geometry,
    }


def fyrpalsfundament_teoretiskt_innan_slagning(px):
    """
    Beräknar teoretisk 3D-geometri, vinklar och valfria stavkrafter för ett
    4-pålsfundament innan slagning.

    Modellen är en geometrisk STM-/fackverksmodell:

        - N1, N2, N3 och N4 är övre noder.
        - N5, N6, N7 och N8 är nedre pålnoder.
        - Trycksträvor: N1-N5, N2-N6, N3-N7 och N4-N8.
        - Dragband: N5-N6, N6-N7, N7-N8 och N8-N5.

    Normal indata är fyra topnoder, centrumavståndet ``d`` mellan intilliggande
    pålar och målvinkeln ``alpha_target``. Bottennoderna antas ligga i en
    kvadratisk pålgrupp där alla sidavstånd är ``d``. Funktionen optimerar
    centrum, rotation och höjd så att vinklarna mellan varje trycksträva och
    respektive dragband hamnar nära ``alpha_target``.

    Parameterformat:
        px = {
            "N1": [x1, y1, z1],
            "N2": [x2, y2, z2],
            "N3": [x3, y3, z3],
            "N4": [x4, y4, z4],
            "d": cc_avstand_mellan_palar,
            "alpha_target": malvinkel,
        }

    Felslagning:
        ``move_node`` kan vara "N5", "N6", "N7" eller "N8".
        ``Delta_x``/``Delta_y`` anges i mm och appliceras efter att den
        teoretiska bottengeometrin tagits fram.

    Origo:
        ``origin_node`` kan anges för att flytta hela redovisningen i plan.
        ``origin_mode="current"`` placerar slutlig/felslagen nod i origo.
        ``origin_mode="original"`` placerar teoretiskt tilltänkt nod i origo.

    Pålaster:
        ``Rz`` anger samma uppåtriktade pålreaktion för alla fyra pålar.
        ``pile_loads`` kan användas för separata värden, till exempel
        ``{"N5": 900, "N6": 878, "N7": 1050, "N8": 950}``.

    Enhetskonvention:
        - koordinater, ``d`` och felslagning i mm
        - vinklar i grader
        - pålaster och stavkrafter i kN

    Returvärde:
        Standardiserad ``details``-dictionary med extra sektionerna
        ``geometri`` och ``krafter``. Använd tillsammans med
        ``print_palsfundament_resultat(details)`` och
        ``plot_palsfundament_3d(details)``.

    Exempel:
        >>> px = {
        ...     "N1": [0.0, 0.0, 0.0],
        ...     "N2": [200.0, 0.0, 0.0],
        ...     "N3": [200.0, 200.0, 0.0],
        ...     "N4": [0.0, 200.0, 0.0],
        ...     "d": 1200.0,
        ...     "alpha_target": 58.0,
        ...     "move_node": "N5",
        ...     "Delta_x": -50.0,
        ...     "Delta_y": 0.0,
        ...     "origin_node": "N5",
        ...     "origin_mode": "original",
        ...     "pile_loads": {"N5": 900.0, "N6": 878.0, "N7": 1050.0, "N8": 950.0},
        ... }
        >>> details = fyrpalsfundament_teoretiskt_innan_slagning(px)
    """
    data = _parse_px(px)
    if data["direct_geometry"]:
        params = [data["cx"], data["cy"], data["theta"], data["h"]]
        optimizer = "direkt geometri"
        opt_error = None
    else:
        if not (0 < data["alpha_target"] < 90):
            raise ValueError("alpha_target måste vara > 0 och < 90 grader.")
        params, optimizer, opt_error = _optimize_bottom_params(data)
        data["cx"], data["cy"], data["theta"], data["h"] = params

    original_nodes = _node_set_from_params(data, params)
    nodes = _move_node(original_nodes, data["move_node"], data["delta_x"], data["delta_y"])
    origin_shift = _origin_shift(nodes, original_nodes, data["origin_node"], data["origin_mode"])
    nodes = _apply_xy_shift(nodes, origin_shift)
    original_nodes = _apply_xy_shift(original_nodes, origin_shift)
    original_angles = _compute_angles(original_nodes)
    angles = _compute_angles(nodes)
    angle_deltas = {name: angles[name] - original_angles[name] for name in angles}
    strut_horizontal_angles = _compute_strut_horizontal_angles(nodes)
    lengths = {f"{a}{b}": _distance(nodes[a], nodes[b]) for a, b in MEMBERS}
    local_forces = _local_equilibrium(nodes, data["pile_loads"])
    global_forces = _global_equilibrium(nodes, data["pile_loads"])

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {"rubrik": "Beräkning", "text": "Funktionen bygger en idealiserad 4-pålsmodell med kvadratisk bottengeometri."},
                {"rubrik": "Begränsning", "text": "Modellen är geometrisk och dimensionerar inte betong, armering, pålar eller knutpunkter."},
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                *[_post(name, name, nodes[name], "mm", f"övre nod {name}") for name in TOP_NODES],
                _post("d", r"d", data["d"], "mm", "cc-avstånd mellan pålar"),
                _post("alpha_target", r"\alpha_{target}", data["alpha_target"], "deg", "målvinkel"),
                _post("move_node", r"N_{flytt}", data["move_node"], "", "felslagen nod"),
                _post("delta_x", r"\Delta x", data["delta_x"], "mm", "felslagning i x-led"),
                _post("delta_y", r"\Delta y", data["delta_y"], "mm", "felslagning i y-led"),
                _post("origin_node", r"N_{origo}", data["origin_node"], "", "nod som placeras i plan-origo"),
                _post("origin_mode", r"\mathrm{origo}", data["origin_mode"], "", "current = slutlig nod, original = teoretisk nod"),
                _post("pile_loads", r"R_z", data["pile_loads"], "kN", "uppåtriktade pålreaktioner"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                *[_post(name, name, nodes[name], "mm", f"nedre nod {name}") for name in BOTTOM_NODES],
                _post("cx", r"c_x", data["cx"], "mm", "beräknad centrumkoordinat x"),
                _post("cy", r"c_y", data["cy"], "mm", "beräknad centrumkoordinat y"),
                _post("theta", r"\theta", data["theta"], "deg", "beräknad rotation"),
                _post("h", r"h", data["h"], "mm", "beräknad höjd"),
                _post("optimizer", r"\mathrm{optimizer}", optimizer, "", "metod för bottengeometri"),
                _post("opt_error", r"e_{opt}", opt_error, "deg^2", "summerat kvadratiskt vinkelfel"),
                *[_post(name, name, value, "mm", f"stavlängd {name}") for name, value in lengths.items()],
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                *[_post(name, name, value, "deg", "vinkel mellan sträva och dragband") for name, value in angles.items()],
                *[_post(f"d{name}", rf"\Delta {name}", value, "deg", "vinkelförändring") for name, value in angle_deltas.items()],
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"\alpha = \arccos\left(\frac{\vec{u}\cdot\vec{v}}{|\vec{u}|\,|\vec{v}|}\right)", "vinkel mellan två vektorer"),
                _ekvation(r"\sum \vec{F}_{nod}=0", "lokal/global jämvikt"),
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
            "move_node": data["move_node"],
            "delta_x": data["delta_x"],
            "delta_y": data["delta_y"],
            "origin_node": data["origin_node"],
            "origin_mode": data["origin_mode"],
            "origin_shift": origin_shift,
            "alpha_target": data["alpha_target"],
            "optimizer": optimizer,
            "opt_error": opt_error,
        },
        "krafter": {
            "pile_loads": data["pile_loads"],
            "member_forces": local_forces,
            "global_equilibrium": global_forces,
            "sign_convention": "positiv = drag, negativ = tryck",
        },
    }


def plot_fyrpalsfundament_3d(details, title="4-pålsfundament - teoretiskt innan slagning"):
    """Skapar en Plotly-figur från details från 4-pålsfunktionen."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError("plot_fyrpalsfundament_3d kräver paketet plotly.") from exc

    geometri = details["geometri"]
    nodes = geometri["nodes"]
    original_nodes = geometri.get("original_nodes", nodes)
    angles = geometri["angles"]
    move_node = geometri.get("move_node")
    fig = go.Figure()

    for i, j in geometri["members"]:
        p, q = nodes[i], nodes[j]
        fig.add_trace(go.Scatter3d(x=[p[0], q[0]], y=[p[1], q[1]], z=[p[2], q[2]], mode="lines", line=dict(width=6), name=f"{i}-{j}"))

    for name, p in nodes.items():
        fig.add_trace(go.Scatter3d(x=[p[0]], y=[p[1]], z=[p[2]], mode="markers+text", marker=dict(size=6), text=[name], textposition="top center", showlegend=False))

    if move_node is not None:
        p0, p1 = original_nodes[move_node], nodes[move_node]
        fig.add_trace(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="markers+text", marker=dict(size=7, symbol="circle-open"), text=[f"{move_node}_orig"], textposition="top center", showlegend=False))
        fig.add_trace(go.Scatter3d(x=[p0[0], p1[0]], y=[p0[1], p1[1]], z=[p0[2], p1[2]], mode="lines", line=dict(width=4, dash="dash"), showlegend=False))

    angle_text = {
        "N5": f"a56={angles['a56']:.1f}°<br>a58={angles['a58']:.1f}°",
        "N6": f"a65={angles['a65']:.1f}°<br>a67={angles['a67']:.1f}°",
        "N7": f"a76={angles['a76']:.1f}°<br>a78={angles['a78']:.1f}°",
        "N8": f"a87={angles['a87']:.1f}°<br>a85={angles['a85']:.1f}°",
    }
    for name, text in angle_text.items():
        p = nodes[name]
        fig.add_trace(go.Scatter3d(x=[p[0]], y=[p[1]], z=[p[2]], mode="text", text=[text], textposition="bottom center", showlegend=False))

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
    plot_palsfundament_3d as plot_fyrpalsfundament_3d,
    print_palsfundament_resultat as print_fyrpalsfundament_resultat,
)
