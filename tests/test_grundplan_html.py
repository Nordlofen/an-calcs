import base64
import copy
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2", "reportlab", "pypdf"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan
    from pypdf import PdfReader


class HtmlSnapshot(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.scripts = []
        self.active = None
        self.resources = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.resources.extend(attrs[key] for key in ("src", "href") if key in attrs)
        if tag == "script":
            self.active = {"attrs": attrs, "text": ""}
            self.scripts.append(self.active)

    def handle_data(self, text):
        if self.active is not None:
            self.active["text"] += text

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = None

    @property
    def snapshot(self):
        return json.loads(next(script["text"] for script in self.scripts
                               if script["attrs"].get("id") == "grundplan-data"))


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook] för HTML-testerna.")
class TestGrundplanHtml(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "ritning.pdf"
        Image.new("RGB", (800, 600), "white").save(self.source, save_all=True,
                                                   append_images=[Image.new("RGB", (600, 800), "#a0c0e0")])
        self.plan = Grundplan(self.source, sida=2, titel="Hus ÅÄÖ")
        self.addCleanup(self.plan.close)

    def tag(self, **kwargs):
        return self.plan.lagg_till(.3, .4, **{"indata": {"F_vy": 100, "b": 1}, **kwargs})

    def snapshot(self):
        return HtmlSnapshot(self.plan._html_bytes().decode("utf-8")).snapshot

    def test_html_contains_calibration_and_offline_pdf_of_selected_page(self):
        self.tag(littera="VS1")
        self.plan.kalibrering = {"start": {"x": .1, "y": .2}, "end": {"x": .7, "y": .2}, "length_m": 12.5}
        original = self.plan._document(), self.plan.taggar, self.plan.resultat
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("No calculation")):
            data = self.snapshot()
        self.assertEqual(data["state"]["calibration"], self.plan.kalibrering)
        self.assertEqual(data["pdf"]["filename"], "ritning_med_etiketter.pdf")
        pdf = base64.b64decode(data["pdf"]["data"], validate=True)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)
        self.assertGreater(float(reader.pages[0].mediabox.height), float(reader.pages[0].mediabox.width))
        self.assertIn("VS1", reader.pages[0].extract_text())
        self.assertEqual((self.plan._document(), self.plan.taggar, self.plan.resultat), original)

    def test_sliding_snapshot_includes_selected_page_totals_and_saved_positions(self):
        self.tag(indata={"glid_x": True, "V_Ed_EQU": 120, "glid_mu": .4, "glid_L": 3})
        self.tag(sida=2, indata={"lang": 0, "glid_x": True, "glid_y": True,
                                "V_Ed_EQU": 240, "glid_mu": .4})
        self.plan.glidning = {"enabled": True, "check_x": True, "check_y": True,
                              "H_x_Ed": 180, "H_y_Ed": 120,
                              "placements": {"2": {"symbol": {"x": .1, "y": .2, "size": 220},
                                                    "legend": {"x": .4, "y": .5, "size": 615}}}}
        snapshot = self.snapshot()
        self.assertEqual(snapshot["state"]["sliding"], self.plan.glidning)
        self.assertEqual(snapshot["state"]["sliding"]["placements"]["2"]["legend"]["size"], 615)
        self.assertEqual(snapshot["state"]["sliding_result"], self.plan.glidningsresultat)
        self.assertEqual(snapshot["state"]["sliding_result"]["x"]["H_Rd"], 240)
        self.assertEqual(snapshot["state"]["sliding_result"]["x"]["count"], 2)
        self.assertEqual(snapshot["state"]["sliding_result"]["y"]["H_Rd"], 96)
        fields = {field["name"]: field for field in snapshot["schema"]["fields"]}
        self.assertEqual(fields["V_Ed_EQU"]["display_symbol"], {"base": "V", "subscript": "Ed,EQU"})
        self.assertEqual(snapshot["state"]["tags"][0]["sliding"]["x"], 144)

    def test_selected_page_and_current_data_are_embedded_without_external_files(self):
        ident = self.tag(indata={"b": 1, "t": .4, "F_vy": 100, "isolering": True,
                                "F_vy_bruk": 70, "f_d_brott": 200, "f_d_bruk": 50,
                                "isolerprodukt": "EPS S200, entré"})
        self.plan.berakna(ident)
        self.tag(sida=2)
        self.plan.etikettstorlek = 150
        original = (self.source.read_bytes(), copy.deepcopy(self.plan.background),
                    self.plan._document(), self.plan.taggar, self.plan.resultat)
        path = self.plan.exportera_html(self.root / "resultat.html")
        page = HtmlSnapshot(path.read_text())
        data = page.snapshot
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.resources, [], "No network resources or paths may be needed to open the file")
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["state"]["label_size"], 150)
        self.assertEqual(data["state"]["tags"], self.plan.taggar)
        self.assertEqual(data["state"]["tags"][0]["summary"]["styrande"], "Isolering · bruk")
        self.assertEqual(set(data["state"]["tags"][0]["summary"]["effective_area"]), {"brott", "bruk"})
        fields = {field["name"]: field for field in data["schema"]["fields"]}
        self.assertEqual(fields["M_insp_l"]["label"], "Moment kring y-axeln")
        self.assertEqual(fields["M_insp_l"]["display_symbol"], {"base": "M", "subscript": "y"})
        self.assertEqual(fields["M_insp_b"]["display_symbol"], {"base": "M", "subscript": "x"})
        self.assertEqual(fields["F_vy"]["display_symbol"], {"base": "V"})
        self.assertEqual(data["schema"]["load_groups"][0]["fields"][0]["symbol"], "V")
        self.assertEqual([page["page"] for page in data["pages"]], [2])
        import base64
        for background in data["pages"]:
            prefix, image = background["url"].split(",", 1)
            self.assertEqual(prefix, "data:image/png;base64")
            with Image.open(io.BytesIO(base64.b64decode(image))) as picture:
                self.assertEqual(picture.size, (background["width"], background["height"]))
        self.assertIn("readOnly: true", page.scripts[1]["text"])
        self.assertEqual((self.source.read_bytes(), self.plan.background, self.plan._document(),
                          self.plan.taggar, self.plan.resultat), original)

    def test_overridden_wall_by_is_embedded_in_results_and_downloadable_pdf(self):
        ident = self.tag(indata={"b": .8, "l": 2.4, "glid_L": 6.2, "glid_x": True})
        data = self.snapshot()
        tag = next(tag for tag in data["state"]["tags"] if tag["id"] == ident)
        self.assertEqual(tag["values"]["l"], 2.4)
        self.assertEqual(tag["values"]["glid_L"], 6.2)
        self.assertEqual(tag["summary"]["effective_area"]["brott"]["by"], 2.4)
        text = PdfReader(io.BytesIO(base64.b64decode(data["pdf"]["data"]))).pages[0].extract_text()
        self.assertIn("0,8 × 2,4 m", text)
        self.assertIn("L\nsu\n 6,2 m", text)

    def test_html_text_och_scriptavslut_behandlas_som_vanlig_text(self):
        text = '</script><img src=x onerror=alert(1)> ÅÄÖ & "\u2028\u2029'
        self.plan.titel = text
        self.plan.underrubrik = text
        self.tag(littera=text, indata={"isolerprodukt": text})
        html = self.plan._html_bytes().decode("utf-8")
        page = HtmlSnapshot(html)
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.resources, [])
        self.assertNotIn("<img src=x", html)
        self.assertEqual(page.snapshot["state"]["title"], text)
        self.assertEqual(page.snapshot["state"]["subtitle"], text)
        self.assertEqual(page.snapshot["state"]["tags"][0]["values"]["isolerprodukt"], text)

    def test_rubriker_sparas_ateroppnas_och_exporteras_utan_att_paverka_berakningar(self):
        ident = self.tag()
        self.plan.berakna(ident)
        tags, results = self.plan.taggar, self.plan.resultat
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Must not recalculate")):
            self.plan._on_message(None, {"action": "heading", "title": "Hus B – grundplan",
                                        "subtitle": "Uppdrag 123\nRevision A\nKontrollerad grundplan"}, [])
            snapshot = self.snapshot()
        self.assertEqual(self.plan.taggar, tags)
        self.assertEqual(self.plan.resultat, results)
        self.assertEqual(snapshot["state"]["title"], "Hus B – grundplan")
        self.assertEqual(snapshot["state"]["subtitle"], "Uppdrag 123\nRevision A\nKontrollerad grundplan")
        for name in ("title", "subtitle"):
            self.assertEqual(self.plan.state[name], snapshot["state"][name])
        path = self.plan.spara(self.root / "projekt.json")
        reopened = Grundplan.oppna(path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.titel, self.plan.titel)
        self.assertEqual(reopened.underrubrik, self.plan.underrubrik)
        self.assertEqual(HtmlSnapshot(reopened._html_bytes().decode()).snapshot["state"], snapshot["state"])
        legacy = self.plan._document()
        del legacy["subtitle"]
        reopened._load_document(json.dumps(legacy).encode())
        self.assertEqual(reopened.underrubrik, "Sulgrundläggning · jordens bärighet")
        reopened.underrubrik = ""
        reopened.spara(path)
        reopened._load_document(path.read_bytes())
        self.assertEqual(reopened.underrubrik, "")

    def test_export_raknar_inte_om_och_visar_inga_inaktuella_resultat(self):
        stale = self.tag()
        self.plan.berakna(stale)
        self.plan.uppdatera(stale, indata={"b": 2})
        error = self.tag(indata={"b": 0})
        with self.assertRaises(ValueError):
            self.plan.berakna(error)
        self.tag()
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Must not recalculate")):
            tags = self.snapshot()["state"]["tags"]
        self.assertEqual([tag["status"] for tag in tags], ["calculated", "error", "calculated"])
        self.assertTrue(all(tags[i]["summary"] is not None for i in (0, 2)))
        self.assertIsNone(tags[1]["summary"])
        self.assertTrue(tags[1]["error"])

    def test_ateroppnad_json_med_rasterbild_kan_exporteras_utan_original(self):
        image = self.root / "plan.png"
        Image.new("RGB", (500, 300), "white").save(image)
        plan = Grundplan(image)
        self.addCleanup(plan.close)
        ident = plan.lagg_till(.5, .5, indata={"F_vy": 100, "b": 1})
        plan.berakna(ident)
        project = plan.spara(self.root / "plan.json")
        image.unlink()
        reopened = Grundplan.oppna(project)
        self.addCleanup(reopened.close)
        data = HtmlSnapshot(reopened.exportera_html(self.root / "resultat.htm").read_text()).snapshot
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["state"]["tags"], plan.taggar)

    def test_exportfel_lamnar_befintlig_fil_och_inga_temporarfiler(self):
        path = self.root / "resultat.html"
        path.write_bytes(b"original")
        before = set(self.root.iterdir())
        with patch.object(Path, "replace", side_effect=OSError("testfel")):
            with self.assertRaisesRegex(OSError, "testfel"):
                self.plan.exportera_html(path)
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(set(self.root.iterdir()), before)
        with self.assertRaisesRegex(ValueError, ".html"):
            self.plan.exportera_html(self.root / "project.json")
        empty = Grundplan()
        self.addCleanup(empty.close)
        with self.assertRaisesRegex(ValueError, "ritning"):
            empty.exportera_html(path)

    def test_widget_skickar_html_som_binarbuffert_och_rapporterar_fel(self):
        self.tag()
        message = {"action": "export_html", "view": "test", "request": 3}
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, message, [])
            reply = send.call_args.args[0]
            self.assertEqual(reply, {"view": "test", "request": 3, "ok": True, "filename": "ritning_resultat.html"})
            data = send.call_args.kwargs["buffers"][0]
            self.assertEqual(HtmlSnapshot(data.decode("utf-8")).snapshot["state"]["tags"], self.plan.taggar)
        with patch.object(self.plan, "_html_bytes", side_effect=ValueError("Testfel")), patch.object(self.plan, "send") as send:
            self.plan._on_message(None, message, [])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertEqual(send.call_args.args[0]["error"], "Testfel")


if __name__ == "__main__":
    unittest.main()
