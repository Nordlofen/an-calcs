import copy
import importlib.util
import io
from itertools import combinations
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
    from an_calcs.notebook.grundplan_colour import DEFAULT_SETTINGS, validate_settings, group_data, background_color, PALETTE, remember_styles


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

    def test_set3_original_colours_then_patterns_cover_many_groups(self):
        tags = [{"id": str(i), "values": {"t": i + 1}} for i in range(73)]
        settings = validate_settings({})
        before = copy.deepcopy((tags, settings))
        groups = group_data(tags, settings)["groups"]
        self.assertEqual([g["background"] for g in groups[:12]], PALETTE)
        self.assertEqual([g["color"] for g in groups[12:24]], PALETTE)
        for index, pattern in ((0, "plain"), (11, "plain"), (12, "bands"), (24, "dots"),
                               (36, "cross"), (48, "horizontal"), (60, "vertical"), (72, "bands")):
            self.assertEqual(groups[index]["pattern"], pattern)
        self.assertEqual(groups[72]["pattern_variant"], 1)
        self.assertEqual((tags, settings), before, "Grouping is pure visual data")

    def test_empty_intervals_and_neutral_groups_do_not_consume_palette_slots(self):
        tags = [{"id": "pad", "values": {"lang": 0, "F_vy": 145}},
                {"id": "wall", "values": {"lang": 1, "F_vy": 195}},
                {"id": "h", "values": {"lang": 1, "endast_h_stabilitet": True}}]
        settings = validate_settings({"category": "V", "bounds": {"pad": list(range(10, 210, 10)),
                                                                  "wall": list(range(10, 210, 10))}})
        data = group_data(tags, settings)
        self.assertEqual([data["assignments"][i]["background"] for i in ("pad", "wall")], PALETTE[:2])
        self.assertTrue(all(g["style_index"] is None for g in data["groups"] if not g["count"] or g["kind"] == "special"))
        saved = remember_styles(tags, settings)
        self.assertEqual(len(saved["styles"]["V:brott"]), 2)
        self.assertTrue(all(g["pattern"] == "plain" for g in data["groups"]))

    def test_saved_styles_survive_added_smaller_values_deletion_switching_and_reload(self):
        first = self.add(t=.3)
        second = self.add(t=.4)
        self.plan.farggruppering = {"enabled": True}
        original = group_data(self.plan.taggar, self.plan.farggruppering)["assignments"]
        key = original[first]["key"]
        third = self.add(t=.2)
        changed = group_data(self.plan.taggar, self.plan.farggruppering)["assignments"]
        self.assertEqual([changed[i]["style_index"] for i in (first, second, third)], [0, 1, 2])
        self.assertEqual(changed[first]["background"], original[first]["background"])
        self.plan.farggruppering = {"colors": {key: "#123456"}, "category": "V"}
        self.plan.farggruppering = {"category": "t"}
        self.plan.ta_bort(second)
        restored = Grundplan.oppna(self.plan.spara(self.folder / "styles.json"))
        self.addCleanup(restored.close)
        groups = group_data(restored.taggar, restored.farggruppering)["assignments"]
        self.assertEqual(groups[first]["color"], "#123456")
        self.assertEqual(groups[third]["style_index"], 2)
        self.assertEqual(restored.farggruppering["styles"]["t"][original[second]["key"]], 1)

    def test_changed_load_intervals_reclaim_retired_colours_before_patterns(self):
        tags = [{"id": "w" + str(i), "values": {"lang": 1, "V_Ed_EQU": value}}
                for i, value in enumerate((150, 250, 350, 450, 550, 650, 750, 850))]
        tags += [{"id": "p" + str(i), "values": {"lang": 0, "V_Ed_EQU": value}}
                 for i, value in enumerate((250, 600))]
        settings = validate_settings({"category": "V", "phase": "EQU",
            "bounds": {"pad": [200, 400], "wall": [200, 300, 400, 500, 600, 700, 800]}})
        keys = [group["key"] for group in group_data(tags, settings)["groups"] if group["count"]]
        settings["styles"] = {"V:EQU": {**{"retired-" + str(i): i for i in range(6)},
                                         **{key: i + 6 for i, key in enumerate(keys)}}}
        settings["colors"][keys[-1]] = "#123456"
        saved = remember_styles(tags, settings)
        validate_settings(saved)
        groups = [group for group in group_data(tags, saved)["groups"] if group["count"]]
        self.assertEqual(len(groups), 10)
        self.assertTrue(all(group["pattern"] == "plain" for group in groups))
        self.assertEqual(len({group["style_index"] for group in groups}), 10)
        self.assertEqual([group["style_index"] for group in groups[:6]], list(range(6, 12)))
        self.assertEqual(groups[-1]["color"], "#123456")
        self.assertNotIn("retired-0", saved["styles"]["V:EQU"])

    def test_shrinking_and_returning_groups_use_twelve_plain_styles_before_each_pattern_batch(self):
        tags = [{"id": str(i), "values": {"t": i + 1}} for i in range(30)]
        settings = remember_styles(tags, validate_settings({}))
        for count in (12, 13, 10, 24, 25, 30):
            active = tags[-count:]
            settings = remember_styles(active, settings)
            validate_settings(settings)
            groups = group_data(active, settings)["groups"]
            self.assertEqual(len({group["style_index"] for group in groups}), count)
            self.assertEqual(sum(group["pattern"] == "plain" for group in groups), min(count, 12))
            self.assertEqual(sum(group["pattern"] == "bands" for group in groups), min(max(count - 12, 0), 12))
            self.assertEqual(sum(group["pattern"] == "dots" for group in groups), max(count - 24, 0))
        settings = remember_styles(tags[-12:], settings)
        for tag in tags[-12:]:
            self.add(**tag["values"])
        self.plan.farggruppering = {**settings, "enabled": True}
        restored = Grundplan.oppna(self.plan.spara(self.folder / "reclaimed-colours.json"))
        self.addCleanup(restored.close)
        self.assertEqual(group_data(tags[-12:], restored.farggruppering), group_data(tags[-12:], settings))

    def test_saved_later_pattern_families_cannot_skip_the_first_pattern_batch(self):
        tags = [{"id": str(i), "values": {"t": i + 1}} for i in range(13)]
        settings = validate_settings({})
        keys = [group["key"] for group in group_data(tags, settings)["groups"]]
        settings["styles"] = {"t": {key: i + 24 for i, key in enumerate(keys)}}
        groups = group_data(tags, settings)["groups"]
        self.assertEqual(sum(group["pattern"] == "plain" for group in groups), 12)
        self.assertEqual(groups[-1]["pattern"], "bands")

    def test_patterned_export_keeps_widgets_and_labels_as_vectors(self):
        from reportlab.pdfgen.canvas import Canvas
        source = self.folder / "vector.pdf"
        canvas = Canvas(str(source), pagesize=(1800, 1400))
        canvas.line(0, 0, 1800, 1400)
        canvas.showPage(); canvas.save()
        self.plan.importera_ritning(source)
        for i in range(25):
            self.plan.lagg_till(.05 + (i % 5) * .16, .03 + (i // 5) * .13,
                               littera=f"VS.{i + 1}", indata={"t": .2 + i * .01, "kommentar": f"Kommentar {i + 1}"})
        self.plan.farggruppering = {"enabled": True, "legend": {"x": .82, "y": .03, "size": 210}}
        self.plan.kommentarwidget = {"enabled": True, "x": .05, "y": .73, "size": 350}
        page = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0]
        self.assertEqual(len(page.images), 0, "Patterns, labels, widgets and drawing remain vectors")
        self.assertIn("VS.25", page.extract_text())
        self.assertIn("Kommentar 25", page.extract_text())
        html = self.plan._html_bytes().decode()
        self.assertIn('gp-group-pattern', html)
        self.assertIn('"styles": {"t":', html)

    def test_invalid_saved_styles_are_atomic(self):
        before = self.plan._document()
        for styles in ([], {"t": []}, {"t": {"a": True}}, {"t": {"a": -1}},
                       {"t": {"a": 5000}}, {"t": {"a": 0, "b": 0}}, {"t": {"a": []}}):
            with self.subTest(styles=styles), self.assertRaises(ValueError):
                self.plan.farggruppering = {"styles": styles}
            self.assertEqual(self.plan._document(), before)

    def test_geometry_uses_actual_width_length_and_thickness_and_excludes_h_only(self):
        wall = self.add(b=.6, t=.25)
        pad = self.add(lang=0, b=1.8, l=2.1, t=.3)
        only_h = self.add(endast_h_stabilitet=True, b=1.8)
        missing = self.add(t=None)
        for category, expected in (("t", (.25, .3)), ("b", (.6, 1.8)), ("l", (1., 2.1))):
            settings = validate_settings({"category": category})
            data = group_data(self.plan.taggar, settings)
            self.assertEqual(tuple(data["assignments"][tag]["value"] for tag in (wall, pad)), expected)
            self.assertNotIn(only_h, data["assignments"])
            self.assertNotIn("na", [group["key"] for group in data["groups"]])
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

    def test_h_only_exclusion_applies_to_either_combination_category_and_pdf(self):
        wall = self.add(t=.3, b=.6)
        only_h = self.add(endast_h_stabilitet=True, t=.3, b=.6, glid_x=True)
        tags = self.plan.taggar
        before = copy.deepcopy(tags)
        for category in ("t", "b", "l"):
            for secondary in ("t", "b", "l", "V", "isolering"):
                if category == secondary:
                    continue
                for first, second in ((category, secondary), (secondary, category)):
                    data = group_data(tags, validate_settings({"category": first, "secondary": second}))
                    self.assertEqual(set(data["assignments"]), {wall})
                    self.assertEqual(sum(group["count"] for group in data["groups"]), 1)
        self.assertEqual(tags, before)
        self.plan.farggruppering = {"enabled": True, "category": "t", "secondary": "b"}
        text = PdfReader(io.BytesIO(self.plan._pdf_bytes())).pages[0].extract_text()
        self.assertNotIn("Ej tillämpligt", text)
        self.assertIn("Endast H-stabilitet", text, "Excluded footings remain on the drawing")
        for category in ("isolering", "V"):
            data = group_data(tags, validate_settings({"category": category}))
            self.assertNotIn(only_h, data["assignments"])
            data = group_data(tags, validate_settings({"category": category, "phase": "EQU", "include_only_h": True}))
            self.assertIn(only_h, data["assignments"])

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
                                  "include_only_h": True,
                                  "colors": colors, "legend": {"x": .4, "y": .1, "size": 350}}
        data = group_data(self.plan.taggar, self.plan.farggruppering)
        self.assertEqual([(group["label"], group["count"], group["unit"]) for group in data["groups"]],
                         [("Med isolering · inget bidrag", 1, ""), ("Utan isolering · inget bidrag", 1, ""),
                          ("Utan isolering · bidrag i X_g", 1, ""), ("Utan isolering · bidrag i Y_g", 2, ""),
                          ("Utan isolering · bidrag i X_g och Y_g", 1, "")])
        for ident, suffix in ((insulated, "1"), (uninsulated, "0"), (only_h, "y"), (x, "x"), (y, "y"), (xy, "xy")):
            self.assertEqual(data["assignments"][ident]["key"], "isolering:" + suffix)
        self.assertEqual([group["color"] for group in data["groups"]],
                         ["#f0d8c8", "#cce7ff", "#bebada", "#fb8072", "#d8eedc"])
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
        self.assertEqual([group["style_index"] for group in data["groups"]], [0, None, None, None, None])
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
            for include in (False, True):
                settings = validate_settings({"category": "V", "phase": phase, "include_only_h": include})
                data = group_data(self.plan.taggar, settings)
                self.assertEqual(data["assignments"][pad]["low"], low)
                self.assertEqual(only_h in data["assignments"], include and phase == "EQU")
                self.assertNotIn("na", [group["key"] for group in data["groups"]])

    def test_h_only_inclusion_filters_all_category_combinations_without_neutral_groups(self):
        normal = self.add(t=.3, b=.6, F_vy=250, F_vy_bruk=150, V_Ed_EQU=200)
        only_h = self.add(endast_h_stabilitet=True, t=.3, b=.6, F_vy=250,
                          F_vy_bruk=150, V_Ed_EQU=200, glid_y=True)
        before = copy.deepcopy((self.plan.taggar, self.plan.resultat))
        for count in range(1, 6):
            for categories in combinations(("t", "b", "l", "V", "isolering"), count):
                for phase in ("brott", "bruk", "EQU"):
                    for include in (False, True):
                        with self.subTest(categories=categories, phase=phase, include=include):
                            data = group_data(self.plan.taggar, validate_settings({
                                "categories": list(categories), "phase": phase, "include_only_h": include}))
                            eligible = include and not set(categories) & {"t", "b", "l"} and ("V" not in categories or phase == "EQU")
                            self.assertEqual(set(data["assignments"]), {normal, only_h} if eligible else {normal})
                            self.assertEqual(sum(group["count"] for group in data["groups"]), 2 if eligible else 1)
                            self.assertFalse(any(group.get("label") == "Ej tillämpligt" for group in data["groups"]))
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)

    def test_h_only_inclusion_saves_and_old_projects_default_to_white(self):
        only_h = self.add(endast_h_stabilitet=True, V_Ed_EQU=200)
        self.plan.farggruppering = {"enabled": True, "category": "V", "phase": "EQU", "include_only_h": True}
        restored = Grundplan.oppna(self.plan.spara(self.folder / "h-inclusion.json"))
        self.addCleanup(restored.close)
        self.assertTrue(restored.farggruppering["include_only_h"])
        self.assertIn(only_h, group_data(restored.taggar, restored.farggruppering)["assignments"])
        legacy = restored._document()
        legacy["version"] = 17
        del legacy["colour_grouping"]["include_only_h"]
        legacy["colour_grouping"]["colors"]["na"] = "#123456"
        restored._load_document(json.dumps(legacy).encode())
        self.assertFalse(restored.farggruppering["include_only_h"])
        self.assertNotIn(only_h, group_data(restored.taggar, restored.farggruppering)["assignments"])

    def test_h_only_pdf_and_html_keep_white_labels_and_omit_inapplicable_groups(self):
        self.add(endast_h_stabilitet=True, F_vy=250, F_vy_bruk=150, V_Ed_EQU=200,
                 glid_y=True, glid_mu=.4, glid_L=3, L_vagg=3, kommentar="Kommentar H")
        self.plan.farggruppering = {"enabled": True, "category": "V", "phase": "bruk", "include_only_h": True}
        content = self.plan._pdf_bytes()
        text = PdfReader(io.BytesIO(content)).pages[0].extract_text()
        self.assertIn("Endast H-stabilitet", text)
        self.assertNotIn("Ej tillämpligt", text)
        self.assertNotIn("Saknar värde", text)
        self.assertNotIn("Linjelaster [kN/m]", text, "Excluded footings create no legend section")
        with pdfium.PdfDocument(content) as pdf:
            image = pdf[0].render(scale=96 / 72).to_pil().convert("RGB")
        self.assertEqual(image.getpixel((165, 180)), (255, 255, 255), "Excluded labels have a white interior")
        self.assertNotEqual(image.getpixel((160, 136)), (255, 255, 255), "The status dot remains visible")
        html = self.plan._html_bytes().decode()
        self.assertIn('"include_only_h": true', html)
        self.assertNotIn("Ej tillämpligt", html)

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

    def test_three_to_five_categories_preserve_group_identity_colours_and_saved_choices(self):
        first = self.add(b=.8, t=.25, F_vy=150, kommentar="Samordnas.")
        same = self.add(b=.8, t=.25, F_vy=190)
        higher = self.add(b=.8, t=.25, F_vy=250)
        thicker = self.add(b=.8, t=.3, F_vy=150)
        pad = self.add(lang=0, b=.8, l=1, t=.25, F_vy=150)
        only_h = self.add(endast_h_stabilitet=True, b=.8, t=.25)
        before = copy.deepcopy((self.plan.taggar, self.plan.resultat))
        settings = validate_settings({"categories": ["V", "b", "t"]})
        data = group_data(self.plan.taggar, settings)
        self.assertEqual(len(data["groups"]), 4)
        self.assertEqual(data["assignments"][first], data["assignments"][same])
        self.assertEqual(data["assignments"][first]["count"], 2)
        self.assertNotIn(only_h, data["assignments"])
        self.assertNotEqual(data["assignments"][first]["key"], data["assignments"][pad]["key"])
        self.assertEqual(len({data["assignments"][ident]["key"] for ident in (first, higher, thicker)}), 3)
        key = data["assignments"][first]["key"]
        self.plan.farggruppering = {"enabled": True, "categories": ["b", "V", "t"], "colors": {key: "#c8e0d8"}}
        expected = self.plan.farggruppering
        self.plan.farggruppering = {"enabled": False}
        restored = Grundplan.oppna(self.plan.spara(self.folder / "three.json"))
        self.addCleanup(restored.close)
        restored.farggruppering = {"enabled": True, "categories": ["V", "t", "b"]}
        self.assertEqual(restored.farggruppering, expected)
        self.assertEqual(group_data(restored.taggar, restored.farggruppering)["assignments"][first]["color"], "#c8e0d8")
        for categories in (["t", "b", "l", "V"], ["t", "b", "l", "V", "isolering"]):
            self.plan.farggruppering = {"categories": categories}
            groups = group_data(self.plan.taggar, self.plan.farggruppering)
            self.assertTrue(all(len(group["parts"]) == len(categories) for group in groups["groups"]))
            self.assertEqual(sum(group["count"] for group in groups["groups"]), 5)
        self.plan.farggruppering = {"category": "V", "secondary": None}
        self.assertIsNone(self.plan.farggruppering["categories"], "Legacy Python calls replace the selected list")
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)
        legacy = validate_settings({"category": "b", "secondary": "t"})
        self.assertEqual(group_data(self.plan.taggar, legacy),
                         group_data(self.plan.taggar, validate_settings({"categories": ["b", "t"]})))

    def test_invalid_settings_and_import_are_atomic_and_old_projects_default_to_off(self):
        document = self.plan._document()
        invalid = [{"enabled": 1}, {"include_only_h": 1}, {"include_only_h": "true"}, {"include_only_h": None},
                   {"category": "phi"}, {"secondary": "t"}, {"secondary": "bad"}, {"secondary": []}, {"phase": "uls"}, {"edit_type": "all"},
                   {"categories": []}, {"categories": ["t", "t"]}, {"categories": ["b", "phi"]},
                   {"categories": "t"}, {"categories": [None]}, {"categories": [["t"]]},
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
        for expected in ("Färggruppering", "Vertikallast V", "Punktlaster [kN]", "100 ≤ V < 200"):
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
        for i in range(25):
            self.add(t=.4 + i * .01, F_vy=25 * i)
        for values in ({"b": .6, "t": .25, "F_vy": 100.5, "F_vy_bruk": None, "V_Ed_EQU": 210, "isolering": True},
                       {"lang": 0, "b": 1.8, "l": 2.1, "t": .3, "F_vy": 399.9999},
                       {"endast_h_stabilitet": True, "V_Ed_EQU": 300, "glid_x": True, "glid_y": True},
                       {"glid_x": True, "glid_mu": None}, {"lang": 0, "glid_y": True, "V_Ed_EQU": 0},
                       {"isolering": True, "glid_x": True, "glid_y": True}, {"t": None},
                       {"lang": 0, "lasttyp": 1, "b": .8, "l": 1.3, "L_vagg": .5, "t": .25, "F_vy": 150}):
            self.add(**values)
        cases = [validate_settings({"category": category, "phase": phase})
                 for category in ("t", "b", "l", "V", "isolering") for phase in ("brott", "bruk", "EQU")]
        cases += [validate_settings({"category": a, "secondary": b, "phase": phase})
                  for a in ("t", "b", "l", "V", "isolering") for b in ("t", "b", "l", "V", "isolering")
                  if a != b for phase in ("brott", "bruk", "EQU")]
        cases += [validate_settings({"categories": list(selected), "phase": phase})
                  for count in range(1, 6) for selected in combinations(("t", "b", "l", "V", "isolering"), count)
                  for phase in ("brott", "bruk", "EQU")]
        cases += [validate_settings({"categories": ["sultyp", *selected], "phase": phase})
                  for selected in ([], ["t"], ["t", "b"], ["V"], ["t", "b", "l", "V", "isolering"])
                  for phase in ("brott", "bruk", "EQU")]
        self.plan.lagg_till(.4, .4, typ="pelarsula", indata={"t": .25, "b": .6, "F_vy": 100.5})
        cases += [remember_styles(self.plan.taggar[::-1], settings) for settings in cases[:15]]
        # Old intervals and group deletions can leave sparse historic indices.
        for settings in cases[:15]:
            groups = group_data(self.plan.taggar, settings)["groups"]
            keys = [group["key"] for group in groups if group["count"] and group["kind"] != "special"]
            scope = "+".join(settings.get("categories") or [settings["category"]]) + (
                ":" + settings["phase"] if settings["category"] == "V" else "")
            cases.append({**settings, "styles": {scope: {**{"retired-" + str(i): i for i in range(12)},
                                                       **{key: i + 24 for i, key in enumerate(keys)}}}})
        cases += [{**settings, "include_only_h": True} for settings in cases]
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
