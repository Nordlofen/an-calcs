"""Betongtvärsnitt via den faktiska Panel- och CalcBlock-kedjan."""

import contextlib
import io
import json
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
                    partial = {item["namn"] for item in report["delresultat"]["items"]}
                    self.assertEqual(next(iter(values)), "stadium")
                    self.assertEqual(values["stadium"], "II" if stage == 2 else "III")
                    self.assertIn(f'class="anp-data-block__rhs">{values["stadium"]}</div>', self.panel.cb.html_sr)
                    self.assertEqual("EI_II" in values, stage == 2)
                    if stage == 2:
                        self.assertTrue({"x", "sigma_c_max", "sigma_s_1", "F_c", "F_s_drag"} <= values.keys())
                        self.assertTrue({"epsilon_c_max", "epsilon_s_1"} <= partial)
                        self.assertEqual("z_II" in values, values["F_s_drag"] > 0)
                    else:
                        self.assertTrue({"x_Rd_verksam", "sigma_s_Rd_1", "F_c_Rd", "F_s_drag_Rd"} <= values.keys())
                        self.assertTrue({"epsilon_c_Rd", "epsilon_s_Rd_1"} <= partial)
                        self.assertEqual("z_Rd" in values, values["F_s_drag_Rd"] > 0)
                        self.assertEqual(values["M_Ed"], moment)
                        self.assertGreater(values["M_Rd"] * moment, 0)
                        self.assertIn("rektangulärt tryckblock", self.panel.cb.html_mb)
                    self.assertFalse(any(name.startswith("epsilon_") for name in values))
                    omitted = {"kappa_II", "M_Rd_min", "M_Rd_max", "inom_kapacitetsintervall", "utnyttjande_M"}
                    self.assertFalse(omitted & (values.keys() | partial))
                    self.assertEqual("h" in self.visible(), geometry != 1)
                    self.assertEqual("b" in self.visible(), geometry != 3)
                    self.assertEqual("n_uk" in self.visible(), geometry != 1)
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

    def test_longitudinal_bars_clear_the_stirrup_in_both_figures(self):
        # Bred balk med grova ÖK-järn som i exemplet där bygeln överlappades.
        self.fields["b"].value = 1000
        self.fields["phi_ok"].value = 34
        for markup in (self.figure(), self.profile()):
            svg = drawing(markup)
            hoop = svg.find(".//*[@data-part='bygel']")
            bars = svg.findall(".//*[@data-part='langsjarn']")
            self.assertEqual(len(bars), 6)
            x, y, w, h, rx, stroke = (float(hoop.get(k)) for k in ("x", "y", "width", "height", "rx", "stroke-width"))
            for bar in bars:
                cx, cy, r = (float(bar.get(k)) for k in ("cx", "cy", "r"))
                self.assertGreaterEqual(cx, x + rx)
                self.assertLessEqual(cx, x + w - rx)
                self.assertGreater(cy - r, y + stroke / 2)
                self.assertLess(cy + r, y + h - stroke / 2)

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
            for wording in ("modellkriterium", "överskrider vald flytgräns", "brottöjningsvillkor"):
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

    def test_no_ultimate_equilibrium_shows_demand_and_warning(self):
        self.fields["stadium"].value = 3
        self.fields["N_d"].value = 1e7
        report = result(self.calculate())
        self.assertEqual(report["stadium"], "III")
        self.assertEqual(report["M_Ed"], self.fields["M"].value)
        self.assertNotIn("M_Rd", report)
        self.assertIn("Ingen admissibel ultimat N-M-profil", self.panel.cb.html_sr)
