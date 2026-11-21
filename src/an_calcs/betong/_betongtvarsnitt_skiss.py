"""Dynamisk måttskiss för Betongtvärsnitt i an-print.Panel."""

from .betongtvarsnitt import _bt_skissdata


def render(values):
    """Rita betong, täckskikt, bygel och längsarmering från Panelens indata."""
    p = _bt_skissdata(values)
    geometry, b, h = p["geometri"], p["b"], p["h"]
    scale = min(280 / b, 216 / h)
    width, height = b * scale, h * scale
    left = 76 + (280 - width) / 2
    right = left + width
    top = 57
    bottom = top + height
    name = {"pale": "Påle", "balk": "Balk", "plattremsa": "Plattremsa"}[geometry]
    tail = max(bottom + 48, 144)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 {tail + 79:.2f}" role="img" '
        f'aria-label="Måttsatt tvärsnitt för {name}" '
        'style="display:block;margin-bottom:6px;font:14px sans-serif;color:var(--anp-fg,#202327)">',
        f'<title>{name} med täckskikt och längsarmering</title>',
        '<desc>Mått i millimeter. Järnens placering i breddled är schematisk.</desc>',
        f'<rect x="1" y="1" width="458" height="{tail + 76:.2f}" rx="6" '
        'fill="none" stroke="var(--anp-line,#d7dce1)"/>',
    ]

    def line(x1, y1, x2, y2, faint=False):
        stroke = 'var(--anp-line,#c7d0d7)' if faint else 'currentColor'
        parts.append(f'<path d="M{x1:.2f} {y1:.2f} L{x2:.2f} {y2:.2f}" stroke="{stroke}" fill="none"/>')

    def tick(x, y):
        line(x - 3, y + 3, x + 3, y - 3)

    def text(x, y, value, anchor="start", size=14, bold=False):
        weight = ' font-weight="600"' if bold else ''
        parts.append(f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
                     f'font-size="{size}" fill="currentColor"{weight}>{value}</text>')

    text(16, 27, "Tvärsnitt", size=18, bold=True)
    text(442, 27, "Mått i mm", "end", 12)
    section, row_positions, stirrup, covers = _snitt_bilddelar(p, left, top, scale)
    parts.extend(section)
    text(left, top - 7, "ÖK", size=12)
    text(left, bottom + 15, "UK", size=12)

    for x in (left, right):
        line(x, bottom + 3, x, bottom + 34, faint=True)
        tick(x, bottom + 30)
    line(left, bottom + 30, right, bottom + 30)
    text((left + right) / 2, bottom + 26, f"b = {b:g}", "middle")
    dim_x = left - 18
    for y in (top, bottom):
        line(dim_x - 3, y, left - 3, y, faint=True)
        tick(dim_x, y)
    line(dim_x, top, dim_x, bottom)
    text(dim_x - 6, (top + bottom) / 2 + 4, f"h = {h:g}", "end")

    top_cover, bottom_cover = covers
    cover_x = right + 17
    for edge, face, offset, sign in (("ÖK", top, top_cover, 1), ("UK", bottom, bottom_cover, -1)):
        if geometry == "pale" and edge == "UK":
            continue
        if geometry == "plattremsa" and edge not in row_positions:
            continue
        cover_y = face + sign * offset * scale
        start_x = row_positions[edge][0] if geometry == "plattremsa" else (left + right) / 2
        line(start_x, cover_y, cover_x + 4, cover_y, faint=True)
        line(right + 3, face, cover_x + 4, face, faint=True)
        line(cover_x, face, cover_x, cover_y)
        tick(cover_x, face)
        if offset > 0:
            tick(cover_x, cover_y)
        label_y = (face + cover_y) / 2 + 4
        if height < 40:
            label_y -= sign * 14
        text(cover_x + 6, label_y, f"{edge} {offset:g}", size=12)

    reference = f"Bygel Ø{stirrup:g} · Täckskikt till bygelns utsida" if stirrup else (
        "Täckskikt till längsarmeringens utsida")
    text(16, tail + 7, reference, size=13)
    line(16, tail + 20, 444, tail + 20, faint=True)
    for x, edge in ((16, "ÖK"), (218, "UK")):
        if edge in row_positions:
            _, count, diameter, spacing = row_positions[edge]
            label = f"Ø{diameter:g} c/c {spacing:g}" if spacing else f"{count} × Ø{diameter:g}"
            text(x, tail + 46, f"{edge}  {label}", bold=True)
    parts.append('</svg>')
    return ''.join(parts)



