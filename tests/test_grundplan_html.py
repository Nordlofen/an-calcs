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
HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


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
        return self.plan.lagg_till(.3, .4, **{"sida": 1, "indata": {"F_vy": 100, "b": 1}, **kwargs})

    def snapshot(self):
        return HtmlSnapshot(self.plan._html_bytes().decode("utf-8")).snapshot

    def test_alla_sidor_och_aktuella_data_baddas_in_utan_externa_filer(self):
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
        self.assertEqual([page["page"] for page in data["pages"]], [1, 2])
        import base64
        for background in data["pages"]:
            prefix, image = background["url"].split(",", 1)
            self.assertEqual(prefix, "data:image/png;base64")
            with Image.open(io.BytesIO(base64.b64decode(image))) as picture:
                self.assertEqual(picture.size, (background["width"], background["height"]))
        self.assertIn("readOnly: true", page.scripts[1]["text"])
        self.assertEqual((self.source.read_bytes(), self.plan.background, self.plan._document(),
                          self.plan.taggar, self.plan.resultat), original)

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
                                        "subtitle": "Uppdrag 123 · Revision A"}, [])
            snapshot = self.snapshot()
        self.assertEqual(self.plan.taggar, tags)
        self.assertEqual(self.plan.resultat, results)
        self.assertEqual(snapshot["state"]["title"], "Hus B – grundplan")
        self.assertEqual(snapshot["state"]["subtitle"], "Uppdrag 123 · Revision A")
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
        self.assertEqual([tag["status"] for tag in tags], ["stale", "error", "new"])
        self.assertTrue(all(tag["summary"] is None for tag in tags))
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
