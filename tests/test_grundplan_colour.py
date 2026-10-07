import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2", "reportlab", "pypdf"))
if HAS_NOTEBOOK:
    from PIL import Image
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    from an_calcs.notebook import Grundplan
    from an_calcs.notebook.grundplan_colour import DEFAULT_SETTINGS, validate_settings, group_data, background_color


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook] för färggrupperingstesterna.")
class TestGrundplanColour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.image = self.folder / "ritning.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image)
        self.addCleanup(self.plan.close)

    def add(self, **values):
        return self.plan.lagg_till(.2, .22, indata=values)

    def test_geometry_uses_actual_width_length_and_thickness_and_excludes_h_only(self):
        wall = self.add(b=.6, t=.25)
        pad = self.add(lang=0, b=1.8, l=2.1, t=.3)
        only_h = self.add(endast_h_stabilitet=True, b=1.8)
        missing = self.add(t=None)
        for category, expected in (("t", (.25, .3)), ("b", (.6, 1.8)), ("l", (1., 2.1))):
            settings = validate_settings({"category": category})
            data = group_data(self.plan.taggar, settings)
            self.assertEqual(tuple(data["assignments"][tag]["value"] for tag in (wall, pad)), expected)
            self.assertEqual(data["assignments"][only_h]["label"], "Ej tillämpligt")
        data = group_data(self.plan.taggar, validate_settings({}))
        self.assertEqual(data["assignments"][missing]["label"], "Saknar värde")

    def test_intervals_have_inclusive_lower_and_exclusive_upper_limits_and_separate_units(self):
        settings = validate_settings({"category": "V", "bounds": {"pad": [100, 200, 400], "wall": [10, 20]}})
        ids = [self.add(lang=0, F_vy=value) for value in (-1, 99.9999, 100, 199.9999, 200, 400)]
        wall = self.add(F_vy=20)
        data = group_data(self.plan.taggar, settings)
        groups = [data["assignments"][ident] for ident in ids]
        self.assertEqual([group["low"] for group in groups], [None, None, 100, 100, 200, 400])
        self.assertEqual([group["high"] for group in groups], [100, 100, 200, 200, 400, None])
        self.assertEqual([group["count"] for group in groups], [2, 2, 2, 2, 1, 1])
        self.assertEqual(data["assignments"][wall]["low"], 20)
        self.assertEqual(data["assignments"][wall]["unit"], "kN/m")
        self.assertEqual(groups[0]["unit"], "kN")
        self.assertEqual(len(data["groups"]), 7)

    def test_insulation_groups_both_footing_types_and_h_only_and_survives_export_and_reload(self):
        insulated = self.add(isolering=True, glid_x=True, glid_y=True,
                             F_vy_bruk=80, f_d_brott=400, f_d_bruk=200)
        uninsulated = self.add(lang=0)
        only_h = self.add(endast_h_stabilitet=True, isolering=True, glid_y=True)
        x = self.add(glid_x=True, glid_mu=None)
        y = self.add(lang=0, glid_y=True, V_Ed_EQU=0, glid_mu=.4)
        xy = self.add(glid_x=True, glid_y=True, V_Ed_EQU=120, glid_mu=.4, glid_L=3)
        before = copy.deepcopy((self.plan.taggar, self.plan.resultat))
        colors = {"isolering:1": "#f0d8c8", "isolering:0": "#cce7ff", "isolering:xy": "#d8eedc"}
        self.plan.farggruppering = {"enabled": True, "category": "isolering",
                                  "colors": colors, "legend": {"x": .4, "y": .1, "size": 350}}
        data = group_data(self.plan.taggar, self.plan.farggruppering)
        self.assertEqual([(group["label"], group["count"], group["unit"]) for group in data["groups"]],
                         [("Med isolering · inget bidrag", 1, ""), ("Utan isolering · inget bidrag", 1, ""),
                          ("Utan isolering · bidrag i X_g", 1, ""), ("Utan isolering · bidrag i Y_g", 2, ""),
                          ("Utan isolering · bidrag i X_g och Y_g", 1, "")])
        for ident, suffix in ((insulated, "1"), (uninsulated, "0"), (only_h, "y"), (x, "x"), (y, "y"), (xy, "xy")):
            self.assertEqual(data["assignments"][ident]["key"], "isolering:" + suffix)
        self.assertEqual([group["color"] for group in data["groups"]],
                         ["#f0d8c8", "#cce7ff", "#ffdfba", "#e5d8ff", "#d8eedc"])
        self.assertFalse(self.plan.state["sliding"]["enabled"], "Directions group independently of the global toggle")
        pdf_text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        for label in ("Isolering och glidmotstånd", *(group["label"].replace("_", "") for group in data["groups"])):
            self.assertIn(label, pdf_text.replace("\n", ""))
        self.assertNotIn("Isolering [m]", pdf_text)
        self.assertNotIn("X_g", pdf_text, "Global indices are lowered glyphs in PDF")
        self.assertNotIn("Y_g", pdf_text)
        self.assertIn('"category": "isolering"', self.plan._html_bytes().decode())
        expected = self.plan.farggruppering
        self.plan.farggruppering = {"enabled": False}
        restored = Grundplan.oppna(self.plan.spara(self.folder / "isolering.json"))
        self.addCleanup(restored.close)
        restored.farggruppering = {"enabled": True}
        self.assertEqual(restored.farggruppering, expected)
        self.assertEqual(group_data(restored.taggar, restored.farggruppering), data)
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)

    def test_insulation_keeps_empty_colour_choices_but_exports_only_populated_legend_groups(self):
        for glid_x in (False, True):
            for glid_y in (False, True):
                self.add(isolering=True, glid_x=glid_x, glid_y=glid_y)
        settings = validate_settings({"category": "isolering"})
        data = group_data(self.plan.taggar, settings)
        self.assertEqual([group["count"] for group in data["groups"]], [4, 0, 0, 0, 0])
        self.assertEqual(len({group["color"] for group in data["groups"]}), 5)
        empty = group_data([], settings)
        self.assertEqual([group["count"] for group in empty["groups"]], [0] * 5)
        self.plan.farggruppering = {"enabled": True, "category": "isolering"}
        text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("Med isolering · inget bidrag", text)
        self.assertNotIn("Utan isolering", text, "All four empty groups are omitted")

    def test_load_legend_exports_only_populated_intervals_and_keeps_saved_colours(self):
        ident = self.add(lang=0, F_vy=150)
        self.plan.farggruppering = {"enabled": True, "category": "V"}
        groups = group_data(self.plan.taggar, self.plan.farggruppering)["groups"]
        self.plan.farggruppering = {"colors": {groups[2]["key"]: "#c8e0d8"}}
        text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("100 ≤ V < 200", text)
        for empty in ("V < 100", "200 ≤ V < 400", "V ≥ 400"):
            self.assertNotIn(empty, text)
        self.plan.uppdatera(ident, indata={"F_vy": 250})
        text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        self.assertIn("200 ≤ V < 400", text)
        self.assertNotIn("100 ≤ V < 200", text)
        data = group_data(self.plan.taggar, self.plan.farggruppering)
        self.assertEqual(data["assignments"][ident]["color"], "#c8e0d8")

    def test_load_phase_is_input_action_without_self_weight_and_h_only_uses_equ(self):
        pad = self.add(lang=0, F_vy=150, F_vy_bruk=80, V_Ed_EQU=250)
        only_h = self.add(endast_h_stabilitet=True, V_Ed_EQU=300)
        for phase, low in (("brott", 100), ("bruk", None), ("EQU", 200)):
            settings = validate_settings({"category": "V", "phase": phase})
            data = group_data(self.plan.taggar, settings)
            self.assertEqual(data["assignments"][pad]["low"], low)
            self.assertEqual(data["assignments"][only_h].get("label"), None if phase == "EQU" else "Ej tillämpligt")

    def test_combined_categories_group_only_matching_pairs_and_keep_custom_colours_when_reversed(self):
        first = self.add(t=.3, b=.6)
        same = self.add(t=.3, b=.6)
        wider = self.add(t=.3, b=.8)
        thicker = self.add(t=.4, b=.6)
        settings = validate_settings({"category": "t", "secondary": "b"})
        data = group_data(self.plan.taggar, settings)
        self.assertEqual(len(data["groups"]), 3)
        self.assertEqual(data["assignments"][first], data["assignments"][same])
        self.assertEqual(data["assignments"][first]["count"], 2)
        self.assertEqual(len({data["assignments"][ident]["color"] for ident in (first, wider, thicker)}), 3)
        key = data["assignments"][first]["key"]
        settings["colors"][key] = "#c8e0d8"
        self.assertEqual(group_data(self.plan.taggar, settings),
                         group_data(self.plan.taggar, {**settings, "category": "b", "secondary": "t"}))
        self.plan.farggruppering = {**settings, "enabled": True}
        path = self.plan.spara(self.folder / "combination.json")
        restored = Grundplan.oppna(path)
        self.addCleanup(restored.close)
        self.assertEqual(restored.farggruppering, self.plan.farggruppering)
        text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        for caption in ("Tjocklek t", "Bredd b", "t 0,3 m", "0,6 m", "0,8 m"):
            self.assertIn(caption, text)
        self.assertIn('"secondary": "b"', self.plan._html_bytes().decode())

    def test_toggle_and_save_restore_preserve_settings_without_changing_engineering_results(self):
        self.add(b=.7)
        before = copy.deepcopy((self.plan.taggar, self.plan.resultat))
        self.plan.farggruppering = {"enabled": True, "category": "V", "phase": "EQU", "edit_type": "wall",
                                  "bounds": {"wall": [100, 300, 600]}, "colors": {"na": "#Ab12Cd"},
                                  "legend": {"x": .3, "y": .4, "size": 450}}
        expected = self.plan.farggruppering
        self.plan.farggruppering = {"enabled": False}
        path = self.plan.spara(self.folder / "project.json")
        restored = Grundplan.oppna(path)
        self.addCleanup(restored.close)
        restored.farggruppering = {"enabled": True}
        self.assertEqual(restored.farggruppering, expected)
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)
        copied = restored.farggruppering
        copied["bounds"]["wall"].clear()
        self.assertEqual(restored.farggruppering, expected)

    def test_invalid_settings_and_import_are_atomic_and_old_projects_default_to_off(self):
        document = self.plan._document()
        invalid = [{"enabled": 1}, {"category": "phi"}, {"secondary": "t"}, {"secondary": "bad"}, {"secondary": []}, {"phase": "uls"}, {"edit_type": "all"},
                   {"bounds": {"wall": []}}, {"bounds": {"pad": [200, 100]}},
                   {"bounds": {"pad": [100, 100]}}, {"bounds": {"pad": [float("nan")]}},
                   {"colors": {"t": "red;display:none"}}, {"colors": {"t": "#abcd"}},
                   {"legend": {"size": 0}}, {"legend": {"x": 1.1}}, {"unknown": True}]
        for settings in invalid:
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    self.plan.farggruppering = settings
                self.assertEqual(self.plan._document(), document)
        broken = {**document, "colour_grouping": {"category": "bad"}}
        with self.assertRaises(ValueError):
            self.plan._load_document(json.dumps(broken).encode())
        self.assertEqual(self.plan._document(), document)
        old = {key: value for key, value in document.items() if key != "colour_grouping"}
        old["version"] = 7
        self.plan._load_document(json.dumps(old).encode())
        self.assertEqual(self.plan.farggruppering, DEFAULT_SETTINGS)

    def test_ui_commands_change_only_group_settings_and_position(self):
        self.add(b=.9)
        before = copy.deepcopy(self.plan.taggar)
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "colour_grouping", "settings": {"enabled": True, "category": "b"}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.plan._on_message(None, {"action": "colour_placement", "page": 1,
                                       "position": {"x": .25, "y": .5, "size": 420}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.plan._on_message(None, {"action": "colour_placement", "page": 2,
                                       "position": {"x": .3, "y": .5, "size": 420}}, [])
            self.assertFalse(send.call_args.args[0]["ok"])
        self.assertEqual(self.plan.taggar, before)
        self.assertEqual(self.plan.farggruppering["legend"], {"x": .25, "y": .5, "size": 420})

    def test_pdf_and_html_keep_group_background_status_and_hidden_legend_independently(self):
        ident = self.add(b=1.8, lang=0, l=1.8, F_vy=150)
        self.plan.farggruppering = {"enabled": True, "category": "V", "legend": {"x": .6, "y": .1}}
        data = group_data(self.plan.taggar, self.plan.farggruppering)
        key = data["assignments"][ident]["key"]
        self.plan.farggruppering = {"colors": {key: "#0000ff"}}
        content = self.plan._pdf_bytes()
        text = PdfReader(io.BytesIO(content)).pages[0].extract_text()
        for expected in ("Färggruppering", "Vertikallast V", "Pelarsulor [kN]", "100 ≤ V < 200"):
            self.assertIn(expected, text)
        with pdfium.PdfDocument(content) as pdf:
            image = pdf[0].render(scale=96 / 72).to_pil().convert("RGB")
        actual = image.getpixel((156, 157))
        expected = tuple(int(background_color("#0000ff")[i:i + 2], 16) for i in (1, 3, 5))
        self.assertTrue(all(abs(a - b) < 3 for a, b in zip(actual, expected)), (actual, expected))
        dot = image.getpixel((160, 136))
        self.assertTrue(dot[1] > dot[0] and dot[1] > dot[2], "Green result status remains visible")
        html = self.plan._html_bytes().decode()
        self.assertIn('"colour_grouping": {"enabled": true', html)
        self.assertIn("#0000ff", html)
        self.plan.farggruppering = {"show_legend": False}
        text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        self.assertNotIn("Färggruppering", text)
        self.assertTrue(self.plan.farggruppering["enabled"])
        self.plan.farggruppering = {"enabled": False}
        self.assertEqual(self.plan.farggruppering["colors"][key], "#0000ff")

    @unittest.skipUnless(shutil.which("node"), "Node krävs för jämförelse med HTML-grupperingen.")
    def test_javascript_and_python_assign_identical_groups_and_colours(self):
        for values in ({"b": .6, "t": .25, "F_vy": 100.5, "F_vy_bruk": None, "V_Ed_EQU": 210, "isolering": True},
                       {"lang": 0, "b": 1.8, "l": 2.1, "t": .3, "F_vy": 399.9999},
                       {"endast_h_stabilitet": True, "V_Ed_EQU": 300, "glid_x": True, "glid_y": True},
                       {"glid_x": True, "glid_mu": None}, {"lang": 0, "glid_y": True, "V_Ed_EQU": 0},
                       {"isolering": True, "glid_x": True, "glid_y": True}, {"t": None}):
            self.add(**values)
        cases = [validate_settings({"category": category, "phase": phase})
                 for category in ("t", "b", "l", "V", "isolering") for phase in ("brott", "bruk", "EQU")]
        cases += [validate_settings({"category": a, "secondary": b, "phase": phase})
                  for a in ("t", "b", "l", "V", "isolering") for b in ("t", "b", "l", "V", "isolering")
                  if a != b for phase in ("brott", "bruk", "EQU")]
        source = Path(__file__).resolve().parents[1] / "src/an_calcs/notebook/grundplan.js"
        script = '''import {readFileSync} from 'node:fs';
const {colourGroups} = await import('data:text/javascript;base64,' + readFileSync(process.argv[1]).toString('base64'));
const input = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(input.cases.map(settings => {const data = colourGroups(input.tags, settings);
return {groups: data.groups, assignments: Object.fromEntries(data.assignments)};})));'''
        result = subprocess.run(["node", "--input-type=module", "-e", script, str(source)],
                                input=json.dumps({"tags": self.plan.taggar, "cases": cases}), text=True,
                                capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), [group_data(self.plan.taggar, settings) for settings in cases])


if __name__ == "__main__":
    unittest.main()
