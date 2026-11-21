"""Måttlösa spännings- och töjningsprofiler från Panelens beräkningsmodell."""

from .betongtvarsnitt import _BT_PANEL_PX, _bt_fran_panel, berakna_betongtvarsnitt


_BLUE = "#297694"
_RED = "#b44340"
_AXIS = "#8295a7"
_GUIDE = "var(--anp-line,#d3dce4)"


def render(values):
    """Rita vald analys med gemensam höjdskala och schematisk profilbredd."""
    raw = berakna_betongtvarsnitt(_bt_fran_panel([values[name] for name in _BT_PANEL_PX]))
    p = raw["indata"]
    elastic = p["stadium"] == "II"
    state = raw["stadium_II"] if elastic else raw["stadium_III"]["vald"]
    if state is None:
        return '<p role="status">Ingen spänningsprofil kan visas. Jämvikt vid angiven normalkraft hittades inte.</p>'

    h = p["h"]
    span, width = 112, 96
    scale = span / h
    top, bottom = 101, 101 + span
    left, right = 142 - width / 2, 142 + width / 2
    strain_axis, stress_axis, force_axis, z_axis = 362, 523, 753, 867
    etop, ebottom = state["epsilon_top"], state["epsilon_bottom"]
    unloaded = etop == ebottom == 0
    x = state["x"] if elastic else state["x_verksam"]
    lower_edge = state["tryckkant"] == "UK"
    start, stop = (h - x, h) if lower_edge else (0, x)
    neutral = None if unloaded or not 0 < x < h else (start if lower_edge else stop)
    # Komprimera skillnaden mot mitten i stadium II:s principskiss.
    # Samma avbildning för alla nivåer bevarar ordningen på krafter och järn.
    schematic = elastic and neutral is not None
    axis_depth = 0.35 * neutral + 0.65 * h / 2 if schematic else neutral
    title = f'Spänningsprofil · Stadium {p["stadium"]}'
    context = "Elastisk profil vid angiven last" if elastic else "Kapacitetsprofil vid angiven normalkraft"
    footer = bottom + 39
    svg_height = footer + (30 if state["z"] is not None else 12)
    parts = [
        '<div style="overflow-x:auto;max-width:100%" tabindex="0" role="region" aria-label="Spänningsfigur">',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 944 {svg_height:.2f}" '
        f'role="img" aria-label="{title}" style="min-width:680px;font:16px sans-serif;color:var(--anp-fg,#202327)">',
        f'<title>{title}</title>',
        '<desc>Tvärsnitt och armeringsjärn är schematiska. Töjning, betongspänning och krafter '
        'visas på motsvarande nivåer, med tryck åt höger och drag åt vänster.</desc>',
        f'<rect x="1" y="1" width="942" height="{svg_height - 2:.2f}" rx="7" '
        f'fill="none" stroke="{_GUIDE}"/>',
    ]

    def depth(y):
        if not schematic:
            return top + y * scale
        if y <= neutral:
            return top + y * axis_depth / neutral * scale
        return bottom - (h - y) * (h - axis_depth) / (h - neutral) * scale

    def line(x1, y1, x2, y2, *, color=_AXIS, dashed=False, tag=""):
        dash = ' stroke-dasharray="5 5"' if dashed else ''
        parts.append(f'<path {tag} d="M{x1:.2f} {y1:.2f} L{x2:.2f} {y2:.2f}" stroke="{color}" fill="none"{dash}/>')

    def label(xp, yp, content, *, size=16, anchor="start", color="currentColor", bold=False):
        weight = ' font-weight="600"' if bold else ''
        parts.append(f'<text x="{xp:.2f}" y="{yp:.2f}" fill="{color}" font-size="{size}" '
                     f'text-anchor="{anchor}"{weight}>{content}</text>')

    def subscript(symbol, index):
        return f'{symbol}<tspan baseline-shift="sub" font-size=".73em">{index}</tspan>'

    def shape(points, *, tag, color, fill="none", closed=False):
        coords = " ".join(f"{xp:.2f},{yp:.2f}" for xp, yp in points)
        element = "polygon" if closed else "polyline"
        opacity = ' fill-opacity=".31"' if fill != "none" else ''
        parts.append(f'<{element} {tag} points="{coords}" fill="{fill}"{opacity} '
                     f'stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')

    def dimension(xp, start_y, end_y, name, color, *, tag=""):
        line(xp, start_y, xp, end_y, color=color, tag=tag)
        for y in (start_y, end_y):
            line(xp - 4, y + 4, xp + 4, y - 4, color=color)
        label(xp + 9, (start_y + end_y) / 2 + 5, name, color=color)

    def arrow(end, y, name, color, tag):
        direction = 1 if end > force_axis else -1
        # Riktningen visar tecknet. Pilens längd är schematisk.
        shape([(force_axis, y), (end, y)], tag=tag, color=color)
        parts.append(f'<path d="M{end} {y:.2f} l{-8 * direction} -4 v8 z" fill="{color}"/>')
        label((force_axis + end) / 2, y - 8, name, anchor="middle", color=color)

    label(20, 22, title, size=22, bold=True)
    label(924, 22, context, size=14, anchor="end")
    line(20, 34, 924, 34, color=_GUIDE)
    n_value = f'{p["N_d"]:.6g}'.replace(".", ",")
    m_value = f'{p["M"]:.6g}'.replace(".", ",")
    n_arrow = "⊗ " if p["N_d"] else ""
    m_arrow = "↻ " if p["M"] > 0 else "↺ " if p["M"] < 0 else ""
    label(20, 54, "Yttre laster", size=14, bold=True)
    label(118, 54, f'{n_arrow}{subscript("N", "d")} = {n_value} kN', size=14)
    label(295, 54, f"{m_arrow}M = {m_value} kNm", size=14)
    for xp, name in ((142, "Tvärsnitt"), (strain_axis, "Töjning ε"),
                     (stress_axis + 31, "Betongspänning"), (force_axis, "Krafter")):
        label(xp, 78, name, anchor="middle", bold=True)
    for level in (top, bottom):
        line(right, level, force_axis + 52, level, color=_GUIDE, dashed=True)

    parts.append(f'<rect data-part="betong" x="{left}" y="{top:.3f}" width="{width}" height="{span}" '
                 'fill="var(--anp-soft,#eef2f5)"/>')
    if not unloaded:
        parts.append(f'<rect data-part="tryckzon" x="{left}" y="{depth(start):.3f}" width="{width}" '
                     f'height="{depth(stop) - depth(start):.3f}" fill="#67bed9" fill-opacity=".37"/>')
    parts.append(f'<rect x="{left}" y="{top}" width="{width}" height="{span}" '
                 'fill="none" stroke="currentColor" stroke-width="1.4"/>')
    for cy in (top + 17, bottom - 17):
        for cx in (left + 20, right - 20):
            parts.append(f'<circle data-part="langsjarn" cx="{cx}" cy="{cy}" r="4" fill="{_RED}"/>')
    label(left, top - 8, "ÖK", size=13)
    label(left, bottom + 16, "UK", size=13)
    if not unloaded:
        for y in (start, stop):
            line(left - 37, depth(y), left - 3, depth(y), color=_GUIDE)
        dimension(left - 38, depth(start), depth(stop), "x" if x < h else "h", _BLUE, tag='data-part="tryckzonshoejd"')

    for xp in (strain_axis, stress_axis, force_axis):
        line(xp, top - 5, xp, bottom + 8)
    # Låt den raka töjningslinjen korsa den ritade neutralaxeln.
    top_width, bottom_width = etop, ebottom
    if schematic:
        sign = -1 if lower_edge else 1
        top_width = sign * axis_depth
        bottom_width = -sign * (h - axis_depth)
    emax = max(abs(top_width), abs(bottom_width))
    if emax:
        strain_top = strain_axis + 73 * top_width / emax
        strain_bottom = strain_axis + 73 * bottom_width / emax
        shape([(strain_axis, top), (strain_top, top), (strain_bottom, bottom), (strain_axis, bottom)],
              tag='data-part="toejning"', color="currentColor")
    if neutral is not None:
        line(left, depth(neutral), stress_axis + 93, depth(neutral), dashed=True, tag='data-part="neutralaxel"')

    if not unloaded:
        stress_end = stress_axis + 84
        if elastic:
            compression = max(etop, ebottom)
            eps_at = lambda y: etop + (ebottom - etop) * y / h
            profile = [(stress_axis, depth(start)),
                       (stress_axis + 84 * max(0, eps_at(start)) / compression, depth(start)),
                       (stress_axis + 84 * max(0, eps_at(stop)) / compression, depth(stop)),
                       (stress_axis, depth(stop))]
            shape(profile, tag='data-part="betongspaenning" data-form="linjaer"', color=_BLUE, fill="#67bed9", closed=True)
            label(stress_end + 6, (bottom + 3) if lower_edge else (top - 8), subscript("σ", "c,max"), color=_BLUE)
        else:
            block = state["a_block"]
            block_start, block_end = (h - block, h) if lower_edge else (0, block)
            shape([(stress_axis, depth(block_start)), (stress_end, depth(block_start)),
                   (stress_end, depth(block_end)), (stress_axis, depth(block_end))],
                  tag='data-part="betongspaenning" data-form="rektangel"', color=_BLUE, fill="#67bed9", closed=True)
            label(stress_end - 9, depth(block_start) - 9, subscript("f", "cd"), color=_BLUE)
            dimension(stress_end + 13, depth(block_start), depth(block_end), "0,8x" if x < h else "a", _BLUE)

    if state["y_Fc"] is not None:
        arrow(force_axis + 65, depth(state["y_Fc"]), subscript("F", "c"), _BLUE, 'data-part="betongkraft"')
    if state["y_dragresultant"] is not None:
        arrow(force_axis - 65, depth(state["y_dragresultant"]), subscript("F", "s,drag"), _RED, 'data-part="dragkraft"')
    if state["z"] is not None:
        z_top, z_bottom = sorted((depth(state["y_tryckresultant"]), depth(state["y_dragresultant"])))
        dimension(z_axis, z_top, z_bottom, "z", _AXIS, tag='data-part="haevarm"')

    if neutral is not None:
        neutral_label = "Neutralaxelns läge visas schematiskt" if schematic else "Streckad linje = neutralaxel"
        label(20, footer, neutral_label, size=14)
    elif unloaded:
        label(20, footer, "Obelastat snitt", size=14)
    label(924, footer, "Schematisk geometri och armering · Tryck åt höger · Drag åt vänster", anchor="end", size=14)
    if state["z"] is not None:
        label(20, footer + 18, "Hävarmen z mäts mellan tryckresultanten och dragresultanten.", size=14)
    parts.append('</svg></div>')
    return ''.join(parts)
