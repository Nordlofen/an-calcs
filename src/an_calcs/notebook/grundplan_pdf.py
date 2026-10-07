"""Statisk PDF-export av grundplanens ritning och minimerade etiketter."""

from decimal import Decimal, ROUND_HALF_UP
import io
import math
import re
from pathlib import Path

from PIL import Image, ImageOps
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter, Transformation
import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from .grundplan_labels import LOAD_GROUPS
from .grundplan_loads import line_loads, load_resultants
from .grundplan_sliding import contribution, project_results, DEFAULT_SETTINGS, DEFAULT_PLACEMENT
from .grundplan_colour import group_data, CATEGORIES, PHASES


_REGULAR = "Grundplan-Vera"
_BOLD = "Grundplan-Vera-Bold"
_ITALIC = "Grundplan-Vera-Italic"
_COLORS = {
    "new": ("#8da4aa", "#ffffff", "#7f969d"),
    "stale": ("#ac802f", "#fffbef", "#7f969d"),
    "error": ("#bc5750", "#fff8f6", "#b4443d"),
    "over": ("#bc5750", "#fff8f6", "#b4443d"),
    "ok": ("#319477", "#f4fcf8", "#238161"),
    "horizontal": ("#708999", "#f1f6fa", "#708999"),
}


def _fonts():
    # Bundled fonts make Swedish labels portable, with no OS font dependency.
    directory = Path(reportlab.__file__).parent / "fonts"
    for name, filename in ((_REGULAR, "Vera.ttf"), (_BOLD, "VeraBd.ttf"), (_ITALIC, "VeraIt.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(directory / filename)))


def _number(value, digits=2):
    if value != 0 and (abs(value) < 1e-6 or abs(value) >= 1e9):
        return format(value, ".2e").replace(".", ",")
    rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    whole, _, fraction = format(rounded, "f").partition(".")
    sign = "-" if rounded < 0 else ""
    whole = sign + format(abs(int(whole)), ",").replace(",", "\N{NO-BREAK SPACE}")
    fraction = fraction.rstrip("0")
    return whole + ("," + fraction if fraction else "")


def _text_parts(text, size):
    # Draw real lowered glyphs for dimensions and global coordinate indices.
    for part in re.split("([ₓᵧ]|[XY]_g|L_su)", text):
        if part in ("ₓ", "ᵧ"):
            yield {"ₓ": "x", "ᵧ": "y"}[part], size * .7, -size * .2
        elif part in ("X_g", "Y_g"):
            yield part[0], size, 0
            yield "g", size * .7, -size * .2
        elif part == "L_su":
            yield "L", size, 0
            yield "su", size * .7, -size * .2
        elif part:
            yield part, size, 0


def _text_width(text, font, size):
    return sum(pdfmetrics.stringWidth(part, font, pt) for part, pt, _ in _text_parts(text, size))


def _draw_text(canvas, x, y, text, font, size):
    for part, pt, offset in _text_parts(text, size):
        canvas.setFont(font, pt)
        canvas.drawString(x, y + offset, part)
        x += pdfmetrics.stringWidth(part, font, pt)


def _math_width(base, index, size):
    return pdfmetrics.stringWidth(base, _ITALIC, size) + pdfmetrics.stringWidth(index, _REGULAR, size * .65)


def _draw_math(canvas, x, y, base, index, size):
    canvas.setFont(_ITALIC, size)
    canvas.drawString(x, y, base)
    canvas.setFont(_REGULAR, size * .65)
    canvas.drawString(x + pdfmetrics.stringWidth(base, _ITALIC, size), y - size * .22, index)


def _sliding_rows(values):
    if values.get("isolering") or not (values.get("glid_x") or values.get("glid_y")):
        return [], []
    result = contribution(values)
    def value(name, unit):
        return "—" if values.get(name) is None else _number(values[name], 3) + " " + unit
    left = [("V", "Ed,EQU", value("V_Ed_EQU", "kN/m" if line_loads(values) else "kN"))]
    if values["lang"] == 1:
        left.append(("L", "su", value("glid_L", "m")))
    if line_loads(values) and values.get("L_vagg") is not None:
        left.append(("L", "vägg", value("L_vagg", "m")))
    right = [("H", axis + ",Rd,i", "—" if result[axis] is None else _number(result[axis], 1) + " kN")
             for axis in ("x", "y") if values.get("glid_" + axis)]
    return left, right


def _load_rows(values):
    if values.get("endast_h_stabilitet"):
        return []
    rows = []
    for group in LOAD_GROUPS:
        if group["label"] == "Bruk" and not values["isolering"]:
            continue
        caption, line = group["label"], ""
        for field in group["fields"]:
            value = values.get(field["name"])
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value == 0:
                continue
            number = (format(value, ".2e").replace(".", ",") if abs(value) < 1e-6 or abs(value) >= 1e9
                      else _number(value, 6))
            unit = field["unit"] + ("/m" if line_loads(values) else "")
            token = f'{field["symbol"]} {number} {unit}'
            if values["lang"] == 0 and line_loads(values) and field["name"] in ("F_vy", "F_vy_bruk"):
                total = load_resultants(values)["brott" if field["name"] == "F_vy" else "bruk"]
                token += " -> " + (_number(total, 3) + " kN" if total is not None else "—")
            candidate = line + "   " + token if line else token
            if line and _text_width(candidate, _REGULAR, 10) > 235:
                rows.append((caption, line))
                caption, line = "", token
            else:
                line = candidate
        if line:
            rows.append((caption, line))
    return rows


def _label(tag, sliding_enabled=False):
    lines = [(" ".join(tag["label"].split()), _BOLD, 13)]
    summary = tag.get("summary") if tag["status"] == "calculated" else None
    values = tag["values"]
    only_h = values.get("endast_h_stabilitet")
    if summary and only_h:
        status = "horizontal"
        lines.append(("Endast H-stabilitet", _REGULAR, 11))
    elif summary:
        status = "ok" if summary["utnyttjandegrad"] <= 1 else "over"
        geometry = (f'bₓ {_number(summary["b"])} m' if tag["values"]["lang"] == 1 and tag["values"]["l"] == 1
                    else f'{_number(summary["b"])} × {_number(tag["values"]["l"])} m')
        lines.append((f'U {_number(summary["utnyttjandegrad"] * 100, 1)} % · {geometry}', _REGULAR, 11))
        if summary.get("isolering"):
            lines.append(("Styrande: " + summary["styrande"], _REGULAR, 10))
    else:
        status = tag["status"] if tag["status"] in ("new", "stale", "error") else "new"
        text = {"new": "Ej beräknad", "stale": "Ändrad · beräkna", "error": "Kontrollera indata"}[status]
        lines.append((text, _REGULAR, 11))
    length = values.get("glid_L")
    sliding_block = (sliding_enabled or only_h) and not values.get("isolering") and (values.get("glid_x") or values.get("glid_y"))
    if (values["lang"] == 1 and isinstance(length, (int, float)) and not isinstance(length, bool)
            and math.isfinite(length) and length > 0 and not sliding_block
            and not values.get("isolering") and (values.get("glid_x") or values.get("glid_y"))):
        text, font, size = lines[1]
        lines[1] = (text + " · L_su " + _number(length, 6) + " m", font, size)
    return lines, status


def _draw_insulation(canvas, left, top, insulated, background):
    """Vector equivalent of the widget icon; only the insulation is struck out."""
    canvas.saveState()
    canvas.translate(left, top)
    canvas.scale(22 / 104, -22 / 104)
    canvas.setDash()
    canvas.setStrokeColor(HexColor("#244951"))
    canvas.setFillColor(HexColor("#eef3f3"))
    canvas.setLineWidth(3)
    canvas.rect(10, 3, 84, 22, stroke=1, fill=1)
    canvas.setLineWidth(2.5)
    canvas.rect(10, 31, 84, 20, stroke=1, fill=0)
    canvas.setLineWidth(2)
    for start in range(0, 94, 14):
        a, b = max(start, 10), min(start + 20, 94)
        canvas.line(a, 51 - (a - start), b, 51 - (b - start))
    if not insulated:
        for color, width in ((background, 8), ("#244951", 3.5)):
            canvas.setStrokeColor(HexColor(color))
            canvas.setLineWidth(width)
            canvas.line(1, 56, 103, 30)
    canvas.restoreState()


def _draw_labels(canvas, width, height, preview_size, tags, label_size, sliding_enabled=False, colour_assignments=None):
    """Map normalized image positions and CSS label size into page coordinates."""
    _fonts()
    for tag in tags:
        lines, status = _label(tag, sliding_enabled)
        insulated = tag["values"]["isolering"]
        insulation_text = "Med isolering" if insulated else "Utan isolering"
        heading_width = _text_width(*lines[0])
        header_width = heading_width + 6 + 22 + 5 + pdfmetrics.stringWidth(insulation_text, _REGULAR, 9)
        has_comment = bool(tag["values"].get("kommentar", "").strip())
        if has_comment:
            header_width += 24
        loads = _load_rows(tag["values"])
        load_width = max((38 + _text_width(text, _REGULAR, 10) for _, text in loads), default=0)
        box_width = max(header_width, load_width, *(_text_width(*line) for line in lines[1:])) + 32
        box_height = 16 + sum(size * 1.3 for _, _, size in lines) + 2 * (len(lines) - 1)
        if loads:
            box_height += 8 + 14 * len(loads)
        slide_left, slide_right = _sliding_rows(tag["values"]) if sliding_enabled or tag["values"].get("endast_h_stabilitet") else ([], [])
        slide_size = 8.2
        if slide_left:
            left_symbols = max(_math_width(base, index, slide_size) for base, index, _ in slide_left)
            right_symbols = max(_math_width(base, index, slide_size) for base, index, _ in slide_right)
            left_width = left_symbols + 8 + max(_text_width(value, _REGULAR, slide_size) for _, _, value in slide_left)
            right_width = right_symbols + 8 + max(_text_width(value, _BOLD, slide_size) for _, _, value in slide_right)
            box_width = max(box_width, 20 + left_width + 16 + right_width + 12)
            box_height += 24 + 12 * max(len(slide_left), len(slide_right))
        # The drawing and labels share zoom in the widget. Export uses their
        # saved ratio, independent of current viewport zoom or pan.
        scale = label_size / 100 * min(width / preview_size[0], height / preview_size[1])
        scale = min(scale, width / box_width, height / box_height)
        left = tag["x"] * width - 10 * scale
        top = tag["y"] * height - 10 * scale
        # Keep labels near the drawing edge readable on the printed page.
        left = min(max(0, left), width - box_width * scale)
        top = min(max(0, top), height - box_height * scale)
        border, background, dot = _COLORS[status]
        if colour_assignments and tag["id"] in colour_assignments:
            background = colour_assignments[tag["id"]]["background"]
        canvas.saveState()
        canvas.translate(left, height - top)
        canvas.scale(scale, scale)
        canvas.setStrokeColor(HexColor(border))
        canvas.setFillColor(HexColor(background))
        canvas.setLineWidth(1)
        if status == "stale":
            canvas.setDash(3, 2)
        canvas.roundRect(0.5, -box_height + 0.5, box_width - 1, box_height - 1, 7, stroke=1, fill=1)
        canvas.setFillColor(HexColor(dot))
        canvas.circle(10.5, -14.5, 3.5, stroke=0, fill=1)
        canvas.setFillColor(HexColor("#18333b"))
        top_of_line = -8
        for index, (text, font, size) in enumerate(lines):
            ascent, descent = pdfmetrics.getAscentDescent(font, size)
            baseline = top_of_line - (size * 1.3 - ascent + descent) / 2 - ascent
            _draw_text(canvas, 20, baseline, text, font, size)
            if index == 0:
                icon_left = 20 + heading_width + 6
                _draw_insulation(canvas, icon_left, top_of_line - (size * 1.3 - 13) / 2, insulated, background)
                # Center the smaller caption on the heading's line box.
                ascent, descent = pdfmetrics.getAscentDescent(_REGULAR, 9)
                caption_baseline = top_of_line - (size * 1.3 - ascent + descent) / 2 - ascent
                canvas.setFillColor(HexColor("#58717a"))
                canvas.setFont(_REGULAR, 9)
                canvas.drawString(icon_left + 22 + 5, caption_baseline, insulation_text)
                canvas.setFillColor(HexColor("#18333b"))
                if has_comment:
                    x, y = box_width - 27, -11
                    canvas.setStrokeColor(HexColor("#19343d"))
                    canvas.setLineWidth(.9)
                    path = canvas.beginPath()
                    path.moveTo(x + 2, y)
                    path.lineTo(x + 15, y); path.lineTo(x + 15, y - 10)
                    path.lineTo(x + 6, y - 10); path.lineTo(x + 2, y - 13)
                    path.lineTo(x + 2, y - 10); path.lineTo(x, y - 10)
                    path.lineTo(x, y); path.close()
                    canvas.drawPath(path, stroke=1, fill=0)
                    for dx in (4, 7.5, 11):
                        canvas.circle(x + dx, y - 5, .6, stroke=0, fill=1)
            top_of_line -= size * 1.3 + 2
        if loads:
            canvas.setDash()
            canvas.setStrokeColor(HexColor("#d4e0e1"))
            canvas.setLineWidth(.6)
            canvas.line(20, top_of_line - 2, box_width - 12, top_of_line - 2)
            top_of_line -= 16
            for caption, text in loads:
                canvas.setFillColor(HexColor("#58717a"))
                _draw_text(canvas, 20, top_of_line, caption, _BOLD, 10)
                canvas.setFillColor(HexColor("#18333b"))
                _draw_text(canvas, 58, top_of_line, text, _REGULAR, 10)
                top_of_line -= 14
        if slide_left:
            canvas.setDash()
            canvas.setStrokeColor(HexColor("#d4e0e1"))
            canvas.setLineWidth(.6)
            canvas.line(20, top_of_line + 4, box_width - 12, top_of_line + 4)
            canvas.setFillColor(HexColor("#58717a"))
            _draw_text(canvas, 20, top_of_line - 9, "Glidmotstånd – globalt", _BOLD, 9)
            canvas.setFillColor(HexColor("#18333b"))
            for rows, x, symbols, font in ((slide_left, 20, left_symbols, _REGULAR),
                                          (slide_right, 20 + left_width + 16, right_symbols, _BOLD)):
                for i, (base, index, value) in enumerate(rows):
                    y = top_of_line - 23 - i * 12
                    _draw_math(canvas, x, y, base, index, slide_size)
                    _draw_text(canvas, x + symbols + 8, y, value, font, slide_size)
        canvas.restoreState()


def _draw_project_overlays(canvas, width, height, preview_size, page, settings, results):
    if not settings["enabled"]:
        return
    _fonts()
    placement = settings["placements"].get(str(page), {})
    symbol = placement.get("symbol", DEFAULT_PLACEMENT["symbol"])
    image_scale = min(width / preview_size[0], height / preview_size[1])
    size = symbol["size"] * image_scale
    left = min(symbol["x"] * width, max(0, width - size))
    top = min(symbol["y"] * height, max(0, height - size))
    canvas.saveState()
    canvas.translate(left, height - top)
    canvas.scale(size / 200, size / 200)
    canvas.setStrokeColor(HexColor("#19343d"))
    canvas.setFillColor(HexColor("#19343d"))
    canvas.setLineWidth(3)
    canvas.line(32, -156, 158, -156)
    canvas.line(32, -156, 32, -36)
    for points in (((158, -156), (147, -151), (147, -161)), ((32, -36), (27, -47), (37, -47))):
        path = canvas.beginPath()
        path.moveTo(*points[0])
        for point in points[1:]: path.lineTo(*point)
        path.close()
        canvas.drawPath(path, stroke=0, fill=1)
    canvas.setFillColor(HexColor("#ffffff"))
    canvas.setLineWidth(2)
    canvas.circle(32, -156, 4, stroke=1, fill=1)
    canvas.setFillColor(HexColor("#19343d"))
    _draw_math(canvas, 168, -163, "X", "g", 22)
    _draw_math(canvas, 24, -24, "Y", "g", 22)
    canvas.restoreState()

    axes = [axis for axis in ("x", "y") if settings["check_" + axis]]
    box_width, box_height = 410, 88 + 46 * len(axes)
    legend = placement.get("legend", DEFAULT_PLACEMENT["legend"])
    scale = min(image_scale * legend.get("size", 410) / 410, width / box_width, height / box_height)
    left = min(legend["x"] * width, max(0, width - box_width * scale))
    top = min(legend["y"] * height, max(0, height - box_height * scale))
    canvas.saveState()
    canvas.translate(left, height - top)
    canvas.scale(scale, scale)
    canvas.setFillColor(HexColor("#ffffff"))
    canvas.setStrokeColor(HexColor("#9fbbbf"))
    canvas.setLineWidth(1)
    canvas.roundRect(0, -box_height, box_width, box_height, 8, stroke=1, fill=1)
    canvas.setFillColor(HexColor("#19343d"))
    _draw_text(canvas, 14, -25, "Glidningskontroll", _BOLD, 15)
    canvas.setFillColor(HexColor("#58717a"))
    _draw_text(canvas, 14, -41, "X och Y kontrolleras var för sig", _REGULAR, 10)
    if axes:
        for x, caption in ((14, "Riktning"), (85, "Lasteffekt"), (185, "Motstånd"), (288, "U"), (366, "Sulor*")):
            _draw_text(canvas, x, -63, caption, _REGULAR, 9)
        for i, axis in enumerate(axes):
            r, y = results[axis], -80 - i * 46
            color = {"ok": "#1e8063", "over": "#b6443f", "incomplete": "#94691f"}[r["status"]]
            canvas.setStrokeColor(HexColor("#d4e0e1"))
            canvas.line(14, y + 8, box_width - 14, y + 8)
            canvas.setFillColor(HexColor(color))
            _draw_math(canvas, 14, y - 12, axis.upper(), "g", 13)
            for x, name, suffix in ((85, "H_Ed", "Ed"), (185, "H_Rd", "Rd")):
                canvas.setFillColor(HexColor("#58717a"))
                _draw_math(canvas, x, y, "H", axis + "," + suffix, 10)
                canvas.setFillColor(HexColor("#19343d"))
                _draw_text(canvas, x, y - 18, "—" if r[name] is None else _number(r[name], 1 if name == "H_Rd" else 2) + " kN", _BOLD, 10)
            canvas.setFillColor(HexColor(color))
            use = "—" if r["status"] == "incomplete" else "∞" if r["utilization"] is None else _number(r["utilization"] * 100, 1) + " %"
            _draw_text(canvas, 288, y, use, _BOLD, 12)
            _draw_text(canvas, 288, y - 17, {"ok": "Godkänd", "over": "Överskriden", "incomplete": "Ofullständig"}[r["status"]], _REGULAR, 8)
            canvas.setFillColor(HexColor("#19343d"))
            _draw_text(canvas, 376, y - 12, str(r["count"]), _BOLD, 12)
        canvas.setFillColor(HexColor("#58717a"))
        _draw_text(canvas, 14, -box_height + 12, "* Sulor med positivt bidrag i respektive riktning.", _REGULAR, 9)
    else:
        _draw_text(canvas, 14, -65, "Ingen global riktning vald.", _REGULAR, 11)
    canvas.restoreState()


def _page_geometry(page):
    """Visible page size and transform back into the original PDF coordinate system.

    Keeping /Rotate and all original page boxes avoids moving existing page
    annotations. The overlay is counter-rotated into the page's own coordinates.
    """
    media, crop = page.mediabox, page.cropbox
    left = max(float(media.left), float(crop.left))
    bottom = max(float(media.bottom), float(crop.bottom))
    right = min(float(media.right), float(crop.right))
    top = min(float(media.top), float(crop.top))
    width, height = right - left, top - bottom
    if not all(math.isfinite(value) for value in (left, bottom, right, top)) or min(width, height) <= 0:
        raise ValueError("PDF-sidan har ogiltiga mått.")
    rotation = page.rotation % 360
    matrices = {
        0: (1, 0, 0, 1, left, bottom),
        90: (0, 1, -1, 0, right, bottom),
        180: (-1, 0, 0, -1, right, top),
        270: (0, -1, 1, 0, left, top),
    }
    if rotation not in matrices:
        raise ValueError("PDF-sidans rotation måste vara en multipel av 90 grader.")
    if rotation in (90, 270):
        width, height = height, width
    return width, height, Transformation(matrices[rotation])


def _colour_caption(group):
    if group.get("label"):
        return group["label"]
    if group["kind"] == "geometry":
        return _number(group["value"], 6) + " m"
    if group["low"] is None:
        return "V < " + _number(group["high"], 6)
    if group["high"] is None:
        return "V ≥ " + _number(group["low"], 6)
    return _number(group["low"], 6) + " ≤ V < " + _number(group["high"], 6)


def _draw_colour_legend(canvas, width, height, preview_size, settings, groups):
    if not settings or not settings["enabled"] or not settings["show_legend"]:
        return
    _fonts()
    rows = []
    previous_kind = None
    for group in groups:
        if group["count"] <= 0:
            continue
        if settings["category"] == "V" and group["kind"] != previous_kind and group["kind"] in ("pad", "wall"):
            rows.append(("heading", "Linjelaster [kN/m]" if group["kind"] == "wall" else "Totala laster [kN]"))
        previous_kind = group["kind"]
        if group["kind"] == "combination":
            caption = [({"t": "t ", "b": "bₓ ", "l": "bᵧ "}.get(category, "") + _colour_caption(part)
                        + (" " + part["unit"] if part["kind"] in ("pad", "wall") else ""))
                       for category, part in zip(group["categories"], group["parts"])]
        else:
            caption = [_colour_caption(group)]
        rows.append(("group", (caption, group)))
    combined = bool(settings.get("secondary"))
    box_width, box_height = 300, 76 + (15 if combined else 0) + sum(28 if kind == "heading" else 28 + 14 * (len(data[0]) - 1) for kind, data in rows)
    legend = settings["legend"]
    scale = min(min(width / preview_size[0], height / preview_size[1]) * legend["size"] / 300,
                width / box_width, height / box_height)
    left = min(legend["x"] * width, max(0, width - box_width * scale))
    top = min(legend["y"] * height, max(0, height - box_height * scale))
    canvas.saveState()
    canvas.translate(left, height - top)
    canvas.scale(scale, scale)
    canvas.setFillColor(HexColor("#ffffff"))
    canvas.setStrokeColor(HexColor("#9fbbbf"))
    canvas.setLineWidth(1)
    canvas.roundRect(0, -box_height, box_width, box_height, 8, stroke=1, fill=1)
    canvas.setFillColor(HexColor("#19343d"))
    _draw_text(canvas, 14, -25, "Färggruppering", _BOLD, 15)
    caption = ("Isolering och glidmotstånd" if settings["category"] == "isolering" else
               CATEGORIES[settings["category"]] + (" · " + PHASES[settings["phase"]] if settings["category"] == "V" else " [m]"))
    if combined:
        caption = CATEGORIES[settings["category"]]
    _draw_text(canvas, 14, -44, caption, _REGULAR, 12)
    if combined:
        subtitle = "+ " + CATEGORIES[settings["secondary"]]
        if "V" in (settings["category"], settings["secondary"]):
            subtitle += " · " + PHASES[settings["phase"]]
        _draw_text(canvas, 14, -59, subtitle, _REGULAR, 12)
    y = -66 - (15 if combined else 0)
    for kind, data in rows:
        if kind == "heading":
            canvas.setFillColor(HexColor("#58717a"))
            _draw_text(canvas, 14, y - 7, data, _BOLD, 11)
        else:
            caption, group = data
            canvas.setFillColor(HexColor(group["background"]))
            canvas.setStrokeColor(HexColor("#b9cdd1"))
            canvas.roundRect(14, y - 14, 26, 21, 3, stroke=1, fill=1)
            canvas.setFillColor(HexColor("#19343d"))
            # Keep long decimal interval labels inside the legend.
            for i, line in enumerate(caption):
                size = min(12, 12 * 214 / max(214, _text_width(line, _REGULAR, 12)))
                _draw_text(canvas, 48, y - 7 - 14 * i, line, _REGULAR, size)
            canvas.setFillColor(HexColor("#58717a"))
            canvas.setFont(_REGULAR, 11)
            canvas.drawRightString(286, y - 7, str(group["count"]))
        y -= 28 + (14 * (len(caption) - 1) if kind != "heading" else 0)
    canvas.setFillColor(HexColor("#58717a"))
    _draw_text(canvas, 14, -box_height + 12, "Antal sulor visas till höger.", _REGULAR, 10)
    canvas.restoreState()


def _draw_insulation_widget(canvas, width, height, preview_size, settings, tags):
    if not settings or not settings["enabled"]:
        return
    _fonts()
    uninsulated = [tag for tag in tags if tag["values"].get("endast_h_stabilitet") or not tag["values"].get("isolering")]
    labels = sorted((" ".join(tag["label"].split()) for tag in uninsulated),
                    key=lambda text: tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                                           for part in re.split(r"(\d+)", text)))
    text = ", ".join(labels) or "Inga sulor"
    lines, line = [], ""
    # Wrap long support IDs as well as lists of ordinary littera.
    for word in text.split():
        if line and _text_width(line + " " + word, _REGULAR, 11) > 272:
            lines.append(line); line = ""
        for character in (" " if line else "") + word:
            if _text_width(line + character, _REGULAR, 11) > 272:
                lines.append(line); line = ""
            line += character
    if line:
        lines.append(line)
    box_width, box_height = 300, 112 + 16 * len(lines)
    scale = min(min(width / preview_size[0], height / preview_size[1]) * settings["size"] / 300,
                width / box_width, height / box_height)
    left = min(settings["x"] * width, max(0, width - box_width * scale))
    top = min(settings["y"] * height, max(0, height - box_height * scale))
    canvas.saveState(); canvas.translate(left, height - top); canvas.scale(scale, scale)
    canvas.setFillColor(HexColor("#ffffff")); canvas.setStrokeColor(HexColor("#9fbbbf")); canvas.setLineWidth(1)
    canvas.roundRect(0, -box_height, box_width, box_height, 8, stroke=1, fill=1)
    canvas.setFillColor(HexColor("#19343d")); _draw_text(canvas, 14, -25, "Isolering", _BOLD, 15)
    for y, caption, count in ((-49, "Med isolering", len(tags) - len(uninsulated)), (-71, "Utan isolering", len(uninsulated))):
        _draw_text(canvas, 14, y, caption, _REGULAR, 12)
        canvas.setFont(_BOLD, 12); canvas.drawRightString(286, y, str(count))
    canvas.setStrokeColor(HexColor("#d4e0e1")); canvas.line(14, -82, 286, -82)
    _draw_text(canvas, 14, -101, "Föreskrivna utan isolering", _BOLD, 11)
    for i, line in enumerate(lines):
        _draw_text(canvas, 14, -119 - i * 16, line, _REGULAR, 11)
    canvas.restoreState()


def _draw_comment_widget(canvas, width, height, preview_size, settings, tags):
    if not settings or not settings["enabled"]:
        return
    _fonts()
    def wrapped(text, font, available):
        lines = []
        for paragraph in text.split("\n"):
            line = ""
            for character in paragraph:
                if line and pdfmetrics.stringWidth(line + character, font, 11) > available:
                    boundary = line.rfind(" ")
                    if boundary > 0:
                        lines.append(line[:boundary]); line = line[boundary + 1:]
                    else:
                        lines.append(line); line = ""
                line += character
            lines.append(line)
        return lines
    tags = sorted((tag for tag in tags if tag["values"].get("kommentar", "").strip()),
                  key=lambda tag: tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                                        for part in re.split(r"(\d+)", tag["label"])))
    rows = [(wrapped(tag["label"], _BOLD, 76), wrapped(tag["values"]["kommentar"].strip(), _REGULAR, 290))
            for tag in tags]
    box_width, box_height = 410, 82 + sum(14 * max(len(label), len(comment)) + 14 for label, comment in rows) if rows else 58
    scale = min(min(width / preview_size[0], height / preview_size[1]) * settings["size"] / 410,
                width / box_width, height / box_height)
    left = min(settings["x"] * width, max(0, width - box_width * scale))
    top = min(settings["y"] * height, max(0, height - box_height * scale))
    canvas.saveState(); canvas.translate(left, height - top); canvas.scale(scale, scale)
    canvas.setFillColor(HexColor("#ffffff")); canvas.setStrokeColor(HexColor("#9fbbbf")); canvas.setLineWidth(1)
    canvas.roundRect(0, -box_height, box_width, box_height, 8, stroke=1, fill=1)
    canvas.setFillColor(HexColor("#19343d")); canvas.setFont(_BOLD, 15); canvas.drawString(14, -25, "Kommentarer")
    canvas.setFillColor(HexColor("#58717a")); canvas.setFont(_REGULAR, 10)
    caption = (f"{len(rows)} sula med kommentar" if len(rows) == 1 else f"{len(rows)} sulor med kommentarer") if rows else "Inga sulor med kommentarer"
    canvas.drawString(14, -44, caption)
    if rows:
        canvas.setFont(_BOLD, 10); canvas.drawString(18, -65, "Littera"); canvas.drawString(102, -65, "Kommentar")
        y = 75
        for labels, comments in rows:
            canvas.setStrokeColor(HexColor("#d4e0e1")); canvas.line(14, -y, 396, -y)
            canvas.setFillColor(HexColor("#19343d"))
            for x, lines, font in ((18, labels, _BOLD), (102, comments, _REGULAR)):
                canvas.setFont(font, 11)
                for index, line in enumerate(lines):
                    canvas.drawString(x, -y - 17 - index * 14, line)
            y += 14 * max(len(labels), len(comments)) + 14
    canvas.restoreState()


