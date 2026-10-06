import copy
import importlib.util
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
class TestGrundplanBulk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "plan.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image)
        self.addCleanup(self.plan.close)
        self.wall1 = self.plan.lagg_till(.1, .2, indata={"F_vy": 90, "b": .8})
        self.wall2 = self.plan.lagg_till(.3, .4, indata={"F_vy": 140, "b": 1.2})
        self.pad = self.plan.lagg_till(.6, .7, typ="pelarsula", indata={"F_vy": 300, "b": 2, "l": 3})
        for ident in (self.wall1, self.wall2, self.pad):
            self.plan.berakna(ident)

    def test_width_patch_preserves_individual_loads_and_unselected_results(self):
        pad = copy.deepcopy(self.plan._tag(self.pad))
        old = {tag["id"]: tag for tag in self.plan.taggar}
        with patch.object(self.plan, "_publish", wraps=self.plan._publish) as publish:
            report = self.plan.uppdatera_flera([self.wall1, self.wall2], indata={"b": 1.1})
        publish.assert_called_once()
        self.assertEqual(report, {"updated": 2, "calculated": 0, "errors": []})
        for ident in (self.wall1, self.wall2):
            tag = self.plan._tag(ident)
            self.assertEqual(tag["values"], {**old[ident]["values"], "b": 1.1})
            self.assertEqual(tag["label"], old[ident]["label"])
            self.assertEqual(tag["status"], "stale")
            self.assertIsNone(tag["summary"])
            self.assertNotIn(ident, self.plan.resultat)
        self.assertEqual(self.plan._tag(self.pad), pad)
        self.assertIn(self.pad, self.plan.resultat)

    def test_pad_bx_by_and_insulation_recalculate_and_roundtrip(self):
        second = self.plan.kopiera(self.pad, .8, .8, indata={"F_vy": 400})
        ids = [self.pad, second]
        values = {"b": 2.2, "l": 2.8, "isolering": True, "isolerprodukt": "EPS S200",
                  "f_d_brott": 200, "f_d_bruk": 80, "F_vy_bruk": 180}
        report = self.plan.uppdatera_flera(ids, indata=values, berakna=True)
        self.assertEqual(report["calculated"], 2)
        self.assertFalse(report["errors"])
        self.assertNotEqual(self.plan._tag(ids[0])["summary"]["last"], self.plan._tag(ids[1])["summary"]["last"])
        for ident in ids:
            self.assertEqual(self.plan._tag(ident)["values"]["b"], 2.2)
            self.assertEqual(self.plan._tag(ident)["values"]["l"], 2.8)
            self.assertIn("isolering", self.plan._tag(ident)["summary"])
        saved = self.plan.spara(Path(self.tmp.name) / "bulk.json")
        reopened = Grundplan.oppna(saved)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.taggar, self.plan.taggar)
        self.assertEqual(reopened.resultat, self.plan.resultat)
        self.plan.uppdatera_flera(ids, indata={"isolering": False}, berakna=True)
        for ident in ids:
            self.assertNotIn("isolering", self.plan._tag(ident)["summary"])
            self.assertEqual(self.plan._tag(ident)["values"]["isolerprodukt"], "EPS S200")
            self.assertEqual(self.plan._tag(ident)["values"]["f_d_bruk"], 80)

    def test_invalid_batch_cannot_partially_change_results_or_values(self):
        before = self.plan._document(), self.plan.resultat, self.plan.state
        cases = [([], {"b": 1}), ([self.wall1, self.wall1], {"b": 1}),
                 ([self.wall1, "missing"], {"b": 1}), ([self.wall1], {}),
                 ([self.wall1], {"lang": 0}), ([self.wall1], {"unknown": 1}),
                 ([self.wall1, self.wall2], {"b": float("nan")}),
                 ([self.wall1, self.wall2], {"isolering": 1}),
                 ([self.wall1, self.pad], {"F_vy": 100}),
                 ([self.wall1, self.pad], {"l": 2}), ([self.wall1], {"l": 2}),
                 ([self.pad], {"glid_L": 3})]
        for ids, values in cases:
            with self.subTest(ids=ids, values=values), self.assertRaises(ValueError):
                self.plan.uppdatera_flera(ids, indata=values)
            self.assertEqual((self.plan._document(), self.plan.resultat, self.plan.state), before)

    def test_calculation_failure_is_per_footing_and_never_retains_old_pass(self):
        self.plan.uppdatera(self.wall1, indata={"f_d_brott": 200, "f_d_bruk": 150, "F_vy_bruk": 70})
        report = self.plan.uppdatera_flera([self.wall1, self.wall2], indata={"isolering": True}, berakna=True)
        self.assertEqual(report["calculated"], 1)
        self.assertEqual([error["id"] for error in report["errors"]], [self.wall2])
        self.assertEqual(self.plan._tag(self.wall1)["status"], "calculated")
        self.assertEqual(self.plan._tag(self.wall2)["status"], "error")
        self.assertIsNone(self.plan._tag(self.wall2)["summary"])
        self.assertNotIn(self.wall2, self.plan.resultat)

    def test_mixed_types_can_change_insulation_but_keep_individual_service_loads(self):
        ids = [self.wall1, self.pad]
        for ident, load in zip(ids, (50, 180)):
            self.plan.uppdatera(ident, indata={"F_vy_bruk": load})
        report = self.plan.uppdatera_flera(ids, indata={"isolering": True, "f_d_brott": 200, "f_d_bruk": 150}, berakna=True)
        self.assertEqual(report["calculated"], 2)
        self.assertEqual([self.plan._tag(ident)["values"]["F_vy_bruk"] for ident in ids], [50, 180])

    def test_comment_and_gliding_patch_preserve_bearing_results_and_refresh_global_sum(self):
        before = self.plan.resultat
        self.plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 200}
        self.plan.uppdatera_flera([self.wall1, self.wall2], indata={
            "isolerprodukt": "Kommentar", "glid_x": True, "glid_mu": .4, "V_Ed_EQU": 120, "glid_L": 3})
        self.assertEqual(self.plan.resultat, before)
        self.assertAlmostEqual(self.plan.glidningsresultat["x"]["H_Rd"], 288)
        self.assertEqual(self.plan.glidningsresultat["x"]["count"], 2)

    def test_widget_command_returns_batch_report(self):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "bulk_update", "ids": [self.wall1, self.wall2],
                "values": {"b": .9}, "calculate": True, "request": 5, "view": "test"}, [])
        reply = send.call_args.args[0]
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["request"], 5)
        self.assertEqual(reply["report"]["calculated"], 2)
