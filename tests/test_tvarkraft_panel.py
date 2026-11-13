"""Integration för Tvärkraft och dess direkta presentationsberoenden."""
import contextlib
import base64
import copy
from importlib.resources import files
import io
import json
import math
import pathlib
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "an-print" / "src"))

from an_calcs.betong import Tvärkraft
from an_print import Panel
from an_print.calcblock import CalcBlock
from ipywidgets import Checkbox


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

    def test_figurer_foljer_metod_och_reduktion_och_innehaller_bilddata(self):
        records = self.panel._figure_records
        self.assertEqual(len(records), 4)
        self.assertIn("anp-panel-illustrated", self.panel._form._dom_classes)
        for record in records:
            spec = record["spec"]
            markup = record["widget"].value
            encoded = re.search(r'data:image/png;base64,([^\"]+)', markup).group(1)
            data = base64.b64decode(encoded)
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(data, files(spec["package"]).joinpath(spec["resource"]).read_bytes())
            self.assertIn(spec["caption"], markup)
            self.assertIn(spec["source"], markup)
            self.assertIn('alt="', markup)
            self.assertNotIn("Layoutskiss", markup)
            self.assertNotIn("<button", markup)
        for method in ("bada", "6.2.2", "6.2.3"):
            for check_load in (False, True):
                for reduction in (False, True):
                    with self.subTest(method=method, check_load=check_load, reduction=reduction):
                        self.w["metod"].value = method
                        self.w["kontrollera_last"].value = check_load
                        self.w["reducera_tvarkraft"].value = reduction
                        expected = {
                            "figures/ec2-figure-6-3.png": method != "6.2.3",
                            "figures/ec2-figure-6-4.png": method != "6.2.3" and check_load and reduction,
                            "figures/ec2-figure-6-5.png": method != "6.2.2",
                            "figures/ec2-figure-6-6.png": method != "6.2.2" and check_load and reduction,
                        }
                        self.assertEqual({r["spec"]["resource"]: r["widget"].layout.display != "none" for r in records}, expected)
                        self.assertEqual({r["spec"]["resource"]: "anp-with-figure" in r["layout"]._dom_classes for r in records}, expected)

    def test_indata_kan_fallas_ihop_utan_att_tappa_varden_eller_berakning(self):
        def contains(root, target):
            return root is target or any(contains(child, target) for child in getattr(root, "children", ()))

        inputs = self.panel._sections["Indata"]
        self.assertEqual(inputs.selected_index, 0)
        self.assertIsNone(self.panel._sections["Beräkningsinställningar"].selected_index)
        self.assertIsNone(self.panel._sections["Redovisning"].selected_index)
        for name in self.visible() - {"cot_theta", "z_auto", "z_manuell", "gamma_c", "gamma_s", "alpha_cc"}:
            self.assertTrue(contains(inputs, self.w[name]), name)
        for record in self.panel._figure_records:
            self.assertTrue(contains(inputs, record["widget"]))
        self.assertFalse(contains(inputs, self.panel._sections["Beräkningsinställningar"]))
        self.assertFalse(contains(inputs, self.panel._sections["Redovisning"]))
        self.assertFalse(contains(inputs, self.panel._button))
        widgets_before = dict(self.w)
        self.w["b_w"].value = 350
        self.w["A_sl"].value = 2500
        before = self.panel.to_px()
        expected = self.calculate()
        inputs.selected_index = None
        self.assertEqual(self.panel.to_px(), before)
        self.assertEqual(self.calculate(), expected)
        inputs.selected_index = 0
        self.assertEqual(self.panel.to_px(), before)
        for name, widget in widgets_before.items():
            self.assertIs(self.w[name], widget)

    def test_figurmetadata_paverkar_inte_px_resultat_eller_sparade_fall(self):
        def legacy(px):
            return Tvärkraft(px)
        legacy.panel_schema = copy.deepcopy(Tvärkraft.panel_schema)
        def remove_figures(sections):
            for section in sections:
                section.pop("figure", None)
                remove_figures(section.get("sections", []))
        remove_figures(legacy.panel_schema["sections"])
        with patch("an_print.panel.files", side_effect=AssertionError("Ingen bild ska läsas")):
            old = Panel(legacy, state_file=pathlib.Path(self.tmp.name) / "old.json")
        self.assertEqual(old._figure_records, [])
        self.assertNotIn("anp-panel-illustrated", old._form._dom_classes)
        self.assertEqual(old.to_px(), self.panel.to_px())
        self.assertEqual(legacy(old.to_px()), Tvärkraft(self.panel.to_px()))
        self.w["kontrollera_last"].value = True
        self.w["reducera_tvarkraft"].value = True
        self.w["m_eff"].value = 2
        self.w["V_Ed"].value = 145
        before = self.panel.to_px()
        self.panel._save_last_values()
        self.assertNotIn("base64", self.state.read_text())
        self.assertNotIn(".png", self.state.read_text())
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(Tvärkraft, state_file=self.state)
        self.assertEqual(restored.to_px(), before)
        self.assertTrue(all(r["widget"].layout.display != "none" for r in restored._figure_records))

    def test_strimlans_knapp_laser_bredd_och_byter_enheter(self):
        self.assertIsInstance(self.w["plattstrimla"], Checkbox)
        self.assertEqual(self.w["plattstrimla"].description, "<i>b</i><span style='vertical-align:sub;font-size:smaller'>w</span>-1m strimla")
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
            self.assertIn("[kN/m]", self.panel._field_rows[name].children[1].value)
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
            self.assertNotIn("kN/m", self.panel._field_rows[name].children[1].value)
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
                        self.assertIn("kN/m", rendered)
                        self.assertNotIn("m-str", rendered)
                        self.assertNotIn(r"\mathrm{kN}", rendered)
                        self.assertNotIn("[kN]", rendered)
                if method != "6.2.3":
                    self.assertIn("kN/m", cb.html_ekv)

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

    def test_cc_val_byter_falt_och_raknar_om_med_bredden(self):
        self.w["n_l"].value = 8
        self.w["A_sl"].value = 1234
        self.w["A_sl_inmatning"].value = "cc"
        self.assertIn(("cc och diameter", "cc"), self.w["A_sl_inmatning"].options)
        self.assertTrue({"cc_l", "phi_l"} <= self.visible())
        self.assertFalse({"n_l", "A_sl"} & self.visible())
        self.w["cc_l"].value = 150
        self.w["phi_l"].value = 20
        self.assertEqual(value(self.calculate(), "n_l"), 3)
        self.w["b_w"].value = 450
        self.assertEqual(value(self.calculate(), "n_l"), 4)
        self.w["plattstrimla"].value = True
        self.assertEqual(value(self.calculate(), "n_l"), 7)
        self.w["plattstrimla"].value = False
        self.assertEqual(value(self.calculate(), "n_l"), 4)
        self.w["metod"].value = "6.2.3"
        self.assertFalse({"A_sl_inmatning", "cc_l", "phi_l", "n_l", "A_sl"} & self.visible())
        self.w["metod"].value = "6.2.2"
        self.assertEqual(self.w["cc_l"].value, 150)
        self.w["A_sl_inmatning"].value = "jarn"
        self.assertNotIn("cc_l", self.visible())
        self.assertEqual(value(self.calculate(), "n_l"), 8)
        self.w["A_sl_inmatning"].value = "area"
        self.assertEqual(value(self.calculate(), "A_sl"), 1234)

    def test_sparat_cc_val_och_rapport_med_antal_och_area(self):
        self.w["A_sl_inmatning"].value = "cc"
        self.w["cc_l"].value = 175
        self.w["phi_l"].value = 16
        self.w["plattstrimla"].value = True
        self.panel._save_last_values()
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(Tvärkraft, state_file=self.state)
        self.assertEqual(restored._field_widgets["A_sl_inmatning"].value, "cc")
        self.assertEqual(restored._field_widgets["cc_l"].value, 175)
        self.assertEqual(restored._field_widgets["phi_l"].value, 16)
        for method in ("bada", "6.2.2", "6.2.3"):
            with self.subTest(method=method):
                restored._field_widgets["metod"].value = method
                details = Tvärkraft(restored.to_px())
                if method != "6.2.3":
                    self.assertEqual(value(details, "n_l"), 6)
                    self.assertAlmostEqual(value(details, "A_sl"), 384 * math.pi)
                cb = CalcBlock(details)
                for block in ("ID", "DR", "EKV"):
                    getattr(cb, block)(visa=False, etikett=True)
                self.assertEqual("cc och diameter" in cb.html_id, method != "6.2.3")
                self.assertEqual("floor" in cb.html_ekv, method != "6.2.3")
                self.assertEqual("avrundning nedåt till heltal" in cb.html_ekv, method != "6.2.3")
                self.assertEqual(r"n_l & = &" in cb.latex_dr, method != "6.2.3")
                self.assertEqual(r"A_{sl} & = &" in cb.latex_dr, method != "6.2.3")

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
        for name in ("metod", "A_sl_inmatning", "n_l", "phi_l", "plattstrimla", "cc_l"):
            fields.pop(name)
        fields.update(cot_theta_min=1.5, cot_theta_max=2, cot_theta=2.5)
        self.state.write_text(json.dumps(old))
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        legacy = Panel(Tvärkraft, state_file=self.state)
        self.assertEqual(legacy._field_widgets["metod"].value, "bada")
        self.assertEqual(legacy._field_widgets["A_sl_inmatning"].value, "area")
        self.assertFalse(legacy._field_widgets["plattstrimla"].value)
        self.assertEqual(legacy._field_widgets["cc_l"].value, 200)
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
