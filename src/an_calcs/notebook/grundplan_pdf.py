"""Statisk PDF-export av grundplanens ritning och minimerade etiketter."""

from collections import defaultdict
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


_REGULAR = "Grundplan-Vera"
_BOLD = "Grundplan-Vera-Bold"
_COLORS = {
    "new": ("#8da4aa", "#ffffff", "#7f969d"),
    "stale": ("#ac802f", "#fffbef", "#7f969d"),
    "error": ("#bc5750", "#fff8f6", "#b4443d"),
    "over": ("#bc5750", "#fff8f6", "#b4443d"),
    "ok": ("#319477", "#f4fcf8", "#238161"),
}


def _fonts():
    # Bundled fonts make Swedish labels portable, with no OS font dependency.
    directory = Path(reportlab.__file__).parent / "fonts"
    for name, filename in ((_REGULAR, "Vera.ttf"), (_BOLD, "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(directory / filename)))


def _number(value, digits=2):
    rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    whole, _, fraction = format(rounded, "f").partition(".")
    sign = "-" if rounded < 0 else ""
    whole = sign + format(abs(int(whole)), ",").replace(",", "\N{NO-BREAK SPACE}")
    fraction = fraction.rstrip("0")
    return whole + ("," + fraction if fraction else "")


def _text_parts(text, size):
    # The bundled font has no Unicode subscript x/y. Draw real lowered glyphs.
    for part in re.split("([ₓᵧ])", text):
        if part in ("ₓ", "ᵧ"):
            yield {"ₓ": "x", "ᵧ": "y"}[part], size * .7, -size * .2
        elif part:
            yield part, size, 0


def _text_width(text, font, size):
    return sum(pdfmetrics.stringWidth(part, font, pt) for part, pt, _ in _text_parts(text, size))


def _draw_text(canvas, x, y, text, font, size):
    for part, pt, offset in _text_parts(text, size):
        canvas.setFont(font, pt)
        canvas.drawString(x, y + offset, part)
        x += pdfmetrics.stringWidth(part, font, pt)


def _load_rows(values):
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
            unit = field["unit"] + ("/m" if values["lang"] == 1 else "")
            token = f'{field["symbol"]} {number} {unit}'
            candidate = line + "   " + token if line else token
            if line and _text_width(candidate, _REGULAR, 10) > 235:
                rows.append((caption, line))
                caption, line = "", token
            else:
                line = candidate
        if line:
            rows.append((caption, line))
    return rows


def _label(tag):
    lines = [(" ".join(tag["label"].split()), _BOLD, 13)]
    summary = tag.get("summary") if tag["status"] == "calculated" else None
    if summary:
        status = "ok" if summary["utnyttjandegrad"] <= 1 else "over"
        geometry = (f'bₓ {_number(summary["b"])} m' if tag["values"]["lang"] == 1
                    else f'{_number(summary["b"])} × {_number(tag["values"]["l"])} m')
        lines.append((f'U {_number(summary["utnyttjandegrad"] * 100, 1)} % · {geometry}', _REGULAR, 11))
        if summary.get("isolering"):
            lines.append(("Styrande: " + summary["styrande"], _REGULAR, 10))
    else:
        status = tag["status"] if tag["status"] in ("new", "stale", "error") else "new"
        text = {"new": "Ej beräknad", "stale": "Ändrad · beräkna", "error": "Kontrollera indata"}[status]
        lines.append((text, _REGULAR, 11))
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


def _draw_labels(canvas, width, height, preview_size, tags, label_size):
    """Map normalized image positions and CSS label size into page coordinates."""
    _fonts()
    for tag in tags:
        lines, status = _label(tag)
        insulated = tag["values"]["isolering"]
        insulation_text = "Med isolering" if insulated else "Utan isolering"
        heading_width = _text_width(*lines[0])
        header_width = heading_width + 6 + 22 + 5 + pdfmetrics.stringWidth(insulation_text, _REGULAR, 9)
        loads = _load_rows(tag["values"])
        load_width = max((38 + _text_width(text, _REGULAR, 10) for _, text in loads), default=0)
        box_width = max(header_width, load_width, *(_text_width(*line) for line in lines[1:])) + 32
        box_height = 16 + sum(size * 1.3 for _, _, size in lines) + 2 * (len(lines) - 1)
        if loads:
            box_height += 8 + 14 * len(loads)
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


def render_pdf(source, tags, label_size, title):
    """Return a PDF containing every original page with static label overlays."""
    if not source:
        raise ValueError("Öppna en ritning först.")
    by_page = defaultdict(list)
    for tag in tags:
        by_page[tag["page"]].append(tag)
    writer = PdfWriter()
    if source.startswith(b"%PDF-"):
        reader = PdfReader(io.BytesIO(source))
        with pdfium.PdfDocument(source) as document:
            for index, original in enumerate(reader.pages):
                page = writer.add_page(original)
                if not by_page[index + 1]:
                    continue
                width, height, transform = _page_geometry(page)
                preview_page = document[index]
                try:
                    pw, ph = preview_page.get_size()
                finally:
                    preview_page.close()
                # Match _render_source/PDFium's rounding of the preview bitmap.
                preview_scale = min(2.0, 2800 / max(pw, ph))
                preview_size = (math.ceil(pw * preview_scale), math.ceil(ph * preview_scale))
                overlay = io.BytesIO()
                canvas = Canvas(overlay, pagesize=(width, height), pageCompression=1)
                _draw_labels(canvas, width, height, preview_size, by_page[index + 1], label_size)
                canvas.showPage()
                canvas.save()
                page.merge_transformed_page(PdfReader(overlay).pages[0], transform, over=True, expand=False)
    else:
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
        _draw_labels(canvas, width, height, preview.size, by_page[1], label_size)
        canvas.showPage()
        canvas.save()
        writer.add_page(PdfReader(stream).pages[0])
    writer.add_metadata({"/Title": title, "/Creator": "an-calcs Grundplan"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
