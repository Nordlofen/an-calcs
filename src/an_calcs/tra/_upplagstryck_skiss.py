"""Schematiska mått- och upplagsskisser för upplagstryckspanelen."""

import math

from .upplagstryck_tra import _effektiv_upplagslangd, _tolka_kontaktkraft, _tolka_l_1

_LINJE = "var(--anp-line,#cad3db)"
_TRA = "var(--anp-soft,#f1f3f5)"
_STOD = "var(--anp-field,#fff)"
_KONTAKT = "#52788f"
_TILLAGG = "#bddeeb"
_KRAFT = "var(--anp-error,#ac403a)"


class _Skiss:
    def __init__(self, title, description, height):
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 {height}" role="img" '
            f'aria-label="{title}" style="font:15px sans-serif;color:var(--anp-fg,#202327)">',
            f"<title>{title}</title><desc>{description}</desc>",
            f'<rect x="1" y="1" width="438" height="{height - 2}" rx="6" fill="none" stroke="{_LINJE}"/>',
        ]
        self.text(16, 27, title, size=19, bold=True)

    def line(self, x1, y1, x2, y2, *, stroke="currentColor", width=1, dashed=False):
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        self.parts.append(
            f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{stroke}" stroke-width="{width}"{dash}/>'
        )

    def rect(self, x, y, width, height, fill, *, part="", stroke="currentColor", dashed=False):
        marker = f' data-part="{part}"' if part else ""
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        self.parts.append(
            f'<rect{marker} x="{x}" y="{y}" width="{width}" height="{height}" '
            f'fill="{fill}" stroke="{stroke}"{dash}/>'
        )

    def text(self, x, y, content, *, anchor="start", size=15, fill="currentColor", bold=False, vertical=False):
        weight = ' font-weight="600"' if bold else ""
        angle = f' transform="rotate(-90 {x} {y})"' if vertical else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
            f'fill="{fill}"{weight}{angle}>{content}</text>'
        )

    def tick(self, x, y):
        self.line(x - 3, y + 3, x + 3, y - 3)

    def dim(self, start, end, y, label, *, from_y=None, size=15):
        if from_y is not None:
            for x in (start, end):
                self.line(x, from_y, x, y, stroke=_LINJE)
        self.line(start, y, end, y)
        self.tick(start, y)
        self.tick(end, y)
        self.text((start + end) / 2, y - 7, label, anchor="middle", size=size)

    def arrow(self, x, start, end):
        base = end + 8 if end < start else end - 8
        self.line(x, start, x, base, stroke=_KRAFT, width=2)
        self.parts.append(f'<path d="M{x} {end} L{x - 4} {base} H{x + 4} Z" fill="{_KRAFT}"/>')

    def svg(self):
        return "".join(self.parts) + "</svg>"


def _symbol(name, index=""):
    sub = f'<tspan baseline-shift="sub" font-size="72%">{index}</tspan>' if index else ""
    return f'<tspan font-style="italic">{name}</tspan>{sub}'


def _tal(value):
    return f"{value:.6g}".replace(".", ",")


