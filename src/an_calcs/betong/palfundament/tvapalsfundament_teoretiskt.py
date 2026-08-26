"""Teoretisk geometri for 2-palsfundament innan slagning."""

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
    _rank,
    _sub,
    _unit_vector,
)


TOP_NODES = ("N1", "N2")
BOTTOM_NODES = ("N3", "N4")
STRUTS = [("N1", "N3"), ("N2", "N4")]
TIES = [("N3", "N4")]
MEMBERS = STRUTS + TIES


def _build_bottom_nodes(data):
    d = data["d"]
    if d <= 0:
        raise ValueError("d måste vara > 0.")
    if not (0 < data["alpha_target"] < 90):
        raise ValueError("alpha_target måste vara > 0 och < 90 grader.")

    n1 = data["N1"]
    n2 = data["N2"]
    vx = n2[0] - n1[0]
    vy = n2[1] - n1[1]
    top_cc = math.hypot(vx, vy)
    if top_cc <= 1e-12:
        ex, ey = 1.0, 0.0
    else:
        ex, ey = vx / top_cc, vy / top_cc

    if d <= top_cc:
        raise ValueError("d måste vara större än horisontellt avstånd mellan N1 och N2 för alpha_target < 90 grader.")

    cx = (n1[0] + n2[0]) / 2.0
    cy = (n1[1] + n2[1]) / 2.0
    half = d / 2.0
    horizontal_offset = (d - top_cc) / 2.0
    h = horizontal_offset * math.tan(math.radians(data["alpha_target"]))

    return {
        "N3": [cx - ex * half, cy - ey * half, -h],
        "N4": [cx + ex * half, cy + ey * half, -h],
    }, {
        "cx": cx,
        "cy": cy,
        "theta": math.degrees(math.atan2(ey, ex)),
        "h": h,
        "top_cc": top_cc,
    }


def _compute_angles(nodes):
    return {
        "a34": _angle_deg(_sub(nodes["N1"], nodes["N3"]), _sub(nodes["N4"], nodes["N3"])),
        "a43": _angle_deg(_sub(nodes["N2"], nodes["N4"]), _sub(nodes["N3"], nodes["N4"])),
    }


def _compute_strut_horizontal_angles(nodes):
    return {
        "alpha13": _angle_to_horizontal_deg(_sub(nodes["N1"], nodes["N3"])),
        "alpha24": _angle_to_horizontal_deg(_sub(nodes["N2"], nodes["N4"])),
    }


def _parse_pile_loads(px):
    if "pile_loads" in px:
        value = px["pile_loads"]
    elif "Rz" in px:
        value = px["Rz"]
    elif any(name in px for name in ("Rz3", "Rz4")):
        value = {"N3": px.get("Rz3", 0.0), "N4": px.get("Rz4", 0.0)}
    else:
        return None

    if isinstance(value, dict):
        return {name: float(value.get(name, value.get(name.lower(), 0.0))) for name in BOTTOM_NODES}
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError("pile_loads måste innehålla två värden för N3 och N4.")
        return {"N3": float(value[0]), "N4": float(value[1])}

    load = float(value)
    return {"N3": load, "N4": load}


def _move_node(nodes, move_node, delta_x, delta_y):
    if move_node is None:
        return {name: point[:] for name, point in nodes.items()}
    if move_node not in BOTTOM_NODES:
        raise ValueError("move_node måste vara None, 'N3' eller 'N4'.")
    moved = {name: point[:] for name, point in nodes.items()}
    moved[move_node] = [moved[move_node][0] + delta_x, moved[move_node][1] + delta_y, moved[move_node][2]]
    return moved


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
        [direction[0] for direction in directions],
        [direction[1] for direction in directions],
        [direction[2] for direction in directions],
    ]
    values, residual_norm, rank = _least_squares(a, [0.0, 0.0, -float(rz)])
    return {
        "forces": dict(zip(connected_nodes.keys(), values)),
        "rank": rank,
        "residual_norm": residual_norm,
    }


def _local_equilibrium(nodes, pile_loads):
    if pile_loads is None:
        return None
    return {
        "N3": _solve_local_node(nodes["N3"], {"N1-N3": nodes["N1"], "N3-N4": nodes["N4"]}, pile_loads["N3"])["forces"],
        "N4": _solve_local_node(nodes["N4"], {"N2-N4": nodes["N2"], "N4-N3": nodes["N3"]}, pile_loads["N4"])["forces"],
    }


