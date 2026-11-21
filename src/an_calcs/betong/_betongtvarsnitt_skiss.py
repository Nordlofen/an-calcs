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
        f'aria-label="Måttsatt tvärsnitt för {name}" style="font:14px sans-serif;color:var(--anp-fg,#202327)">',
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
    parts.append(f'<rect x="{left:.2f}" y="{top}" width="{width:.2f}" height="{height:.2f}" '
                 'fill="var(--anp-soft,#e8edf1)" stroke="currentColor" stroke-width="1.4"/>')
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

    stirrup = p["phi_b"] if geometry in {"pale", "balk"} else 0.0
    if geometry == "pale":
        top_cover = bottom_cover = side_cover = p["c_nom"]
    else:
        top_cover, bottom_cover = p["c_nom_ok"], p["c_nom_uk"]
        bars_width = max(row["antal_ekv"] * row["phi"] for row in p["rader"])
        side_cover = max(0, min(b * 0.09, (b - bars_width - 2 * stirrup) / 2))
    if stirrup:
        outer_left = left + side_cover * scale
        outer_top = top + top_cover * scale
        inner_width = width - 2 * side_cover * scale
        inner_height = height - (top_cover + bottom_cover) * scale
        stroke = stirrup * scale
        radius = min(10, inner_width / 7, inner_height / 7)
        parts.append(f'<rect x="{outer_left + stroke / 2:.2f}" y="{outer_top + stroke / 2:.2f}" '
                     f'width="{inner_width - stroke:.2f}" height="{inner_height - stroke:.2f}" '
                     f'rx="{radius:.2f}" fill="none" stroke="#52788f" stroke-width="{stroke:.2f}"/>')

    row_positions = {}
    for row in p["rader"]:
        count = int(row["indatavarde"])
        count_drawn = min(count, 70)
        margin = side_cover + stirrup + row["phi"] / 2
        centers = [b / 2] if count_drawn == 1 else [
            margin + i * (b - 2 * margin) / (count_drawn - 1) for i in range(count_drawn)
        ]
        cy = top + row["y"] * scale
        radius = row["phi"] / 2 * scale
        for center in centers:
            parts.append(f'<circle cx="{left + center * scale:.2f}" cy="{cy:.2f}" '
                         f'r="{max(radius, 1.05):.2f}" fill="#ae4946"/>')
        edge = "ÖK" if row["namn"].endswith("ÖK") else "UK"
        row_positions[edge] = (left + centers[-1] * scale, count, row["phi"])

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
            _, count, diameter = row_positions[edge]
            text(x, tail + 46, f"{edge}  {count} × Ø{diameter:g}", bold=True)
    parts.append('</svg>')
    return ''.join(parts)
