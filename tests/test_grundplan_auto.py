import copy
import importlib.util
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


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook] för notebooktesterna.")
class TestAutomaticCalculation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "plan.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image)
        self.addCleanup(self.plan.close)

    def test_new_changed_and_corrected_objects_calculate_automatically_on_all_pages(self):
        current = self.plan.lagg_till(.1, .1, indata={"F_vy": 80})
        changed = self.plan.lagg_till(.3, .3, indata={"F_vy": 100})
        for ident in (current, changed):
            self.plan.berakna(ident)
        old = copy.deepcopy(self.plan._tag(current)), self.plan.resultat[current]
        self.plan.uppdatera(changed, indata={"b": .9})
        failed = self.plan.lagg_till(.4, .4, indata={"b": -1})
        with self.assertRaises(ValueError):
            self.plan.berakna(failed)
        self.plan.uppdatera(failed, indata={"b": .8})
        self.plan.background = {**self.plan.background, "page_count": 2}
        new = self.plan.lagg_till(.6, .6, typ="pelarsula", sida=2, indata={"b": 2, "l": 3})
        self.assertEqual((self.plan._tag(current), self.plan.resultat[current]), old)
        self.assertTrue(all(tag["status"] == "calculated" for tag in self.plan.taggar))
        self.assertEqual(self.plan._tag(changed)["summary"]["b"], .9)
        self.assertEqual(self.plan._tag(failed)["summary"]["b"], .8)
        self.assertEqual(self.plan._tag(new)["page"], 2)

    def test_errors_do_not_stop_other_objects_or_leave_old_passes_and_can_be_retried(self):
        bad = self.plan.lagg_till(.1, .1)
        self.plan.berakna(bad)
        self.plan.uppdatera(bad, indata={"b": None})
        good = self.plan.lagg_till(.2, .2)
        self.assertEqual(self.plan._tag(bad)["status"], "error")
        self.assertIsNone(self.plan._tag(bad)["summary"])
        self.assertNotIn(bad, self.plan.resultat)
        self.assertIn(good, self.plan.resultat)
        self.plan.uppdatera(bad, indata={"b": .9})
        self.assertEqual(self.plan._tag(bad)["status"], "calculated")
        self.assertIn(bad, self.plan.resultat)

    def test_widget_calculates_authoritative_values_and_reports_all_objects(self):
        ident = self.plan.lagg_till(.2, .3, indata={"F_vy": 100})
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "update", "id": ident, "values": {"F_vy": 150},
                                       "summary": {"utnyttjandegrad": 0},
                                       "request": 8, "view": "table"}, [])
        reply = send.call_args.args[0]
        self.assertTrue(reply["ok"])
        self.assertEqual(self.plan._tag(ident)["status"], "calculated")
        self.assertEqual(self.plan._tag(ident)["values"]["F_vy"], 150)
        self.assertGreater(self.plan._tag(ident)["summary"]["utnyttjandegrad"], 0)
        saved = self.plan.spara(Path(self.tmp.name) / "table.json")
        reopened = Grundplan.oppna(saved)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.taggar, self.plan.taggar)
        self.assertEqual(reopened.resultat, self.plan.resultat)

    def test_old_uncomputed_project_recalculates_without_trusting_saved_summary(self):
        ident = self.plan.lagg_till(.2, .3)
        document = self.plan._document()
        document["calculator_version"] = "old"
        document["tags"][0]["calculated"] = False
        document["tags"][0]["summary"] = {"utnyttjandegrad": 0}
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan._tag(ident)["status"], "calculated")
        self.assertGreater(self.plan._tag(ident)["summary"]["utnyttjandegrad"], 0)

    def test_label_position_comment_and_sliding_changes_keep_current_bearing_result(self):
        ident = self.plan.lagg_till(.2, .3)
        old = self.plan._tag(ident)["summary"], self.plan.resultat[ident]
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Must not recalculate unchanged bearing inputs")):
            self.plan.uppdatera(ident, littera="VS7", x=.4, y=.5,
                               indata={"isolerprodukt": "Kommentar", "V_Ed_EQU": 100, "glid_x": True})
        self.assertEqual((self.plan._tag(ident)["summary"], self.plan.resultat[ident]), old)
