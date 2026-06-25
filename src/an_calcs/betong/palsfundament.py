"""Gemensam presentation for pålfundamentmodeller."""


def _node_number(name):
    return int(name[1:]) if name.startswith("N") and name[1:].isdigit() else 10**9


def _angle_node(name):
    if name.startswith("a") and len(name) >= 3 and name[1].isdigit():
        return f"N{name[1]}"
    return None


def _angle_sort_key(name):
    return tuple(int(char) for char in name[1:] if char.isdigit())


def _reaction_sort_key(name):
    axis_order = {"x": 0, "y": 1, "z": 2}
    if len(name) >= 3 and name[0] == "R" and name[1].isdigit():
        return int(name[1]), axis_order.get(name[2], 9)
    return 999, 999


def _member_sort_key(name):
    digits = "".join(char for char in name if char.isdigit())
    return int(digits) if digits else 10**9


def _format_angle_label(name, angles, angle_deltas=None):
    text = f"{name}={angles[name]:.1f}°"
    if angle_deltas and name in angle_deltas:
        text += f" ({angle_deltas[name]:+.1f})"
    return text


def plot_palsfundament_3d(details, title=None):
    """Skapar en Plotly-figur från en 3- eller 4-påls-details-dictionary."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError("plot_palsfundament_3d kräver paketet plotly.") from exc

    geometri = details["geometri"]
    nodes = geometri["nodes"]
    original_nodes = geometri.get("original_nodes", nodes)
    members = geometri["members"]
    angles = geometri["angles"]
    angle_deltas = geometri.get("angle_deltas", {})
    move_node = geometri.get("move_node")
    delta_x = geometri.get("delta_x", 0.0)
    delta_y = geometri.get("delta_y", 0.0)

    if title is None:
        pile_count = len([name for name in nodes if name.startswith("N")]) // 2
        title = f"{pile_count}-pålsfundament"
        if move_node is not None:
            title += f" - efter felslagning ({move_node}, dx={delta_x:g} mm, dy={delta_y:g} mm)"
        else:
            title += " - teoretiskt innan slagning"

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

    for name, p in sorted(nodes.items(), key=lambda item: _node_number(item[0])):
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

    grouped_angles = {}
    for name in sorted(angles, key=_angle_sort_key):
        node = _angle_node(name)
        if node is not None and node in nodes:
            grouped_angles.setdefault(node, []).append(name)

    for node, names in grouped_angles.items():
        p = nodes[node]
        text = "<br>".join(_format_angle_label(name, angles, angle_deltas if move_node is not None else None) for name in names)
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


def format_palsfundament_resultat(details):
    """Returnerar en kompakt textsammanställning för 3- eller 4-pålsfundament."""
    geometri = details["geometri"]
    krafter = details.get("krafter", {})
    angles = geometri["angles"]
    strut_angles = geometri.get("strut_horizontal_angles", {})
    pile_loads = krafter.get("pile_loads")
    local_forces = krafter.get("member_forces")
    global_equilibrium = krafter.get("global_equilibrium")

    lines = ["=== VINKLAR mellan sträva och dragband  ==="]
    for name in sorted(angles, key=_angle_sort_key):
        lines.append(f"{name} = {angles[name]:.2f}°")

    if strut_angles:
        lines.extend(["", "=== STRÄVOR: VINKEL MOT HORISONTALPLAN (xy) ==="])
        for name in sorted(strut_angles, key=lambda value: int(value[5:]) if value[5:].isdigit() else 10**9):
            digits = name[5:]
            lines.append(f"α{digits} (N{digits[0]}-N{digits[1:]}) = {strut_angles[name]:.2f}°")

    if global_equilibrium is not None:
        lines.extend(
            [
                "",
                "=== GLOBAL JÄMVIKT (1 kraft per stav) ===",
                f"Rank(A) = {global_equilibrium['rank']}  | residual-norm = {global_equilibrium['residual_norm']:.3e}",
                "",
                "Stavkrafter (positiv = drag, negativ = tryck):",
            ]
        )
        for name in sorted(global_equilibrium["member_forces"], key=_member_sort_key):
            lines.append(f"  {name}: {global_equilibrium['member_forces'][name]:.1f}")
        lines.extend(["", "Stödreaktioner i toppen:"])
        for name in sorted(global_equilibrium["top_reactions"], key=_reaction_sort_key):
            lines.append(f"  {name}: {global_equilibrium['top_reactions'][name]:.1f}")

    if local_forces is not None:
        same_load = pile_loads and len({round(value, 12) for value in pile_loads.values()}) == 1
        lines.extend(["", "=== LOKAL NODJÄMVIKT (pålnoder) ==="])
        if same_load:
            lines.append(f"Rz per påle = {next(iter(pile_loads.values())):.1f} (uppåt, +z)")
        else:
            lines.append("Rz per påle (uppåt, +z):")
            for node in sorted(pile_loads, key=_node_number):
                lines.append(f"  {node}: {pile_loads[node]:.1f}")
        lines.append("")

        for node in sorted(local_forces, key=_node_number):
            lines.append(f"{node}:")
            for member, value in local_forces[node].items():
                lines.append(f"  {member}: {value:.1f}")
            lines.append("")

    return "\n".join(lines).rstrip()


def print_palsfundament_resultat(details):
    """Skriver ut samma text som ``format_palsfundament_resultat`` returnerar."""
    print(format_palsfundament_resultat(details))