def render_geometri(values):
    """Rita kontaktytans mått med samma tillägg som beräkningen."""
    b, l, h = (values[key] for key in ("b", "l", "h"))
    for key, value in (("b", b), ("l", l), ("h", h)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} måste vara ett positivt, ändligt tal.")
    mitt = values["upplagsplacering"] == "mittupplag"
    a = None if mitt else values["a"]
    if a is not None and (not math.isfinite(a) or a < 0):
        raise ValueError("a måste vara ett ändligt tal ≥ 0.")
    l_1, x_in = _tolka_l_1(values["l_1"])
    x_end, l_ef = _effektiv_upplagslangd(l, x_in, a)
    kraft = _tolka_kontaktkraft(values["N_c_90_Ed"])

    title = "Mittupplag" if mitt else "Ändupplag"
    skiss = _Skiss(title, "Schematiska mått i millimeter. Mörkblått visar fysisk upplagsyta.", 322)
    skiss.text(424, 27, "Schematisk · mm", anchor="end", size=13)
    beam, top, bottom = 65, 92, 155
    if mitt:
        start, left = 150, 88
    elif a == 0:
        start = left = beam
    else:
        start = 144
        left = beam if x_end == a else 89
    stop, right, next_contact = start + 96, start + 158, 349
    center = (start + stop) / 2

    skiss.rect(beam, top, 408 - beam, bottom - top, _TRA, part="virkesdel")
    skiss.rect(start, bottom, stop - start, 27, _STOD, part="upplag")
    if l_1 != "lang":
        skiss.rect(next_contact, bottom, 39, 20, _STOD, stroke=_LINJE, dashed=True)
        skiss.text(369, 191, "Nästa kontakt", anchor="middle", size=12)
    skiss.rect(left, bottom - 8, right - left, 8, _TILLAGG, part="effektiv-langd", stroke=_KONTAKT)
    skiss.rect(start, bottom - 8, stop - start, 8, _KONTAKT, part="fysisk-langd", stroke=_KONTAKT)

    for x in (stop, next_contact):
        skiss.line(x, 64, x, bottom - 8, stroke=_LINJE, dashed=True)
    l_1_label = "lång" if l_1 == "lang" else _tal(l_1)
    skiss.dim(stop, next_contact, 64, f'{_symbol("l", "1")} = {l_1_label}')
    for y in (top, bottom):
        skiss.line(50, y, beam - 3, y, stroke=_LINJE)
        skiss.tick(50, y)
    skiss.line(50, top, 50, bottom)
    skiss.text(39, (top + bottom) / 2, f'{_symbol("h")} = {_tal(h)}', anchor="middle", vertical=True)

    skiss.arrow(center, bottom + 20, bottom - 10)
    label = _symbol("F", "c,90,Ed")
    if kraft is not None:
        label += f" = {_tal(kraft)} kN"
    skiss.text(center, bottom - 25, label, anchor="middle", fill=_KRAFT)

    for x in (left, right):
        skiss.line(x, bottom + 2, x, 232, stroke=_LINJE)
    skiss.dim(start, stop, 207, f'{_symbol("l")} = {_tal(l)}', from_y=182)
    in_label = f'{_symbol("x", "in")} = {_tal(x_in)}'
    skiss.dim(stop, right, 207, in_label, size=13)
    if mitt:
        skiss.dim(left, start, 207, in_label, size=13)
    elif x_end > 0:
        skiss.dim(left, start, 207, f'{_symbol("x", "end")} = {_tal(x_end)}', size=13)
    skiss.dim(left, right, 232, f'{_symbol("l", "ef")} = {_tal(l_ef)}')
    if a == 0:
        skiss.text(beam, 260, f'{_symbol("a")} = 0 · {_symbol("x", "end")} = 0')
    elif a is not None:
        skiss.line(start, 207, start, 267, stroke=_LINJE)
        skiss.dim(beam, start, 267, f'{_symbol("a")} = {_tal(a)}')

    skiss.text(369, 216, "Tvärsnitt", anchor="middle", size=13)
    skiss.rect(349, 222, 40, 28, _TRA)
    skiss.rect(349, 244, 40, 6, _KONTAKT, stroke=_KONTAKT)
    skiss.dim(349, 389, 279, f'{_symbol("b")} = {_tal(b)}', from_y=251)

    skiss.rect(16, 297, 15, 9, _KONTAKT, stroke=_KONTAKT)
    skiss.text(38, 306, "Fysisk upplagsyta", size=13)
    skiss.rect(187, 297, 15, 9, _TILLAGG, stroke=_KONTAKT)
    skiss.text(209, 306, "Tillägg till effektiv längd", size=13)
    return skiss.svg()


def render_upplagsfall(values):
    """Visa var den koncentrerade kontaktkraften angriper i valt upplagsfall."""
    helt = values["upplagsfall"] == "understodd_barverksdel_dubbelsidig"
    title = "Helt understödd" if helt else "Diskret upplag"
    skiss = _Skiss(title, "Koncentrerad kontaktkraft vinkelrätt mot fiberriktningen.", 164)
    skiss.rect(54, 80, 332, 35, _TRA, part="virkesdel")
    if helt:
        skiss.rect(54, 115, 332, 13, _STOD, part="kontinuerligt-stod")
        skiss.rect(183, 80, 74, 6, _KONTAKT, stroke=_KONTAKT)
        skiss.arrow(220, 47, 79)
        skiss.text(232, 61, _symbol("F", "c,90,Ed"), fill=_KRAFT)
        skiss.text(220, 150, "Samma fall vid dubbelsidig belastning", anchor="middle", size=14)
    else:
        skiss.rect(183, 115, 74, 24, _STOD, part="diskret-stod")
        skiss.rect(183, 109, 74, 6, _KONTAKT, stroke=_KONTAKT)
        skiss.arrow(220, 134, 107)
        skiss.text(232, 103, _symbol("F", "c,90,Ed"), fill=_KRAFT)
        skiss.text(220, 154, "Kontaktkraft vid ett lokalt stöd", anchor="middle", size=14)
    return skiss.svg()