def _draw_text_objects(canvas, width, height, preview_size, objects):
    if not objects:
        return
    _fonts()
    image_scale = min(width / preview_size[0], height / preview_size[1])
    def wrapped(text, font, size, width, spacing=0):
        if not text:
            return []
        lines = []
        for paragraph in text.split("\n"):
            line = ""
            for character in paragraph:
                candidate = line + character
                if line and pdfmetrics.stringWidth(candidate, font, size) + spacing * (len(candidate) - 1) > width:
                    boundary = line.rfind(" ")
                    if boundary > 0:
                        lines.append(line[:boundary]); line = line[boundary + 1:]
                    else:
                        lines.append(line); line = ""
                line += character
            lines.append(line)
        return lines

    def draw_lines(lines, font, size, top, color, spacing=0):
        canvas.setFillColor(HexColor(color))
        for index, line in enumerate(lines):
            text = canvas.beginText(4, -top - size * 1.12 - size * 1.45 * index)
            text.setFont(font, size); text.setCharSpace(spacing); text.textOut(line)
            canvas.drawText(text)

    for item in objects:
        heading = item["kind"] == "heading"
        font, spacing = (_BOLD, -.5) if heading else (_REGULAR, 0)
        wrap_width = item.get("width", 420) - 8
        lines = wrapped(item["text"], font, 20, wrap_width, spacing)
        subtitles = wrapped(item.get("subtitle", ""), _REGULAR, 13, wrap_width) if heading else []
        scale = image_scale * item["size"] / 20
        canvas.saveState()
        canvas.translate(item["x"] * width, height - item["y"] * height)
        canvas.scale(scale, scale)
        draw_lines(lines, font, 20, 4, "#18333b", spacing)
        draw_lines(subtitles, _REGULAR, 13, 4 + 29 * len(lines) + 3, "#58717a")
        canvas.restoreState()


