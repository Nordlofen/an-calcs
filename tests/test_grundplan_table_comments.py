import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2", "pypdf", "reportlab"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook] för notebooktesterna.")
class TestTableAndComments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.image = self.folder / "plan.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image)
        self.addCleanup(self.plan.close)

    def test_comment_update_and_copy_preserve_calculations_and_newlines(self):
        ident = self.plan.lagg_till(.1, .2)
        before = copy.deepcopy((self.plan._tag(ident)["summary"], self.plan.resultat))
        comment = 'Kontrollera vid entré.\n<script>alert("hej")</script>'
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Text must not recalculate")):
            self.plan.uppdatera(ident, indata={"kommentar": comment})
        self.assertEqual((self.plan._tag(ident)["summary"], self.plan.resultat), before)
        clone = self.plan.kopiera(ident, .3, .4)
        self.plan.uppdatera(clone, indata={"kommentar": "Egen kommentar"})
        self.assertEqual(self.plan._tag(ident)["values"]["kommentar"], comment)
        self.assertEqual(self.plan._tag(clone)["values"]["kommentar"], "Egen kommentar")
        html = self.plan._html_bytes().decode()
        snapshot = json.loads(re.search(r'<script id="grundplan-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(snapshot["state"]["tags"][0]["values"]["kommentar"], comment)
        self.assertNotIn('<script>alert("hej")</script>', html)

    def test_comments_bulk_edit_mixed_types_and_h_only_without_engineering_changes(self):
        wall = self.plan.lagg_till(.1, .2)
        pad = self.plan.lagg_till(.3, .4, typ="pelarsula", indata={"endast_h_stabilitet": True})
        before = copy.deepcopy(self.plan.resultat)
        self.plan.uppdatera_flera([wall, pad], indata={"kommentar": "Samma\nkommentar"})
        self.assertEqual(self.plan.resultat, before)
        self.assertEqual([tag["values"]["kommentar"] for tag in self.plan.taggar], ["Samma\nkommentar"] * 2)
        self.assertFalse(self.plan._tag(pad)["values"]["isolering"])
        before = self.plan._document()
        with self.assertRaises(ValueError):
            self.plan.uppdatera_flera([wall, pad], indata={"kommentar": None})
        self.assertEqual(self.plan._document(), before)

    def test_table_view_and_comments_roundtrip_and_old_projects_default(self):
        ident = self.plan.lagg_till(.1, .2, indata={"kommentar": "Två\nrader"})
        self.plan.tabellvy = {"collapsed": ["lang", "F_vy", "isolering"], "sort": {"key": "glid_mu", "direction": "descending"}}
        expected = self.plan.tabellvy
        path = self.plan.spara(self.folder / "project.json")
        restored = Grundplan.oppna(path)
        self.addCleanup(restored.close)
        self.assertEqual(restored.tabellvy, expected)
        self.assertEqual(restored._tag(ident)["values"]["kommentar"], "Två\nrader")
        html = restored._html_bytes().decode()
        snapshot = json.loads(re.search(r'<script id="grundplan-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(snapshot["state"]["table_view"], expected)
        old = self.plan._document()
        old["version"] = 8
        del old["table_view"]
        del old["tags"][0]["values"]["kommentar"]
        self.plan._load_document(json.dumps(old).encode())
        self.assertEqual(self.plan.tabellvy, {"collapsed": [], "sort": {"key": None, "direction": "ascending"}})
        self.assertEqual(self.plan._tag(ident)["values"]["kommentar"], "")

    def test_table_view_validation_commands_are_atomic_and_do_not_change_tags(self):
        self.plan.lagg_till(.1, .2)
        before = self.plan._document()
        invalid = [{"collapsed": ["unknown"]}, {"collapsed": ["lang", "lang"]}, {"collapsed": "lang"},
                   {"sort": {"key": "unknown", "direction": "ascending"}}, {"sort": {"key": "b", "direction": "bad"}},
                   {"sort": {"key": "b"}}, {"unknown": 5}]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.plan.tabellvy = value
                self.assertEqual(self.plan._document(), before)
                with self.assertRaises(ValueError):
                    self.plan._load_document(json.dumps({**before, "table_view": value}).encode())
                self.assertEqual(self.plan._document(), before)
        tags, calculations = self.plan.taggar, self.plan.resultat
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "table_view", "settings": {"sort": {"key": "b", "direction": "ascending"}}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
        self.assertEqual((self.plan.taggar, self.plan.resultat), (tags, calculations))
        detached = self.plan.tabellvy
        detached["sort"]["key"] = "t"
        self.assertEqual(self.plan.tabellvy["sort"]["key"], "b")

    def test_display_sizes_roundtrip_in_projects_html_and_legacy_defaults(self):
        self.plan.lagg_till(.1, .2)
        self.plan.visningsstorlekar = {"board_height": 900, "table_height": 320, "board_width": 1200, "table_width": 850}
        expected = self.plan.visningsstorlekar
        restored = Grundplan.oppna(self.plan.spara(self.folder / "heights.json"))
        self.addCleanup(restored.close)
        self.assertEqual(restored.visningsstorlekar, expected)
        self.assertEqual(restored.state["layout"], expected)
        snapshot = json.loads(re.search(r'<script id="grundplan-data" type="application/json">(.*?)</script>',
            restored._html_bytes().decode(), re.S).group(1))
        self.assertEqual(snapshot["state"]["layout"], expected)
        old = self.plan._document()
        del old["layout"]
        restored._load_document(json.dumps(old).encode())
        self.assertEqual(restored.visningshojder, {"board_height": None, "table_height": None})
        self.assertEqual(restored.visningsstorlekar, dict.fromkeys(expected))
        old["layout"] = {"board_height": 720, "table_height": 300}
        restored._load_document(json.dumps(old).encode())
        self.assertEqual(restored.visningsstorlekar, {"board_height": 720, "table_height": 300, "board_width": None, "table_width": None})

    def test_display_sizes_validate_atomically_without_recalculating_or_mutating_tags(self):
        self.plan.lagg_till(.1, .2)
        before = self.plan._document()
        for invalid in [None, [], {"other": 500}, {"board_height": True}, {"board_height": "900"},
                        {"board_height": float("inf")}, {"board_height": 279}, {"board_height": 2401},
                        {"table_height": 159}, {"table_height": 1801}, {"board_width": True}, {"board_width": "900"},
                        {"board_width": float("nan")}, {"board_width": 319}, {"table_width": 4001}]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.plan.visningsstorlekar = invalid
                with self.assertRaises(ValueError):
                    self.plan._load_document(json.dumps({**before, "layout": invalid}).encode())
                self.assertEqual(self.plan._document(), before)
        tags, calculations = self.plan.taggar, self.plan.resultat
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Display must not recalculate")):
            with patch.object(self.plan, "send") as send:
                self.plan._on_message(None, {"action": "layout", "settings": {"board_height": 800, "board_width": 1300}}, [])
                self.assertTrue(send.call_args.args[0]["ok"])
            self.plan.visningshojder = {"table_height": 400}
        self.assertEqual((self.plan.taggar, self.plan.resultat), (tags, calculations))
        self.assertEqual(self.plan.visningshojder, {"board_height": 800, "table_height": 400})
        self.assertEqual(self.plan.visningsstorlekar, {"board_height": 800, "table_height": 400, "board_width": 1300, "table_width": None})
        detached = self.plan.visningsstorlekar
        detached["board_width"] = 1000
        self.assertEqual(self.plan.visningsstorlekar["board_width"], 1300)
        self.plan.visningshojder = {"board_height": None}
        self.assertEqual(self.plan.visningshojder, {"board_height": None, "table_height": 400})
        self.assertEqual(self.plan.visningsstorlekar["board_width"], 1300, "Legacy height updates preserve width")

    def test_insulation_widget_is_saved_exported_and_counts_h_only_as_uninsulated(self):
        from io import BytesIO
        from pypdf import PdfReader
        self.plan.lagg_till(.1, .2, littera="VS10", indata={"isolering": True})
        self.plan.lagg_till(.3, .4, littera="VS2")
        self.plan.lagg_till(.5, .6, littera="VS1", indata={"endast_h_stabilitet": True, "isolering": True})
        before = (self.plan.taggar, self.plan.resultat)
        settings = {"enabled": True, "x": .65, "y": .3, "size": 450}
        self.plan.isoleringswidget = settings
        pdf = PdfReader(BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("Föreskrivna utan isolering", pdf)
        self.assertIn("Med isolering\n1", pdf)
        self.assertIn("Utan isolering\n2", pdf)
        self.assertIn("VS1, VS2", pdf)
        snapshot = json.loads(re.search(r'<script id="grundplan-data" type="application/json">(.*?)</script>', self.plan._html_bytes().decode(), re.S).group(1))
        self.assertEqual(snapshot["state"]["insulation_widget"], settings)
        self.plan.isoleringswidget = {"enabled": False}
        restored = Grundplan.oppna(self.plan.spara(self.folder / "widget.json"))
        self.addCleanup(restored.close)
        restored.isoleringswidget = {"enabled": True}
        self.assertEqual(restored.isoleringswidget, settings)
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)

    def test_insulation_widget_invalid_settings_and_commands_are_atomic(self):
        before = self.plan._document()
        for settings in ({"enabled": 1}, {"size": 0}, {"x": -1}, {"y": 1.2}, {"size": float("nan")}, {"unknown": 1}):
            with self.assertRaises(ValueError):
                self.plan.isoleringswidget = settings
            self.assertEqual(self.plan._document(), before)
            with self.assertRaises(ValueError):
                self.plan._load_document(json.dumps({**before, "insulation_widget": settings}).encode())
            self.assertEqual(self.plan._document(), before)
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "insulation_widget", "settings": {"enabled": True}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.plan._on_message(None, {"action": "insulation_placement", "page": 1, "position": {"x": .2, "y": .3, "size": 400}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
        self.assertEqual(self.plan.isoleringswidget, {"enabled": True, "x": .2, "y": .3, "size": 400})