def _global_equilibrium(nodes, pile_loads):
    if pile_loads is None:
        return None

    unknowns = ["N13", "N24", "N34", "R1x", "R1y", "R1z", "R2x", "R2y", "R2z"]
    members = {
        "N13": ("N1", "N3"),
        "N24": ("N2", "N4"),
        "N34": ("N3", "N4"),
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
        "member_forces": {name: result[name] for name in ("N13", "N24", "N34")},
        "top_reactions": {name: result[name] for name in unknowns if name.startswith("R")},
        "rank": rank,
        "residual_norm": residual_norm,
    }


def _parse_px(px):
    if px is None:
        raise ValueError("px måste anges.")
    if not isinstance(px, dict):
        raise ValueError("2-pålsfunktionen förväntar px som dict.")

    required = ("N1", "N2", "d", "alpha_target")
    missing = [name for name in required if name not in px]
    if missing:
        raise ValueError(f"px saknar värden: {', '.join(missing)}.")

    return {
        "N1": _as_point("N1", px["N1"]),
        "N2": _as_point("N2", px["N2"]),
        "d": float(px["d"]),
        "alpha_target": float(px["alpha_target"]),
        "move_node": px.get("move_node"),
        "delta_x": float(px.get("delta_x", px.get("Delta_x", 0.0))),
        "delta_y": float(px.get("delta_y", px.get("Delta_y", 0.0))),
        "origin_node": px.get("origin_node"),
        "origin_mode": px.get("origin_mode", "current"),
        "pile_loads": _parse_pile_loads(px),
    }


def tvapalsfundament_teoretiskt_innan_slagning(px):
    """
    Beräknar teoretisk 3D-geometri, vinklar och valfria stavkrafter för ett
    2-pålsfundament innan slagning.

    Modellen har två topnoder ``N1`` och ``N2`` samt två pålnoder ``N3`` och
    ``N4``. Trycksträvorna är ``N1-N3`` och ``N2-N4``. Dragbandet är
    ``N3-N4``.

    Indata är topnoderna, centrumavståndet ``d`` mellan pålarna och målvinkeln
    ``alpha_target`` mellan trycksträva och dragband. Bottenpålarna placeras
    längs linjen mellan ``N1`` och ``N2`` med cc-avstånd ``d``. Höjden räknas
    fram så att grundgeometrin får målvinkeln.

    Valfri felslagning anges med ``move_node`` = "N3" eller "N4" samt
    ``Delta_x``/``Delta_y`` i mm. ``origin_node`` och ``origin_mode`` fungerar
    på samma sätt som för 3- och 4-pålsfunktionerna.
    """
    data = _parse_px(px)

    original_nodes = {"N1": data["N1"], "N2": data["N2"]}
    bottom_nodes, geometry_params = _build_bottom_nodes(data)
    original_nodes.update(bottom_nodes)

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
                {"rubrik": "Beräkning", "text": "Funktionen bygger en idealiserad 2-pålsmodell med två trycksträvor och ett dragband."},
                {"rubrik": "Begränsning", "text": "Modellen är geometrisk och dimensionerar inte betong, armering, pålar eller knutpunkter."},
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("N1", r"N_1", nodes["N1"], "mm", "övre nod N1"),
                _post("N2", r"N_2", nodes["N2"], "mm", "övre nod N2"),
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
                _post("N3", r"N_3", nodes["N3"], "mm", "pålnod N3"),
                _post("N4", r"N_4", nodes["N4"], "mm", "pålnod N4"),
                _post("h", r"h", geometry_params["h"], "mm", "beräknad höjd"),
                _post("top_cc", r"d_{top}", geometry_params["top_cc"], "mm", "horisontellt avstånd mellan N1 och N2"),
                _post("theta", r"\theta", geometry_params["theta"], "deg", "riktning för pållinje"),
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
                _ekvation(r"h = \frac{d-d_{top}}{2}\tan(\alpha_{target})", "höjd från målvinkel"),
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
        },
        "krafter": {
            "pile_loads": data["pile_loads"],
            "member_forces": local_forces,
            "global_equilibrium": global_forces,
            "sign_convention": "positiv = drag, negativ = tryck",
        },
    }
