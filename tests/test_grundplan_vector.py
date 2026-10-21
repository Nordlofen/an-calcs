import base64
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in
                   ('anywidget', 'PIL', 'pypdfium2', 'pymupdf', 'pypdf', 'reportlab'))
if HAS_NOTEBOOK:
    from PIL import Image, ImageChops
    import pypdfium2 as pdfium
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject
    from reportlab.pdfgen.canvas import Canvas
    from an_calcs.notebook import Grundplan
    from an_calcs.notebook.grundplan import _render_source

SVG = '{http://www.w3.org/2000/svg}'


@unittest.skipUnless(HAS_NOTEBOOK, 'Installera an-calcs[notebook].')
class TestGrundplanVector(unittest.TestCase):
    def drawing(self, size=(601.25, 401.5), *, rotation=0, crop=False):
        buffer = io.BytesIO(); canvas = Canvas(buffer, pagesize=size)
        canvas.setLineWidth(.15); canvas.line(40, 40, size[0]-40, size[1]-40)
        canvas.setFillColorRGB(1, 0, 0); canvas.rect(60, 70, 25, 20, fill=1, stroke=0)
        canvas.setFillColorRGB(0, 0, 0); canvas.setFont('Helvetica', 6)
        canvas.drawString(60, 120, 'VECTOR 123 ABC')
        canvas.showPage(); canvas.save()
        writer = PdfWriter(); page = writer.add_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
        if crop: page.cropbox = RectangleObject((25.25, 30.5, size[0]-35.25, size[1]-40.5))
        page.rotate(rotation); result = io.BytesIO(); writer.write(result); return result.getvalue()

    def svg(self, background):
        self.assertTrue(background['url'].startswith('data:image/svg+xml;base64,'))
        return ET.fromstring(base64.b64decode(background['url'].split(',', 1)[1]))

    def test_vectors_and_glyph_outlines_keep_exact_legacy_frame_without_bitmap_rendering(self):
        for size in ((601.25, 401.5), (3001.25, 2001.5)):
            for crop in (False, True):
                for rotation in (0, 90, 180, 270):
                    with self.subTest(size=size, crop=crop, rotation=rotation):
                        data = self.drawing(size, rotation=rotation, crop=crop)
                        with pdfium.PdfDocument(data) as document:
                            page = document[0]; width, height = page.get_size(); page.close()
                        scale = min(2, 2800 / max(width, height))
                        with patch.object(pdfium.PdfPage, 'render', side_effect=AssertionError('No rasterization')):
                            background = _render_source(data, 'drawing.pdf')
                        self.assertEqual((background['width'], background['height']),
                                         (math.ceil(width*scale), math.ceil(height*scale)))
                        self.assertEqual((background['width_pt'], background['height_pt']), (width, height))
                        svg = self.svg(background)
                        self.assertEqual((svg.get('width'), svg.get('height')),
                                         (f"{background['width']}px", f"{background['height']}px"))
                        self.assertEqual(svg.get('preserveAspectRatio'), 'none')
                        self.assertGreater(len(svg.findall('.//' + SVG + 'path')), 3)
                        self.assertTrue(svg.findall('.//' + SVG + 'use'), 'Text uses vector glyph outlines')
                        self.assertFalse(svg.findall('.//' + SVG + 'text'), 'No external font substitution')
                        self.assertFalse(svg.findall('.//' + SVG + 'image'), 'Vector source remains vector artwork')
                        self.assertEqual(svg[0].get('fill'), '#fff')

    def test_raster_input_keeps_existing_png_display(self):
        buffer = io.BytesIO(); Image.new('RGB', (800, 600), '#abcdef').save(buffer, format='PNG')
        background = _render_source(buffer.getvalue(), 'drawing.png')
        self.assertTrue(background['url'].startswith('data:image/png;base64,'))
        self.assertEqual((background['width'], background['height']), (800, 600))

    def test_old_project_reopens_as_vectors_without_moving_any_saved_object_or_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'drawing.pdf'; source.write_bytes(self.drawing(rotation=90, crop=True))
            plan = Grundplan(source); self.addCleanup(plan.close)
            ident = plan.lagg_till(.37, .61, indata={'b': 1.2, 't': .35})
            plan.ritningsunderlag = {'x': -.1, 'y': .08, 'scale': 1.4}
            plan.kalibrering = {'start': {'x': .1, 'y': .2}, 'end': {'x': .6, 'y': .2}, 'length_m': 10}
            plan.las_indata([ident]); plan.lagg_till_datum('26/10/21', x=.7, y=.12)
            before = copy.deepcopy(plan._document()); legacy = copy.deepcopy(before); legacy['version'] = 26
            self.assertNotIn('url', legacy['drawing'], 'Project stores original PDF, not display SVG or PNG')
            restored = Grundplan(); self.addCleanup(restored.close)
            restored._load_document(json.dumps(legacy).encode())
            self.assertEqual(restored._document(), before)
            self.assertEqual(restored.taggar, plan.taggar)
            self.assertEqual(restored.kalibrering, plan.kalibrering)
            self.assertEqual(restored.ritningsunderlag, plan.ritningsunderlag)
            self.svg(restored.background)

    def test_failed_vector_conversion_preserves_current_drawing_and_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'drawing.pdf'; source.write_bytes(self.drawing())
            plan = Grundplan(source); self.addCleanup(plan.close)
            plan.kalibrering = {'start': {'x': .1, 'y': .2}, 'end': {'x': .6, 'y': .2}, 'length_m': 10}
            before = copy.deepcopy((plan._document(), plan.background, plan.state))
            with patch('an_calcs.notebook.grundplan.svg_preview', side_effect=ValueError('Konverteringsfel')):
                with self.assertRaisesRegex(ValueError, 'Konverteringsfel'): plan.importera_ritning(source)
            self.assertEqual((plan._document(), plan.background, plan.state), before)

    @unittest.skipUnless(importlib.util.find_spec('playwright'), 'Installera Playwright.')
    def test_browser_landmark_positions_match_previous_bitmap_with_rotation_crop_and_offset(self):
        from playwright.sync_api import sync_playwright, Error
        with sync_playwright() as runtime:
            browser = None
            for channel in ('chrome', 'msedge', None):
                try:
                    browser = runtime.chromium.launch(channel=channel, headless=True, chromium_sandbox=True)
                    break
                except Error:
                    continue
            if browser is None: self.skipTest('Ingen lokal Chromium, Chrome eller Edge.')
            try:
                context = browser.new_context(viewport={'width': 1600, 'height': 1500})
                context.route('**/*', lambda route: route.abort())
                page = context.new_page()
                for offset in (False, True):
                    for rotation in (0, 90, 180, 270):
                        with self.subTest(offset=offset, rotation=rotation):
                            data = self.drawing(rotation=rotation, crop=True)
                            if offset:
                                writer = PdfWriter(); source = writer.add_page(PdfReader(io.BytesIO(data)).pages[0])
                                source.mediabox = RectangleObject((10, 20, 611.25, 421.5))
                                buffer = io.BytesIO(); writer.write(buffer); data = buffer.getvalue()
                            background = _render_source(data, 'drawing.pdf')
                            with pdfium.PdfDocument(data) as document:
                                pdf_page = document[0]
                                bitmap = pdf_page.render(scale=min(2, 2800 / max(pdf_page.get_size())))
                                reference = bitmap.to_pil().convert('RGB'); bitmap.close(); pdf_page.close()
                            page.set_content('<img id="drawing" style="display:block">')
                            page.locator('#drawing').evaluate('(el, src) => el.src = src', background['url'])
                            page.wait_for_function('document.querySelector("img").complete && document.querySelector("img").naturalWidth > 0')
                            actual = Image.open(io.BytesIO(page.locator('#drawing').screenshot())).convert('RGB')
                            self.assertEqual(actual.size, reference.size)
                            def landmark(image):
                                r, g, b = image.split()
                                mask = ImageChops.multiply(r.point(lambda v: 255 if v > 200 else 0),
                                    g.point(lambda v: 255 if v < 70 else 0))
                                return ImageChops.multiply(mask, b.point(lambda v: 255 if v < 70 else 0)).getbbox()
                            expected, observed = landmark(reference), landmark(actual)
                            self.assertIsNotNone(expected); self.assertIsNotNone(observed)
                            for a, b in zip(expected, observed): self.assertLessEqual(abs(a-b), 1)
            finally:
                browser.close()
