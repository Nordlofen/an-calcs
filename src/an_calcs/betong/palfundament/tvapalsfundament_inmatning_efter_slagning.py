"""Inmätt geometri for 2-palsfundament efter slagning."""

from __future__ import annotations

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


TOP_NODES = ("N1", "N2")
BOTTOM_NODES = ("N4", "N5")
STRUTS = [("N1", "N4"), ("N2", "N5")]
TIES = [("N4", "N5")]
MEMBERS = STRUTS + TIES


def _as_xy(name, value):
    if len(value) != 2:
        raise ValueError(f"{name} måste innehålla 2 koordinater [x, y].")
    return [float(value[0]), float(value[1])]


def _node3(xy, z):
    return [float(xy[0]), float(xy[1]), float(z)]


def _compute_angles(nodes):
    return {
        "a45": _angle_deg(_sub(nodes["N1"], nodes["N4"]), _sub(nodes["N5"], nodes["N4"])),
        "a54": _angle_deg(_sub(nodes["N2"], nodes["N5"]), _sub(nodes["N4"], nodes["N5"])),
    }


def _compute_strut_horizontal_angles(nodes):
    return {
        "alpha14": _angle_to_horizontal_deg(_sub(nodes["N1"], nodes["N4"])),
        "alpha25": _angle_to_horizontal_deg(_sub(nodes["N2"], nodes["N5"])),
    }


def _parse_pile_loads(px):
    if "pile_loads" in px:
        value = px["pile_loads"]
    elif "Rz" in px:
        value = px["Rz"]
    elif any(name in px for name in ("Rz4", "Rz5")):
        value = {"N4": px.get("Rz4", 0.0), "N5": px.get("Rz5", 0.0)}
    else:
        return None

    if isinstance(value, dict):
        return {name: float(value.get(name, value.get(name.lower(), 0.0))) for name in BOTTOM_NODES}
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError("pile_loads måste innehålla två värden för N4 och N5.")
        return {"N4": float(value[0]), "N5": float(value[1])}

    load = float(value)
    return {"N4": load, "N5": load}


def _solve_local_node(node, connected_nodes, rz):
    directions = [_unit_vector(node, other) for other in connected_nodes.values()]
    a = [
        [direction[0] for direction in directions],
        [direction[1] for direction in directions],
        [direction[2] for direction in directions],
    ]
    values, _, _ = _least_squares(a, [0.0, 0.0, -float(rz)])
    return dict(zip(connected_nodes.keys(), values))


def _local_equilibrium(nodes, pile_loads):
    if pile_loads is None:
        return None
    return {
        "N4": _solve_local_node(nodes["N4"], {"N1-N4": nodes["N1"], "N4-N5": nodes["N5"]}, pile_loads["N4"]),
        "N5": _solve_local_node(nodes["N5"], {"N2-N5": nodes["N2"], "N5-N4": nodes["N4"]}, pile_loads["N5"]),
    }


def _global_equilibrium(nodes, pile_loads):
    if pile_loads is None:
        return None

    unknowns = ["N14", "N25", "N45", "R1x", "R1y", "R1z", "R2x", "R2y", "R2z"]
    members = {
        "N14": ("N1", "N4"),
        "N25": ("N2", "N5"),
        "N45": ("N4", "N5"),
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
        "member_forces": {name: result[name] for name in ("N14", "N25", "N45")},
        "top_reactions": {name: result[name] for name in unknowns if name.startswith("R")},
        "rank": rank,
        "residual_norm": residual_norm,
    }


def _parse_theoretical_piles(value):
    if value is None:
        return None
    return [_as_xy("theo_piles_xy", xy) for xy in value]


def _parse_px(px):
    if px is None:
        raise ValueError("px måste anges.")
    if not isinstance(px, dict):
        raise ValueError("2-pålsinmätning förväntar px som dict.")

    required = ("h", "N1_xy", "N2_xy", "N4_xy", "N5_xy")
    missing = [name for name in required if name not in px]
    if missing:
        raise ValueError(f"px saknar värden: {', '.join(missing)}.")

    h = float(px["h"])
    if h <= 0:
        raise ValueError("h måste vara > 0.")

    return {
        "h": h,
        "N1_xy": _as_xy("N1_xy", px["N1_xy"]),
        "N2_xy": _as_xy("N2_xy", px["N2_xy"]),
        "N4_xy": _as_xy("N4_xy", px["N4_xy"]),
        "N5_xy": _as_xy("N5_xy", px["N5_xy"]),
        "theo_piles_xy": _parse_theoretical_piles(px.get("theo_piles_xy")),
        "pile_loads": _parse_pile_loads(px),
    }


