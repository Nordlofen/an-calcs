"""PDF export: original drawing plus the shared HTML/CSS vector layout."""

import io
import math

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from .grundplan_labels import LOAD_GROUPS
from .grundplan_loads import load_resultants
from .grundplan_sliding import contribution, project_results, DEFAULT_SETTINGS
from .grundplan_canvas import DEFAULT_BOUNDS, validate_bounds
from .grundplan_objects import drawing_layout as validate_drawing_layout


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



def render_pdf(source, tags, label_size, title, sliding=None, *, page_number=1, colour_grouping=None, insulation_widget=None, comment_widget=None, reference_widget=None, text_objects=None, canvas_bounds=None, drawing_layout=None, object_layout=None):
    """Merge the shared HTML/CSS vector overlay onto the original drawing."""
    from .grundplan_pdf_browser import render_overlay
    from .grundplan_reference import group_data as reference_groups

    if not source:
        raise ValueError("Öppna en ritning först.")
    bounds = validate_bounds(DEFAULT_BOUNDS if canvas_bounds is None else canvas_bounds)
    cropped = bounds != DEFAULT_BOUNDS
    tags = [tag for tag in tags if tag["page"] == page_number]
    writer = PdfWriter()
    settings = sliding or DEFAULT_SETTINGS
    if source.startswith(b"%PDF-"):
        reader = PdfReader(io.BytesIO(source))
        if isinstance(page_number, bool) or not isinstance(page_number, int) or not 1 <= page_number <= len(reader.pages):
            raise ValueError("Ritningssidan finns inte i PDF-filen.")
        page = writer.add_page(reader.pages[page_number - 1])
        width, height, transform = _page_geometry(page)
        # Match the preview rounding used by _render_source, without rendering
        # or embedding the drawing bitmap in the browser's overlay.
        preview_scale = min(2.0, 2800 / max(width, height))
        preview_size = (math.ceil(width * preview_scale), math.ceil(height * preview_scale))
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
        canvas.showPage()
        canvas.save()
        page = writer.add_page(PdfReader(stream).pages[0])
        preview_size, transform = preview.size, Transformation()
    ru = validate_drawing_layout(drawing_layout or {}, {"width": preview_size[0], "height": preview_size[1], "width_pt": width, "height_pt": height})
    canvas_width, canvas_height = ru["canvas_width_pt"], ru["canvas_height_pt"]
    custom_underlay = (ru["x"] != 0 or ru["y"] != 0 or ru["scale"] != 1
                       or ru["canvas_width"] != preview_size[0] or ru["canvas_height"] != preview_size[1]
                       or canvas_width != width or canvas_height != height)
    cropped = cropped or custom_underlay
    if cropped:
        # Source PDF coordinates -> visible, unrotated page -> cropped page.
        # Keep the original vectors and annotations; never render the drawing.
        a, b, c, d, e, f = transform.ctm
        determinant = a * d - b * c
        inverse = (d / determinant, -b / determinant, -c / determinant, a / determinant,
                   (c * f - d * e) / determinant, (b * e - a * f) / determinant)
        sx = canvas_width / ru["canvas_width"] * preview_size[0] / width * ru["scale"]
        sy = canvas_height / ru["canvas_height"] * preview_size[1] / height * ru["scale"]
        source_transform = Transformation(inverse).scale(sx, sy).translate(
            (ru["x"] - bounds["left"]) * canvas_width,
            (bounds["bottom"] - ru["y"]) * canvas_height - height * sy)
        original = page
        crop_writer = PdfWriter()
        page = crop_writer.add_blank_page(width=canvas_width * (bounds["right"] - bounds["left"]),
                                          height=canvas_height * (bounds["bottom"] - bounds["top"]))
        page.merge_transformed_page(original, source_transform, over=True, expand=False)
        writer = crop_writer
    if (tags or settings["enabled"] or colour_grouping and colour_grouping["enabled"]
            or insulation_widget and insulation_widget["enabled"]
            or comment_widget and comment_widget["enabled"]
            or reference_widget and reference_widget["enabled"] or text_objects):
        # Hidden blank preview supplies dimensions only. The original page is
        # retained below the transparent overlay, including vector drawings.
        background = {"page": page_number, "width": ru["canvas_width"], "height": ru["canvas_height"],
                      "source_width": preview_size[0], "source_height": preview_size[1],
                      "url": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"}
        snapshot = {"page": page_number, "pages": [background],
                    "schema": {"fields": [], "load_groups": LOAD_GROUPS},
                    "state": {"title": title, "subtitle": "", "label_size": label_size,
                              "tags": [{**tag, "sliding": contribution(tag["values"]),
                                        "load_resultants": load_resultants(tag["values"])} for tag in tags],
                              "sliding": settings, "sliding_result": project_results(tags, settings),
                              "colour_grouping": colour_grouping, "insulation_widget": insulation_widget,
                              "comment_widget": comment_widget, "reference_widget": reference_widget,
                              "reference_data": reference_groups(tags), "text_objects": text_objects or [],
                              "canvas_bounds": bounds, "drawing_layout": ru, "object_layout": object_layout or {}}}
        overlay = PdfReader(io.BytesIO(render_overlay(snapshot))).pages[0]
        sx = canvas_width * (bounds["right"] - bounds["left"]) / float(overlay.mediabox.width)
        sy = canvas_height * (bounds["bottom"] - bounds["top"]) / float(overlay.mediabox.height)
        a, b, c, d, e, f = transform.ctm
        matrix = (sx, 0, 0, sy, 0, 0) if cropped else (sx * a, sx * b, sy * c, sy * d, e, f)
        page.merge_transformed_page(overlay, Transformation(matrix),
                                    over=True, expand=False)
    writer.add_metadata({"/Title": title, "/Creator": "an-calcs Grundplan"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
