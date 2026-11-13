"""Integration för Tvärkraft och dess direkta presentationsberoenden."""
import contextlib
import io
import json
import math
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "an-print" / "src"))

from an_calcs.betong import Tvärkraft
from an_print import Panel
from an_print.calcblock import CalcBlock
from ipywidgets import Checkbox, ToggleButton


def value(details, name):
    return next(i["value"] for section in ("indata", "delresultat", "slutresultat")
                for i in details[section]["items"] if i["namn"] == name)


class TestTvarkraftPanel(unittest.TestCase):
    def setUp(self):
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(Panel._LAST_VALUES.clear)
        self.addCleanup(Panel._LAST_BY_FUNCTION.clear)
        self.state = pathlib.Path(self.tmp.name) / "state.json"
        self.panel = Panel(Tvärkraft, state_file=self.state)
        self.w = self.panel._field_widgets

    def visible(self):
        rows = [row for group in self.panel._scalar_field_groups for row in group["box"].children]
        return {name for name, row in self.panel._field_rows.items() if row in rows}

    def calculate(self):
        # Kör Panel -> Tvärkraft -> CalcBlock utan notebookutskrift i testloggen.
        with contextlib.redirect_stdout(io.StringIO()):
            return self.panel.calculate()

    def test_strimlans_knapp_laser_bredd_och_byter_enheter(self):
        self.assertIsInstance(self.w["plattstrimla"], ToggleButton)
        self.assertEqual(self.w["plattstrimla"].description, "<i>b</i><sub>w</sub>-1m strimla")
        self.assertTrue(self.w["plattstrimla"].description_allow_html)
        self.assertIsInstance(self.w["kontrollera_last"], Checkbox)
        self.w["b_w"].value = 350
        self.w["kontrollera_last"].value = True
        self.w["V_Ed"].value = 123
        self.w["A_sl"].value = 2345
        self.w["plattstrimla"].value = True
        self.assertEqual(self.w["b_w"].value, 1000)
        self.assertTrue(self.w["b_w"].disabled)
        for name in ("N_Ed", "V_Ed"):
            self.assertIn("kN/m-str", self.panel._field_rows[name].children[1].value)
        for name in ("A_sl", "n_l", "A_c", "n_skar"):
            self.assertIn("1 m", self.panel._field_rows[name].children[0].value)
        details = self.calculate()
        self.assertEqual(value(details, "b_w"), 1000)
        self.assertEqual(value(details, "V_Ed"), 123)
        self.assertEqual(value(details, "A_sl"), 2345)
        self.w["plattstrimla"].value = False
        self.assertEqual(self.w["b_w"].value, 350)
        self.assertFalse(self.w["b_w"].disabled)
        for name in ("N_Ed", "V_Ed"):
            self.assertNotIn("m-str", self.panel._field_rows[name].children[1].value)
        self.assertEqual(self.w["V_Ed"].value, 123)
        self.assertEqual(self.w["A_sl"].value, 2345)

    def test_sparat_strimlelage_minns_tidigare_bredd(self):
        self.w["b_w"].value = 350
        self.w["plattstrimla"].value = True
        self.panel._save_last_values()
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(Tvärkraft, state_file=self.state)
        widgets = restored._field_widgets
        self.assertTrue(widgets["plattstrimla"].value)
        self.assertTrue(widgets["b_w"].disabled)
        self.assertEqual(value(Tvärkraft(restored.to_px()), "b_w"), 1000)
        widgets["plattstrimla"].value = False
        self.assertEqual(widgets["b_w"].value, 350)

    def test_strimlans_rapport_visar_kraftenheter_for_varje_metod(self):
        self.w["plattstrimla"].value = True
        self.w["kontrollera_last"].value = True
        self.w["reducera_tvarkraft"].value = True
        self.w["m_eff"].value = 2
        for method in ("bada", "6.2.2", "6.2.3"):
            with self.subTest(method=method):
                self.w["metod"].value = method
                cb = CalcBlock(Tvärkraft(self.panel.to_px()))
                cb.MB(visa=False)
                cb.EKV(visa=False, etikett=True)
                self.assertIn("b_w-1m strimla", cb.html_mb)
                for block in ("ID", "DR", "SR"):
                    getattr(cb, block)(visa=False, etikett=True)
                    for rendered in (getattr(cb, "latex_" + block.lower()), getattr(cb, "html_" + block.lower())):
                        self.assertIn("kN/m-str", rendered)
                        self.assertNotIn(r"\mathrm{kN}", rendered)
                        self.assertNotIn("[kN]", rendered)
                if method != "6.2.3":
                    self.assertIn("kN/m-str", cb.html_ekv)

    def test_metodval_styr_synliga_falt_och_berakning(self):
        self.assertEqual(self.w["metod"].value, "bada")
        self.assertTrue({"A_sl", "phi_w", "cot_theta"} <= self.visible())
        self.w["metod"].value = "6.2.2"
        self.w["s"].value = 0  # dolt, ska inte valideras
        self.assertTrue({"A_sl", "A_sl_inmatning"} <= self.visible())
        self.assertFalse({"phi_w", "n_skar", "s", "f_ywk", "cot_theta", "gamma_s", "z_auto"} & self.visible())
        stirrups = next(r for r in self.panel._section_records if any(f["name"] == "phi_w" for f in r["fields"]))
        self.assertEqual(stirrups["widget"].layout.display, "none")
        self.assertGreater(value(self.calculate(), "V_Rd_c"), 0)
        self.w["s"].value = 200
        self.w["metod"].value = "6.2.3"
        self.w["A_sl"].value = -1  # dolt i detta läge
        self.assertFalse({"A_sl", "n_l", "phi_l", "A_sl_inmatning"} & self.visible())
        self.assertTrue({"phi_w", "cot_theta"} <= self.visible())
        self.assertNotEqual(stirrups["widget"].layout.display, "none")
        self.assertGreater(value(self.calculate(), "V_Rd_s"), 0)

    def test_armeringsval_bevarar_indata_och_anvander_ratt_area(self):
        self.w["A_sl"].value = 1234
        self.w["A_sl_inmatning"].value = "jarn"
        self.w["n_l"].value = 6
        self.w["phi_l"].value = 20
        self.assertTrue({"n_l", "phi_l"} <= self.visible())
        self.assertNotIn("A_sl", self.visible())
        self.assertAlmostEqual(value(self.calculate(), "A_sl"), 600 * math.pi)
        self.w["metod"].value = "6.2.3"
        self.w["metod"].value = "bada"
        self.assertEqual(self.w["A_sl_inmatning"].value, "jarn")
        self.assertEqual(self.w["n_l"].value, 6)
        self.w["A_sl_inmatning"].value = "area"
        self.assertFalse({"n_l", "phi_l"} & self.visible())
        self.assertEqual(value(self.calculate(), "A_sl"), 1234)

    def test_normalkraft_och_reduktion_visar_metodens_kompletteringar(self):
        self.w["N_Ed"].value = 60
        self.w["kontrollera_last"].value = True
        self.w["reducera_tvarkraft"].value = True
        self.w["m_eff"].value = 2
        self.assertFalse(self.w["z_auto"].value)
        self.assertTrue({"A_c", "z_manuell", "m_eff", "a_v"} <= self.visible())
        for method, present, absent in (("6.2.2", {"A_c", "a_v"}, {"z_manuell", "m_eff"}),
                                        ("6.2.3", {"z_manuell", "m_eff", "a_v"}, {"A_c"})):
            self.w["metod"].value = method
            self.assertTrue(present <= self.visible())
            self.assertFalse(absent & self.visible())
            self.calculate()
        self.w["kontrollera_last"].value = False
        self.assertFalse({"V_Ed", "a_v", "m_eff"} & self.visible())
        self.assertFalse(self.w["reducera_tvarkraft"].value)
        self.calculate()

    def test_cot_hjalptext_och_fasta_granser(self):
        row = self.panel._field_rows["cot_theta"]
        self.assertIs(row.children[-2], self.w["cot_theta"])
        help_text = row.children[-1].value
        for text in ("V_Rd,s", "V_Rd,max", "V_Rd,c", "45°", "21,8°", "längdaxel"):
            self.assertIn(text, help_text)
        self.assertNotIn("cot_theta_min", self.w)
        self.assertNotIn("cot_theta_max", self.w)
        for cot in (1, 2.5):
            self.w["cot_theta"].value = cot
            self.calculate()
        for cot in (0.99, 2.51):
            self.w["cot_theta"].value = cot
            with self.assertRaises(ValueError):
                self.calculate()

    def test_sparade_fall_bevarar_nya_val_och_laser_aldre_fall(self):
        self.w["metod"].value = "6.2.2"
        self.w["A_sl_inmatning"].value = "jarn"
        self.w["n_l"].value = 6
        self.panel._save_last_values()
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(Tvärkraft, state_file=self.state)
        self.assertEqual(restored._field_widgets["metod"].value, "6.2.2")
        self.assertEqual(restored._field_widgets["A_sl_inmatning"].value, "jarn")
        self.assertEqual(restored._field_widgets["n_l"].value, 6)
        old = json.loads(self.state.read_text())
        fields = old[self.panel._last_key]
        for name in ("metod", "A_sl_inmatning", "n_l", "phi_l", "plattstrimla"):
            fields.pop(name)
        fields.update(cot_theta_min=1.5, cot_theta_max=2, cot_theta=2.5)
        self.state.write_text(json.dumps(old))
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        legacy = Panel(Tvärkraft, state_file=self.state)
        self.assertEqual(legacy._field_widgets["metod"].value, "bada")
        self.assertEqual(legacy._field_widgets["A_sl_inmatning"].value, "area")
        self.assertFalse(legacy._field_widgets["plattstrimla"].value)
        self.assertGreater(value(Tvärkraft(legacy.to_px()), "V_Rd_s"), 0)

    def test_calcblock_redovisar_korta_vansterled_och_vald_metod(self):
        self.w["kontrollera_last"].value = True
        self.w["reducera_tvarkraft"].value = True
        self.w["m_eff"].value = 2
        self.w["A_sl_inmatning"].value = "jarn"
        for method in ("bada", "6.2.2", "6.2.3"):
            with self.subTest(method=method):
                self.w["metod"].value = method
                cb = CalcBlock(Tvärkraft(self.panel.to_px()))
                for block in ("MB", "ID", "DR", "SR", "EKV"):
                    getattr(cb, block)(visa=False) if block == "MB" else getattr(cb, block)(visa=False, etikett=True)
                for suffix in ("mb", "id", "dr", "sr", "ekv"):
                    self.assertTrue(getattr(cb, "latex_" + suffix))
                    self.assertTrue(getattr(cb, "html_" + suffix))
                    for rendered in (getattr(cb, "latex_" + suffix), getattr(cb, "html_" + suffix)):
                        for obsolete in ("V_Rd_c_last", "V_Rd_s_last", "Rd,c,last", "Rd,s,last", "suffixet 'last'"):
                            self.assertNotIn(obsolete, rendered)
                left = re.findall(r'<div class="anp-eq-block__lhs">(.*?)</div>', cb.html_ekv)
                self.assertTrue(left)
                for text in left:
                    self.assertNotIn("≤", text)
                    self.assertNotIn(r"\leq", text)
                    self.assertNotIn("min,val", text)
                if method != "6.2.2":
                    self.assertIn(r"\cot\theta & = & 2{,}5", cb.latex_ekv)
                self.assertEqual("V_{Rd,c}" in cb.latex_sr, method != "6.2.3")
                self.assertEqual("V_{Rd,s}" in cb.latex_sr, method != "6.2.2")
                for branch, active in (("c", method != "6.2.3"), ("s", method != "6.2.2")):
                    for part in ("reducerad", "oreducerad"):
                        symbol = r"\eta_{\mathrm{" + branch + "." + part + "}}"
                        self.assertEqual(symbol in cb.latex_ekv, active)
                        self.assertEqual(symbol in cb.latex_sr, active)


if __name__ == "__main__":
    unittest.main()
