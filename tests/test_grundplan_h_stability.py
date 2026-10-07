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


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestHStability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        drawing = self.folder / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(drawing)
        self.plan = Grundplan(drawing)
        self.addCleanup(self.plan.close)
        self.plan.glidning = {"enabled": True, "check_x": True, "check_y": True,
                             "H_x_Ed": 100, "H_y_Ed": 100}

    def add(self, **values):
        return self.plan.lagg_till(.2, .3, indata={"endast_h_stabilitet": True,
            "glid_x": True, "glid_y": False, "V_Ed_EQU": 120,
            "glid_mu": .4, "glid_L": 3, **values})

    def test_no_bearing_engines_are_called_even_with_missing_bearing_and_insulation_data(self):
        with patch("an_calcs.notebook.grundplan.allmanna_barighetsekvationen", side_effect=AssertionError("Soil engine")), \
             patch("an_calcs.notebook.grundplan.isolering_under_sula", side_effect=AssertionError("Insulation engine")):
            ident = self.add(b=None, F_vy=None, phi_k=None, gamma_m=0, f_d_brott=None, f_d_bruk=None)
            tag = self.plan.taggar[0]
            self.assertEqual(tag["status"], "calculated")
            self.assertEqual(tag["summary"]["kontroller"], [])
            self.assertIsNone(tag["summary"]["utnyttjandegrad"])
            self.assertNotIn("effective_area", tag["summary"])
            self.assertEqual(self.plan.berakna(ident), {"endast_h_stabilitet": True, "kontroller": []})
            self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 144)
            self.assertEqual(self.plan.glidningsresultat["y"]["count"], 0)
            self.plan.uppdatera(ident, indata={"isolering": True})
            self.assertEqual(self.plan._tag(ident)["status"], "calculated")
            self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 0)
            json.dumps(self.plan.state, allow_nan=False)
        self.plan.uppdatera(ident, indata={"endast_h_stabilitet": False})
        self.assertEqual(self.plan._tag(ident)["status"], "error")
        self.assertIsNone(self.plan._tag(ident)["summary"])

    def test_toggle_restores_existing_bearing_checks_without_changing_sliding_settings(self):
        ident = self.add(endast_h_stabilitet=False, isolering=True, f_d_brott=200, f_d_bruk=100, F_vy_bruk=60)
        original = self.plan.taggar[0]
        details = self.plan.resultat[ident]
        self.plan.uppdatera(ident, indata={"endast_h_stabilitet": True})
        self.assertEqual(self.plan._tag(ident)["summary"]["kontroller"], [])
        self.assertEqual(self.plan.taggar[0]["sliding"]["x"], 0)
        self.plan.uppdatera(ident, indata={"endast_h_stabilitet": False})
        self.assertEqual(self.plan.taggar[0], original)
        self.assertEqual(self.plan.resultat[ident], details)
        self.plan.uppdatera(ident, indata={"endast_h_stabilitet": True, "isolering": False})
        self.plan.uppdatera(ident, indata={"glid_L": 4})
        self.assertEqual(self.plan.taggar[0]["sliding"]["x"], 192)
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 192)

    def test_missing_sliding_inputs_remain_incomplete_and_direction_choices_are_explicit(self):
        ident = self.add(V_Ed_EQU=None)
        self.assertEqual(self.plan.glidningsresultat["x"]["status"], "incomplete")
        self.assertIsNone(self.plan.glidningsresultat["x"]["H_Rd"])
        self.plan.uppdatera(ident, indata={"glid_x": False})
        self.assertEqual(self.plan.taggar[0]["sliding"]["status"], "inactive")
        self.assertEqual(self.plan.glidningsresultat["x"]["count"], 0)
        self.plan.uppdatera(ident, indata={"glid_y": True, "V_Ed_EQU": 120})
        self.assertEqual(self.plan.glidningsresultat["y"]["H_Rd"], 144)
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 0)

    def test_copy_bulk_save_and_legacy_projects_preserve_modes(self):
        wall = self.add()
        pad = self.add(lang=0, V_Ed_EQU=200)
        copied = self.plan.kopiera(wall, .6, .6)
        self.assertTrue(self.plan._tag(copied)["values"]["endast_h_stabilitet"])
        self.plan.uppdatera_flera([wall, pad], indata={"endast_h_stabilitet": False})
        for ident in (wall, pad):
            self.assertNotIn("endast_h_stabilitet", self.plan._tag(ident)["summary"])
        self.plan.uppdatera_flera([wall, pad], indata={"endast_h_stabilitet": True})
        restored = Grundplan.oppna(self.plan.spara(self.folder / "saved.json"))
        self.addCleanup(restored.close)
        self.assertEqual(restored.taggar, self.plan.taggar)
        self.assertEqual(restored.resultat, self.plan.resultat)
        legacy = self.plan._document()
        legacy["version"] = 6
        for tag in legacy["tags"]:
            del tag["values"]["endast_h_stabilitet"]
        restored._load_document(json.dumps(legacy).encode())
        for tag in restored.taggar:
            self.assertFalse(tag["values"]["endast_h_stabilitet"])
            self.assertEqual(len(tag["summary"]["kontroller"]), 1)

    def test_mode_requires_boolean_and_invalid_updates_are_atomic(self):
        ident = self.add()
        original = self.plan.taggar
        for value in (None, 0, 1, "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan.uppdatera(ident, indata={"endast_h_stabilitet": value})
            self.assertEqual(self.plan.taggar, original)
