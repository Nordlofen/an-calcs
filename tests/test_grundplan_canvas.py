import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ('anywidget', 'PIL', 'pypdfium2', 'pypdf', 'reportlab'))
if HAS_NOTEBOOK:
    from PIL import Image
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject
    import pypdfium2 as pdfium
    from reportlab.pdfgen.canvas import Canvas
    from an_calcs.notebook import Grundplan
    from an_calcs.notebook.grundplan_canvas import DEFAULT_BOUNDS


@unittest.skipUnless(HAS_NOTEBOOK, 'Installera an-calcs[notebook].')
class TestCanvas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'drawing.png'
        Image.new('RGB', (800, 600), '#ddeeff').save(self.source)
        self.plan = Grundplan(self.source); self.addCleanup(self.plan.close)
        self.ident = self.plan.lagg_till(.3, .4, littera='VS.1', indata={'F_vy': 100})
        self.bounds = {'left': -.4, 'top': -.2, 'right': 1.3, 'bottom': 1.2}

    def test_crop_changes_no_coordinates_calibration_locks_or_calculations(self):
        self.plan.kalibrering = {'start': {'x': .1, 'y': .2}, 'end': {'x': .6, 'y': .2}, 'length_m': 10}
        self.plan.las_placering([{'type': 'tag', 'id': self.ident}])
        self.plan.referens = {'enabled': True, 'x': .6}
        before = self.plan._document(), self.plan.resultat
        with patch.object(self.plan, '_refresh_tag') as calculate:
            self.plan.ritningsram = self.bounds
        calculate.assert_not_called()
        after = self.plan._document(); expected = copy.deepcopy(before[0]); expected['canvas_bounds'] = self.bounds
        self.assertEqual(after, expected); self.assertEqual(self.plan.resultat, before[1])
        self.plan.ritningsram = {'left': .4, 'top': .5, 'right': .9, 'bottom': .95}
        self.assertEqual(self.plan.taggar[0]['x'], .3, 'Hidden objects are retained')
        self.plan.ritningsram = DEFAULT_BOUNDS
        self.assertEqual(self.plan._document(), before[0])

    def test_added_margins_support_every_object_and_survive_crop_save_and_reopen(self):
        self.plan.ritningsram = self.bounds
        text = self.plan.lagg_till_rubrik('I marginalen', x=-.3, y=-.1)
        kinds = ['symbol', 'legend', 'colour', 'insulation', 'comments', 'reference', 'text:' + text]
        self.plan.flytta_objekt([{'type': 'tag', 'id': self.ident, 'x': -.25, 'y': 1.1},
            *[{'type': 'overlay', 'page': 1, 'kind': kind, 'x': -.3, 'y': -.1} for kind in kinds]])
        new = self.plan.lagg_till(1.1, -.1, littera='PS.MARGINAL', typ='pelarsula')
        self.plan.hanvisningslinje(self.ident, {'enabled': True, 'attachment': {'side': 'top', 'offset': .5},
            'nodes': [{'x': -.2, 'y': -.1, 'in': {'x': 0, 'y': 0}, 'out': {'x': .05, 'y': .02}}],
            'end_handle': {'x': 0, 'y': -.1}})
        self.plan.ritningsram = DEFAULT_BOUNDS
        # A hidden widget can still be resized/disabled and a hidden label edited.
        self.plan.referens = {'enabled': True, 'size': 350}
        self.plan.kommentarwidget = {'enabled': True}
        self.plan.uppdatera_text(text, text='Finns kvar')
        self.plan.uppdatera(self.ident, indata={'kommentar': 'Finns kvar'})
        saved = self.plan._document(); self.assertEqual(saved['version'], 22)
        self.plan._load_document(json.dumps(saved).encode()); self.assertEqual(self.plan._document(), saved)
        self.assertEqual(self.plan._tag(new)['x'], 1.1)
        self.plan.ritningsram = self.bounds
        self.assertEqual(self.plan.referens['x'], -.3)
        replacement = self.root / 'replacement.png'; Image.new('RGB', (1200, 500), 'white').save(replacement)
        self.plan.importera_ritning(replacement)
        self.assertEqual(self.plan.ritningsram, self.bounds)
        self.assertEqual(self.plan._tag(self.ident)['x'], -.25)

    def test_invalid_frames_and_legacy_defaults_are_atomic(self):
        before = self.plan._document()
        invalid = [None, [], {'left': 0}, {**self.bounds, 'top': True}, {**self.bounds, 'left': float('nan')},
                   {**self.bounds, 'right': 12}, {**self.bounds, 'right': -.5},
                   {**self.bounds, 'left': 1.299}, {**self.bounds, 'bottom': 11}]
        for bounds in invalid:
            with self.subTest(bounds=bounds):
                with self.assertRaises(ValueError): self.plan.ritningsram = bounds
                self.assertEqual(self.plan._document(), before)
                with self.assertRaises(ValueError): self.plan._load_document(json.dumps({**before, 'canvas_bounds': bounds}).encode())
                self.assertEqual(self.plan._document(), before)
        legacy = {**before, 'version': 21}; legacy.pop('canvas_bounds')
        self.plan._load_document(json.dumps(legacy).encode()); self.assertEqual(self.plan.ritningsram, DEFAULT_BOUNDS)
        with patch.object(self.plan, 'send') as send:
            self.plan._on_message(None, {'action': 'canvas_bounds', 'bounds': self.bounds, 'request': 1}, [])
            self.assertTrue(send.call_args.args[0]['ok']); self.assertEqual(self.plan.ritningsram, self.bounds)

    def test_expanded_pdf_and_html_match_frame_and_keep_margin_labels(self):
        self.plan.ritningsram = self.bounds
        self.plan.uppdatera(self.ident, x=-.3, y=.2)
        self.plan.kommentarwidget = {'enabled': True, 'x': -.3, 'y': .5}
        self.plan.uppdatera(self.ident, indata={'kommentar': 'I marginalen'})
        pdf = self.plan._pdf_bytes(); page = PdfReader(io.BytesIO(pdf)).pages[0]
        self.assertAlmostEqual(float(page.mediabox.width), 600 * 1.7)
        self.assertAlmostEqual(float(page.mediabox.height), 450 * 1.4)
        self.assertEqual(len(page.images), 1, 'Only the original raster drawing is an image')
        with pdfium.PdfDocument(pdf) as document:
            text = document[0].get_textpage(); index = text.get_text_range().index('VS.1')
            x1, y1, x2, y2 = text.get_charbox(index); text.close()
            self.assertGreater(x1, 0); self.assertLess(x2, 600 * .4, 'The label stays in the added left margin')
        html = self.plan._html_bytes().decode(); snapshot = json.loads(html.split('<script id="grundplan-data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(snapshot['state']['canvas_bounds'], self.bounds)
        self.assertEqual(snapshot['state']['tags'][0]['x'], -.3)

    def test_rotated_vector_sources_are_translated_and_clipped_without_rescaling(self):
        source = self.root / 'vector.pdf'
        canvas = Canvas(str(source), pagesize=(500, 700))
        canvas.setFillColorRGB(0, 1, 0); canvas.rect(95, 195, 10, 10, fill=1, stroke=0)
        canvas.drawString(70, 160, 'ORIGINAL'); canvas.showPage(); canvas.save()
        for rotation, xy in ((0, (50, 450)), (90, (100, 50)), (180, (350, 100)), (270, (450, 350))):
            with self.subTest(rotation=rotation):
                writer = PdfWriter(); page = writer.add_page(PdfReader(source).pages[0])
                page.cropbox = RectangleObject((50, 100, 450, 650)); page.rotate(rotation)
                path = self.root / f'rotated-{rotation}.pdf'; writer.write(path)
                plan = Grundplan(path); self.addCleanup(plan.close)
                plan.ritningsram = {'left': -.2, 'top': .1, 'right': 1.1, 'bottom': 1.2}
                pdf = plan._pdf_bytes(); page = PdfReader(io.BytesIO(pdf)).pages[0]
                w, h = (400, 550) if rotation in (0, 180) else (550, 400)
                self.assertAlmostEqual(float(page.mediabox.width), w * 1.3)
                self.assertAlmostEqual(float(page.mediabox.height), h * 1.1)
                self.assertFalse(page.images); self.assertEqual(page.rotation, 0)
                with pdfium.PdfDocument(pdf) as document:
                    bitmap = document[0].render(scale=1).to_pil().convert('RGB')
                    self.assertEqual(bitmap.getpixel((round(xy[0] + .2*w), round(xy[1] - .1*h))), (0, 255, 0))
                    self.assertEqual(bitmap.getpixel((2, 2)), (255, 255, 255), 'Added margin is blank')

    def test_restoring_original_frame_keeps_margin_objects_clipped_in_pdf(self):
        self.plan.ritningsram = {'left': -.9, 'top': 0, 'right': 1, 'bottom': 1}
        self.plan.uppdatera(self.ident, x=-.8, y=.2)
        self.plan.referens = {'enabled': True, 'x': -.8, 'y': .5}
        self.plan.ritningsram = DEFAULT_BOUNDS
        before = self.plan._document()
        with pdfium.PdfDocument(self.plan._pdf_bytes()) as document:
            bitmap = document[0].render(scale=1).to_pil().convert('RGB')
            self.assertEqual(bitmap.getextrema(), ((221, 221), (238, 238), (255, 255)),
                             'Restoring the frame must not fit hidden objects back onto the exported page')
        self.assertEqual(self.plan._document(), before)

    def test_group_movement_can_bring_hidden_margin_objects_back_towards_the_visible_frame(self):
        self.plan.ritningsram = self.bounds
        self.plan.uppdatera(self.ident, x=-.3)
        self.plan.referens = {'x': -.3}
        self.plan.ritningsram = DEFAULT_BOUNDS
        self.plan.flytta_objekt([{'type': 'tag', 'id': self.ident, 'x': -.2, 'y': .4},
            {'type': 'overlay', 'page': 1, 'kind': 'reference', 'x': -.2, 'y': .3}])
        self.assertEqual(self.plan._tag(self.ident)['x'], -.2)
        self.assertEqual(self.plan.referens['x'], -.2)
        before = self.plan._document()
        with self.assertRaises(ValueError):
            self.plan.flytta_objekt([{'type': 'tag', 'id': self.ident, 'x': .1, 'y': .4},
                {'type': 'overlay', 'page': 1, 'kind': 'reference', 'x': -.4, 'y': .3}])
        self.assertEqual(self.plan._document(), before, 'An outwards move outside both old and current bounds fails atomically')
