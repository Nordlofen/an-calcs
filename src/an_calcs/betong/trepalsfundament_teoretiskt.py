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


def _angle_deg(v1, v2):
    n1 = math.sqrt(sum(x * x for x in v1))
    n2 = math.sqrt(sum(x * x for x in v2))
    if n1 == 0 or n2 == 0:
        raise ValueError("Vinkel kan inte beräknas för nollvektor.")
    c = sum(a * b for a, b in zip(v1, v2)) / (n1 * n2)
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


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


def _parse_px(px):
    if px is None:
        raise ValueError("px måste anges.")

    if isinstance(px, dict):
        required = ("N1", "N2", "N3", "d45", "x_mid", "y0", "x6", "y6", "h")
        missing = [name for name in required if name not in px]
        if missing:
            raise ValueError(f"px saknar värden: {', '.join(missing)}.")
        return {
            "N1": _as_point("N1", px["N1"]),
            "N2": _as_point("N2", px["N2"]),
            "N3": _as_point("N3", px["N3"]),
            "d45": float(px["d45"]),
            "x_mid": float(px["x_mid"]),
            "y0": float(px["y0"]),
            "x6": float(px["x6"]),
            "y6": float(px["y6"]),
            "h": float(px["h"]),
            "move_node": px.get("move_node"),
            "delta_x": float(px.get("delta_x", 0.0)),
            "delta_y": float(px.get("delta_y", 0.0)),
        }

    if len(px) not in (9, 12):
        raise ValueError(
            "px måste innehålla 9 eller 12 värden: "
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
        "x_mid": float(x_mid),
        "y0": float(y0),
        "x6": float(x6),
        "y6": float(y6),
        "h": float(h),
        "move_node": move_node,
        "delta_x": float(delta_x),
        "delta_y": float(delta_y),
    }


def trepalsfundament_teoretiskt_innan_slagning(px):
    """
    Beräknar teoretisk 3D-geometri och nodvinklar for ett 3-palsfundament.

    Parameterformat utan felslagning:
        px = [N1, N2, N3, d45, x_mid, y0, x6, y6, h]

    Parameterformat med felslagning:
        px = [N1, N2, N3, d45, x_mid, y0, x6, y6, h, move_node, delta_x, delta_y]

    Alternativt kan px vara en dict med samma namngivna värden. ``move_node``
    kan vara "N4", "N5" eller "N6". ``delta_x`` och ``delta_y`` anges i
    samma längdenhet som koordinaterna.

    Enhetskonvention:
        - koordinater och avstånd i m
        - vinklar i grader

    Returvärde:
        dict
            Standardiserad details-dictionary med extra sektionen ``geometri``,
            avsedd att skickas vidare till ``plot_trepalsfundament_3d``.
    """
    data = _parse_px(px)

    original_nodes = {
        "N1": data["N1"],
        "N2": data["N2"],
        "N3": data["N3"],
    }
    original_nodes.update(
        _build_bottom_nodes(
            data["d45"],
            data["x_mid"],
            data["y0"],
            data["x6"],
            data["y6"],
            data["h"],
        )
    )

    nodes = _move_node(original_nodes, data["move_node"], data["delta_x"], data["delta_y"])
    original_angles = _compute_angles(original_nodes)
    angles = _compute_angles(nodes)
    angle_deltas = {name: angles[name] - original_angles[name] for name in angles}
    lengths = {f"{a}{b}": _distance(nodes[a], nodes[b]) for a, b in MEMBERS}
    original_lengths = {f"{a}{b}": _distance(original_nodes[a], original_nodes[b]) for a, b in MEMBERS}

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
                _post("N1", r"N_1", nodes["N1"], "m", "övre nod 1"),
                _post("N2", r"N_2", nodes["N2"], "m", "övre nod 2"),
                _post("N3", r"N_3", nodes["N3"], "m", "övre nod 3"),
                _post("d45", r"d_{45}", data["d45"], "m", "låst avstånd mellan N4 och N5"),
                _post("x_mid", r"x_{mid}", data["x_mid"], "m", "mittkoordinat för N4-N5"),
                _post("y0", r"y_0", data["y0"], "m", "y-koordinat för N4 och N5"),
                _post("x6", r"x_6", data["x6"], "m", "x-koordinat för N6"),
                _post("y6", r"y_6", data["y6"], "m", "y-koordinat för N6"),
                _post("h", r"h", data["h"], "m", "djup till bottenplanet"),
                _post("move_node", r"N_{flytt}", data["move_node"], "", "felslagen nod"),
                _post("delta_x", r"\Delta x", data["delta_x"], "m", "felslagning i x-led"),
                _post("delta_y", r"\Delta y", data["delta_y"], "m", "felslagning i y-led"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("N4", r"N_4", nodes["N4"], "m", "nedre nod 4"),
                _post("N5", r"N_5", nodes["N5"], "m", "nedre nod 5"),
                _post("N6", r"N_6", nodes["N6"], "m", "nedre nod 6"),
                _post("N4_orig", r"N_{4,orig}", original_nodes["N4"], "m", "ursprunglig nedre nod 4"),
                _post("N5_orig", r"N_{5,orig}", original_nodes["N5"], "m", "ursprunglig nedre nod 5"),
                _post("N6_orig", r"N_{6,orig}", original_nodes["N6"], "m", "ursprunglig nedre nod 6"),
                *[
                    _post(name, name, value, "m", f"stavlängd {name}")
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
                _post("da45", r"\Delta\alpha_{45}", angle_deltas["a45"], "deg", "vinkelförändring a45"),
                _post("da46", r"\Delta\alpha_{46}", angle_deltas["a46"], "deg", "vinkelförändring a46"),
                _post("da54", r"\Delta\alpha_{54}", angle_deltas["a54"], "deg", "vinkelförändring a54"),
                _post("da56", r"\Delta\alpha_{56}", angle_deltas["a56"], "deg", "vinkelförändring a56"),
                _post("da64", r"\Delta\alpha_{64}", angle_deltas["a64"], "deg", "vinkelförändring a64"),
                _post("da65", r"\Delta\alpha_{65}", angle_deltas["a65"], "deg", "vinkelförändring a65"),
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
            ],
        },
        "geometri": {
            "nodes": nodes,
            "original_nodes": original_nodes,
            "members": [list(member) for member in MEMBERS],
            "angles": angles,
            "original_angles": original_angles,
            "angle_deltas": angle_deltas,
            "lengths": lengths,
            "original_lengths": original_lengths,
            "move_node": data["move_node"],
            "delta_x": data["delta_x"],
            "delta_y": data["delta_y"],
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
        title = f"3-pålsfundament - efter felslagning ({move_node}, dx={delta_x:g}, dy={delta_y:g})"

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
            xaxis=dict(title="X", showticklabels=False, showgrid=True, gridcolor="black", showbackground=False),
            yaxis=dict(title="Y", showticklabels=False, showgrid=True, gridcolor="black", showbackground=False),
            zaxis=dict(title="Z", showticklabels=False, showgrid=True, gridcolor="black", showbackground=False),
        ),
    )

    return fig
