"""Måttlösa spännings- och töjningsprofiler från Panelens beräkningsmodell."""

from .betongtvarsnitt import _BT_PANEL_PX, _bt_fran_panel, berakna_betongtvarsnitt


_BLUE = "#297694"
_RED = "#b44340"
_GREEN = "var(--bt-profil-gron,#23784c)"
_AXIS = "#8295a7"
_GUIDE = "var(--anp-line,#d3dce4)"


def render(values):
    """Rita vald analys med gemensam höjdskala och schematisk profilbredd."""
    raw = berakna_betongtvarsnitt(_bt_fran_panel([values.get(name) for name in _BT_PANEL_PX]))
    p = raw["indata"]
    elastic = p["stadium"] == "II"
    state = raw["stadium_II"] if elastic else raw["stadium_III"]["vald"]
    if state is None:
        return '<p role="status">Ingen spänningsprofil kan visas. Jämvikt vid angiven normalkraft hittades inte.</p>'

    h = p["h"]
    geometry = p["geometri"]
    if elastic:
        span, top, section_center = 112, 101, 142
        widths = {"pale": span, "balk": 96, "plattremsa": 176}
        strain_axis, stress_axis, force_axis, z_axis = 362, 523, 753, 867
        svg_width, minimum_width = 944, 680
    else:
        span, top, section_center = 160, 110, 162
        widths = {"pale": span, "balk": 136, "plattremsa": 185}
        strain_axis, stress_axis, force_axis, z_axis = 466, 630, 875, 1034
        svg_width, minimum_width = 1120, 760
    width = widths[geometry]
    bottom = top + span
    left, right = section_center - width / 2, section_center + width / 2
    bar_radius = 4
    hoop_inset, hoop_stroke = 9, 2
    hoop_corner = hoop_stroke / 2 + bar_radius
    if geometry == "plattremsa":
        bar_inset_x, bar_inset_y = (20, 17) if elastic else (21, 23)
    else:
        bar_inset_x = bar_inset_y = hoop_inset + hoop_corner
    etop, ebottom = state["epsilon_top"], state["epsilon_bottom"]
    unloaded = etop == ebottom == 0
    x = state["x"] if elastic else state["x_verksam"]
    lower_edge = state["tryckkant"] == "UK"
    start, stop = (h - x, h) if lower_edge else (0, x)
    neutral = None if unloaded or not 0 < x < h else (start if lower_edge else stop)
    # Fäst neutralaxeln och dragresultanten vid motsvarande nivåer i skissen.
    neutral_fraction = .5 if elastic else (.5625 if lower_edge else .4375)
    levels = [(0.0, top)]
    if neutral is not None:
        levels.append((neutral, top + span * neutral_fraction))
        if not elastic and state["y_dragresultant"] is not None:
            bar_level = top + bar_inset_y if lower_edge else bottom - bar_inset_y
            levels.append((state["y_dragresultant"], bar_level))
    levels.append((h, bottom))
    levels.sort()
    intervals = list(zip(levels, levels[1:]))
    title = f'Spänningsprofil · Stadium {p["stadium"]}'
    context = "Elastisk profil vid angiven last" if elastic else "Kapacitetsprofil vid angiven normalkraft"
    footer = bottom + (39 if elastic else 49)
    svg_height = footer + ((30 if state["z"] is not None else 12) if elastic else 22)
    blue = _BLUE if elastic else f"var(--bt-profil-bla,{_BLUE})"
    red = _RED if elastic else f"var(--bt-profil-rod,{_RED})"
    parts = [
        '<div style="overflow-x:auto;max-width:100%" tabindex="0" role="region" aria-label="Spänningsfigur">',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height:.2f}" '
        f'role="img" aria-label="{title}" style="min-width:{minimum_width}px;font:16px sans-serif;color:var(--anp-fg,#202327)">',
        f'<title>{title}</title>',
        '<desc>Tvärsnitt och armeringsjärn är schematiska. Töjning, betongspänning och krafter '
        'visas på motsvarande nivåer, med tryck åt höger och drag åt vänster.</desc>',
        f'<rect x="1" y="1" width="{svg_width - 2}" height="{svg_height - 2:.2f}" rx="7" '
        f'fill="none" stroke="{_GUIDE}"/>',
    ]
    if not elastic:
        parts.append('<style>[data-jp-theme-light="false"] svg[aria-label="Spänningsprofil · Stadium III"]'
                     '{--bt-profil-rod:#ff8a80;--bt-profil-gron:#75cd9c;--bt-profil-bla:#72c2de}</style>')

    def depth(y):
        for (start_y, start_level), (end_y, end_level) in intervals:
            if y < end_y:
                fraction = (y - start_y) / (end_y - start_y)
                return start_level + fraction * (end_level - start_level)
        return bottom

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

    def dimension(xp, start_y, end_y, name, color, *, tag="", label_color=None):
        line(xp, start_y, xp, end_y, color=color, tag=tag)
        for y in (start_y, end_y):
            line(xp - 4, y + 4, xp + 4, y - 4, color=color)
        label(xp + 9, (start_y + end_y) / 2 + 5, name, color=label_color or color)

    def arrow(end, y, name, color, tag, *, below=False):
        direction = 1 if end > force_axis else -1
        # Riktningen visar tecknet. Pilens längd är schematisk.
        shape([(force_axis, y), (end, y)], tag=tag, color=color)
        parts.append(f'<path d="M{end} {y:.2f} l{-8 * direction} -4 v8 z" fill="{color}"/>')
        label((force_axis + end) / 2, y + 19 if below else y - 8, name, anchor="middle", color=color)

    title_y, rule_y = (22, 34) if elastic else (33, 48)
    label(20, title_y, title, size=22 if elastic else 24, bold=True)
    label(svg_width - 20, title_y, context, size=14, anchor="end")
    line(20, rule_y, svg_width - 20, rule_y, color=_GUIDE)
    n_value = f'{p["N_d"]:.6g}'.replace(".", ",")
    if elastic:
        m_value = f'{p["M"]:.6g}'.replace(".", ",")
        n_arrow = "⊗ " if p["N_d"] else ""
        m_arrow = "↻ " if p["M"] > 0 else "↺ " if p["M"] < 0 else ""
        label(20, 54, "Yttre laster", size=14, bold=True)
        label(118, 54, f'{n_arrow}{subscript("N", "d")} = {n_value} kN', size=14)
        label(295, 54, f"{m_arrow}M = {m_value} kNm", size=14)
    for xp, name in ((section_center, "Tvärsnitt"), (strain_axis, "Töjning ε"),
                     (stress_axis + (31 if elastic else 49), "Betongspänning"),
                     (force_axis + (0 if elastic else 29), "Krafter")):
        label(xp, 78, name, anchor="middle", bold=True)

    strain_top_y, strain_bottom_y = top, bottom
    drag_y = None if state["y_dragresultant"] is None else depth(state["y_dragresultant"])
    if elastic:
        for level in (top, bottom):
            line(right, level, force_axis + 52, level, color=_GUIDE, dashed=True)
    else:
        compression_edge = bottom if lower_edge else top
        line(right, compression_edge, z_axis, compression_edge, color=_GUIDE, dashed=True)
        if drag_y is not None:
            if lower_edge:
                strain_top_y = drag_y
            else:
                strain_bottom_y = drag_y
            line(right, drag_y, force_axis, drag_y, color=_GUIDE, dashed=True, tag='data-part="dragniva"')

    parts.append(f'<rect data-part="betong" x="{left}" y="{top:.3f}" width="{width}" height="{span}" '
                 'fill="var(--anp-soft,#eef2f5)"/>')
    if not unloaded:
        parts.append(f'<rect data-part="tryckzon" x="{left}" y="{depth(start):.3f}" width="{width}" '
                     f'height="{depth(stop) - depth(start):.3f}" fill="#67bed9" fill-opacity=".37"/>')
    parts.append(f'<rect x="{left}" y="{top}" width="{width}" height="{span}" '
                 'fill="none" stroke="currentColor" stroke-width="1.4"/>')
    if geometry != "plattremsa":
        parts.append(f'<rect data-part="bygel" x="{left + hoop_inset}" y="{top + hoop_inset}" '
                     f'width="{width - 2 * hoop_inset}" height="{span - 2 * hoop_inset}" rx="{hoop_corner:g}" '
                     f'fill="none" stroke="#52788f" stroke-width="{hoop_stroke}"/>')
    for cy in (top + bar_inset_y, bottom - bar_inset_y):
        for cx in (left + bar_inset_x, right - bar_inset_x):
            parts.append(f'<circle data-part="langsjarn" cx="{cx}" cy="{cy}" r="{bar_radius}" fill="{red}"/>')
    label(left, top - 8, "ÖK", size=13)
    label(left, bottom + 16, "UK", size=13)
    if not unloaded:
        for y in (start, stop):
            line(left - 37, depth(y), left - 3, depth(y), color=_GUIDE)
        dimension(left - 38, depth(start), depth(stop), "x" if x < h else "h", blue, tag='data-part="tryckzonshoejd"')

    if not elastic:
        mid_y = (top + bottom) / 2
        line(section_center + 6, mid_y, right, mid_y, color="currentColor", dashed=True)
        parts.append(f'<g data-part="tyngdpunkt" transform="translate({section_center} {mid_y})">'
                     '<circle r="6" fill="#fff"/>'
                     '<path d="M0 0V-6A6 6 0 0 1 6 0Z M0 0V6A6 6 0 0 1 -6 0Z" fill="currentColor"/>'
                     '<circle r="6" fill="none" stroke="currentColor"/></g>')
        parts.append(f'<g data-part="normalkraft"><title>N_Ed = {n_value} kN</title>')
        if p["N_d"]:
            shape([(right + 62, mid_y), (right + 3, mid_y)], tag="", color=red)
            parts.append(f'<path d="M{right + 3} {mid_y} l8 -4 v8 z" fill="{red}"/>')
        n_label = subscript("N", "Ed") + ("" if p["N_d"] else " = 0")
        label(right + 32, mid_y - 12, n_label, anchor="middle", color=red)
        parts.append('</g>')

        moment = state["M_Rd"] / 1e6
        moment_value = f'{moment:.6g}'.replace(".", ",")
        parts.append(f'<g data-part="kapacitetsmoment"><title>M_Rd = {moment_value} kNm</title>')
        has_moment = abs(moment) > 1e-9
        if has_moment:
            direction = 1 if moment < 0 else -1
            arc_x, arc_end = right + 72, mid_y + 31 * direction
            parts.append(f'<path d="M{arc_x} {mid_y - 31 * direction} Q{arc_x + 32} {mid_y} {arc_x} {arc_end}" '
                         f'fill="none" stroke="{_GREEN}" stroke-width="2"/>')
            parts.append(f'<path d="M{arc_x} {arc_end} l3 {-9 * direction} 6 {5 * direction} z" fill="{_GREEN}"/>')
        label(right + 102, mid_y + 6, subscript("M", "Rd") + ("" if has_moment else " = 0"), color=_GREEN)
        parts.append('</g>')

    for xp in (strain_axis, stress_axis, force_axis):
        line(xp, top - 5 if elastic else strain_top_y, xp, bottom + 8 if elastic else strain_bottom_y,
             tag='data-part="profilaxel"')
    # Låt den raka töjningslinjen korsa den ritade neutralaxeln.
    top_width, bottom_width = etop, ebottom
    if neutral is not None:
        sign = -1 if lower_edge else 1
        neutral_y = depth(neutral)
        top_width = sign * (neutral_y - strain_top_y)
        bottom_width = sign * (neutral_y - strain_bottom_y)
    emax = max(abs(top_width), abs(bottom_width))
    if emax:
        strain_top = strain_axis + 73 * top_width / emax
        strain_bottom = strain_axis + 73 * bottom_width / emax
        shape([(strain_axis, strain_top_y), (strain_top, strain_top_y),
               (strain_bottom, strain_bottom_y), (strain_axis, strain_bottom_y)],
              tag='data-part="toejning"', color="currentColor")
        if not elastic:
            compression_x, compression_y = (strain_bottom, bottom) if lower_edge else (strain_top, top)
            compression_label = ("cu3" if p["tryckblock"] == "rektangel" else "cu2") if neutral is not None else "c,max"
            parts.append(f'<circle cx="{compression_x:.2f}" cy="{compression_y:.2f}" r="3" fill="currentColor"/>')
            label(compression_x + 9, compression_y + 5, subscript("ε", compression_label))
            if drag_y is not None:
                tension_x = strain_top if lower_edge else strain_bottom
                parts.append(f'<circle data-part="dragtoejning" cx="{tension_x:.2f}" cy="{drag_y:.2f}" r="3" fill="currentColor"/>')
                label(tension_x - 9, drag_y - 4, subscript("ε", "s"), anchor="end")
    if neutral is not None:
        line(left, depth(neutral), stress_axis + 93 if elastic else stress_axis - 8,
             depth(neutral), dashed=True, tag='data-part="neutralaxel"')

    if not unloaded:
        stress_end = stress_axis + (84 if elastic else 100)
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
                  tag='data-part="betongspaenning" data-form="rektangel"', color=blue, fill="#67bed9", closed=True)
            label(stress_end - 9, depth(block_start) - 9, subscript("f", "cd"), color=blue)
            dimension(stress_end + 13, depth(block_start), depth(block_end), "0,8x" if x < h else "a", blue)

    concrete_y = None if state["y_Fc"] is None else depth(state["y_Fc"])
    compression_steel_y = None
    if not elastic and state["F_s_tryck"] > 0:
        compression_steel_y = depth(sum(max(0, row["F"]) * row["y"] for row in state["rader"]) / state["F_s_tryck"])
    steel_above_concrete = compression_steel_y is not None and concrete_y is not None and compression_steel_y < concrete_y
    if concrete_y is not None:
        arrow(force_axis + (65 if elastic else 74), concrete_y, subscript("F", "c"), blue,
              'data-part="betongkraft"', below=steel_above_concrete)
    if compression_steel_y is not None:
        arrow(force_axis + 56, compression_steel_y, subscript("F′", "s"), red,
              'data-part="tryckarmeringskraft"', below=not steel_above_concrete)
    if drag_y is not None:
        arrow(force_axis - 65, drag_y, subscript("F", "s,drag" if elastic else "s"), red, 'data-part="dragkraft"')
    if state["z"] is not None:
        compression_y = depth(state["y_tryckresultant"])
        if not elastic:
            marker_x = force_axis + 94
            line(force_axis, drag_y, z_axis, drag_y, dashed=True)
            line(marker_x, compression_y, z_axis, compression_y, dashed=True)
            parts.append(f'<circle data-part="tryckresultant" cx="{marker_x}" cy="{compression_y:.2f}" r="3.7" fill="currentColor"/>')
            result_label_y = bottom + 35 if lower_edge else top - 12
            line(marker_x, compression_y, marker_x, result_label_y + (-13 if lower_edge else 5))
            label(marker_x, result_label_y, "Gemensam tryckresultant" if compression_steel_y is not None else "Tryckresultant",
                  anchor="middle", size=13)
        z_top, z_bottom = sorted((compression_y, drag_y))
        dimension(z_axis, z_top, z_bottom, "z", _AXIS, tag='data-part="haevarm"',
                  label_color=None if elastic else "currentColor")

    if elastic and neutral is not None:
        label(20, footer, "Neutralaxelns läge visas schematiskt", size=14)
    elif unloaded:
        label(20, footer, "Obelastat snitt", size=14)
    label(924 if elastic else 20, footer, "Schematisk geometri och armering · Tryck åt höger · Drag åt vänster",
          anchor="end" if elastic else "start", size=14)
    if elastic and state["z"] is not None:
        label(20, footer + 18, "Hävarmen z mäts mellan tryckresultanten och dragresultanten.", size=14)
    parts.append('</svg></div>')
    return ''.join(parts)
