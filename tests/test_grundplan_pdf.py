import copy
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
HAS_PDF = all(importlib.util.find_spec(name) for name in
              ("anywidget", "PIL", "pypdfium2", "reportlab", "pypdf"))
if HAS_PDF:
    from PIL import Image, ImageChops
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject
    import pypdfium2 as pdfium
    from reportlab.pdfgen.canvas import Canvas
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_PDF, "Installera an-calcs[notebook] för PDF-testerna.")
class TestGrundplanPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "ritning.png"
        Image.new("RGB", (800, 600), "white").save(self.image)

    def plan(self, source=None, **kwargs):
        plan = Grundplan(source or self.image, **kwargs)
        self.addCleanup(plan.close)
        return plan

    def tag(self, plan, **kwargs):
        return plan.lagg_till(**{
            "x": .3, "y": .4, "indata": {"b": 1, "F_vy": 100}, **kwargs,
        })

    def test_inactive_exports_comment_and_white_vector_label_without_old_results(self):
        source = self.root / "drawing.pdf"
        canvas = Canvas(str(source), pagesize=(600, 450))
        canvas.setFillColorRGB(.9, .95, .9); canvas.rect(0, 0, 600, 450, fill=1, stroke=0)
        canvas.showPage(); canvas.save()
        plan = self.plan(source)
        ident = self.tag(plan, littera="VS.PAUS", indata={"F_vy": 999, "b": 1.7, "t": .31,
            "glid_x": True, "V_Ed_EQU": 999, "glid_mu": .4, "glid_L": 3, "kommentar": "Avvaktar granskning"})
        plan.farggruppering = {"enabled": True, "category": "t"}
        plan.kommentarwidget = {"enabled": True, "x": .1, "y": .7}
        plan.uppdatera(ident, indata={"inaktiv": True})
        pdf = PdfReader(io.BytesIO(plan._pdf_bytes()))
        page = pdf.pages[0]; text = page.extract_text()
        self.assertIn("VS.PAUS", text)
        self.assertIn("Inaktiv", text)
        self.assertIn("Avvaktar granskning", text)
        for absent in ("999", "Brott", "Bruk", "Styrande", "Glidmotstånd", "1,7", "0,31"):
            self.assertNotIn(absent, text)
        self.assertEqual(len(page.images), 0, "Drawing, label, frame and comments remain vectors")
        html = plan._html_bytes().decode()
        self.assertIn('"inaktiv": true', html)
        self.assertIn('"status": "inactive"', html)
        self.assertIn("Avvaktar granskning", html)

    def test_horizontal_only_exports_mode_and_contribution_without_bearing_results_or_loads(self):
        plan = self.plan()
        ident = self.tag(plan, indata={"endast_h_stabilitet": True, "glid_x": True, "glid_y": True,
                        "V_Ed_EQU": 120, "glid_mu": .4, "glid_L": 3,
                        "F_vy": 999, "F_vy_bruk": 999, "b": 1.7, "l": 2.4, "l_override": True, "phi_k": None})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("Endast H-stabilitet", text)

        self.assertIn("Glidmotstånd – globalt", text)
        self.assertIn("120 kN/m", text)
        self.assertIn("144 kN", text)
        for absent in ("999", "Brott", "Bruk", "U 0", "Styrande", "None", "1,7", "2,4"):
            self.assertNotIn(absent, text)
        html = plan._html_bytes().decode()
        self.assertIn('"endast_h_stabilitet": true', html)
        self.assertIn('"utnyttjandegrad": null', html)
        plan.uppdatera(ident, indata={"isolering": True, "f_d_brott": None, "f_d_bruk": None})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("Endast H-stabilitet", text)
        self.assertIn("Utan isolering", text)
        self.assertIn("Glidmotstånd – globalt", text)
        self.assertIn("144 kN", text)
        self.assertNotIn("Styrande", text)
        plan.uppdatera(ident, indata={"lang": 0, "lasttyp": 0})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("Endast H-stabilitet", text)
        self.assertIn("48 kN", text)
        self.assertNotIn("1,7", text)
        self.assertNotIn("2,4", text)

    def test_comment_widget_wraps_literal_multiline_text_inside_raster_and_pdf_drawing(self):
        source = self.root / "drawing.pdf"
        canvas = Canvas(str(source), pagesize=(600, 450)); canvas.showPage(); canvas.save()
        for drawing in (self.image, source):
            with self.subTest(drawing=drawing.suffix):
                plan = self.plan(drawing)
                comment = "ÅÄÖ_x – samordna med stomritning. " * 5 + "\n" + "LångtOrd" * 15
                self.tag(plan, x=0, y=0, littera="VS.123456789", indata={"kommentar": comment})
                plan.kommentarwidget = {"enabled": True, "x": 1, "y": 1, "size": 1230}
                data = plan._pdf_bytes()
                text = PdfReader(io.BytesIO(data)).pages[0].extract_text().split("Kommentarer")[1]
                self.assertIn("1 sula med kommentar", text)
                self.assertIn("ÅÄÖ_x", text, "Comments must not interpret literal subscripts as formula notation")
                self.assertIn("LångtOrd" * 15, text.replace("\n", ""))
                with pdfium.PdfDocument(data) as document:
                    page = document[0]; textpage = page.get_textpage()
                    try:
                        for index in range(textpage.count_chars()):
                            left, bottom, right, top = textpage.get_charbox(index)
                            self.assertGreaterEqual(left, -.1); self.assertGreaterEqual(bottom, -.1)
                            self.assertLessEqual(right, page.get_width() + .1); self.assertLessEqual(top, page.get_height() + .1)
                    finally:
                        textpage.close(); page.close()

    def test_three_parameter_legend_and_coloured_comments_stay_vector_in_pdf_and_html(self):
        plan = self.plan(self.drawing())
        for label, load in (("VS.1", 150), ("VS.2", 250)):
            self.tag(plan, x=.65, y=.2 if load == 150 else .4, littera=label,
                     indata={"b": .8, "t": .25, "F_vy": load, "kommentar": "Samordnas med stomritning."})
        plan.farggruppering = {"enabled": True, "categories": ["b", "t", "V"], "phase": "brott",
                              "legend": {"x": .05, "y": .05, "size": 360}}
        plan.kommentarwidget = {"enabled": True, "x": .05, "y": .55, "size": 410}
        page = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        text = page.extract_text()
        self.assertIn("Tjocklek t + Bredd bₓ + V · brott", text)
        self.assertIn("100 ≤ V < 200 kN/m", text)
        self.assertIn("200 ≤ V < 400 kN/m", text)
        self.assertIn("2 sulor med kommentarer", text)
        self.assertFalse(page.images, "The multiline legend and coloured comment labels are vectors")
        html = plan._html_bytes().decode()
        self.assertIn('"categories": ["t", "b", "V"]', html)
        self.assertIn('"gp-colour-legend-load"', html)
        self.assertIn('"gp-comment-label"', html)

    def test_spline_leaders_are_vector_curves_in_pdf_and_saved_in_readonly_html(self):
        plan = self.plan(self.drawing())
        ident = self.tag(plan, x=.55, y=.15, littera="VS.SPLINE")
        leader = {"enabled": True, "attachment": {"side": "left", "offset": .6},
                  "nodes": [{"x": .12, "y": .6, "in": {"x": 0, "y": 0}, "out": {"x": .08, "y": .02}},
                            {"x": .3, "y": .4, "in": {"x": -.08, "y": .1}, "out": {"x": .08, "y": -.1}}],
                  "end_handle": {"x": -.08, "y": 0}}
        before = plan.resultat
        plan.etikettstorlek = 150
        plan.hanvisningslinje(ident, leader)
        visible = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        self.assertFalse(visible.images, "Spline, arrow and labels must all remain vectors")
        self.assertIn("VS.SPLINE", visible.extract_text())
        # The overlay retains both Bezier segments and vector clearance bands
        # along the arrow arms, without a reshaped transition at the tip.
        curves = sum(operator == b"c" for _, operator in visible.get_contents().operations)
        clips = sum(operator in (b"W", b"W*") for _, operator in visible.get_contents().operations)
        plan.hanvisningslinje(ident, {**leader, "enabled": False})
        hidden = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        self.assertGreaterEqual(curves - sum(operator == b"c" for _, operator in hidden.get_contents().operations), 2)
        self.assertGreater(clips, sum(operator in (b"W", b"W*") for _, operator in hidden.get_contents().operations))
        self.assertEqual(plan.resultat, before)
        html = plan._html_bytes().decode()
        self.assertIn('"leader": {"enabled": false', html)
        self.assertIn('"end_handle": {"x": -0.08', html)

    def drawing(self):
        source = self.root / "original.pdf"
        canvas = Canvas(str(source), pagesize=(500, 700))
        for index, size in enumerate(((500, 700), (700, 500), (600, 600))):
            canvas.setPageSize(size)
            canvas.drawString(70, 180, f"ORIGINAL {index + 1}")
            canvas.rect(60, 150, 100, 150)
            canvas.showPage()
        canvas.save()
        return source

    def test_insulation_widget_excludes_horizontal_only_footings_and_preserves_vectors(self):
        plan = self.plan(self.drawing())
        self.tag(plan, littera="VS.1", indata={"isolering": True})
        self.tag(plan, littera="VS.10", indata={"isolering": False})
        self.tag(plan, littera="VS.2", indata={"isolering": False})
        horizontal = self.tag(plan, littera="H-GR.1", indata={"endast_h_stabilitet": True})
        plan.isoleringswidget = {"enabled": True, "x": .1, "y": .1}
        before = plan._document()
        page = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        widget_text = page.extract_text().rsplit("Isolering\n", 1)[1]
        self.assertRegex(widget_text, r"Med isolering\s+1\s+Utan isolering\s+2\s")
        self.assertIn("VS.2, VS.10", widget_text)
        self.assertNotIn("H-GR.1", widget_text)
        self.assertIn("H-GR.1", page.extract_text(), "The H-only footing still has its own label")
        self.assertFalse(page.images, "The drawing, labels and widget must remain vectors")
        self.assertEqual(plan._document(), before)
        for tag in plan.taggar:
            if tag["id"] != horizontal:
                plan.ta_bort(tag["id"])
        page = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        widget_text = page.extract_text().rsplit("Isolering\n", 1)[1]
        self.assertRegex(widget_text, r"Med isolering\s+0\s+Utan isolering\s+0\s")
        self.assertIn("Inga sulor", widget_text)
        self.assertNotIn("H-GR.1", widget_text)

    def test_shared_layout_keeps_combined_groups_inline_and_embeds_fonts_with_vector_shadows(self):
        plan = self.plan(self.drawing())
        self.tag(plan, x=.6, y=.15, littera="VS.1", indata={"t": .3, "b": .8, "kommentar": "Kontrollera anslutningen.\nSamordnas med VS.2."})
        self.tag(plan, x=.6, y=.4, littera="VS.2", indata={"t": .3, "b": .8})
        plan.farggruppering = {"enabled": True, "category": "t", "secondary": "b",
                              "legend": {"x": .05, "y": .05, "size": 300}}
        plan.kommentarwidget = {"enabled": True, "x": .05, "y": .55, "size": 410}
        page = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        text = page.extract_text()
        self.assertIn("Tjocklek t + Bredd bₓ", text)
        self.assertRegex(text, r"t 0,3 m · b\s*x\s+0,8 m")
        self.assertIn("Kontrollera anslutningen.", text)
        self.assertIn("Samordnas med VS.2.", text)
        self.assertFalse(page.images, "Even shadows, symbols and text are vector content")
        fonts = page["/Resources"]["/Font"]
        self.assertTrue(fonts)
        for font in fonts.values():
            font = font.get_object()
            # The drawing has an unused base Helvetica. Check every font
            # actually added by the browser, including math and index fonts.
            if font.get("/Subtype") == "/Type0":
                descendant = font["/DescendantFonts"][0].get_object()
                descriptor = descendant["/FontDescriptor"].get_object()
                self.assertTrue(any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")))
                self.assertIn("/ToUnicode", font)
            elif font.get("/Subtype") == "/Type3":
                # System variable fonts can be embedded as vector glyph
                # programs rather than as a copied TTF font file.
                self.assertTrue(font["/CharProcs"])
                self.assertIn("/ToUnicode", font)

    def test_sliding_overlays_show_only_view_totals_and_hide_insulated_contributions(self):
        plan = self.plan(self.drawing())
        self.tag(plan, littera="VS1", sida=1, indata={"glid_x": True, "glid_y": True,
                 "V_Ed_EQU": 120, "glid_mu": .4, "glid_L": 3})
        self.tag(plan, littera="PS1", sida=1, indata={"lang": 0, "glid_x": True,
                 "V_Ed_EQU": 240, "glid_mu": .4})
        self.tag(plan, littera="Isolerad", sida=1, indata={"isolering": True, "glid_x": True})
        plan.glidning = {"enabled": True, "check_x": True, "check_y": True,
                        "H_x_Ed": 180, "H_y_Ed": 200}
        before = plan._document()
        reader = PdfReader(io.BytesIO(plan._pdf_bytes()))
        for page in reader.pages:
            text = page.extract_text()
            self.assertIn("Glidningskontroll", text)
            self.assertIn("240 kN", text)
            self.assertIn("144 kN", text)
            self.assertIn("75 %", text)
            self.assertIn("Överskriden", text)
            self.assertFalse(page.images)
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(reader.pages[0].extract_text().count("Glidmotstånd – globalt"), 2)
        self.assertIn("120 kN/m", reader.pages[0].extract_text())
        self.assertIn("96 kN", reader.pages[0].extract_text())
        self.assertEqual(plan._document(), before)
        plan.glidning = {"enabled": False}
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertNotIn("Glidningskontroll", text)
        self.assertEqual(text.count("Glidmotstånd – globalt"), 2)
        self.assertIn("144 kN", text)
        self.assertIn("96 kN", text)

    def test_heading_subtitle_and_date_overlay_pdf_without_any_footings(self):
        plan = self.plan(self.drawing(), sida=2)
        subtitle = "Kontroller: allmänna bärighetsekvationen, isolering och H-stabilitet i X-led"
        plan.lagg_till_rubrik("Hus 1 – X_g", underrubrik="Revision A\n" + subtitle, x=.1, y=.1, bredd=1000)
        plan.lagg_till_datum("26/10/08", x=.7, y=.1)
        before = plan._document()
        reader = PdfReader(io.BytesIO(plan._pdf_bytes()))
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        for expected in ("ORIGINAL 2", "Hus 1 – X_g", "Revision A", subtitle, "26/10/08"):
            self.assertIn(expected, page.extract_text())
        self.assertFalse(page.images)
        self.assertEqual(tuple(page.mediabox), (0, 0, 700, 500))
        self.assertEqual(plan._document(), before)

    def test_heading_text_width_does_not_change_its_drawing_position_or_font_size(self):
        plan = self.plan()
        ident = plan.lagg_till_rubrik("Hus 1", underrubrik="Revision A", x=.3, y=.2, bredd=400)
        before = self.render(plan._pdf_bytes())
        plan.uppdatera_text(ident, width=1200)
        after = self.render(plan._pdf_bytes())
        self.assertIsNone(ImageChops.difference(before, after).getbbox())

    def test_sliding_capacity_rounds_display_to_one_decimal_but_preserves_result_precision(self):
        plan = self.plan()
        ident = self.tag(plan, indata={"glid_x": True, "V_Ed_EQU": 215.4, "glid_mu": .9, "glid_L": 6.4})
        plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 100.123}
        before = plan._document()
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertEqual(text.replace("\u00a0", " ").count("1 240,7 kN"), 2, "Label and global legend use one decimal")
        self.assertIn("100,12 kN", text, "The demand keeps its existing precision")
        self.assertNotIn("1 240,704", text.replace("\u00a0", " "))
        self.assertEqual(plan._document(), before)
        tag = next(tag for tag in plan.taggar if tag["id"] == ident)
        self.assertAlmostEqual(tag["sliding"]["x"], 1240.704)
        self.assertAlmostEqual(plan.glidningsresultat["x"]["H_Rd"], 1240.704)

    def render(self, data, page=0, scale=2):
        with pdfium.PdfDocument(data) as document:
            pdf_page = document[page]
            try:
                bitmap = pdf_page.render(scale=scale)
                try:
                    return bitmap.to_pil().convert("RGB")
                finally:
                    bitmap.close()
            finally:
                pdf_page.close()

    def test_wall_length_is_exported_only_with_sliding_direction_and_not_repeated_when_active(self):
        plan = self.plan()
        ident = self.tag(plan, indata={"glid_L": 6.2})
        for calculated in (False, True):
            if calculated:
                plan.berakna(ident)
            for enabled in (False, True):
                plan.glidning = {"enabled": enabled}
                text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
                self.assertNotIn(" · L 6,2 m", text)
                self.assertNotIn("Glidmotstånd – globalt", text)
        plan.uppdatera(ident, indata={"glid_x": True, "V_Ed_EQU": 120, "glid_mu": .4})
        for enabled in (False, True):
            plan.glidning = {"enabled": enabled}
            text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
            self.assertNotIn(" · Lsu", text)
            self.assertIn("Glidmotstånd – globalt", text)
            self.assertEqual(text.count("6,2 m"), 1)
        plan.uppdatera(ident, indata={"isolering": True})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertNotIn(" · L 6,2 m", text)
        self.assertNotIn("Glidmotstånd – globalt", text)
        plan.uppdatera(ident, indata={"lang": 0, "lasttyp": 0})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertNotIn("6,2 m", text)

    def test_overridden_wall_by_is_shown_in_export_with_separate_gliding_length(self):
        plan = self.plan()
        ident = self.tag(plan, indata={"b": .8, "l": 2.4, "glid_L": 6.2, "glid_x": True})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertRegex(text, r"bₓ 0,8 m · b\s*ᵧ\s+2,4 m · t 0,3 m")
        self.assertRegex(text, r"L\s*su\s+6,2 m")
        plan.uppdatera(ident, indata={"l": 1})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("bₓ 0,8 m", text)
        self.assertNotIn("×", text)

    def test_legend_scales_all_pdf_content_without_changing_axes_or_calculations(self):
        Image.new("RGB", (1600, 1000), "white").save(self.image)
        plan = self.plan()
        plan.glidning = {"enabled": True, "check_x": True, "check_y": True,
                        "H_x_Ed": 100, "H_y_Ed": 150,
                        "placements": {"1": {"symbol": {"x": .8, "y": .7, "size": 160},
                                              "legend": {"x": .1, "y": .1, "size": 410}}}}
        images, bounds = [], []
        results = plan.glidningsresultat
        for size in (205, 820):
            plan.glidning = {"placements": {"1": {"symbol": {"x": .8, "y": .7, "size": 160},
                                                   "legend": {"x": .1, "y": .1, "size": size}}}}
            image = self.render(plan._pdf_bytes(), scale=1)
            images.append(image)
            crop = image.crop((110, 65, 800, 650))
            bounds.append(ImageChops.difference(crop, Image.new("RGB", crop.size, "white")).getbbox())
            self.assertEqual(plan.glidningsresultat, results)
        small, big = bounds
        self.assertAlmostEqual((big[2] - big[0]) / (small[2] - small[0]), 4, delta=.05)
        self.assertAlmostEqual((big[3] - big[1]) / (small[3] - small[1]), 4, delta=.1)
        self.assertIsNone(ImageChops.difference(images[0].crop((900, 500, 1200, 750)),
                                              images[1].crop((900, 500, 1200, 750))).getbbox())

    def test_selected_page_retains_vector_text_and_page_format_without_changing_project(self):
        source = self.drawing()
        original = source.read_bytes()
        plan = self.plan(source, sida=2)
        first = self.tag(plan, littera="VS ÅÄÖ")
        self.tag(plan, littera="PS2")
        plan.berakna(first)
        snapshot = (plan.taggar, plan.resultat, copy.deepcopy(plan.background), plan._document())
        exported = plan.exportera_pdf(self.root / "export.pdf")
        reader = PdfReader(exported)
        self.assertEqual(len(reader.pages), 1)
        before, after = PdfReader(io.BytesIO(original)).pages[1], reader.pages[0]
        self.assertEqual(before.mediabox, after.mediabox)
        self.assertIn("ORIGINAL 2", after.extract_text())
        self.assertNotIn("ORIGINAL 1", after.extract_text())
        self.assertNotIn("ORIGINAL 3", after.extract_text())
        self.assertFalse(after.get("/Annots"), "Labels are page content, not interactive annotations")
        self.assertFalse(after.images, "Vector drawings must not be rasterized")
        self.assertIn("VS ÅÄÖ", reader.pages[0].extract_text())
        self.assertIn("PS2", reader.pages[0].extract_text())
        self.assertEqual((plan.taggar, plan.resultat, plan.background, plan._document()), snapshot)
        self.assertEqual(source.read_bytes(), original)

    def test_etiketter_foljer_beskurna_och_roterade_sidors_synliga_koordinater(self):
        source = self.drawing()
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                writer = PdfWriter()
                page = writer.add_page(PdfReader(source).pages[0])
                page.cropbox = RectangleObject((50, 100, 450, 650))
                page.rotate(rotation)
                cropped = self.root / f"cropped-{rotation}.pdf"
                writer.write(cropped)
                plan = self.plan(cropped)
                ident = self.tag(plan)
                plan.berakna(ident)
                output = plan.exportera_pdf(self.root / f"out-{rotation}.pdf")
                exported = PdfReader(output).pages[0]
                self.assertEqual(exported.rotation, rotation)
                self.assertEqual(exported.cropbox, page.cropbox)
                before = self.render(cropped)
                after = self.render(output)
                self.assertEqual(before.size, after.size)
                # Shadows now follow the interface too; measure the opaque
                # card rather than its translucent shadow around the border.
                bbox = ImageChops.difference(before, after).convert("L").point(lambda value: 255 if value > 50 else 0).getbbox()
                self.assertAlmostEqual(bbox[0], after.width * .3 - 10, delta=2)
                self.assertAlmostEqual(bbox[1], after.height * .4 - 10, delta=2)
                # The green dot is at the same drawing coordinate in all rotations.
                dot = (round(after.width * .3 + .5), round(after.height * .4 + 4.5))
                self.assertEqual(after.getpixel(dot), (35, 129, 97))

    def test_sparat_projekt_kan_exporteras_utan_originalfil(self):
        source = self.drawing()
        plan = self.plan(source)
        ident = self.tag(plan)
        plan.berakna(ident)
        project = plan.spara(self.root / "project.json")
        source.unlink()
        reopened = Grundplan.oppna(project)
        self.addCleanup(reopened.close)
        output = reopened.exportera_pdf(self.root / "reopened.pdf")
        self.assertIn("VS1", PdfReader(output).pages[0].extract_text())
        self.assertEqual(len(PdfReader(output).pages), 1)

    def test_etikettstorlek_andrar_bara_etiketterna(self):
        plan = self.plan()
        ident = self.tag(plan)
        plan.berakna(ident)
        bounds = []
        for size in (20, 180):
            plan.etikettstorlek = size
            image = self.render(plan._pdf_bytes(), scale=4)
            self.assertEqual(image.size, (2400, 1800))
            bounds.append(ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox())
        small, large = bounds
        self.assertAlmostEqual((large[2] - large[0]) / (small[2] - small[0]), 9, delta=.3)
        self.assertAlmostEqual((large[3] - large[1]) / (small[3] - small[1]), 9, delta=.3)

    def test_status_for_inaktuella_sulor_och_isoleringsresultat(self):
        plan = self.plan()
        self.tag(plan, littera="Ny")
        stale = self.tag(plan, littera="Ändrad")
        plan.berakna(stale)
        plan.uppdatera(stale, indata={"b": 2})
        error = self.tag(plan, littera="Fel", indata={"b": 0})
        with self.assertRaises(ValueError):
            plan.berakna(error)
        insulated = self.tag(plan, littera="Isolerad", indata={
            "isolering": True, "b": 1, "t": .4, "F_vy": 100,
            "F_vy_bruk": 70, "f_d_brott": 200, "f_d_bruk": 50,
        })
        plan.berakna(insulated)
        pad = self.tag(plan, littera="Pelarsula", typ="pelarsula", indata={"b": 1.8, "l": 2.4, "F_vy": 100})
        plan.berakna(pad)
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        for expected in ("U 22,7 %", "U 6,4 %", "Kontrollera indata", "U 160 % · bₓ 1 m",
                         "Med isolering", "Utan isolering"):
            self.assertIn(expected, text)
        self.assertRegex(text, r"bₓ 1,8 m · b\s*ᵧ\s+2,4 m · t 0,3 m")
        self.assertIn("Styrande: Isolering · bruk", text)
        self.assertEqual(text.count("Styrande: Jord · brott"), 3)
        self.assertEqual(text.count("Styrande:"), 4, "Every current bearing result has a governing-check line")
        self.assertEqual(text.count("U "), 4, "All valid objects are current; failed objects never show a utilization")

    def test_laster_filtreras_med_ratt_axel_enhet_och_negativa_sma_varden(self):
        plan = self.plan()
        ident = self.tag(plan, indata={"b": 2, "F_vy": 100, "F_hb": 0, "F_hl": None,
                                      "M_insp_b": -.25, "M_insp_l": 1e-8,
                                      "isolering": True, "F_vy_bruk": 50})
        text = "".join(PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text().split())
        for expected in ("Brott", "Bruk", "V100kN/m", "Mₓ−0,25kNm/m", "Mᵧ1,00e-8kNm/m", "V50kN/m"):
            self.assertIn(expected, text)
        self.assertNotIn("H", text)
        plan.uppdatera(ident, indata={"lang": 0, "lasttyp": 0, "isolering": False})
        text = "".join(PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text().split())
        self.assertNotIn("/m", text)
        self.assertNotIn("Bruk", text)
        self.assertNotIn("V50", text)
        self.assertIn("Mₓ−0,25kNm", text)
        self.assertIn("Mᵧ1,00e-8kNm", text)

    def test_bildens_fulla_upplosning_och_exif_rotation_bevaras(self):
        picture = self.root / "large.png"
        Image.new("RGB", (4000, 2000), "white").save(picture)
        plan = self.plan(picture)
        self.tag(plan)
        page = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        self.assertEqual((page.mediabox.width, page.mediabox.height), (3000, 1500))
        self.assertEqual(page.images[0].image.size, (4000, 2000))
        exif = Image.Exif()
        exif[274] = 6
        picture = self.root / "rotated.jpg"
        Image.new("RGB", (200, 100), "white").save(picture, exif=exif)
        plan = self.plan(picture)
        self.tag(plan)
        page = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0]
        self.assertEqual((page.mediabox.width, page.mediabox.height), (75, 150))
        self.assertEqual(page.images[0].image.size, (100, 200))

    def test_lang_etikett_vid_sidkanten_ryms_hela_vagen(self):
        plan = self.plan()
        label = "ÅÄÖ väggsula 12345678 " * 3
        self.tag(plan, x=1, y=1, littera=label.strip())
        plan.etikettstorlek = 180
        data = plan._pdf_bytes()
        self.assertIn(label.strip(), PdfReader(io.BytesIO(data)).pages[0].extract_text())
        with pdfium.PdfDocument(data) as document:
            page = document[0]
            try:
                text = page.get_textpage()
                try:
                    for i in range(text.count_chars()):
                        left, bottom, right, top = text.get_charbox(i)
                        self.assertGreaterEqual(left, -.1)
                        self.assertGreaterEqual(bottom, -.1)
                        self.assertLessEqual(right, page.get_width() + .1)
                        self.assertLessEqual(top, page.get_height() + .1)
                finally:
                    text.close()
            finally:
                page.close()

    def test_exportfel_skriver_inte_over_fil_och_ui_skickar_pdf_som_binarbuffert(self):
        plan = self.plan()
        self.tag(plan)
        path = self.root / "existing.pdf"
        path.write_bytes(b"original")
        with patch.object(plan, "_pdf_bytes", side_effect=ValueError("testfel")):
            with self.assertRaisesRegex(ValueError, "testfel"):
                plan.exportera_pdf(path)
        self.assertEqual(path.read_bytes(), b"original")
        with self.assertRaisesRegex(ValueError, ".pdf"):
            plan.exportera_pdf(self.root / "project.json")
        empty = Grundplan()
        self.addCleanup(empty.close)
        with self.assertRaisesRegex(ValueError, "ritning"):
            empty.exportera_pdf(path)
        with patch.object(plan, "send") as send:
            plan._on_message(None, {"action": "export_pdf", "view": "test", "request": 1}, [])
            reply = send.call_args.args[0]
            self.assertTrue(reply["ok"])
            self.assertEqual(reply["filename"], "ritning_med_etiketter.pdf")
            data = send.call_args.kwargs["buffers"][0]
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertIn("VS1", PdfReader(io.BytesIO(data)).pages[0].extract_text())


if __name__ == "__main__":
    unittest.main()
