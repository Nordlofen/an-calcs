"""Physical contour persistence, opt-in legacy defaults and trusted edits."""
import copy
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(n) for n in ("anywidget", "PIL", "pypdfium2", "pypdf", "reportlab"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestContours(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image); self.addCleanup(self.plan.close)
        self.pad = self.plan.lagg_till(.2, .3, typ="pelarsula", littera="PS.1", indata={"F_vy": 100})
        self.wall = self.plan.lagg_till(.5, .6, littera="VS.1", indata={"F_vy": 100})
        self.calibration = {"start": {"x": .1, "y": .1}, "end": {"x": .6, "y": .1}, "length_m": 10}
        self.position = {"kind": "pad", "center": {"x": .4, "y": .4}, "angle_deg": 30}

    def message(self, action, **payload):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(self.plan, {"action": action, "view": "test", "request": 1, **payload}, [])
        return send.call_args.args[0]

    def test_legacy_is_opt_in_and_preserves_inputs_labels_and_results(self):
        old = self.plan._document(); old["version"] = 28; old.pop("contours")
        before = copy.deepcopy(self.plan.taggar)
        self.plan._load_document(json.dumps(old).encode())
        self.assertFalse(self.plan.sulkonturer["enabled"])
        self.assertEqual(self.plan.sulkonturer["placements"], {})
        self.assertEqual(self.plan.taggar, before)
        self.plan.sulkonturer = {"enabled": True}
        self.assertEqual(self.plan.taggar, before)
        self.assertEqual(self.plan.sulkonturer["placements"], {}, "No placement is inferred from labels")

    def test_roundtrip_geometry_does_not_recalculate_or_move_labels(self):
        self.plan.kalibrering = self.calibration
        before = copy.deepcopy(self.plan.taggar)
        with patch.object(self.plan, "_refresh_tag") as calculate:
            self.plan.placera_sulkontur(self.pad, self.position)
            self.plan.placera_sulkontur(self.wall, {"kind":"wall", "start":{"x":.2,"y":.2}, "end":{"x":.7,"y":.2}})
            self.plan.sulkonturer = {"enabled": True, "fill_opacity": 0}
        calculate.assert_not_called(); self.assertEqual(self.plan.taggar, before)
        document = self.plan._document()
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan._document(), document)
        self.plan.uppdatera(self.pad, indata={"b": 2.5})
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)
        self.plan.uppdatera(self.pad, x=.8, y=.9)
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)

    def test_invalid_or_uncalibrated_placement_is_atomic_and_locks_are_respected(self):
        before = self.plan._document()
        with self.assertRaises(ValueError): self.plan.placera_sulkontur(self.pad, self.position)
        self.assertEqual(self.plan._document(), before)
        self.plan.kalibrering = self.calibration
        for p in [{**self.position, "angle_deg": float("nan")}, {**self.position, "center": {"x": 15,"y": .1}},
                  {"kind":"wall", "start":{"x":.2,"y":.2}, "end":{"x":.2,"y":.2}},
                  {"kind":"wall", "start":{"x":.2,"y":.2}, "end":{"x":.5,"y":.2}}]:
            with self.assertRaises(ValueError): self.plan.placera_sulkontur(self.pad, p)
        self.plan.las_placering([{"type":"tag","id":self.pad}])
        with self.assertRaises(ValueError): self.plan.placera_sulkontur(self.pad, self.position)
        for s in [{"enabled":1},{"fill_opacity":float("nan")},{"fill_opacity":-1},{"fill_opacity":2}]:
            with self.assertRaises(ValueError): self.plan.sulkonturer = s

    def test_history_and_deleted_objects_and_drawing_recalibration(self):
        self.plan.kalibrering = self.calibration
        self.assertTrue(self.message("contour_placement", id=self.pad, placement=self.position)["ok"])
        self.assertTrue(self.message("undo")["ok"])
        self.assertNotIn(self.pad, self.plan.sulkonturer["placements"])
        self.assertTrue(self.message("redo")["ok"])
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)
        self.plan.ritningsunderlag = {"scale": 1.2}
        self.assertIsNone(self.plan.kalibrering)
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)
        self.plan.ta_bort(self.pad)
        self.assertNotIn(self.pad, self.plan.sulkonturer["placements"])

    def test_export_snapshots_have_calibration_and_contours(self):
        self.plan.kalibrering = self.calibration
        self.plan.placera_sulkontur(self.pad, self.position)
        self.plan.sulkonturer = {"enabled":True}
        with patch.object(self.plan, "_pdf_bytes", return_value=b""), patch("an_calcs.notebook.grundplan_html.render_html", return_value=b"") as render:
            self.plan._html_bytes()
        self.assertEqual(render.call_args.args[0]["state"]["contours"], self.plan.sulkonturer)
        with patch("an_calcs.notebook.grundplan_pdf.render_pdf", return_value=b"") as render:
            self.plan._pdf_bytes()
        self.assertEqual(render.call_args.kwargs["calibration"], self.calibration)
        self.assertEqual(render.call_args.kwargs["contours"], self.plan.sulkonturer)

    def test_batch_directions_keep_anchors_inputs_and_legacy_wall_length_with_one_undo(self):
        self.plan.kalibrering = self.calibration
        self.plan.placera_sulkontur(self.pad, self.position)
        wall = {"kind": "wall", "start": {"x": .3, "y": .5}, "end": {"x": .5, "y": .5}}
        self.plan.placera_sulkontur(self.wall, wall)
        self.plan.las_indata([self.pad, self.wall])
        before = self.plan._document()
        with patch.object(self.plan, "_refresh_tag", side_effect=AssertionError("Rotation cannot recalculate")):
            reply = self.message("contour_directions", ids=[self.pad, self.wall], angle=90, relative=True)
            self.assertTrue(reply["ok"], reply)
            self.assertEqual(reply["report"], {"updated": 2, "locked": 0, "unplaced": 0})
            after = self.plan._document()
            pad, rotated = (self.plan.sulkonturer["placements"][i] for i in (self.pad, self.wall))
            self.assertEqual(pad["center"], self.position["center"])
            self.assertEqual(pad["angle_deg"], 120)
            self.assertEqual(rotated["start"], wall["start"])
            self.assertAlmostEqual(rotated["end"]["x"], .3)
            self.assertAlmostEqual(rotated["end"]["y"], .5 - 160 / 600)
            self.assertEqual(after["tags"], before["tags"])
            self.assertEqual(self.plan.state["history"]["undo_count"], 1)
            self.assertEqual(self.plan.state["history"]["undo"], "Ändra konturriktning för 2 sulor")
            self.assertTrue(self.message("undo")["ok"])
            self.assertEqual(self.plan._document(), before)
            self.assertTrue(self.message("redo")["ok"])
            self.assertEqual(self.plan._document(), after)
        self.plan._load_document(json.dumps(after).encode())
        self.assertEqual(self.plan._document(), after)

    def test_batch_absolute_direction_skips_locked_unplaced_and_rejects_invalid_atomically(self):
        self.plan.kalibrering = self.calibration
        self.plan.placera_sulkontur(self.pad, self.position)
        self.plan.placera_sulkontur(self.wall, {"kind": "wall", "start": {"x": .4, "y": .4}, "angle_deg": 75})
        self.plan.las_placering([{"type": "tag", "id": self.wall}])
        unplaced = self.plan.lagg_till(.8, .8)
        before = self.plan._document()
        for angle in (True, float("nan"), float("inf"), 36001, "90"):
            with self.assertRaises(ValueError):
                self.plan.andra_konturriktning([self.pad, self.wall], vinkel=angle)
            self.assertEqual(self.plan._document(), before)
        with self.assertRaises(ValueError):
            self.plan.andra_konturriktning([self.pad, "missing"], vinkel=45)
        self.assertEqual(self.plan._document(), before)
        report = self.plan.andra_konturriktning([self.pad, self.wall, unplaced], vinkel=-45)
        self.assertEqual(report, {"updated": 1, "locked": 1, "unplaced": 1})
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad]["angle_deg"], 315)
        self.assertEqual(self.plan.sulkonturer["placements"][self.wall], before["contours"]["placements"][self.wall])

    def test_batch_rotation_of_trimmed_wall_keeps_visible_start_and_rebases_later_length_edits(self):
        self.plan.kalibrering = self.calibration
        ident = self.plan.lagg_till(.5, .5, indata={"L_vagg": 3, "l": 2, "l_override": True, "length_end": 1})
        self.plan.placera_sulkontur(ident, {"kind": "wall", "start": {"x": .5, "y": .5}, "angle_deg": 0})
        self.plan.andra_konturriktning([ident], vinkel=90)
        rotated = self.plan.sulkonturer["placements"][ident]
        self.assertEqual(rotated["start"], {"x": .5, "y": .5})
        self.assertAlmostEqual(rotated["reference_start"]["x"], .55)
        self.plan.uppdatera(ident, indata={"l": 1})
        shorter = self.plan.sulkonturer["placements"][ident]
        self.assertAlmostEqual(shorter["start"]["x"], .45)
        self.assertAlmostEqual(shorter["start"]["y"], .5)

    def test_malformed_saved_placements_leave_project_intact(self):
        before = self.plan._document()
        bad = {**before, "contours":{"placements":{"missing":self.position}}}
        with self.assertRaises(ValueError): self.plan._load_document(json.dumps(bad).encode())
        self.assertEqual(self.plan._document(), before)

    def test_print_width_defaults_validation_history_and_legacy_roundtrip(self):
        self.assertEqual(self.plan.sulkonturer["line_width_mm"], .10)
        self.assertFalse(self.plan.sulkonturer["show_print_width"])
        for changes in [{"line_width_mm":0},{"line_width_mm":-1},{"line_width_mm":2.1},
                        {"line_width_mm":True},{"line_width_mm":float("nan")},{"show_print_width":1}]:
            before = self.plan._document()
            with self.assertRaises(ValueError): self.plan.sulkonturer = changes
            self.assertEqual(self.plan._document(), before)
        result = self.message("contours", settings={"line_width_mm":.15,"show_print_width":True})
        self.assertTrue(result["ok"])
        self.assertEqual(self.plan.sulkonturer["line_width_mm"], .15)
        saved = self.plan._document(); self.plan._load_document(json.dumps(saved).encode())
        self.assertEqual(self.plan._document(), saved)
        legacy = copy.deepcopy(saved); legacy["version"] = 29
        legacy["contours"].pop("line_width_mm"); legacy["contours"].pop("show_print_width")
        self.plan._load_document(json.dumps(legacy).encode())
        self.assertEqual(self.plan.sulkonturer["line_width_mm"], .10)
        self.assertFalse(self.plan.sulkonturer["show_print_width"])
        self.assertTrue(self.message("contours", settings={"line_width_mm":.20,"show_print_width":True})["ok"])
        self.assertTrue(self.message("undo")["ok"])
        self.assertEqual(self.plan.sulkonturer["line_width_mm"], .10)
        self.assertTrue(self.message("redo")["ok"])
        self.assertEqual(self.plan.sulkonturer["line_width_mm"], .20)

    def test_hatch_density_validation_history_and_legacy_default(self):
        self.assertEqual(self.plan.sulkonturer['hatch_density'], 1)
        for density in (0, .24, 4.1, True, float('nan'), float('inf'), '2'):
            before = self.plan._document()
            with self.subTest(density=density), self.assertRaises(ValueError):
                self.plan.sulkonturer = {'hatch_density': density}
            self.assertEqual(self.plan._document(), before)
        before = copy.deepcopy(self.plan.resultat)
        with patch.object(self.plan, '_refresh_tag', side_effect=AssertionError('Visual-only setting')):
            self.assertTrue(self.message('contours', settings={'hatch_density': 2})['ok'])
            self.assertTrue(self.message('undo')['ok'])
            self.assertEqual(self.plan.sulkonturer['hatch_density'], 1)
            self.assertTrue(self.message('redo')['ok'])
            self.assertEqual(self.plan.sulkonturer['hatch_density'], 2)
        self.assertEqual(self.plan.resultat, before)
        saved = self.plan._document(); self.plan._load_document(json.dumps(saved).encode())
        self.assertEqual(self.plan.sulkonturer['hatch_density'], 2)
        saved['contours'].pop('hatch_density')
        self.plan._load_document(json.dumps(saved).encode())
        self.assertEqual(self.plan.sulkonturer['hatch_density'], 1)

    @unittest.skipUnless(importlib.util.find_spec("pymupdf"), "Installera PyMuPDF.")
    def test_exported_group_patterns_match_screen_without_pdf_tiling_resources(self):
        """Keep the drawing-grid pattern through PDF merging and viewer scaling."""
        import io
        import pymupdf
        from PIL import ImageChops
        from pypdf import PdfReader
        from playwright.sync_api import sync_playwright, Error
        from reportlab.pdfgen.canvas import Canvas
        from an_calcs.notebook.grundplan_html import render_html

        source = Path(self.tmp.name) / "patterns.pdf"
        canvas = Canvas(str(source), pagesize=(400, 300)); canvas.showPage(); canvas.save()
        plan = Grundplan(source); self.addCleanup(plan.close)
        plan.etikettstorlek = 20
        plan.kalibrering = {"start":{"x":0,"y":0}, "end":{"x":.5,"y":0}, "length_m":10}
        # One placed red footing in each pattern family, some with rotated axes.
        for index in range(72):
            ident = plan.lagg_till(.02, .02, typ="pelarsula", indata={"b":2,"l":2,"t":.2+index*.001,"F_vy":100})
            if index in (15, 27, 39, 51, 63):
                column = index // 12 - 1
                plan.placera_sulkontur(ident, {"kind":"pad", "center":{"x":.12+column*.18,"y":.6}, "angle_deg":column*15})
        plan.farggruppering = {"enabled":True, "categories":["t"], "show_legend":False}
        plan.sulkonturer = {"enabled":True, "fill_opacity":.3}
        snapshot = {"state":plan.state,"schema":plan.schema,"pages":[plan.background],"page":1}
        with sync_playwright() as runtime:
            browser = None
            for channel in (None, "chrome", "msedge"):
                try:
                    browser = runtime.chromium.launch(channel=channel, headless=True, chromium_sandbox=True)
                    break
                except Error:
                    continue
            self.assertIsNotNone(browser, "PDF-export kräver Chromium, Chrome eller Edge")
            try:
                page = browser.new_page(viewport={"width":800,"height":600})
                page.route("**/*", lambda route: route.abort())
                page.set_content(render_html(snapshot, pdf_mode=True).decode())
                page.locator('html[data-pdf-ready="true"]').wait_for(state="attached")
                self.assertEqual(page.locator('.gp-contour-fills > g').count(), 5)
                screen = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            finally:
                browser.close()
        exported = plan._pdf_bytes()
        # Pattern resources inside transparency forms are interpreted differently
        # by PDF viewers. All group marks must instead be explicit vector paths.
        def check_resources(resources):
            resources = resources.get_object()
            self.assertFalse(resources.get("/Pattern"))
            for item in resources.get("/XObject", {}).values():
                item = item.get_object()
                self.assertNotEqual(item.get("/Subtype"), "/Image")
                if "/Resources" in item:
                    check_resources(item["/Resources"])
        check_resources(PdfReader(io.BytesIO(exported)).pages[0]["/Resources"])
        with pymupdf.open(stream=exported, filetype="pdf") as document:
            pixels = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            printed = Image.frombytes("RGB", (pixels.width, pixels.height), pixels.samples)
        # Exclude labels and contour edges; allow different vector antialiasing.
        region = (0, 280, 800, 440)
        r, g, b = ImageChops.difference(screen.crop(region), printed.crop(region)).split()
        histogram = ImageChops.lighter(ImageChops.lighter(r, g), b).histogram()
        mismatch = sum(count for value, count in enumerate(histogram) if value > 16)
        self.assertLess(mismatch / (800 * 160), .03)

    @unittest.skipUnless(importlib.util.find_spec("pymupdf"), "Installera PyMuPDF.")
    def test_pdf_paper_line_width_is_exact_across_page_sizes_crop_and_preview_choice(self):
        import pymupdf
        from reportlab.lib.pagesizes import A0, A1, landscape
        from reportlab.pdfgen.canvas import Canvas
        from an_calcs.notebook.grundplan_canvas import DEFAULT_BOUNDS
        for name, size, mm, preview, cropped in [
                ("a1", landscape(A1), .10, False, False),
                ("a1-preview", landscape(A1), .10, True, True),
                ("a0", landscape(A0), .20, False, False)]:
            with self.subTest(name=name):
                source = Path(self.tmp.name) / (name + ".pdf")
                canvas = Canvas(str(source), pagesize=size); canvas.showPage(); canvas.save()
                plan = Grundplan(source); self.addCleanup(plan.close)
                ident = plan.lagg_till(.05, .05, typ="pelarsula", indata={"b":2,"l":3,"F_vy":100,"B_x":300,"B_y":400})
                if cropped:
                    plan.ritningsram = {"left":-.2,"top":-.1,"right":1.2,"bottom":1.1}
                    plan.ritningsunderlag = {"scale":1.4}
                plan.kalibrering = self.calibration
                plan.placera_sulkontur(ident, {"kind":"pad","center":{"x":.5,"y":.5},"angle_deg":0})
                plan.sulkonturer = {"enabled":True,"fill_opacity":0,"line_width_mm":mm,"show_print_width":preview}
                pdf = plan._pdf_bytes()
                with pymupdf.open(stream=pdf, filetype="pdf") as document:
                    # The contour uses this explicit darkened default teal stroke.
                    outlines = [d for d in document[0].get_drawings() if d.get("color")
                                and abs(d["color"][0] - .351) < .025
                                and abs(d["color"][1] - .499) < .025
                                and abs(d["color"][2] - .502) < .025]
                    self.assertTrue(outlines, "Exported contour path exists")
                    for outline in outlines:
                        self.assertAlmostEqual(outline["width"] * 25.4 / 72, mm, delta=.001)
                    upper = [d for d in document[0].get_drawings() if d.get('color')
                             and all(abs(d['color'][i] - c / 255) < .01 for i,c in enumerate((53,81,92)))]
                    self.assertGreaterEqual(len(upper), 2, 'Both upper outline and hatch lines are vectors')
                    for drawing in upper:
                        self.assertAlmostEqual(drawing['width'] * 25.4 / 72, mm, delta=.001)
                    self.assertEqual(len(document[0].get_images()), 0)
                    # Keep a rendered export available during local visual QA.
                    document[0].get_pixmap(matrix=pymupdf.Matrix(.6,.6)).save(str(Path(self.tmp.name)/(name+".png")))