def _snitt_bilddelar(p, left, top, scale):
    """Rita betong, eventuell bygel och armering i måttskissen."""
    geometry, b, h = p["geometri"], p["b"], p["h"]
    width, height = b * scale, h * scale
    parts = [f'<rect data-part="betong" x="{left:.3f}" y="{top:.3f}" '
             f'width="{width:.3f}" height="{height:.3f}" fill="var(--anp-soft,#eef2f5)"/>']
    parts.append(f'<rect x="{left:.3f}" y="{top:.3f}" width="{width:.3f}" height="{height:.3f}" '
                 'fill="none" stroke="currentColor" stroke-width="1.4"/>')

    stirrup = p["phi_b"] if geometry in {"pale", "balk"} else 0.0
    if geometry == "pale":
        top_cover = bottom_cover = side_cover = p["c_nom"]
    else:
        top_cover, bottom_cover = p["c_nom_ok"], p["c_nom_uk"]
        bars_width = max(row["antal_ekv"] * row["phi"] for row in p["rader"])
        side_cover = max(0, min(b * 0.09, (b - bars_width - 2 * stirrup) / 2))

    outer_width = width - 2 * side_cover * scale
    outer_top, outer_bottom = top + top_cover * scale, top + (h - bottom_cover) * scale
    outer_height = outer_bottom - outer_top
    stroke = min(stirrup * scale, .45 * outer_height)
    inside_left = left + side_cover * scale + stroke
    clear_width = outer_width - 2 * stroke
    clear_top = outer_top + stroke
    clear_bottom = outer_bottom - stroke
    rows = []
    for row in p["rader"]:
        spacing = row["indatavarde"] if row["indatametod"] == "s" else None
        count = int(row["antal_ekv"] + .5)
        if spacing:
            count = max(1, min(count, 1 + int(max(0, b - row["phi"]) / spacing)))
        drawn = min(count, 70)
        radius = min(max(1.05, row["phi"] * scale / 2), clear_width / (2 * drawn),
                     (clear_bottom - clear_top) / 2)
        if spacing:
            radius = min(radius, row["phi"] * scale / 2)
        rows.append((row, count, drawn, radius, spacing))

    if stirrup:
        # Lägg yttersta järnet förbi bygelböjen. Vid täta rader minskar
        # hörnradien i skissen så att järnen också ryms i breddled.
        room = min(clear_width / 2 - (n - 1) * radius for _, _, n, radius, _ in rows)
        corner = min(10, outer_width / 7, outer_height / 7, room + stroke / 2)
        parts.append(f'<rect data-part="bygel" x="{inside_left - stroke / 2:.3f}" '
                     f'y="{clear_top - stroke / 2:.3f}" width="{outer_width - stroke:.3f}" '
                     f'height="{outer_height - stroke:.3f}" rx="{corner:.3f}" '
                     f'fill="none" stroke="#52788f" stroke-width="{stroke:.3f}"/>')
    else:
        corner = 0.0

    row_positions = {}
    for row, count, drawn, radius, spacing in rows:
        room = clear_width / 2 - (drawn - 1) * radius
        gap = min(.55, max(0, room - radius), max(0, (clear_bottom - clear_top) / 2 - radius)) if stirrup else 0
        margin = min(room, max(radius, corner - stroke / 2) + gap)
        if drawn == 1:
            centers = [left + width / 2]
        elif spacing:
            span = (count - 1) * spacing * scale
            centers = [left + (width - span) / 2 + i * span / (drawn - 1) for i in range(drawn)]
        else:
            centers = [inside_left + margin + i * (clear_width - 2 * margin) / (drawn - 1)
                       for i in range(drawn)]
        cy = max(clear_top + radius + gap,
                 min(top + row["y"] * scale, clear_bottom - radius - gap))
        for cx in centers:
            parts.append(f'<circle data-part="langsjarn" cx="{cx:.3f}" cy="{cy:.3f}" '
                         f'r="{radius:.3f}" fill="#ae4946"/>')
        edge = "ÖK" if row["namn"].endswith("ÖK") else "UK"
        row_positions[edge] = (centers[-1], count, row["phi"], spacing)
    return parts, row_positions, stirrup, (top_cover, bottom_cover)