def render_pdf(source, tags, label_size, title, sliding=None, *, page_number=1, colour_grouping=None, insulation_widget=None, comment_widget=None, text_objects=None):
    """Return the selected drawing page with static label overlays."""
    if not source:
        raise ValueError("Öppna en ritning först.")
    tags = [tag for tag in tags if tag["page"] == page_number]
    writer = PdfWriter()
    settings = sliding or DEFAULT_SETTINGS
    results = project_results(tags, settings)
    coloured = group_data(tags, colour_grouping) if colour_grouping and colour_grouping["enabled"] else None
    if source.startswith(b"%PDF-"):
        reader = PdfReader(io.BytesIO(source))
        if isinstance(page_number, bool) or not isinstance(page_number, int) or not 1 <= page_number <= len(reader.pages):
            raise ValueError("Ritningssidan finns inte i PDF-filen.")
        page = writer.add_page(reader.pages[page_number - 1])
        if (tags or settings["enabled"] or coloured is not None or insulation_widget and insulation_widget["enabled"]
                or comment_widget and comment_widget["enabled"] or text_objects):
            with pdfium.PdfDocument(source) as document:
                width, height, transform = _page_geometry(page)
                preview_page = document[page_number - 1]
                try:
                    pw, ph = preview_page.get_size()
                finally:
                    preview_page.close()
                # Match _render_source/PDFium's rounding of the preview bitmap.
                preview_scale = min(2.0, 2800 / max(pw, ph))
                preview_size = (math.ceil(pw * preview_scale), math.ceil(ph * preview_scale))
                overlay = io.BytesIO()
                canvas = Canvas(overlay, pagesize=(width, height), pageCompression=1)
                _draw_labels(canvas, width, height, preview_size, tags, label_size, settings["enabled"], coloured and coloured["assignments"])
                _draw_project_overlays(canvas, width, height, preview_size, page_number, settings, results)
                _draw_colour_legend(canvas, width, height, preview_size, colour_grouping, coloured["groups"] if coloured else [])
                _draw_insulation_widget(canvas, width, height, preview_size, insulation_widget, tags)
                _draw_comment_widget(canvas, width, height, preview_size, comment_widget, tags)
                _draw_text_objects(canvas, width, height, preview_size, text_objects)
                canvas.showPage()
                canvas.save()
                page.merge_transformed_page(PdfReader(overlay).pages[0], transform, over=True, expand=False)
    else:
        if type(page_number) is not int or page_number != 1:
            raise ValueError("En bild har endast en ritningssida.")
        with Image.open(io.BytesIO(source)) as original:
            rgba = ImageOps.exif_transpose(original).convert("RGBA")
            picture = Image.new("RGBA", rgba.size, "white")
            picture.alpha_composite(rgba)
            picture = picture.convert("RGB")
        # Raster drawings have no known drawing scale; use 96 dpi for page size.
        width, height = picture.width * 72 / 96, picture.height * 72 / 96
        preview = picture.copy()
        preview.thumbnail((2800, 2800))
        stream = io.BytesIO()
        canvas = Canvas(stream, pagesize=(width, height), pageCompression=1)
        canvas.drawImage(ImageReader(picture), 0, 0, width, height)
        _draw_labels(canvas, width, height, preview.size, tags, label_size, settings["enabled"], coloured and coloured["assignments"])
        _draw_project_overlays(canvas, width, height, preview.size, 1, settings, results)
        _draw_colour_legend(canvas, width, height, preview.size, colour_grouping, coloured["groups"] if coloured else [])
        _draw_insulation_widget(canvas, width, height, preview.size, insulation_widget, tags)
        _draw_comment_widget(canvas, width, height, preview.size, comment_widget, tags)
        _draw_text_objects(canvas, width, height, preview.size, text_objects)
        canvas.showPage()
        canvas.save()
        writer.add_page(PdfReader(stream).pages[0])
    writer.add_metadata({"/Title": title, "/Creator": "an-calcs Grundplan"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
