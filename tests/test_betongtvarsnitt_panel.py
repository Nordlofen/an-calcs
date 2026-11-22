"""Betongtvärsnitt via den faktiska Panel- och CalcBlock-kedjan."""

import contextlib
import io
import json
import math
import pathlib
import sys
import tempfile
import unittest
from xml.etree import ElementTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "an-print" / "src"))

from an_calcs.betong import betongtvarsnitt, bojstyvhet_betongpalar
from an_print import Panel
from an_print.calcblock import CalcBlock


def result(details):
    return {item["namn"]: item["value"] for item in details["slutresultat"]["items"]}


def drawing(markup):
    start = markup.index("<svg")
    end = markup.index("</svg>", start) + len("</svg>")
    return ElementTree.fromstring(markup[start:end])


class PanelTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.addCleanup(Panel._LAST_BY_FUNCTION.clear)
        self.addCleanup(Panel._LAST_VALUES.clear)
        self.state = pathlib.Path(work.name) / "panel_state.json"
        self.panel = Panel(betongtvarsnitt, state_file=self.state)
        self.fields = self.panel._field_widgets

    def calculate(self, panel=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return (panel or self.panel).calculate()

    def visible(self):
        visible_rows = [row for group in self.panel._scalar_field_groups for row in group["box"].children]
        return {name for name, row in self.panel._field_rows.items() if row in visible_rows}

    def figure(self):
        return self.panel._figure_records[0]["widget"].value

    def profile(self):
        return self.panel._figure_records[1]["widget"].value

    def test_three_geometries_and_both_stages(self):
        self.assertNotIn("tryckblock", self.fields)
        self.fields["f_cd"].value = 17.5
        for geometry, width, height, force, moment in (
            (1, 235, 600, 700, 30), (2, 300, 600, 200, 100), (3, 1000, 260, 0, -50),
        ):
            for key, value in dict(geometri=geometry, b=width, h=height, N_d=force, M=moment).items():
                self.fields[key].value = value
            for stage in (2, 3):
                with self.subTest(geometry=geometry, stage=stage):
                    self.fields["stadium"].value = stage
                    report = self.calculate()
                    self.assertIsInstance(self.panel.cb, CalcBlock)
                    values = result(report)
                    input_names = {item["namn"] for item in report["indata"]["items"]}
                    self.assertFalse({"geometri", "stadium"} & input_names)
                    partial = {item["namn"] for item in report["delresultat"]["items"]}
                    materials = {"E_s", "f_yk", "gamma_s", "epsilon_cu", "epsilon_c0"}
                    self.assertTrue(materials <= partial)
                    self.assertFalse((materials | {"f_cd"}) & input_names)
                    self.assertIn("f_ck", input_names)
                    self.assertEqual("f_cd" in partial, stage == 3)
                    self.assertEqual(next(iter(values)), "stadium")
                    self.assertEqual(values["stadium"], "II" if stage == 2 else "III")
                    self.assertIn(f'class="anp-data-block__rhs">{values["stadium"]}</div>', self.panel.cb.html_sr)
                    self.assertEqual("EI_II" in values, stage == 2)
                    self.assertEqual("sigma_c_Rd" in values, stage == 3)
                    self.assertEqual("momentkontroll" in values, stage == 3)
                    if stage == 2:
                        self.assertTrue({"x", "sigma_c_max", "F_c", "F_s_drag", "F_s_tryck"} <= values.keys())
                        self.assertTrue({"epsilon_c_max", "epsilon_sy"} <= partial)
                        self.assertEqual("z_II" in values, values["F_s_drag"] > 0)
                    else:
                        self.assertTrue({"x_Rd_verksam", "F_c_Rd", "F_s_drag_Rd", "F_s_tryck_Rd", "balanskontroll"} <= values.keys())
                        self.assertEqual(values["sigma_c_Rd"], self.fields["f_cd"].value)
                        self.assertTrue({"epsilon_c_Rd", "epsilon_sy"} <= partial)
                        self.assertEqual("z_Rd" in values, values["F_s_drag_Rd"] > 0)
                        self.assertEqual(values["M_Ed"], moment)
                        self.assertGreater(values["M_Rd"] * moment, 0)
                        self.assertIn("rektangulärt tryckblock", self.panel.cb.html_mb)
                    self.assertFalse(any(name.startswith("epsilon_") for name in values))
                    omitted = {"kappa_II", "M_Rd_min", "M_Rd_max", "inom_kapacitetsintervall", "utnyttjande_M"}
                    self.assertFalse(omitted & (values.keys() | partial))
                    self.assertTrue({"geometri", "stadium"} <= self.visible())
                    self.assertEqual("h" in self.visible(), geometry != 1)
                    self.assertEqual("b" in self.visible(), geometry != 3)
                    self.assertEqual("n_uk" in self.visible(), geometry == 2)
                    self.assertEqual("s_uk" in self.visible(), geometry == 3)
                    self.assertEqual("phi_h" in self.visible(), geometry == 1)
                    self.assertEqual("phi_b" in self.visible(), geometry != 3)
                    self.assertEqual("E_cd" in self.visible(), stage == 2)
                    self.assertEqual("f_cd" in self.visible(), stage == 3)
                    self.assertNotIn("pal_EI", values)
                    self.assertNotIn("K_c_override", self.fields)

    def test_plate_width_is_fixed_in_figures_reports_and_saved_cases(self):
        self.fields["b"].value = 381
        self.fields["geometri"].value = 3
        self.assertNotIn("b", self.visible())
        self.assertIn("b = 1000", self.figure())
        px = self.panel.to_px()
        i = betongtvarsnitt.panel_schema["px"].index("b")
        self.assertEqual(px[i], 1000)
        px[i] = 381  # Listindata kan skickas även utan Panelens låsta widget.
        report = betongtvarsnitt(px)
        self.assertEqual(next(row["value"] for row in report["indata"]["items"] if row["namn"] == "b"), 1000)
        self.panel._save_case("Meterremsa")
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(betongtvarsnitt, key="Meterremsa", state_file=self.state)
        restored._field_widgets["geometri"].value = 2
        self.assertEqual(restored.to_px()[i], 381)

    def test_plate_spacing_drives_area_and_automatic_bar_positions(self):
        for field, value in dict(geometri=3, h=260, M=-50, s_ok="150,5", s_uk="200").items():
            self.fields[field].value = value
        report = self.calculate()
        data = {row["namn"]: row["value"] for row in report["indata"]["items"]}
        self.assertEqual(data["s_1"], 150.5)
        self.assertAlmostEqual(data["As_1"], 1000 / 150.5 * math.pi * data["phi_1"]**2 / 4)
        self.assertAlmostEqual(data["As_2"], 1000 / 200 * math.pi * data["phi_2"]**2 / 4)
        svg = drawing(self.figure())
        bars = svg.findall(".//*[@data-part='langsjarn']")
        self.assertEqual(len(bars), 12)
        scale = float(svg.find(".//*[@data-part='betong']").get("width")) / 1000
        self.assertAlmostEqual((float(bars[1].get("cx")) - float(bars[0].get("cx"))) / scale, 150.5, places=2)
        self.fields["s_uk"].value = "0"
        self.assertEqual(len(drawing(self.figure()).findall(".//*[@data-part='langsjarn']")), 7)

    def test_old_plate_case_retains_area_when_spacing_fields_are_missing(self):
        self.fields["geometri"].value = 3
        self.fields["n_uk"].value = 7
        self.panel._save_case("Platta äldre fall")
        saved = json.loads(self.state.read_text())
        for case in saved.values():
            for field in ("s_ok", "s_uk"):
                case.pop(field, None)
        self.state.write_text(json.dumps(saved))
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(betongtvarsnitt, key="Platta äldre fall", state_file=self.state)
        data = {row["namn"]: row["value"] for row in self.calculate(restored)["indata"]["items"]}
        self.assertAlmostEqual(data["s_2"], 1000 / 7)
        self.assertAlmostEqual(data["As_2"], 7 * math.pi * data["phi_2"]**2 / 4)
        older_px = [value for name, value in zip(betongtvarsnitt.panel_schema["px"], restored.to_px())
                    if name not in {"s_ok", "s_uk", "c_nom_sida"} and "_lager_" not in name]
        self.assertEqual(self.calculate(restored), betongtvarsnitt(older_px))

    def test_outer_longitudinal_bars_touch_the_stirrup_in_each_layer(self):
        self.fields["b"].value = 1000
        self.fields["phi_ok"].value = 34
        self.panel._table_widgets["balk_lager"].add_row({"sida": "ok", "phi": 16, "mangd": 3, "a_v": 25})
        svg = drawing(self.figure())
        hoop = svg.find(".//*[@data-part='bygel']")
        bars = svg.findall(".//*[@data-part='langsjarn']")
        x, y, w, h, corner, stroke = (float(hoop.get(k)) for k in ("x", "y", "width", "height", "rx", "stroke-width"))
        inner_left, inner_right = x + stroke / 2, x + w - stroke / 2
        inner_top, inner_bottom = y + stroke / 2, y + h - stroke / 2
        layers = {}
        for bar in bars:
            cx, cy, r = (float(bar.get(k)) for k in ("cx", "cy", "r"))
            self.assertGreaterEqual(cy + .002, y + corner)
            self.assertLessEqual(cy - .002, y + h - corner)
            layers.setdefault(cy, []).append((cx, r))
        top, middle, bottom = sorted(layers)
        self.assertEqual([len(layers[cy]) for cy in (top, middle, bottom)], [2, 3, 4])
        for layer in layers.values():
            cx, r = layer[0]
            self.assertAlmostEqual(cx - r, inner_left, delta=.002)
            cx, r = layer[-1]
            self.assertAlmostEqual(cx + r, inner_right, delta=.002)
        self.assertAlmostEqual(top - layers[top][0][1], inner_top, delta=.002)
        self.assertAlmostEqual(bottom + layers[bottom][0][1], inner_bottom, delta=.002)

    def test_profile_uses_fixed_section_but_updates_external_loads(self):
        def geometry(profile):
            return [part.attrib for part in drawing(profile) if part.get("data-part") in {"betong", "bygel", "langsjarn"}]

        widths = {}
        for kind in (1, 2, 3):
            self.fields["geometri"].value = kind
            svg = drawing(self.profile())
            widths[kind] = float(svg.find(".//*[@data-part='betong']").get("width"))
            hoop = svg.find(".//*[@data-part='bygel']")
            self.assertEqual(hoop is not None, kind != 3)
            if hoop is not None:
                x, y, w, h, stroke = (float(hoop.get(k)) for k in ("x", "y", "width", "height", "stroke-width"))
                for bar in svg.findall(".//*[@data-part='langsjarn']"):
                    cx, cy, r = (float(bar.get(k)) for k in ("cx", "cy", "r"))
                    self.assertAlmostEqual(min(cx - x, x + w - cx) - r, stroke / 2)
                    self.assertAlmostEqual(min(cy - y, y + h - cy) - r, stroke / 2)
        self.assertGreater(widths[3], max(widths[1], widths[2]))
        schematic = {}
        for stage in (2, 3):
            self.fields["stadium"].value = stage
            schematic[stage] = geometry(self.profile())
            self.assertEqual(len(schematic[stage]), 5)
        for field, value in dict(h=225, s_uk="180", N_d=125.5, M=-90).items():
            self.fields[field].value = value
        for stage in (2, 3):
            self.fields["stadium"].value = stage
            profile = self.profile()
            self.assertEqual(geometry(profile), schematic[stage])
            if stage == 2:
                self.assertIn("Yttre laster", profile)
                self.assertIn("125,5 kN", profile)
                self.assertIn("-90 kNm", profile)
            else:
                capacity = result(self.calculate())["M_Rd"]
                self.assertIn("N_Ed = 125,5 kN", profile)
                self.assertIn(f'M_Rd = {capacity:.6g} kNm'.replace(".", ","), profile)

    def test_stress_profile_switches_stage_and_follows_bending_direction(self):
        self.fields["M"].value = 100
        svg = drawing(self.profile())
        self.assertEqual(svg.find(".//*[@data-part='betongspaenning']").get("data-form"), "linjaer")
        self.assertEqual(svg.find(".//*[@data-part='tryckzon']").get("y"), svg.find(".//*[@data-part='betong']").get("y"))
        self.fields["stadium"].value = 3
        self.fields["M"].value = -100
        svg = drawing(self.profile())
        self.assertEqual(svg.find(".//*[@data-part='betongspaenning']").get("data-form"), "rektangel")
        concrete, compression = (svg.find(f".//*[@data-part='{part}']") for part in ("betong", "tryckzon"))
        for part in ("neutralaxel", "toejning", "betongkraft", "dragkraft", "haevarm"):
            self.assertIsNotNone(svg.find(f".//*[@data-part='{part}']"))
        self.assertGreater(float(compression.get("y")), float(concrete.get("y")))
        self.assertAlmostEqual(float(compression.get("y")) + float(compression.get("height")),
                               float(concrete.get("y")) + float(concrete.get("height")), places=2)
        self.fields["N_d"].value = 1e7
        self.assertIn("Jämvikt vid angiven normalkraft hittades inte", self.profile())
        self.assertIn("Måttsatt tvärsnitt", self.figure())

    def test_schematic_axis_aligns_with_strain_line_and_compression_zone(self):
        for stage in (2, 3):
            self.fields["stadium"].value = stage
            for moment in (100, -100):
                with self.subTest(stage=stage, moment=moment):
                    self.fields["M"].value = moment
                    profile = self.profile()
                    relative_depth = .5 if stage == 2 else (.4375 if moment > 0 else .5625)
                    svg = drawing(profile)
                    concrete = svg.find(".//*[@data-part='betong']")
                    top, height = float(concrete.get("y")), float(concrete.get("height"))
                    points = svg.find(".//*[@data-part='toejning']").get("points").split()
                    zero, a, b, _ = [tuple(map(float, point.split(","))) for point in points]
                    crossing = a[1] + (b[1] - a[1]) * (zero[0] - a[0]) / (b[0] - a[0])
                    zone = svg.find(".//*[@data-part='tryckzon']")
                    zone_top = float(zone.get("y"))
                    zone_height = float(zone.get("height"))
                    self.assertAlmostEqual(crossing, top + height * relative_depth, places=1)
                    self.assertAlmostEqual(crossing, zone_top + (zone_height if moment > 0 else 0), places=1)

    def test_stage_iii_profile_aligns_the_steel_strain_and_resultants(self):
        for name, value in dict(geometri=3, stadium=3, h=300, N_d=900,
                                c_nom_ok=18, c_nom_uk=18, s_ok="130", s_uk="130").items():
            self.fields[name].value = value
        for moment in (-90, 90):
            with self.subTest(moment=moment):
                self.fields["M"].value = moment
                profile = self.profile()
                svg = drawing(profile)
                parts = {part.get("data-part"): part for part in svg.iter() if part.get("data-part")}
                self.assertIn("tyngdpunkt", parts)
                self.assertIn("#b44340", list(parts["normalkraft"])[-1].get("fill"))
                self.assertIn("#23784c", list(parts["kapacitetsmoment"])[-1].get("fill"))
                tension = float(parts["dragtoejning"].get("cy"))
                compression = float(parts["tryckresultant"].get("cy"))
                concrete_y, steel_y = (float(parts[name].get("points").split()[0].split(",")[1])
                                       for name in ("betongkraft", "tryckarmeringskraft"))
                self.assertLess(min(concrete_y, steel_y), compression)
                self.assertLess(compression, max(concrete_y, steel_y))
                for name in ("dragkraft", "dragniva"):
                    xy = parts[name].get("points", parts[name].get("d")).replace(",", " ").split()
                    self.assertEqual(float(xy[1]), tension)
                self.assertEqual(sorted(float(parts["haevarm"].get("d").split()[i]) for i in (1, 3)),
                                 sorted((tension, compression)))
                for axis in svg.findall(".//*[@data-part='profilaxel']"):
                    self.assertEqual([float(axis.get("d").split()[i]) for i in (1, 3)],
                                     [tension, 270] if moment < 0 else [110, tension])

    def test_stage_iii_keeps_the_axial_and_compression_steel_arrows_at_zero(self):
        for name, value in dict(geometri=3, stadium=3, h=300, N_d=0, M=-325,
                                c_nom_ok=45, s_ok="100", phi_ok=25, s_uk="0").items():
            self.fields[name].value = value
        svg = drawing(self.profile())
        force = svg.find(".//*[@data-part='normalkraft']")
        self.assertIsNotNone(force.find("{*}polyline"))
        self.assertEqual("".join(force.find("{*}text").itertext()), "NEd = 0")
        self.assertIsNotNone(svg.find(".//*[@data-part='tryckarmeringskraft']"))
        self.assertIn("F′s = 0", ["".join(text.itertext()) for text in svg.findall("{*}text")])
        concrete = svg.find(".//*[@data-part='betongkraft']")
        resultant = svg.find(".//*[@data-part='tryckresultant']")
        self.assertEqual(concrete.get("points").split()[0].split(",")[1], resultant.get("cy"))

    def test_equations_show_the_transformed_section_in_stage_ii_only(self):
        self.calculate()
        latex = self.panel.cb.latex_ekv
        for equation in (r"\alpha", "A_{II}(x)", "x_{tp}(x)", "I_{II}(x)", "M_{tp}(x)",
                         r"\sigma_{\min}(h)", r"\sigma_{II}(x;x)", "EI_{II}"):
            self.assertIn(equation, latex)
        self.assertIn("Lösning för x", latex)
        self.fields["stadium"].value = 3
        self.calculate()
        self.assertNotIn("I_{II}(x)", self.panel.cb.latex_ekv)
        self.assertIn(r"\min(0.8x,h)", self.panel.cb.latex_ekv)
        for equation in (r"N_{Ed} & = & F_c(x)+\sum_i F_{s,i}(x)", "M_{Rd,u} & = & F_c",
                         r"\varepsilon_{s,i}(x) & = & \varepsilon_{cu3}\left(1-\frac{u_i}{x}\right)",
                         r"F_c & = & f_{cd}(ba-A_{s,\mathrm{block}})", "|M_{Rd}| & = & F_c z"):
            self.assertIn(equation, self.panel.cb.latex_ekv)
        self.assertNotIn(r"\varepsilon(y)", self.panel.cb.latex_ekv)
        self.assertNotIn("d-0{,}4x", self.panel.cb.latex_ekv)
        self.assertIn("ren böjning utan tryckarmering", self.panel.cb.latex_ekv)

    def test_figure_and_saved_case_follow_layer_inputs(self):
        self.assertIn("UK  4 × Ø20", self.figure())
        self.assertIn("Bygel Ø8", self.figure())
        self.fields["n_uk"].value = 5
        self.fields["c_nom_uk"].value = 44
        self.fields["phi_b"].value = 10
        self.assertIn("UK  5 × Ø20", self.figure())
        self.assertIn("UK 44", self.figure())
        self.assertIn("Bygel Ø10", self.figure())
        self.assertNotIn("Stångcentrum y", self.figure())
        self.fields["stadium"].value = 3
        self.panel._save_case("Balk 1")
        px = self.panel.to_px()
        saved = json.loads(self.state.read_text())
        saved[self.panel._last_key]["tryckblock"] = "parabel"  # Fall sparat i tidigare Panel.
        self.state.write_text(json.dumps(saved))
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(betongtvarsnitt, key="Balk 1", state_file=self.state)
        self.assertEqual(restored.to_px(), px)
        self.assertEqual(restored._figure_records[0]["widget"].value, self.figure())
        self.assertEqual(self.calculate(restored), self.calculate())
        self.assertIn("rektangulärt tryckblock", restored.cb.html_mb)

    def test_old_pile_case_stays_under_old_key(self):
        legacy = Panel(bojstyvhet_betongpalar, state_file=self.state)
        legacy._field_widgets["K_c_override"].value = True
        legacy._field_widgets["K_c_manuell"].value = 0.5
        legacy._save_case("Påle 1")
        old_px = legacy.to_px()
        old_report = self.calculate(legacy)
        self.panel._save_case("Balk 1")
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(bojstyvhet_betongpalar, key="Påle 1", state_file=self.state)
        self.assertEqual(restored.to_px(), old_px)
        self.assertEqual(self.calculate(restored), old_report)
        self.assertEqual(betongtvarsnitt(old_px), old_report)

    def test_warnings_and_strain_criterion_are_in_calcblock(self):
        self.fields["M"].value = 20000
        details = self.calculate()
        cb = self.panel.cb
        for key in ("html_mb", "html_sr", "latex_sr"):
            block = getattr(cb, key)
            for wording in ("elastiska töjningsgränsen", "överskrider flytgränsen", "tillåtna stuktöjning", "Kritisk varning"):
                self.assertIn(wording, block)
        self.assertIn("Definition:", cb.html_id)
        self.assertIn("Definition:", cb.latex_id)
        self.assertIn("EI_II", result(details))
        self.assertNotIn("M_Rd_max", result(details))
        self.fields["epsilon_c_lim_manuell"].value = True
        self.fields["epsilon_c_lim_pm"].value = 0.4
        details = self.calculate()
        entry = next(row for row in details["indata"]["items"] if row["namn"] == "epsilon_c_lim")
        self.assertEqual(entry["value"], 0.4)
        self.assertIn("manuellt", entry["etikett"])

    def test_missing_axial_equilibrium_shows_demand_and_critical_warning(self):
        self.fields["stadium"].value = 3
        self.fields["N_d"].value = 1e7
        report = result(self.calculate())
        self.assertEqual(report["stadium"], "III")
        self.assertEqual(report["M_Ed"], self.fields["M"].value)
        self.assertNotIn("M_Rd", report)
        self.assertNotIn("sigma_c_Rd", report)
        self.assertEqual(report["momentkontroll"], "Ej godkänd")
        self.assertIn("Kritisk varning. Ingen jämvikt hittades", self.panel.cb.html_sr)

    def test_report_uses_tension_and_compression_groups_in_both_stages(self):
        self.fields["N_d"].value = 200
        for stage, suffix in ((2, ""), (3, "_Rd")):
            self.fields["stadium"].value = stage
            for moment in (-100, 100):
                with self.subTest(stage=stage, moment=moment):
                    self.fields["M"].value = moment
                    details = self.calculate()
                    final = result(details)
                    partial = {row["namn"]: row["value"] for row in details["delresultat"]["items"]}
                    self.assertFalse(any(name.startswith("sigma_s_") for name in final))
                    self.assertGreater(final[f"F_s_drag{suffix}"], 0)
                    self.assertGreater(final[f"F_s_tryck{suffix}"], 0)
                    self.assertGreater(partial["epsilon_s_drag"], 0)
                    self.assertGreater(partial["epsilon_s_tryck"], 0)
                    self.assertAlmostEqual(partial["d"], 549 if moment < 0 else 542)
                    self.assertAlmostEqual(partial["d_prime"], 58 if moment < 0 else 51)

    def test_multiple_layers_report_each_depth_before_the_group_centroid(self):
        self.fields["N_d"].value = 200
        self.panel._table_widgets["balk_lager"].add_row({"sida": "ok", "phi": 12, "mangd": 3, "a_v": 25})
        centroid = (2 * 16**2 * 51 + 3 * 12**2 * 90) / (2 * 16**2 + 3 * 12**2)
        for stage in (2, 3):
            self.fields["stadium"].value = stage
            for moment, name, symbol, first, second, combined in (
                (100, "d_prime", "d'", 51, 90, centroid),
                (-100, "d", "d", 549, 510, 600 - centroid),
            ):
                with self.subTest(stage=stage, moment=moment):
                    self.fields["M"].value = moment
                    report = self.calculate()
                    partial = {row["namn"]: row for row in report["delresultat"]["items"]}
                    keys = list(partial)
                    index = keys.index(name)
                    self.assertEqual(keys[index - 2:index], [f"{name}_1", f"{name}_2"])
                    for i, expected in enumerate((first, second), 1):
                        row = partial[f"{name}_{i}"]
                        self.assertEqual(row["latex"], rf"{symbol}_{{{i}}}")
                        self.assertEqual(row["value"], expected)
                    self.assertAlmostEqual(partial[name]["value"], combined)
                    self.assertIn("gemensamma areatyngdpunkt", self.panel.cb.html_dr)
                    self.assertNotIn("d_3", partial)
                    self.assertNotIn("d_prime_3", partial)

    def test_stage_iii_reports_force_depths_and_signed_steel_strains(self):
        for name, value in dict(geometri=3, stadium=3, h=200, N_d=0, M=-90,
                                c_nom_ok=45, phi_ok=10, s_ok="100", s_uk="0").items():
            self.fields[name].value = value
        self.panel._table_widgets["plattremsa_lager"].add_row({"sida": "ok", "phi": 20, "mangd": 200, "a_v": 10})
        details = self.calculate()
        rows = {row["namn"]: row for row in details["delresultat"]["items"]}
        self.assertEqual(rows["epsilon_c_Rd"]["latex"], r"ε_{cu3}")
        self.assertNotIn("epsilon_top_Rd", rows)
        self.assertEqual(rows["epsilon_bottom_Rd"]["value"], 3.5)
        x = rows["x_Rd"]["value"]
        self.assertAlmostEqual(rows["u_c"]["value"], 0.4 * x)
        for i, depth in enumerate((150, 125), 1):
            self.assertEqual(rows[f"u_s_{i}"]["value"], depth)
            self.assertAlmostEqual(rows[f"epsilon_s_{i}"]["value"], 3.5 * (1 - depth / x))
        self.assertAlmostEqual(rows["d"]["value"], (150 + 2 * 125) / 3)

    def test_plate_with_steel_below_yield_has_no_warning_in_stage_iii(self):
        for key, value in dict(geometri=3, stadium=3, h=260, c_nom_ok=45, phi_ok=25,
                               s_ok="50", s_uk="0", N_d=0, M=-325).items():
            self.fields[key].value = value
        report = self.calculate()
        values = result(report)
        rows = {row["namn"]: row for row in report["slutresultat"]["items"]}
        self.assertEqual(rows["sigma_c_Rd"]["latex"], r"\sigma_c=f_{cd}")
        self.assertEqual(rows["sigma_c_Rd"]["unit"], "MPa")
        self.assertAlmostEqual(values["M_Rd"], -342.089560, places=5)
        self.assertFalse(any(name.startswith("varning_") for name in values))
        self.assertEqual(values["balanskontroll"], "Överarmerat · Ej godkänd")
        self.assertEqual(values["momentkontroll"], "Godkänd")
        self.assertEqual(rows["stadium"]["etikett"], "")
        for name, symbol in {"F_c_Rd": "F_c", "F_s_drag_Rd": "F_s", "F_s_tryck_Rd": "F'_s", "z_Rd": "z"}.items():
            self.assertEqual(rows[name]["latex"], symbol)
        self.assertEqual(rows["F_s_drag_Rd"]["etikett"], "armeringens dragkraft")
        self.assertEqual(rows["M_Rd"]["etikett"], "momentkapacitet i lastens riktning")
        self.assertIn("dragtöjning vid d", self.panel.cb.html_sr)

    def test_extra_beam_layers_update_the_sketch_and_survive_case_restore(self):
        self.fields["c_nom_sida"].value = "30"
        table = self.panel._table_widgets["balk_lager"]
        table.add_row({"sida": "ok", "phi": 12, "mangd": 3, "a_v": 25})
        self.assertIn("ÖK  2 lager", self.figure())
        bars = drawing(self.figure()).findall(".//*[@data-part='langsjarn']")
        self.assertEqual(len(bars), 9)
        self.assertEqual(len({bar.get("cy") for bar in bars}), 3)
        details = self.calculate()
        partial = {row["namn"]: row["value"] for row in details["delresultat"]["items"]}
        self.assertAlmostEqual(partial["a_h_1"], 192)
        self.assertAlmostEqual(partial["a_h_2"], 94)
        self.assertAlmostEqual(partial["a_v_1_2"], 25)
        self.panel._save_case("Balk med extra lager")
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(betongtvarsnitt, key="Balk med extra lager", state_file=self.state)
        self.assertEqual(restored.to_px(), self.panel.to_px())
        self.assertEqual(self.calculate(restored), details)
        self.assertEqual(restored._figure_records[0]["widget"].value, self.figure())
        restored._table_widgets["balk_lager"].rows[-1]["remove_button"].click()
        updated = drawing(restored._figure_records[0]["widget"].value)
        self.assertEqual(len(updated.findall(".//*[@data-part='langsjarn']")), 6)

    def test_balance_uses_tension_centroid_when_only_one_layer_yields(self):
        for name, value in dict(geometri=3, stadium=3, h=400, s_ok="0", s_uk="65", M=200).items():
            self.fields[name].value = value
        self.panel._table_widgets["plattremsa_lager"].add_row(
            {"sida": "uk", "phi": 16, "mangd": 45, "a_v": 50})
        details = self.calculate()
        final = result(details)
        partial = {row["namn"]: row["value"] for row in details["delresultat"]["items"]}
        self.assertAlmostEqual(partial["a_h_2"], 29)
        self.assertAlmostEqual(partial["a_v_2_1"], 50)
        area_fraction = (20**2 / 65) / (20**2 / 65 + 16**2 / 45)
        depth = area_fraction * 350 + (1 - area_fraction) * 282
        self.assertAlmostEqual(partial["d"], depth)
        self.assertAlmostEqual(partial["epsilon_s_drag"], 3.5 * (depth / partial["x_Rd"] - 1))
        self.assertAlmostEqual(partial["flytandel_drag"], 100 * area_fraction)
        self.assertIn(r"\%", self.panel.cb.latex_dr)
        self.assertEqual(final["balanskontroll"], "Överarmerat · Ej godkänd")
        self.assertGreater(final["M_Rd"], final["M_Ed"])

    def test_balance_reports_the_yield_boundary_and_passes_on_the_underreinforced_side(self):
        fyd = 500 / 1.15
        x_bal = 350 * .0035 / (.0035 + fyd / 200000)
        area_bal = 1000 * .8 * x_bal * 20 / fyd
        spacing_bal = 1000 * math.pi * 20**2 / (4 * area_bal)
        for name, value in dict(geometri=3, stadium=3, h=400, s_ok="0", M=100).items():
            self.fields[name].value = value
        self.fields["s_uk"].value = str(spacing_bal)
        self.assertEqual(result(self.calculate())["balanskontroll"], "Balanserat · Gränsfall")
        self.fields["s_uk"].value = str(spacing_bal * 1.1)
        capacity = result(self.calculate())["M_Rd"]
        for moment, expected in ((capacity, "Godkänd"), (capacity + 1, "Ej godkänd")):
            with self.subTest(moment=moment):
                self.fields["M"].value = moment
                final = result(self.calculate())
                self.assertEqual(final["balanskontroll"], "Underarmerat · Godkänd")
                self.assertEqual(final["momentkontroll"], expected)
                rows = list(final)
                self.assertEqual(rows[rows.index("balanskontroll") + 1], "momentkontroll")
                self.assertEqual(rows[-1], "momentkontroll")
                html = self.panel.cb.html_sr
                self.assertRegex(html, rf"(?s)Balanskontroll.*Momentkontroll.*>{expected}</div>")
                if expected == "Ej godkänd":
                    self.assertIn("ligger utanför snittets momentkapacitet", self.panel.cb.html_mb)
                    self.assertIn(f"Gräns {capacity:.6g} kNm.", self.panel.cb.html_mb)
