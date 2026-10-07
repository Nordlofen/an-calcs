"""Finite line supports and footing geometry must never share a load factor."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


def loads(length=.6, brott=200, bruk=100, equ=150):
    return json.dumps({"schemaVersion": 1, "distribution": "uniform", "supports": [{
        "supportId": "VS1", "type": "line", "length": {"value": length, "unit": "m"},
        "results": [{"category": phase, "V": value, "unit": "kN/m"}
                    for phase, value in (("Brott", brott), ("Bruk", bruk), ("EQU", equ))]}]}).encode()


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestWallLoads(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        image = self.folder / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(image)
        self.plan = Grundplan(image)
        self.addCleanup(self.plan.close)

    def imported(self):
        self.plan._start_load_import(loads(), "loads.json")
        return self.plan.placera_lasteffekt(.2, .3)

    def test_short_support_import_keeps_line_loads_and_converts_actual_total(self):
        ident = self.imported()
        v = self.plan._tag(ident)["values"]
        self.assertEqual((v["L_vagg"], v["glid_L"], v["l"]), (.6, .6, 1))
        self.assertEqual((v["F_vy"], v["F_vy_bruk"], v["V_Ed_EQU"]), (200, 100, 150))
        self.plan.uppdatera(ident, indata={"b": 1, "t": .4, "glid_x": True, "glid_mu": .4})
        r = self.plan._tag(ident)["summary"]
        self.assertAlmostEqual(r["last"], 120 + 1.5 * 25 * 1 * .4)
        self.assertEqual(r["lastenhet"], "kN")
        self.assertAlmostEqual(r["utnyttjandegrad"], r["last"] / r["barformaga"])
        self.assertAlmostEqual(self.plan.taggar[0]["sliding"]["x"], 150 * .6 * .4)

    def test_geometry_self_weight_moments_and_both_insulation_phases_use_same_total(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"b": 1, "t": .4, "l": 2.4, "isolering": True,
            "f_d_brott": 200, "f_d_bruk": 100, "M_insp_b": 10, "M_insp_l": -5,
            "M_insp_b_bruk": -8, "M_insp_l_bruk": 4, "F_hb": 30, "F_hl": -20})
        r = self.plan._tag(ident)["summary"]
        for phase, normal, mx, my in (("brott", 120 + 1.5 * 24, 6, -3), ("bruk", 60 + 24, -4.8, 2.4)):
            a = r["effective_area"][phase]
            self.assertAlmostEqual(a["V"], normal)
            self.assertAlmostEqual(a["Mx"], mx)
            self.assertAlmostEqual(a["My"], my)
            self.assertAlmostEqual(a["ex_moment"], my / normal)
            self.assertAlmostEqual(a["ey_moment"], mx / normal)
            self.assertAlmostEqual(r["isolering"]["isolering_N_" + phase], normal)
            self.assertAlmostEqual(r["isolering"]["isolering_q_Ed_" + phase], normal / a["area"])
        self.assertAlmostEqual(r["last"], 156)
        self.assertAlmostEqual(r["barformaga"], r["q_bd"] * 1 * 2.4)
        self.assertEqual(r["load_conversion"]["bruk"], 60)

    def test_footing_length_is_independent_of_bearing_and_equ_support_length(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"glid_x": True, "glid_mu": .4})
        before = copy.deepcopy(self.plan.resultat), self.plan.taggar[0]["sliding"]
        self.plan.uppdatera(ident, indata={"glid_L": 3})
        self.assertEqual((self.plan.resultat, self.plan.taggar[0]["sliding"]), before)
        self.plan.uppdatera(ident, indata={"L_vagg": .4})
        self.assertEqual(self.plan._tag(ident)["values"]["glid_L"], 3)
        self.assertAlmostEqual(self.plan.taggar[0]["sliding"]["x"], 24)
        self.assertEqual(self.plan._tag(ident)["summary"]["load_conversion"]["brott"], 80)

    def test_equal_support_and_reference_lengths_keep_uniform_per_metre_utilization(self):
        legacy = self.plan.lagg_till(.2, .3, indata={"b": 1, "t": .4, "F_vy": 200, "l": 5})
        explicit = self.plan.kopiera(legacy, .5, .6, indata={"L_vagg": 5})
        old, new = (self.plan._tag(ident)["summary"] for ident in (legacy, explicit))
        self.assertEqual(new["utnyttjandegrad"], old["utnyttjandegrad"])
        self.assertAlmostEqual(new["last"], (200 + 15) * 5)
        self.assertAlmostEqual(new["barformaga"], old["barformaga"] * 5)

    def test_exports_keep_all_lengths_total_actions_and_support_based_resistance(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"glid_L": 3, "glid_x": True, "glid_mu": .4})
        self.plan.glidning = {"enabled": True}
        html = self.plan.exportera_html(self.folder / "result.html").read_text()
        snapshot = json.loads(html.split('<script id="grundplan-data" type="application/json">')[1].split('</script>')[0])
        tag = snapshot["state"]["tags"][0]
        self.assertEqual((tag["values"]["L_vagg"], tag["values"]["glid_L"], tag["values"]["l"]), (.6, 3, 1))
        self.assertEqual(tag["summary"]["load_conversion"]["brott"], 120)
        self.assertAlmostEqual(tag["sliding"]["x"], 36)
        from pypdf import PdfReader
        pdf = self.plan.exportera_pdf(self.folder / "result.pdf")
        text = PdfReader(pdf).pages[0].extract_text()
        self.assertIn("vägg", text)
        self.assertIn("su", text)
        self.assertIn("36 kN", text)

    def test_import_updates_unedited_seed_but_preserves_manual_length_after_reload_and_copy(self):
        ident = self.imported()
        self.plan._start_load_import(loads(.8), "updated.json")
        self.assertEqual(self.plan._tag(ident)["values"]["glid_L"], .8)
        self.plan.uppdatera(ident, indata={"glid_L": 3})
        path = self.plan.spara(self.folder / "saved.json")
        restored = Grundplan.oppna(path)
        self.addCleanup(restored.close)
        copied = restored.kopiera(ident, .5, .6, littera="VS2")
        self.assertEqual(restored._tag(copied)["imported_length"], .8)
        restored._start_load_import(loads(.4), "updated.json")
        self.assertEqual(restored._tag(ident)["values"]["glid_L"], 3)
        self.assertEqual(restored._tag(ident)["values"]["L_vagg"], .4)
        self.assertEqual(restored._tag(copied)["values"]["L_vagg"], .8)
        restored._start_load_import(loads(.4), "identical.json")
        self.assertEqual(restored._tag(ident)["values"]["glid_L"], 3)

    def test_copied_unedited_import_seed_still_follows_its_own_import(self):
        source = self.imported()
        copied = self.plan.kopiera(source, .5, .6, littera="VS2")
        data = json.loads(loads(.9)); data["supports"][0]["supportId"] = "VS2"
        self.plan._start_load_import(json.dumps(data).encode(), "copy.json")
        self.assertEqual(self.plan._tag(copied)["values"]["glid_L"], .9)
        self.assertEqual(self.plan._tag(source)["values"]["glid_L"], .6)

    def test_old_project_keeps_previous_results_until_actual_support_is_imported(self):
        ident = self.plan.lagg_till(.2, .3, littera="VS1", indata={
            "F_vy": 200, "V_Ed_EQU": 150, "glid_x": True, "glid_mu": .4, "glid_L": 3})
        before = self.plan.resultat, self.plan.taggar[0]["sliding"]
        document = self.plan._document(); document["version"] = 9
        document["tags"][0]["values"].pop("L_vagg")
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual((self.plan.resultat, self.plan.taggar[0]["sliding"]), before)
        self.assertIsNone(self.plan._tag(ident)["values"]["L_vagg"])
        self.plan._start_load_import(loads(), "restore-length.json")
        self.assertEqual(self.plan._tag(ident)["values"]["glid_L"], 3)
        self.assertEqual(self.plan._tag(ident)["values"]["L_vagg"], .6)

    def test_h_only_uses_support_length_with_no_bearing_geometry_or_footing_length(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"endast_h_stabilitet": True, "glid_x": True,
            "glid_mu": .4, "glid_L": None, "b": None, "l": None, "t": None})
        self.assertTrue(self.plan._tag(ident)["summary"]["endast_h_stabilitet"])
        self.assertAlmostEqual(self.plan.taggar[0]["sliding"]["x"], 36)

    def test_invalid_length_never_retains_previous_bearing_or_sliding_pass(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"glid_x": True, "glid_mu": .4})
        for length in (0, -1):
            self.plan.uppdatera(ident, indata={"L_vagg": length})
            tag = self.plan.taggar[0]
            self.assertEqual(tag["status"], "error")
            self.assertIsNone(tag["summary"])
            self.assertEqual(tag["sliding"]["status"], "incomplete")
            self.assertIsNone(tag["sliding"]["x"])
        self.plan.uppdatera(ident, indata={"L_vagg": .6})
        self.assertEqual(self.plan.taggar[0]["status"], "calculated")

    def test_support_length_edits_in_bulk_and_pads_remain_unaffected(self):
        first = self.imported()
        second = self.plan.kopiera(first, .5, .6)
        self.plan.uppdatera_flera([first, second], indata={"L_vagg": .4})
        for tag in self.plan.taggar:
            self.assertEqual(tag["summary"]["load_conversion"]["brott"], 80)
        pad = self.plan.lagg_till(.7, .7, typ="pelarsula", indata={"V_Ed_EQU": 150, "glid_x": True, "glid_mu": .4})
        before = self.plan._tag(pad)["summary"]
        self.plan.uppdatera(pad, indata={"L_vagg": .2})
        self.assertEqual(self.plan._tag(pad)["summary"], before)
        self.assertAlmostEqual(self.plan.taggar[-1]["sliding"]["x"], 60)
        with self.assertRaisesRegex(ValueError, "endast väggsulor"):
            self.plan.uppdatera_flera([pad], indata={"L_vagg": .5})
