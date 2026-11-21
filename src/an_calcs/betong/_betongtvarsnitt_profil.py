"""Måttlösa spännings- och töjningsprofiler från Panelens beräkningsmodell."""

from ._betongtvarsnitt_skiss import _snitt_bilddelar
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

    h, b = p["h"], p["b"]
    scale = min(185 / b, 168 / h)
    span = h * scale
    top, bottom = 108, 108 + span
    left = 142 - b * scale / 2
    right = left + b * scale
    strain_axis, stress_axis, force_axis, z_axis = 362, 523, 753, 867
    etop, ebottom = state["epsilon_top"], state["epsilon_bottom"]
    unloaded = etop == ebottom == 0
    x = state["x"] if elastic else state["x_verksam"]
    lower_edge = state["tryckkant"] == "UK"
    start, stop = (h - x, h) if lower_edge else (0, x)
    neutral = None if unloaded or not 0 < x < h else (start if lower_edge else stop)
    title = f'Spänningsprofil · Stadium {p["stadium"]}'
    context = "Elastisk profil vid angiven last" if elastic else "Ultimat profil · rektangulärt tryckblock"
    svg_height = bottom + 73
    parts = [
        '<div style="overflow-x:auto;max-width:100%" tabindex="0" role="region" aria-label="Spänningsfigur">',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 944 {svg_height:.2f}" '
        f'role="img" aria-label="{title}" style="min-width:680px;font:16px sans-serif;color:var(--anp-fg,#202327)">',
        f'<title>{title}</title>',
        '<desc>Gemensam höjdskala för tvärsnitt, töjning, betongspänning och krafter. '
        'Tryck åt höger och drag åt vänster. Profilernas bredd visas schematiskt.</desc>',
        f'<rect x="1" y="1" width="942" height="{svg_height - 2:.2f}" rx="7" '
        f'fill="none" stroke="{_GUIDE}"/>',
    ]

    def depth(y):
        return top + y * scale

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

    label(20, 28, title, size=22, bold=True)
    label(924, 28, context, size=14, anchor="end")
    line(20, 44, 924, 44, color=_GUIDE)
    for xp, name in ((142, "Tvärsnitt"), (strain_axis, "Töjning ε"),
                     (stress_axis + 31, "Betongspänning"), (force_axis, "Krafter")):
        label(xp, 72, name, anchor="middle", bold=True)
    for level in (top, bottom):
        line(right, level, force_axis + 52, level, color=_GUIDE, dashed=True)

    concrete, _, _, _ = _snitt_bilddelar(p, left, top, scale, None if unloaded else (start, stop))
    parts.extend(concrete)
    label(left, top - 8, "ÖK", size=13)
    label(left, bottom + 16, "UK", size=13)
    if not unloaded:
        for y in (start, stop):
            line(left - 37, depth(y), left - 3, depth(y), color=_GUIDE)
        dimension(left - 38, depth(start), depth(stop), "x" if x < h else "h", _BLUE, tag='data-part="tryckzonshoejd"')

    for xp in (strain_axis, stress_axis, force_axis):
        line(xp, top - 5, xp, bottom + 8)
    emax = max(abs(etop), abs(ebottom))
    if emax:
        strain_top = strain_axis + 73 * etop / emax
        strain_bottom = strain_axis + 73 * ebottom / emax
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
        label(20, bottom + 32, "Streckad linje = neutralaxel", size=14)
    elif unloaded:
        label(20, bottom + 32, "Obelastat snitt", size=14)
    label(924, bottom + 32, "Tryck åt höger · Drag åt vänster · Schematisk profilbredd", anchor="end", size=14)
    if state["z"] is not None:
        label(20, bottom + 53, "Hävarmen z mäts från samlad tryckresultant (betong och tryckarmering) till dragresultanten.", size=14)
    parts.append('</svg></div>')
    return ''.join(parts)
