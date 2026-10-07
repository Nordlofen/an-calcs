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
        self.assertNotIn("Glidmotstånd – globalt", text)

    def test_sliding_capacity_rounds_display_to_one_decimal_but_preserves_result_precision(self):
        plan = self.plan()
        ident = self.tag(plan, indata={"glid_x": True, "V_Ed_EQU": 215.4, "glid_mu": .9, "glid_L": 6.4})
        plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 100.123}
        before = plan._document()
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertEqual(text.count("1 240,7 kN"), 2, "Label and global legend use one decimal")
        self.assertIn("100,12 kN", text, "The demand keeps its existing precision")
        self.assertNotIn("1 240,704", text)
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
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertNotIn(" · L 6,2 m", text)
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
        self.assertIn("0,8 × 2,4 m", text)
        self.assertIn("L\nsu\n 6,2 m", text)
        plan.uppdatera(ident, indata={"l": 1})
        text = PdfReader(io.BytesIO(plan._pdf_bytes())).pages[0].extract_text()
        self.assertRegex(text, r"b\s*x\s*0,8 m")
        self.assertNotIn("×", text)

    def test_legend_scales_all_pdf_content_without_changing_axes_or_calculations(self):
        Image.new("RGB", (1600, 1000), "white").save(self.image)
        plan = self.plan()
        plan.glidning = {"enabled": True, "check_x": True, "check_y": True,
                        "H_x_Ed": 100, "H_y_Ed": 150}
        images, bounds = [], []
        results = plan.glidningsresultat
        for size in (205, 820):
            plan.glidning = {"placements": {"1": {"legend": {"x": .1, "y": .1, "size": size}}}}
            image = self.render(plan._pdf_bytes(), scale=1)
            images.append(image)
            crop = image.crop((110, 65, 800, 355))
            bounds.append(ImageChops.difference(crop, Image.new("RGB", crop.size, "white")).getbbox())
            self.assertEqual(plan.glidningsresultat, results)
        small, big = bounds
        self.assertAlmostEqual((big[2] - big[0]) / (small[2] - small[0]), 4, delta=.05)
        self.assertAlmostEqual((big[3] - big[1]) / (small[3] - small[1]), 4, delta=.1)
        self.assertIsNone(ImageChops.difference(images[0].crop((0, 355, 1200, 750)),
                                              images[1].crop((0, 355, 1200, 750))).getbbox())

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
                bbox = ImageChops.difference(before, after).getbbox()
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
        for size in (60, 180):
            plan.etikettstorlek = size
            image = self.render(plan._pdf_bytes(), scale=4)
            self.assertEqual(image.size, (2400, 1800))
            bounds.append(ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox())
        small, large = bounds
        self.assertAlmostEqual((large[2] - large[0]) / (small[2] - small[0]), 3, delta=.1)
        self.assertAlmostEqual((large[3] - large[1]) / (small[3] - small[1]), 3, delta=.1)

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
        for expected in ("U 22,7 %", "U 6,4 %", "Kontrollera indata", "U 160 % · b\nx\n 1 m",
                         "Med isolering", "Utan isolering", "1,8 × 2,4 m"):
            self.assertIn(expected, text)
        self.assertIn("Styrande: Isolering · bruk", text)
        self.assertEqual(text.count("Styrande:"), 1, "Only the current insulation result has a governing-check line")
        self.assertEqual(text.count("U "), 4, "All valid objects are current; failed objects never show a utilization")

    def test_laster_filtreras_med_ratt_axel_enhet_och_negativa_sma_varden(self):
        from an_calcs.notebook.grundplan_pdf import _fonts, _load_rows
        _fonts()
        plan = self.plan()
        ident = self.tag(plan, indata={"b": 2, "F_vy": 100, "F_hb": 0, "F_hl": None,
                                      "M_insp_b": -.25, "M_insp_l": 1e-8,
                                      "isolering": True, "F_vy_bruk": 50})
        values = copy.deepcopy(plan._tag(ident)["values"])
        rows = _load_rows(values)
        text = " ".join(caption + " " + line for caption, line in rows)
        for expected in ("Brott", "Bruk", "V 100 kN/m", "Mₓ -0,25 kNm/m", "Mᵧ 1,00e-08 kNm/m", "V 50 kN/m"):
            self.assertIn(expected, text)
        self.assertNotIn("H", text)
        values.update(lang=0, lasttyp=0, isolering=False)
        rows = _load_rows(values)
        text = " ".join(caption + " " + line for caption, line in rows)
        self.assertNotIn("/m", text)
        self.assertNotIn("Bruk", text)
        self.assertNotIn("50", text)
        pdf = plan._pdf_bytes()
        output = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
        self.assertIn("-0,25 kNm/m", output)
        self.assertIn("1,00e-08 kNm/m", output)

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
