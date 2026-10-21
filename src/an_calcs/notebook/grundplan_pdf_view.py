"""Self-contained vector underlay, using the established preview coordinate frame."""

import base64
import xml.etree.ElementTree as ET


_SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", _SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def svg_preview(data, page, width, height):
    """Keep paths/glyph outlines, while matching the former PNG's exact dimensions.

    The SVG viewBox remains in PDF page units, including CropBox and rotation.
    Pixel dimensions are only the legacy layout frame, not a rendering limit.
    No source SVG or PDF scripts are injected into the notebook DOM: this is
    generated page artwork displayed as an image with embedded image resources.
    """
    try:
        import pymupdf
    except ImportError as exc:
        raise ImportError("Vektorvisning av PDF kräver PyMuPDF. Uppdatera an-calcs[notebook] och starta om kerneln.") from exc
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            svg = ET.fromstring(document[page - 1].get_svg_image(text_as_path=True))
    except (ValueError, RuntimeError, ET.ParseError) as exc:
        raise ValueError("PDF-sidans vektorvisning kunde inte skapas.") from exc
    svg.set("width", f"{width}px")
    svg.set("height", f"{height}px")
    svg.set("preserveAspectRatio", "none")
    # Match the previous RGB preview's white page, including transparent PDFs.
    svg.insert(0, ET.Element(f"{{{_SVG}}}rect", {"width": "100%", "height": "100%", "fill": "#fff"}))
    return "data:image/svg+xml;base64," + base64.b64encode(ET.tostring(svg, encoding="utf-8")).decode("ascii")
