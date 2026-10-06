"""Statisk PDF-export av grundplanens ritning och minimerade etiketter."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import io
import math
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
    whole = format(int(whole), ",").replace(",", "\N{NO-BREAK SPACE}")
    fraction = fraction.rstrip("0")
    return whole + ("," + fraction if fraction else "")


def _label(tag):
    lines = [(" ".join(tag["label"].split()), _BOLD, 13)]
    summary = tag.get("summary") if tag["status"] == "calculated" else None
    if summary:
        status = "ok" if summary["utnyttjandegrad"] <= 1 else "over"
        lines.append((f'U {_number(summary["utnyttjandegrad"] * 100, 1)}% · b {_number(summary["b"])} m', _REGULAR, 11))
        if summary.get("isolering"):
            lines.append(("Styrande: " + summary["styrande"], _REGULAR, 10))
    else:
        status = tag["status"] if tag["status"] in ("new", "stale", "error") else "new"
        text = {"new": "Ej beräknad", "stale": "Ändrad · beräkna", "error": "Kontrollera indata"}[status]
        lines.append((text, _REGULAR, 11))
    return lines, status


def _draw_labels(canvas, width, height, preview_size, tags, label_size):
    """Map normalized image positions and CSS label size into page coordinates."""
    _fonts()
    for tag in tags:
        lines, status = _label(tag)
        box_width = max(pdfmetrics.stringWidth(text, font, size) for text, font, size in lines) + 32
        box_height = 16 + sum(size * 1.3 for _, _, size in lines) + 2 * (len(lines) - 1)
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
        for text, font, size in lines:
            ascent, descent = pdfmetrics.getAscentDescent(font, size)
            baseline = top_of_line - (size * 1.3 - ascent + descent) / 2 - ascent
            canvas.setFont(font, size)
            canvas.drawString(20, baseline, text)
            top_of_line -= size * 1.3 + 2
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