def tvapalsfundament_inmätning_efter_slagning(px):
    """
    Beräknar geometri, vinklar och valfria stavkrafter för ett inmätt
    2-pålsfundament efter slagning.

    Indata:
        - ``h``: fackverkshöjd i mm. Toppplan ligger i z=0 och pålplan i z=-h.
        - ``N1_xy``, ``N2_xy``: topnoder/pelarfotspunkter i plan.
        - ``N4_xy``, ``N5_xy``: inmätta påltoppar i plan.
        - ``theo_piles_xy``: valfria teoretiska pållägen som markeras i plotten.
        - ``Rz`` eller ``pile_loads``: valfria uppåtriktade pålreaktioner i kN.

    Modell:
        Trycksträvorna är ``N1-N4`` och ``N2-N5``. Dragbandet är ``N4-N5``.
        Funktionen optimerar inte geometri utan använder inmätta pålkoordinater
        direkt.
    """
    data = _parse_px(px)

    nodes = {
        "N1": _node3(data["N1_xy"], 0.0),
        "N2": _node3(data["N2_xy"], 0.0),
        "N4": _node3(data["N4_xy"], -data["h"]),
        "N5": _node3(data["N5_xy"], -data["h"]),
    }
    angles = _compute_angles(nodes)
    strut_horizontal_angles = _compute_strut_horizontal_angles(nodes)
    lengths = {f"{a}{b}": _distance(nodes[a], nodes[b]) for a, b in MEMBERS}
    local_forces = _local_equilibrium(nodes, data["pile_loads"])
    global_forces = _global_equilibrium(nodes, data["pile_loads"])

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {"rubrik": "Beräkning", "text": "Funktionen bygger en inmätt 2-pålsmodell efter slagning."},
                {"rubrik": "Begränsning", "text": "Modellen är geometrisk och dimensionerar inte betong, armering, pålar eller knutpunkter."},
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("h", r"h", data["h"], "mm", "fackverkshöjd"),
                _post("N1_xy", r"N_{1,xy}", data["N1_xy"], "mm", "topnod N1 i plan"),
                _post("N2_xy", r"N_{2,xy}", data["N2_xy"], "mm", "topnod N2 i plan"),
                _post("N4_xy", r"N_{4,xy}", data["N4_xy"], "mm", "inmätt pålnod N4 i plan"),
                _post("N5_xy", r"N_{5,xy}", data["N5_xy"], "mm", "inmätt pålnod N5 i plan"),
                _post("theo_piles_xy", r"N_{teo,xy}", data["theo_piles_xy"], "mm", "teoretiska pållägen"),
                _post("pile_loads", r"R_z", data["pile_loads"], "kN", "uppåtriktade pålreaktioner"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                *[_post(name, name, nodes[name], "mm", f"nod {name}") for name in ("N1", "N2", "N4", "N5")],
                *[_post(name, name, value, "mm", f"stavlängd {name}") for name, value in lengths.items()],
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                *[_post(name, name, value, "deg", "vinkel mellan sträva och dragband") for name, value in angles.items()],
                *[_post(name, name, value, "deg", "sträva mot horisontalplan") for name, value in strut_horizontal_angles.items()],
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
            "original_nodes": nodes,
            "members": [list(member) for member in MEMBERS],
            "angles": angles,
            "original_angles": angles,
            "strut_horizontal_angles": strut_horizontal_angles,
            "angle_deltas": {},
            "lengths": lengths,
            "move_node": None,
            "delta_x": 0.0,
            "delta_y": 0.0,
            "theoretical_piles_xy": data["theo_piles_xy"],
            "theoretical_piles_z": -data["h"],
        },
        "krafter": {
            "pile_loads": data["pile_loads"],
            "member_forces": local_forces,
            "global_equilibrium": global_forces,
            "sign_convention": "positiv = drag, negativ = tryck",
        },
    }
