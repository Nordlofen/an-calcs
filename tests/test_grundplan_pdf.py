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

    def plan(self, source=None):
        plan = Grundplan(source or self.image)
        self.addCleanup(plan.close)
        return plan

    def tag(self, plan, **kwargs):
        return plan.lagg_till(**{
            "x": .3, "y": .4, "indata": {"b": 1, "F_vy": 100}, **kwargs,
        })

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

    def test_alla_sidor_originaltext_och_sidformat_bevaras_utan_att_andra_projektet(self):
        source = self.drawing()
        original = source.read_bytes()
        plan = self.plan(source)
        first = self.tag(plan, littera="VS ÅÄÖ", sida=1)
        self.tag(plan, littera="PS2", sida=2)
        plan.berakna(first)
        plan.visa_sida(2)
        snapshot = (plan.taggar, plan.resultat, copy.deepcopy(plan.background), plan._document())
        exported = plan.exportera_pdf(self.root / "export.pdf")
        reader = PdfReader(exported)
        self.assertEqual(len(reader.pages), 3)
        for index, (before, after) in enumerate(zip(PdfReader(io.BytesIO(original)).pages, reader.pages)):
            self.assertEqual(before.mediabox, after.mediabox)
            self.assertIn(f"ORIGINAL {index + 1}", after.extract_text())
            self.assertFalse(after.get("/Annots"), "Labels are page content, not interactive annotations")
            self.assertFalse(after.images, "Vector drawings must not be rasterized")
        self.assertIn("VS ÅÄÖ", reader.pages[0].extract_text())
        self.assertNotIn("PS2", reader.pages[0].extract_text())
        self.assertIn("PS2", reader.pages[1].extract_text())
        self.assertEqual(reader.pages[2].extract_text(), "ORIGINAL 3\n")
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
        self.assertEqual(len(PdfReader(output).pages), 3)

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
        for expected in ("Ej beräknad", "Ändrad · beräkna", "Kontrollera indata", "U 160 % · b 1 m",
                         "Med isolering", "Utan isolering", "1,8 × 2,4 m"):
            self.assertIn(expected, text)
        self.assertIn("Styrande: Isolering · bruk", text)
        self.assertEqual(text.count("Styrande:"), 1, "Only the current insulation result has a governing-check line")
        self.assertEqual(text.count("U "), 2, "Stale or failed results must never be printed as current")

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
