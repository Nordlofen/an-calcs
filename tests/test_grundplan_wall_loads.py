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

    def test_pad_model_line_actions_match_independent_total_actions_for_short_and_long_walls(self):
        for length in (.6, 1, 2.4):
            with self.subTest(length=length):
                actions = {"F_vy": 200, "F_vy_bruk": 100, "F_hb": 5, "F_hl": -3,
                           "M_insp_b": 10, "M_insp_l": -5, "M_insp_b_bruk": 4, "M_insp_l_bruk": -2}
                geometry = {"b": 1.2, "l": 1.3, "t": .4, "isolering": True,
                            "f_d_brott": 200, "f_d_bruk": 100}
                line = self.plan.lagg_till(.2, .3, typ="pelarsula", indata={
                    **geometry, **actions, "lasttyp": 1, "L_vagg": length})
                point = self.plan.lagg_till(.5, .6, typ="pelarsula", indata={
                    **geometry, **{name: value * length for name, value in actions.items()}})
                a, b = (self.plan._tag(ident)["summary"] for ident in (line, point))
                for name in ("last", "barformaga", "utnyttjandegrad", "effective_area", "isolering", "kontroller"):
                    self.assertEqual(a[name], b[name], name)
                self.assertEqual(a["load_conversion"]["brott"], 200 * length)
                self.assertEqual(a["load_conversion"]["bruk"], 100 * length)
                self.assertFalse(a["load_conversion"]["at_least_one"])
                self.assertAlmostEqual(a["last"], 200 * length + 1.5 * 25 * 1.2 * 1.3 * .4)
                self.assertEqual(self.plan._tag(line)["values"]["F_vy"], 200)

    def test_imported_wall_keeps_line_basis_during_model_changes_and_updates(self):
        self.plan._start_load_import(loads(2.4), "loads.json")
        ident = self.plan.placera_lasteffekt(.2, .3)
        self.plan.uppdatera(ident, indata={"lang": 0, "b": 1.2, "l": 1.3, "glid_x": True, "glid_mu": .4})
        tag = self.plan.taggar[0]
        self.assertEqual(tag["values"]["lasttyp"], 1)
        self.assertEqual(tag["load_resultants"], {"brott": 480, "bruk": 240})
        self.assertEqual(tag["sliding"]["x"], 150 * 2.4 * .4)
        self.plan._start_load_import(loads(3, brott=220, bruk=110, equ=160), "new.json")
        tag = self.plan.taggar[0]
        self.assertEqual((tag["values"]["lang"], tag["values"]["lasttyp"], tag["values"]["l"]), (0, 1, 1.3))
        self.assertEqual(tag["load_resultants"], {"brott": 660, "bruk": 330})
        self.assertEqual(tag["sliding"]["x"], 160 * 3 * .4)
        self.plan.uppdatera(ident, indata={"lang": 1})
        self.assertEqual(self.plan.taggar[0]["load_resultants"], {"brott": 220, "bruk": 110})
        self.plan.uppdatera(ident, indata={"lang": 0})
        self.assertEqual(self.plan.taggar[0]["load_resultants"], {"brott": 660, "bruk": 330})
        self.assertEqual(self.plan.taggar[0]["values"]["F_vy"], 220)

    def test_line_pad_length_is_required_and_footing_dimensions_never_replace_it(self):
        ident = self.plan.lagg_till(.2, .3, typ="pelarsula", indata={"lasttyp": 1,
            "F_vy": 200, "F_vy_bruk": 100, "V_Ed_EQU": 150, "glid_x": True, "glid_mu": .4, "glid_L": 8})
        for length in (None, 0, -1):
            self.plan.uppdatera(ident, indata={"L_vagg": length})
            tag = self.plan.taggar[0]
            self.assertEqual(tag["status"], "error")
            self.assertEqual(tag["load_resultants"], {"brott": None, "bruk": None})
            self.assertEqual(tag["sliding"]["status"], "incomplete")
        self.plan.uppdatera(ident, indata={"L_vagg": 5})
        before = self.plan.taggar[0]["load_resultants"], self.plan.taggar[0]["sliding"]
        self.plan.uppdatera(ident, indata={"b": 2, "l": 3, "glid_L": 10})
        self.assertEqual((self.plan.taggar[0]["load_resultants"], self.plan.taggar[0]["sliding"]), before)
        self.plan.uppdatera(ident, indata={"lasttyp": 0})
        self.assertEqual(self.plan.taggar[0]["load_resultants"], {"brott": 200, "bruk": 100})
        self.assertEqual(self.plan.taggar[0]["sliding"]["x"], 60)

    def test_resultants_are_independent_of_other_errors_but_never_reuse_invalid_or_missing_loads(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"b": None})
        self.assertEqual(self.plan.taggar[0]["load_resultants"], {"brott": 120, "bruk": 60})
        self.plan.uppdatera(ident, indata={"F_vy": None, "F_vy_bruk": 0})
        self.assertEqual(self.plan.taggar[0]["load_resultants"], {"brott": None, "bruk": 0})
        self.plan.uppdatera(ident, indata={"F_vy": -10})
        self.assertEqual(self.plan.taggar[0]["load_resultants"]["brott"], -6)
        self.plan.uppdatera(ident, indata={"endast_h_stabilitet": True})
        self.assertEqual(self.plan.taggar[0]["load_resultants"], {"brott": None, "bruk": None})

    def test_pad_line_basis_survives_copy_save_old_imported_project_and_exports(self):
        ident = self.imported()
        self.plan.uppdatera(ident, indata={"lang": 0, "b": 1.2, "l": 1.3, "isolering": True})
        copied = self.plan.kopiera(ident, .5, .6)
        restored = Grundplan.oppna(self.plan.spara(self.folder / "line-pad.json"))
        self.addCleanup(restored.close)
        self.assertEqual(restored.taggar, self.plan.taggar)
        self.assertEqual(restored._tag(copied)["values"]["lasttyp"], 1)
        document = restored._document(); document["version"] = 11
        for tag in document["tags"]:
            del tag["values"]["lasttyp"]
        restored._load_document(json.dumps(document).encode())
        self.assertEqual(restored.taggar, self.plan.taggar)
        snapshot = json.loads(restored._html_bytes().decode().split('<script id="grundplan-data" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(snapshot["state"]["tags"][0]["load_resultants"], {"brott": 120, "bruk": 60})
        from pypdf import PdfReader
        import io
        pdf_text = PdfReader(io.BytesIO(restored._pdf_bytes())).pages[0].extract_text()
        self.assertIn("V 200 kN/m → 120 kN", pdf_text)
        restored.tabellvy = {"sort": {"key": "V_res_bruk", "direction": "descending"}}
        self.assertEqual(restored._document()["table_view"]["sort"]["key"], "V_res_bruk")

    def test_bulk_line_pads_edit_length_and_loads_but_mixed_units_are_rejected(self):
        first = self.imported()
        self.plan.uppdatera(first, indata={"lang": 0})
        second = self.plan.kopiera(first, .5, .6)
        self.plan.uppdatera_flera([first, second], indata={"L_vagg": 2.4, "F_vy": 220})
        for tag in self.plan.taggar:
            self.assertEqual(tag["load_resultants"]["brott"], 528)
        point = self.plan.lagg_till(.7, .7, typ="pelarsula")
        before = self.plan.taggar
        with self.assertRaisesRegex(ValueError, "samma lasttyp"):
            self.plan.uppdatera_flera([first, point], indata={"F_vy": 100})
        self.assertEqual(self.plan.taggar, before)
        self.plan.uppdatera_flera([first, point], indata={"lasttyp": 1, "L_vagg": .8, "F_vy": 100})
        self.assertEqual(self.plan.taggar[0]["load_resultants"]["brott"], 80)
        self.assertEqual(self.plan.taggar[-1]["load_resultants"]["brott"], 80)
        for bad in (None, True, "line", 2):
            with self.assertRaises(ValueError):
                self.plan.uppdatera(first, indata={"lasttyp": bad})

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

    def test_unknown_and_long_supports_use_one_metre_resultant_independent_of_by(self):
        legacy = self.plan.lagg_till(.2, .3, indata={"b": 1, "t": .4, "F_vy": 200, "l": 5})
        explicit = self.plan.kopiera(legacy, .5, .6, indata={"L_vagg": 5})
        old, new = (self.plan._tag(ident)["summary"] for ident in (legacy, explicit))
        self.assertEqual(new["utnyttjandegrad"], old["utnyttjandegrad"])
        self.assertAlmostEqual(new["last"], 200 + 15 * 5)
        self.assertEqual(new["barformaga"], old["barformaga"])
        self.assertEqual(new["load_conversion"]["brott"], 200)

    def test_one_and_five_metre_imports_have_same_local_check_but_different_global_equ(self):
        self.plan._start_load_import(loads(1), "one.json")
        one = self.plan.placera_lasteffekt(.2, .3)
        self.plan.uppdatera(one, indata={"b": 1, "t": .4, "glid_x": True, "glid_mu": .4,
            "M_insp_b": 10, "M_insp_l": -5, "F_hb": 30, "F_hl": -20})
        before = copy.deepcopy(self.plan._tag(one)["summary"])
        self.plan._start_load_import(loads(5), "five.json")
        v, r = (self.plan._tag(one)[key] for key in ("values", "summary"))
        self.assertIs(v["L_vagg_minst_1"], True)
        self.assertEqual((v["L_vagg"], v["glid_L"]), (5, 5))
        for name in ("last", "barformaga", "utnyttjandegrad", "effective_area"):
            self.assertEqual(r[name], before[name])
        self.assertEqual(r["load_conversion"]["brott"], 200)
        self.assertAlmostEqual(r["last"], 215)
        self.assertAlmostEqual(self.plan.taggar[0]["sliding"]["x"], 150 * 5 * .4)

    def test_by_spreads_same_local_resultant_for_short_and_long_supports_in_both_phases(self):
        ident = self.imported()
        for length, external in ((.6, 120), (5, 200)):
            self.plan.uppdatera(ident, indata={"L_vagg": length, "b": 1, "t": .4,
                "isolering": True, "f_d_brott": 200, "f_d_bruk": 100,
                "glid_x": True, "glid_mu": .4})
            for by in (1, 2):
                self.plan.uppdatera(ident, indata={"l": by})
                r = self.plan._tag(ident)["summary"]
                self.assertEqual(r["load_conversion"]["brott"], external)
                self.assertEqual(r["load_conversion"]["bruk"], external / 2)
                self.assertAlmostEqual(r["last"], external + 15 * by)
                self.assertAlmostEqual(r["isolering"]["isolering_q_Ed_brott"], external / by + 15)
                self.assertAlmostEqual(r["isolering"]["isolering_q_Ed_bruk"], external / 2 / by + 10)
                self.assertEqual(r["effective_area"]["brott"]["area"], by)
            self.plan.uppdatera(ident, indata={"isolering": False})
            self.assertAlmostEqual(self.plan.taggar[0]["sliding"]["x"], 150 * length * .4)

    def test_import_threshold_and_checkbox_survive_bulk_copy_and_saved_projects(self):
        ident = self.imported()
        self.assertIs(self.plan._tag(ident)["values"]["L_vagg_minst_1"], False)
        other = self.plan.kopiera(ident, .5, .6, indata={"L_vagg": 5})
        self.assertIs(self.plan._tag(other)["values"]["L_vagg_minst_1"], True)
        self.plan.uppdatera_flera([ident, other], indata={"L_vagg_minst_1": True})
        restored = Grundplan.oppna(self.plan.spara(self.folder / "minimum.json"))
        self.addCleanup(restored.close)
        for tag in restored.taggar:
            self.assertIs(tag["values"]["L_vagg_minst_1"], True)
            self.assertEqual(tag["summary"]["load_conversion"]["brott"], 200)
        self.assertEqual(restored._tag(other)["values"]["L_vagg"], 5)
        restored._start_load_import(loads(.4), "short.json")
        self.assertIs(restored._tag(ident)["values"]["L_vagg_minst_1"], False)
        self.assertEqual(restored._tag(ident)["summary"]["load_conversion"]["brott"], 80)

    def test_old_version_ten_projects_infer_local_checkbox_and_recalculate_long_walls(self):
        for length in (.6, 1, 5):
            self.plan._start_load_import(loads(length), "loads.json")
            if not self.plan.taggar:
                ident = self.plan.placera_lasteffekt(.2, .3)
            document = self.plan._document()
            document["version"] = 10
            del document["tags"][0]["values"]["L_vagg_minst_1"]
            self.plan._load_document(json.dumps(document).encode())
            tag = self.plan._tag(ident)
            self.assertEqual(tag["values"]["L_vagg_minst_1"], length >= 1)
            self.assertEqual(tag["summary"]["load_conversion"]["brott"], 200 * min(length, 1))
            self.assertEqual(tag["values"]["L_vagg"], length)

    def test_unchecked_missing_or_long_length_cannot_show_valid_local_result(self):
        ident = self.imported()
        for length in (None, 0, -1, 5):
            self.plan.uppdatera(ident, indata={"L_vagg": length, "L_vagg_minst_1": False})
            self.assertEqual(self.plan._tag(ident)["status"], "error")
            self.assertIsNone(self.plan._tag(ident)["summary"])
        self.plan.uppdatera(ident, indata={"L_vagg_minst_1": True})
        self.assertEqual(self.plan._tag(ident)["summary"]["load_conversion"]["brott"], 200)
        for invalid in (1, None, "true"):
            with self.assertRaises(ValueError):
                self.plan.uppdatera(ident, indata={"L_vagg_minst_1": invalid})

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
        with self.assertRaisesRegex(ValueError, "endast linjelaster"):
            self.plan.uppdatera_flera([pad], indata={"L_vagg": .5})
