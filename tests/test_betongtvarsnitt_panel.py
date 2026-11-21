"""Betongtvärsnitt via den faktiska Panel- och CalcBlock-kedjan."""

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "an-print" / "src"))

from an_calcs.betong import betongtvarsnitt, bojstyvhet_betongpalar
from an_print import Panel
from an_print.calcblock import CalcBlock


def result(details):
    return {item["namn"]: item["value"] for item in details["slutresultat"]["items"]}


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

    def test_three_geometries_and_both_stages_and_concrete_models(self):
        for geometry, width, height, force, moment in (
            (1, 235, 600, 700, 30), (2, 300, 600, 200, 100), (3, 1000, 260, 0, -50),
        ):
            for key, value in dict(geometri=geometry, b=width, h=height, N_d=force, M=moment).items():
                self.fields[key].value = value
            for stage, model in ((2, "rektangel"), (3, "rektangel"), (3, "parabel")):
                with self.subTest(geometry=geometry, stage=stage, model=model):
                    self.fields["stadium"].value = stage
                    self.fields["tryckblock"].value = model
                    report = self.calculate()
                    self.assertIsInstance(self.panel.cb, CalcBlock)
                    values = result(report)
                    self.assertEqual("EI_II" in values, stage == 2)
                    if stage == 3:
                        self.assertEqual(values["kapacitetsjamvikt"], 1)
                        self.assertLess(values["M_Rd_min"], values["M_Rd_max"])
                    self.assertEqual("h" in self.visible(), geometry != 1)
                    self.assertEqual("n_uk" in self.visible(), geometry != 1)
                    self.assertEqual("phi_h" in self.visible(), geometry == 1)
                    self.assertEqual("phi_b" in self.visible(), geometry != 3)
                    self.assertEqual("E_cd" in self.visible(), stage == 2)
                    self.assertEqual("f_cd" in self.visible(), stage == 3)
                    self.assertNotIn("pal_EI", values)
                    self.assertNotIn("K_c_override", self.fields)

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
        self.fields["tryckblock"].value = "parabel"
        self.panel._save_case("Balk 1")
        px = self.panel.to_px()
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(betongtvarsnitt, key="Balk 1", state_file=self.state)
        self.assertEqual(restored.to_px(), px)
        self.assertEqual(restored._figure_records[0]["widget"].value, self.figure())
        self.assertEqual(self.calculate(restored), self.calculate())

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
