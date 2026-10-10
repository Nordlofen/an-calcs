import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan
    from an_calcs.notebook.grundplan_colour import group_data


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestInactiveFootings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        drawing = self.root / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(drawing)
        self.plan = Grundplan(drawing)
        self.addCleanup(self.plan.close)
        self.plan.glidning = {"enabled": True, "check_x": True, "check_y": True,
                              "H_x_Ed": 100, "H_y_Ed": 100}

    def add(self, **values):
        return self.plan.lagg_till(.2, .3, indata={"b": 1, "F_vy": 100,
            "glid_x": True, "glid_y": True, "V_Ed_EQU": 120,
            "glid_mu": .4, "glid_L": 3, **values})

    def test_inactive_missing_inputs_never_enter_calculator_or_global_sliding(self):
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Calculator called")):
            ident = self.add(inaktiv=True, b=None, F_vy=None, phi_k=None, gamma_m=0,
                             isolering=True, f_d_brott=None, f_d_bruk=None, V_Ed_EQU=None)
            self.assertEqual(self.plan.berakna(ident), {"inaktiv": True, "kontroller": []})
            self.plan.uppdatera(ident, indata={"kommentar": "Behåll objektet"})
            tag = self.plan.taggar[0]
            self.assertEqual(tag["status"], "inactive")
            self.assertEqual(tag["summary"], {"inaktiv": True, "utnyttjandegrad": None, "kontroller": []})
            self.assertEqual(tag["load_resultants"], {"brott": None, "bruk": None})
            self.assertEqual(tag["sliding"]["selected"], {"x": False, "y": False})
            self.assertEqual(tag["sliding"]["capacity"], 0)
            for axis in ("x", "y"):
                result = self.plan.glidningsresultat[axis]
                self.assertEqual(result["H_Rd"], 0)
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["missing"], [])
            json.dumps(self.plan.state, allow_nan=False)

    def test_toggle_preserves_inputs_and_reactivation_restores_real_results(self):
        ident = self.add(isolering=True, f_d_brott=200, f_d_bruk=100, F_vy_bruk=60)
        original = self.plan.taggar[0]
        details = self.plan.resultat[ident]
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Calculator called")):
            self.plan.uppdatera(ident, indata={"inaktiv": True})
            self.plan.uppdatera(ident, indata={"kommentar": "Pausad"})
            self.assertEqual(self.plan._tag(ident)["values"], {**original["values"], "inaktiv": True, "kommentar": "Pausad"})
            self.assertEqual(self.plan._tag(ident)["summary"]["kontroller"], [])
        self.plan.uppdatera(ident, indata={"inaktiv": False})
        self.assertEqual(self.plan.resultat[ident], details)
        self.assertEqual(self.plan.taggar[0], {**original, "values": {**original["values"], "kommentar": "Pausad"}})
        # A genuine global contributor must disappear completely, not poison the total.
        self.plan.uppdatera(ident, indata={"isolering": False})
        other = self.add()
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 288)
        self.plan.uppdatera(ident, indata={"inaktiv": True})
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 144)
        self.assertEqual([item["id"] for item in self.plan.glidningsresultat["x"]["contributors"]], [other])

    def test_locked_fields_cannot_be_changed_through_api_until_reactivated(self):
        ident = self.add(inaktiv=True)
        original = copy.deepcopy(self.plan._tag(ident))
        for updates in ({"b": 2}, {"glid_L": 4}, {"isolering": True}, {"lang": 0}, {"endast_h_stabilitet": True}):
            with self.subTest(updates=updates), self.assertRaisesRegex(ValueError, "inaktiv"):
                self.plan.uppdatera(ident, indata=updates)
            self.assertEqual(self.plan._tag(ident), original)
        with self.assertRaisesRegex(ValueError, "inaktiv"):
            self.plan.uppdatera(ident, littera="Ny")
        with self.assertRaisesRegex(ValueError, "inaktiv"):
            self.plan.hanvisningslinje(ident, None)
        for invalid in (1, "true", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.plan.uppdatera(ident, indata={"inaktiv": invalid})
        self.plan.uppdatera(ident, x=.4, y=.5, indata={"kommentar": "Endast kommentar"})
        self.assertEqual(self.plan._tag(ident)["x"], .4)
        self.plan.uppdatera(ident, indata={"inaktiv": False, "b": 2}, littera="Ny")
        self.assertEqual(self.plan._tag(ident)["status"], "calculated")
        self.assertEqual(self.plan._tag(ident)["values"]["b"], 2)

    def test_bulk_is_atomic_and_copy_inherits_inactive_mode(self):
        active, inactive = self.add(), self.add(inaktiv=True)
        before = self.plan.taggar
        with self.assertRaisesRegex(ValueError, "inaktiv"):
            self.plan.uppdatera_flera([active, inactive], indata={"b": 2})
        self.assertEqual(self.plan.taggar, before)
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Calculator called")):
            report = self.plan.uppdatera_flera([active, inactive], indata={"inaktiv": True}, berakna=False)
            self.assertEqual(report, {"updated": 2, "calculated": 0, "errors": [], "inactive": 2})
            report = self.plan.uppdatera_flera([active, inactive], indata={"kommentar": "Gemensam"})
            self.assertEqual(report["calculated"], 0)
            duplicate = self.plan.kopiera(inactive, .5, .5)
            self.assertEqual(self.plan._tag(duplicate)["status"], "inactive")
            self.assertTrue(self.plan._tag(duplicate)["values"]["inaktiv"])
        report = self.plan.uppdatera_flera([active, inactive], indata={"inaktiv": False})
        self.assertEqual(report, {"updated": 2, "calculated": 2, "errors": []})

    def test_save_reload_does_not_calculate_inactive_and_legacy_objects_default_active(self):
        ident = self.add(inaktiv=True, kommentar="Sparad kommentar")
        path = self.plan.spara(self.root / "project.json")
        document = json.loads(path.read_text())
        self.assertEqual(document["version"], 22)
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Calculator called")):
            loaded = Grundplan.oppna(path)
            self.addCleanup(loaded.close)
            self.assertEqual(loaded.taggar, self.plan.taggar)
            self.assertEqual(loaded.resultat, self.plan.resultat)
        document["version"] = 18
        document["tags"][0]["values"].pop("inaktiv")
        path.write_text(json.dumps(document))
        loaded = Grundplan.oppna(path)
        self.addCleanup(loaded.close)
        self.assertFalse(loaded._tag(ident)["values"]["inaktiv"])
        self.assertEqual(loaded._tag(ident)["status"], "calculated")

    def test_every_colour_category_and_combination_excludes_inactive_objects(self):
        active, inactive = self.add(), self.add(inaktiv=True, t=.8, b=9)
        for categories in (["t"], ["b"], ["l"], ["V"], ["isolering"], ["t", "b", "V"], ["t", "b", "l", "V", "isolering"]):
            for phase in ("brott", "bruk", "EQU"):
                self.plan.farggruppering = {"enabled": True, "categories": categories, "phase": phase, "include_only_h": True}
                data = group_data(self.plan.taggar, self.plan.farggruppering)
                self.assertNotIn(inactive, data["assignments"])
                self.assertEqual(sum(group["count"] for group in data["groups"]), 1)
                self.assertIn(active, data["assignments"])

    def test_load_import_skips_matching_inactive_objects_without_replacing_inputs(self):
        inactive, active = self.add(inaktiv=True), self.add()
        labels = [self.plan._tag(ident)["label"] for ident in (inactive, active)]
        before = copy.deepcopy(self.plan._tag(inactive))
        data = {"schemaVersion": 1, "distribution": "uniform", "component": "z'", "supports": [
            {"supportId": label, "type": "line", "length": {"value": 8, "unit": "m"},
             "results": [{"category": category, "V": value, "unit": "kN/m",
                          "source": {"kind": "loadCombination", "loadCombination": "1"}}
                         for category, value in zip(("Brott", "Bruk", "EQU"), (200, 150, 120))]}
            for label in labels]}
        report = self.plan._start_load_import(json.dumps(data).encode(), "loads.json")
        self.assertEqual(report, {"updated": 1, "new": 0, "skipped_inactive": 1, "updated_ids": [active]})
        self.assertEqual(self.plan._tag(inactive), before)
        self.assertEqual(self.plan._tag(active)["values"]["F_vy"], 200)
        self.assertIsNone(self.plan.lasteffekt_import)
