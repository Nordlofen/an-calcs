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


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestSliding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.image = self.folder / "drawing.png"
        Image.new("RGB", (1000, 750), "white").save(self.image)
        self.plan = Grundplan(self.image)
        self.addCleanup(self.plan.close)
        self.plan.glidning = {"enabled": True, "check_x": True, "check_y": True, "H_x_Ed": 180, "H_y_Ed": 300}

    def add(self, **values):
        return self.plan.lagg_till(.2, .3, indata={"glid_x": True, "glid_y": True,
                 "V_Ed_EQU": 120, "glid_mu": .4, "glid_L": 3, **values})

    def test_strip_and_pad_totals_use_explicit_equ_load_without_self_weight(self):
        wall = self.add()
        pad = self.add(lang=0, V_Ed_EQU=240, glid_L=None)
        self.assertEqual(self.plan.taggar[0]["sliding"]["x"], 144)
        self.assertEqual(self.plan.taggar[1]["sliding"]["x"], 96)
        x, y = (self.plan.glidningsresultat[axis] for axis in ("x", "y"))
        self.assertEqual(x["H_Rd"], 240)
        self.assertEqual(x["count"], 2)
        self.assertEqual(x["utilization"], .75)
        self.assertEqual((x["status"], y["status"]), ("ok", "over"))
        self.plan.uppdatera(wall, indata={"F_vy": 9999, "t": 20, "gamma": 99})
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 240)
        self.plan.ta_bort(pad)
        self.assertEqual(self.plan.glidningsresultat["y"]["H_Rd"], 144)

    def test_direction_selection_zero_and_insulation_override_missing_fields(self):
        wall = self.add(glid_y=False)
        insulated = self.add(isolering=True, V_Ed_EQU=None, glid_mu=None, glid_L=None)
        self.add(V_Ed_EQU=0)
        self.assertEqual((self.plan.glidningsresultat["x"]["H_Rd"], self.plan.glidningsresultat["x"]["count"]), (144, 1))
        self.assertEqual((self.plan.glidningsresultat["y"]["H_Rd"], self.plan.glidningsresultat["y"]["count"]), (0, 0))
        self.assertEqual(self.plan.glidningsresultat["y"]["status"], "over")
        self.assertIsNone(self.plan.glidningsresultat["y"]["utilization"])
        self.plan.glidning = {"H_y_Ed": 0}
        self.assertEqual(self.plan.glidningsresultat["y"]["utilization"], 0)
        self.plan.uppdatera(insulated, indata={"isolering": False})
        self.assertEqual(self.plan.glidningsresultat["x"]["status"], "incomplete")
        self.plan.uppdatera(insulated, indata={"glid_x": False, "glid_y": False})
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 144)
        copied = self.plan.kopiera(wall, .5, .6)
        self.assertEqual(self.plan._tag(copied)["values"]["glid_L"], 3)

    def test_wall_length_and_local_one_metre_toggle_do_not_change_global_resistance(self):
        wall = self.add(L_vagg=.6, L_vagg_minst_1=False, glid_L=2.5,
                        V_Ed_EQU=200, glid_mu=.6)
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 300)
        for local in ({"L_vagg": .4}, {"L_vagg": 5}, {"L_vagg_minst_1": True},
                      {"l_override": True, "l": 3}, {"L_vagg": None}):
            self.plan.uppdatera(wall, indata=local)
            self.assertEqual(self.plan.taggar[0]["sliding"]["x"], 300)
            self.assertEqual(self.plan.glidningsresultat["y"]["H_Rd"], 300)
        self.plan.uppdatera(wall, indata={"glid_L": 4})
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 480)

    def test_wall_length_cannot_replace_missing_footing_length_in_any_line_model(self):
        ident = self.add(L_vagg=5)
        for model in (1, 0):
            for length in (None, 0, -1):
                self.plan.uppdatera(ident, indata={"lang": model, "lasttyp": 1, "glid_L": length})
                self.assertEqual(self.plan.taggar[0]["sliding"]["status"], "incomplete")
                self.assertIsNone(self.plan.glidningsresultat["x"]["H_Rd"])
        self.plan.uppdatera(ident, indata={"glid_L": 3})
        self.assertEqual(self.plan.taggar[0]["sliding"]["x"], 144)

    def test_missing_invalid_inputs_never_produce_a_pass_or_partial_total(self):
        self.add()
        bad = self.add(glid_y=False)
        for field, value in (("V_Ed_EQU", None), ("V_Ed_EQU", -1), ("glid_mu", None),
                             ("glid_mu", -1), ("glid_L", 0), ("glid_L", None)):
            self.plan.uppdatera(bad, indata={"V_Ed_EQU": 120, "glid_mu": .4, "glid_L": 3, field: value})
            r = self.plan.glidningsresultat
            self.assertEqual(r["x"]["status"], "incomplete")
            self.assertIsNone(r["x"]["H_Rd"])
            self.assertEqual(r["y"]["H_Rd"], 144)
        self.plan.uppdatera(bad, indata={"V_Ed_EQU": 1e308, "glid_mu": 10, "glid_L": 3})
        json.dumps(self.plan.state, allow_nan=False)
        self.assertEqual(self.plan.glidningsresultat["x"]["status"], "incomplete")

    def test_gliding_edits_do_not_invalidate_ground_result_and_negative_demand_uses_magnitude(self):
        ident = self.add()
        self.plan.berakna(ident)
        before = copy.deepcopy(self.plan.resultat)
        self.plan.uppdatera(ident, indata={"glid_mu": .5})
        self.assertEqual(self.plan._tag(ident)["status"], "calculated")
        self.assertEqual(self.plan.resultat, before)
        self.plan.glidning = {"H_x_Ed": -180}
        self.assertEqual(self.plan.glidningsresultat["x"]["utilization"], 1)
        self.plan.glidning = {"enabled": False}
        self.assertEqual(self.plan.glidningsresultat["x"]["status"], "off")
        self.plan.glidning = {"enabled": True, "check_y": False}
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Ed"], -180)
        self.assertEqual(self.plan.glidningsresultat["y"]["status"], "off")

    def test_settings_and_positions_save_restore_and_invalid_import_is_atomic(self):
        self.add()
        positions = {"1": {"symbol": {"x": .7, "y": .4, "size": 235}, "legend": {"x": .15, "y": .2, "size": 615}}}
        self.plan.glidning = {"placements": positions}
        path = self.plan.spara(self.folder / "saved.json")
        self.image.unlink()
        restored = Grundplan.oppna(path)
        self.addCleanup(restored.close)
        self.assertEqual(restored.glidning, self.plan.glidning)
        self.assertEqual(restored.glidningsresultat, self.plan.glidningsresultat)
        before = restored._document()
        for invalid in ({"enabled": 1}, {"H_x_Ed": float("nan")},
                        {"placements": {"2": positions["1"]}},
                        {"placements": {"1": {"symbol": {"x": .5, "y": .5, "size": 1}}}}):
            data = {**before, "sliding": {**before["sliding"], **invalid}}
            with self.assertRaises(ValueError):
                restored._load_document(json.dumps(data).encode())
            self.assertEqual(restored._document(), before)
        with patch.object(restored, "send") as send:
            restored._on_message(None, {"action": "sliding_placement", "page": 1, "kind": "legend",
                                       "position": {"x": .4, "y": .7}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
        self.assertEqual(restored.glidning["placements"]["1"]["legend"]["y"], .7)

    def test_old_legend_positions_keep_default_size_and_invalid_sizes_are_atomic(self):
        self.plan.glidning = {"placements": {"1": {"legend": {"x": .2, "y": .3}}}}
        self.assertEqual(self.plan.glidning["placements"]["1"]["legend"]["size"], 410)
        before = self.plan._document()
        for size in (204, 1231, None, True, float("nan"), float("inf")):
            with self.subTest(size=size), self.assertRaises(ValueError):
                self.plan.glidning = {"placements": {"1": {"legend": {"x": .2, "y": .3, "size": size}}}}
            self.assertEqual(self.plan._document(), before)
        for size in (205, 1230):
            self.plan.glidning = {"placements": {"1": {"legend": {"x": .2, "y": .3, "size": size}}}}
            self.assertEqual(self.plan.glidning["placements"]["1"]["legend"]["size"], size)

    def test_version_three_projects_keep_ground_results_and_start_with_sliding_off(self):
        ident = self.add()
        self.plan.berakna(ident)
        old = self.plan._document()
        old["version"] = 3
        old.pop("sliding")
        for tag in old["tags"]:
            for name in ("glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L"):
                tag["values"].pop(name)
        self.plan._load_document(json.dumps(old).encode())
        self.assertFalse(self.plan.glidning["enabled"])
        self.assertFalse(self.plan.taggar[0]["values"]["glid_x"])
        self.assertEqual(self.plan.taggar[0]["status"], "calculated")


if __name__ == "__main__":
    unittest.main()
