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

    def test_short_and_long_imports_use_actual_source_length_without_floor(self):
        for length in (.5, 1, 5):
            with self.subTest(length=length):
                self.plan._start_load_import(loads(length), "loads.json")
                ident = self.plan.placera_lasteffekt(.2,.3)
                tag = self.plan.taggar[-1]
                self.assertEqual(tag["values"]["l"], length)
                self.assertFalse(tag["values"]["l_override"])
                self.assertEqual(tag["load_resultants"], {"brott": 200*length, "bruk": 100*length})
                self.assertEqual(tag["load_intensity"]["current"]["F_vy"],200)
                self.plan.ta_bort(ident)

    def test_repeated_length_edits_conserve_loads_and_equ_including_existing_selfweight(self):
        self.plan._start_load_import(loads(2.6), "loads.json")
        ident = self.plan.placera_lasteffekt(.2,.3)
        self.plan.uppdatera(ident, indata={"glid_x":True,"glid_mu":.4})
        for by in (2, 1.5, 3.5, 2):
            with self.subTest(by=by):
                self.plan.uppdatera(ident,indata={"l":by,"l_override":True})
                tag = self.plan.taggar[0]
                self.assertEqual(tag["values"]["F_vy"],200)
                self.assertEqual(tag["values"]["F_vy_bruk"],100)
                self.assertEqual(tag["load_resultants"],{"brott":520,"bruk":260})
                self.assertAlmostEqual(tag["load_intensity"]["current"]["F_vy"],520/by)
                self.assertAlmostEqual(tag["sliding"]["x"],150*2.6*.4)
                self.assertEqual(tag["summary"]["load_conversion"]["brott"],520)
        self.plan.uppdatera(ident,indata={"l_override":False})
        self.assertEqual(self.plan.taggar[0]["values"]["l"],2.6)
        self.assertFalse(self.plan.taggar[0]["load_intensity"]["adjusted"])

    def test_all_line_actions_use_source_to_physical_length_conversion(self):
        ident=self.imported()
        actions={"F_hb":4,"F_hl":3,"M_insp_l":2,"M_insp_b":1,
                 "M_insp_l_bruk":.3,"M_insp_b_bruk":.2}
        self.plan.uppdatera(ident,indata={**actions,"b":1.2,"l":.8,"isolering":True,"f_d_brott":300,"f_d_bruk":200})
        tag=self.plan.taggar[0]
        for key,value in actions.items():
            self.assertAlmostEqual(tag["load_intensity"]["current"][key],value*.6/.8)
        for phase,suffix in (("brott",""),("bruk","_bruk")):
            area=tag["summary"]["effective_area"][phase]
            self.assertAlmostEqual(area["Mx"],actions["M_insp_b"+suffix]*.6)
            self.assertAlmostEqual(area["My"],actions["M_insp_l"+suffix]*.6)

    def test_model_changes_preserve_source_resultant(self):
        ident=self.imported()
        for model in (0,1,0):
            self.plan.uppdatera(ident,indata={"lang":model,"b":1.2,"l":1.3})
            self.assertEqual(self.plan.taggar[0]["load_resultants"],{"brott":120,"bruk":60})

    def test_imported_support_length_is_locked_in_api_bulk_copy_and_common_foundation(self):
        ident=self.imported()
        before=copy.deepcopy(self.plan._document())
        operations=[lambda:self.plan.uppdatera(ident,indata={"L_vagg":1}),
            lambda:self.plan.uppdatera_flera([ident],indata={"L_vagg":1}),
            lambda:self.plan.kopiera(ident,.4,.4,indata={"L_vagg":1}),
            lambda:self.plan.satt_gemensamt_fundament([ident],namn="G1",bx=2,by=2,t=.3,stodindata={ident:{"L_vagg":1}})]
        for operation in operations:
            with self.assertRaisesRegex(ValueError,"L_stöd"):
                operation()
            self.assertEqual(self.plan._document(),before)
        self.plan.uppdatera(ident,indata={"L_vagg_minst_1":True})
        self.assertEqual(self.plan.taggar[0]["load_resultants"]["brott"],120)

    def test_reimport_follows_source_unless_length_is_adjusted_and_is_idempotent(self):
        ident=self.imported()
        self.plan._start_load_import(loads(3),"new.json")
        self.assertEqual(self.plan.taggar[0]["values"]["l"],3)
        self.plan.uppdatera(ident,indata={"l":2})
        self.plan._start_load_import(loads(4,brott=220),"new.json")
        tag=self.plan.taggar[0]
        self.assertEqual(tag["values"]["l"],2)
        self.assertEqual(tag["load_resultants"]["brott"],880)
        self.assertEqual(tag["load_intensity"]["current"]["F_vy"],440)
        before=copy.deepcopy(self.plan.taggar)
        self.plan._start_load_import(loads(4,brott=220),"new.json")
        self.assertEqual(self.plan.taggar,before)

    def test_contour_length_moves_selected_end_and_retains_the_opposite_end(self):
        from an_calcs.notebook.grundplan_lengths import wall_axes,metres_per_pixel
        ident=self.imported()
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        original={"kind":"wall","start":{"x":.5,"y":.7},"angle_deg":0}
        self.plan.placera_sulkontur(ident,original)
        self.plan.uppdatera(ident,indata={"l":.4,"length_end":0})
        self.assertEqual(self.plan.sulkonturer["placements"][ident],{**original,"reference_start":original["start"]})
        self.plan.uppdatera(ident,indata={"l":.2,"length_end":1})
        p=self.plan.sulkonturer["placements"][ident]
        self.assertAlmostEqual(p["start"]["y"],.7-.4*80/600)
        end=p["start"]["y"]-.2*80/600
        self.assertAlmostEqual(end,.7-.6*80/600)
        self.plan._start_load_import(loads(.8),"new.json")
        self.assertAlmostEqual(self.plan.sulkonturer["placements"][ident]["start"]["y"],p["start"]["y"])

    def test_unadjusted_reimport_moves_start_when_end_is_pinned(self):
        ident=self.imported()
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        self.plan.placera_sulkontur(ident,{"kind":"wall","start":{"x":.5,"y":.7},"angle_deg":0})
        self.plan.uppdatera(ident,indata={"length_end":1})
        self.plan._start_load_import(loads(1),"new.json")
        p=self.plan.sulkonturer["placements"][ident]
        self.assertAlmostEqual(p["start"]["y"],.7+.4*80/600)

    def test_save_copy_and_undo_keep_raw_sources_and_adjusted_length(self):
        ident=self.imported()
        from unittest.mock import patch
        with patch.object(self.plan,"send"):
            self.plan._on_message(self.plan,{"action":"update","id":ident,"values":{"l":.4},"request":1,"view":"test"},[])
        twin=self.plan.kopiera(ident,.5,.5)
        self.assertEqual(self.plan._tag(twin)["imported_length"],.6)
        loaded=Grundplan.oppna(self.plan.spara(self.folder/"saved.json"));self.addCleanup(loaded.close)
        self.assertEqual(loaded.taggar,self.plan.taggar)
        with patch.object(self.plan,"send"):
            self.plan._on_message(self.plan,{"action":"update","id":ident,"values":{"l":.3},"request":2,"view":"test"},[])
        self.plan.angra()
        self.assertEqual(self.plan.taggar[0]["values"]["l"],.4)
        self.plan.gor_om()
        self.assertEqual(self.plan.taggar[0]["values"]["l"],.3)

    def test_legacy_import_migrates_strip_length_and_preserves_equ_total(self):
        ident=self.imported()
        doc=self.plan._document();doc["version"]=30
        tag=doc["tags"][0];tag["values"].update(l=1,l_override=False,L_vagg=7,glid_L=3,glid_x=True,glid_mu=.4)
        for name in ("physical_length","equ_reference_length","length_end"):tag["values"].pop(name,None)
        self.plan._load_document(json.dumps(doc).encode())
        tag=self.plan.taggar[0]
        self.assertEqual(tag["values"]["L_vagg"],.6)
        self.assertEqual(tag["values"]["l"],.6)
        self.assertEqual(tag["sliding"]["x"],150*3*.4)
        self.plan.uppdatera(ident,indata={"l":.4})
        self.assertEqual(self.plan.taggar[0]["sliding"]["x"],150*3*.4)

    def test_legacy_contour_recovers_actual_length_without_moving_its_start(self):
        ident=self.imported()
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        doc=self.plan._document();doc["version"]=30
        doc["tags"][0]["values"].update(l=1,l_override=False)
        doc["contours"]["placements"][ident]={"kind":"wall","start":{"x":.5,"y":.7},"end":{"x":.5,"y":.5}}
        self.plan._load_document(json.dumps(doc).encode())
        self.assertAlmostEqual(self.plan.taggar[0]["values"]["l"],1.5)
        self.assertEqual(self.plan.sulkonturer["placements"][ident],{"kind":"wall","start":{"x":.5,"y":.7},"angle_deg":0,"reference_start":{"x":.5,"y":.7}})

    def test_wall_by_is_excluded_from_reference_geometry(self):
        ident=self.imported();twin=self.plan.kopiera(ident,.5,.5)
        self.plan.uppdatera(twin,indata={"l":.4})
        groups=self.plan.referensgrupper["groups"]
        self.assertEqual(len(groups),1)
        self.assertEqual(set(groups[0]["geometry"]),{"b","t"})

    def test_schema_has_adjusted_length_and_no_minimum_or_independent_sliding_length(self):
        fields={f["name"]:f for f in self.plan.schema["fields"]}
        self.assertNotIn("L_vagg_minst_1",fields)
        self.assertNotIn("glid_L",fields)
        self.assertEqual(fields["L_vagg"]["display_symbol"]["subscript"],"stöd")
        self.assertEqual(fields["l_override"]["label"],"Justerad längd")
        self.assertIn("length_end",fields)

    def test_invalid_contour_length_is_atomic_and_does_not_lose_pinned_end(self):
        ident=self.imported()
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        self.plan.placera_sulkontur(ident,{"kind":"wall","start":{"x":.5,"y":.7},"angle_deg":0})
        before=copy.deepcopy((self.plan.taggar,self.plan.sulkonturer,self.plan.resultat))
        with self.assertRaisesRegex(ValueError,"positivt b_y"):
            self.plan.uppdatera(ident,indata={"l":None,"l_override":True,"length_end":1})
        self.assertEqual((self.plan.taggar,self.plan.sulkonturer,self.plan.resultat),before)
        self.plan.uppdatera(ident,indata={"l":.4,"l_override":True,"length_end":1})
        self.assertAlmostEqual(self.plan.sulkonturer["placements"][ident]["start"]["y"],.7-.2*80/600)

    def test_legacy_unknown_source_model_does_not_change_on_unrelated_popup_edit(self):
        ident=self.plan.lagg_till(.3,.3,indata={"F_vy":200})
        doc=self.plan._document();doc["version"]=30;doc["tags"][0]["values"].update(L_vagg=3,l=1,l_override=False)
        self.plan._load_document(json.dumps(doc).encode())
        values=copy.deepcopy(self.plan._tag(ident)["values"]);values["t"]=.4
        self.plan.uppdatera(ident,indata=values)
        self.assertFalse(self.plan.taggar[0]["values"]["physical_length"])
        self.assertEqual(self.plan.taggar[0]["load_resultants"]["brott"],200)

    def test_adjusted_export_shows_both_values_and_hides_wall_by(self):
        from pypdf import PdfReader
        import io
        ident=self.imported()
        self.plan.uppdatera(ident,indata={"l":.4})
        before=copy.deepcopy(self.plan.taggar)
        text=PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        for expected in ("Omräknad last","V 300 kN/m","V 150 kN/m","urspr. 200","urspr. 100"):
            self.assertIn(expected,text)
        self.assertNotIn("bᵧ",text)
        self.assertEqual(self.plan.taggar,before)

    def test_rotated_start_adjustment_keeps_the_far_end_in_both_axes(self):
        from an_calcs.notebook.grundplan_lengths import wall_axes
        ident=self.imported()
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        for angle in (45,90,210):
            with self.subTest(angle=angle):
                self.plan.uppdatera(ident,indata={"l":.6,"length_end":0})
                self.plan.placera_sulkontur(ident,{"kind":"wall","start":{"x":.5,"y":.5},"angle_deg":angle})
                self.plan.uppdatera(ident,indata={"l":.4,"length_end":1})
                point=self.plan.sulkonturer["placements"][ident]["start"]
                for axis,direction,span in zip(("x","y"),wall_axes(angle),(800,600)):
                    self.assertAlmostEqual(point[axis]+direction*.4*80/span,.5+direction*.6*80/span)

    def test_switching_trimmed_end_and_reset_never_moves_the_full_length_origin(self):
        ident=self.imported()
        self.plan._start_load_import(loads(2.6),"new.json")
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        start={"x":.5,"y":.7}
        self.plan.placera_sulkontur(ident,{"kind":"wall","start":start,"angle_deg":0})
        original=self.plan.sulkonturer["placements"][ident]
        for _ in range(4):
            self.plan.uppdatera(ident,indata={"l":2.05,"l_override":True,"length_end":0})
            self.assertEqual(self.plan.sulkonturer["placements"][ident]["start"],start)
            self.plan.uppdatera(ident,indata={"length_end":1})
            placed=self.plan.sulkonturer["placements"][ident]
            self.assertAlmostEqual(placed["start"]["y"],.7-.55*80/600)
            self.assertAlmostEqual(placed["start"]["y"]-2.05*80/600,.7-2.6*80/600)
            self.plan.uppdatera(ident,indata={"length_end":0})
            self.assertEqual(self.plan.sulkonturer["placements"][ident]["start"],start)
            self.plan.uppdatera(ident,indata={"length_end":1})
            self.plan.uppdatera(ident,indata={"l_override":False})
            self.assertEqual(self.plan.sulkonturer["placements"][ident],original)
            self.assertEqual(self.plan.taggar[0]["values"]["l"],2.6)
            self.assertEqual(self.plan.taggar[0]["load_resultants"]["brott"],520)

    def test_trim_reference_survives_save_undo_and_legacy_migration_without_moving_visible_contour(self):
        from unittest.mock import patch
        ident=self.imported()
        self.plan.kalibrering={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        self.plan.placera_sulkontur(ident,{"kind":"wall","start":{"x":.5,"y":.7},"angle_deg":0})
        self.plan.uppdatera(ident,indata={"l":.4,"length_end":0})
        before=self.plan.sulkonturer
        with patch.object(self.plan,"send"):
            self.plan._on_message(self.plan,{"action":"update","id":ident,"values":{"length_end":1},"view":"test","request":1},[])
        after=self.plan.sulkonturer
        self.assertNotEqual(before,after)
        self.plan.angra();self.assertEqual(self.plan.sulkonturer,before)
        self.plan.gor_om();self.assertEqual(self.plan.sulkonturer,after)
        doc=self.plan._document()
        self.plan._load_document(json.dumps(doc).encode())
        self.assertEqual(self.plan.sulkonturer,after)
        doc["version"]=31
        doc["contours"]["placements"][ident].pop("reference_start")
        self.plan._load_document(json.dumps(doc).encode())
        p=self.plan.sulkonturer["placements"][ident]
        self.assertEqual(p["start"],after["placements"][ident]["start"])
        self.assertAlmostEqual(p["reference_start"]["y"],.7)
        self.plan.uppdatera(ident,indata={"l_override":False})
        self.assertAlmostEqual(self.plan.sulkonturer["placements"][ident]["start"]["y"],.7)

    def test_wall_ignores_longitudinal_placement_eccentricity_but_pad_model_retains_it(self):
        ident=self.imported()
        before=copy.deepcopy(self.plan._tag(ident)["summary"])
        self.plan.uppdatera(ident,indata={"e_l_plac":.1})
        self.assertEqual(self.plan._tag(ident)["summary"],before)
        self.assertEqual(self.plan._tag(ident)["summary"]["effective_area"]["brott"]["ey_placement"],0)
        self.plan.uppdatera(ident,indata={"lang":0,"b":.5,"l":1.3})
        self.assertEqual(self.plan._tag(ident)["summary"]["effective_area"]["brott"]["ey_placement"],.1)

    def test_new_calibration_preserves_full_length_origin_for_a_trimmed_start(self):
        ident=self.imported()
        calibration={"start":{"x":0,"y":0},"end":{"x":.1,"y":0},"length_m":1}
        self.plan.kalibrering=calibration
        self.plan.placera_sulkontur(ident,{"kind":"wall","start":{"x":.5,"y":.7},"angle_deg":0})
        self.plan.uppdatera(ident,indata={"l":.4,"length_end":1})
        self.plan.kalibrering={**calibration,"length_m":2}
        placed=self.plan.sulkonturer["placements"][ident]
        self.assertEqual(placed["reference_start"],{"x":.5,"y":.7})
        self.assertAlmostEqual(placed["start"]["y"],.7-.2*40/600)
        self.plan.uppdatera(ident,indata={"l_override":False})
        self.assertEqual(self.plan.sulkonturer["placements"][ident]["start"],{"x":.5,"y":.7})
