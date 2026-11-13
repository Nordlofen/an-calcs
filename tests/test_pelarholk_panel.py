"""Panel -> Pelarholk -> CalcBlock, figurresurser och sparade fall."""

import base64
import contextlib
from importlib.resources import files
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT.parent / "an-print" / "src")]
from an_calcs.betong import Pelarholk
from an_calcs.betong._pelarholk_skiss import render
from an_print import Panel, CalcBlock


def values(details):
    return {i["namn"]: i["value"] for k in ("indata", "delresultat", "slutresultat") for i in details[k]["items"]}


class TestPelarholkPanel(unittest.TestCase):
    def setUp(self):
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(Panel._LAST_VALUES.clear)
        self.addCleanup(Panel._LAST_BY_FUNCTION.clear)
        self.state = Path(tmp.name)/"state.json"
        self.p = Panel(Pelarholk, state_file=self.state)
        self.w = self.p._field_widgets

    def calculate(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.p.calculate()

    def test_berakning_och_calcblock_bada_lagen(self):
        for wall in ("pelare", "vagg"):
            for free in (True, False):
                self.w["typ"].value = wall
                self.w["fristaende"].value = free
                d = self.calculate()
                r = values(d)
                self.assertAlmostEqual(r["V_Ed_2"], r["F2"])
                self.assertEqual("V_Ed_1" in r, free)
                if free:
                    self.assertAlmostEqual(r["V_Ed_1"], r["F1"])
                self.assertAlmostEqual(r["a_v_2"], 55)
                self.assertEqual("As_req" in r, free)
                cb = CalcBlock(d)
                for block in ("MB", "ID", "DR", "EKV", "SR"):
                    getattr(cb, block)(visa=False)
                    self.assertTrue(getattr(cb, "html_"+block.lower()))
                if wall == "vagg":
                    self.assertIn("kN/m", cb.html_sr)
                if not free:
                    self.assertNotIn("Böjarmering", cb.html_sr)
                json.dumps(d, allow_nan=False)

    def test_aktiva_falt_och_djup(self):
        self.w["typ"].value = "pelare"
        self.w["D"].value = 725
        self.w["typ"].value = "vagg"
        self.assertTrue(self.w["D"].disabled)
        self.assertEqual(self.w["D"].value, 1000)
        self.assertIn("kN/m", self.p._field_rows["Fv"].children[1].value)
        self.w["fristaende"].value = False
        self.w["phi"].value = -1
        self.w["f_yd"].value = 0
        self.assertFalse(self.p._field_is_visible({"visible_if": {"field": "fristaende", "equals": True}}))
        rows = [row for group in self.p._scalar_field_groups for row in group["box"].children]
        for name in ("phi", "f_yd", "c_nom"):
            self.assertNotIn(self.p._field_rows[name], rows)
        self.assertIn(self.p._field_rows["t_p"], rows)
        self.calculate()
        self.w["typ"].value = "pelare"
        self.assertFalse(self.w["D"].disabled)
        self.assertEqual(self.w["D"].value, 725)

    def test_insticksdjup_hjalptext_och_ofullstandigt_resultat(self):
        help_widget = self.p._help_checks[0]["widget"]
        for h, l, error in ((200, 100, True), (200, 240, False), (201, 240, True), (200, 241, False)):
            self.w["h"].value = h
            self.w["l"].value = l
            self.assertEqual("anp-help-error" in help_widget._dom_classes, error)
            d = self.calculate()
            self.assertEqual(values(d)["status_insticksdjup"], "Ej uppfyllt" if error else "Uppfyllt")
            if error:
                self.assertEqual(self.p.cb.latex_dr, "")
                self.assertEqual(self.p.cb.latex_ekv, "")
                self.assertNotIn("F1", values(d))
        self.w["l"].value = 100
        self.p._save_last_values()
        Panel._LAST_VALUES.clear()
        reopened = Panel(Pelarholk, state_file=self.state)
        self.assertIn("anp-help-error", reopened._help_checks[0]["widget"]._dom_classes)

    def test_index_och_aldre_sparade_material(self):
        self.assertIn("<sub>Ed,1</sub>", self.p._field_rows["fristaende"].children[-1].value)
        self.assertIn("<sub>1</sub>", self.p._field_rows["bh"].children[-1].value)
        figure = self.p._figure_records[1]
        self.assertIn("<sub>1</sub>", figure["widget"].value)
        old_values = self.p._collect_values()
        old_values.update(f_cd_ig=35, f_cd_c=22)
        self.p._apply_values(old_values)
        self.p._save_last_values()
        Panel._LAST_VALUES.clear()
        reopened = Panel(Pelarholk, state_file=self.state)
        self.assertNotIn("f_cd_ig", reopened._field_widgets)
        self.assertNotIn("f_cd_c", reopened._field_widgets)
        self.assertEqual(reopened._collect_values()["f_cd_ig"], 35)
        self.assertEqual(reopened._collect_values()["f_cd_c"], 22)
        self.assertEqual(len(reopened.to_px()), 15)

    def test_fem_figurer_med_paketerade_resurser(self):
        self.assertEqual(len(self.p._figure_records), 5)
        for record in self.p._figure_records[1:]:
            spec, markup = record["spec"], record["widget"].value
            encoded = re.search(r'data:image/(?:png|svg\+xml);base64,([^\"]+)', markup).group(1)
            self.assertEqual(base64.b64decode(encoded), files(spec["package"]).joinpath(spec["resource"]).read_bytes())
            self.assertIn(spec["source"], markup)
            self.assertIn("anp-figure-full", record["layout"]._dom_classes)
        for title in ("Friläggning för böjarmering", "Kontaktzoner och tryckspridning", "Lastavstånd för vänstra holkväggen", "EC2 · figur 10.7"):
            self.assertIsNone(self.p._sections[title].layout.display)
            self.p._sections[title].selected_index = 0
        self.assertEqual(self.p._sections["Indata"].selected_index, 0)
        self.assertIsNone(self.p._sections["Beräkningsinställningar"].selected_index)

    def test_bojfigur_visas_endast_for_fristaende_holk(self):
        figure = next(r for r in self.p._figure_records if r["spec"].get("resource") == "figures/pelarholk-bojarmering-kompakt.svg")
        accordion = self.p._sections["Friläggning för böjarmering"]
        section = next(r["widget"] for r in self.p._section_records if accordion in r["widget"].children)
        for free in (True, False, True):
            self.w["fristaende"].value = free
            expected = None if free else "none"
            self.assertEqual(figure["widget"].layout.display, expected)
            self.assertEqual(section.layout.display, expected)

    def test_matt_och_holktyp_uppdaterar_skissen(self):
        figure = self.p._figure_records[0]["widget"]
        original = figure.value
        before = self.p.to_px()
        self.w["bv"].value = 400
        self.assertNotEqual(original, figure.value)
        self.assertIn('data-B="1100"', figure.value)
        self.assertEqual(before, self.p.to_px())
        self.w["fristaende"].value = False
        self.assertIn('data-standalone="false"', figure.value)
        self.assertIn("anslutande platta", figure.value)
        self.w["H"].value = 750
        self.assertIn("H = 750", figure.value)
        sx, sy = re.search(r'data-scale-x="([^"]+)" data-scale-y="([^"]+)"', figure.value).groups()
        self.assertEqual(sx, sy)
        self.w["H"].value = -1
        self.assertIn("Skissen kan inte visas", figure.value)
        self.calculate()  # skissmått blockerar inte beräkningen
        self.w["H"].value = 750
        self.assertIn("<svg", figure.value)

    def test_sparning_atlasning_och_fallbyte_uppdaterar_skissen(self):
        self.w["typ"].value = "pelare"
        self.w["D"].value = 820
        self.w["typ"].value = "vagg"
        self.w["fristaende"].value = False
        self.w["bv"].value = 420
        self.w["H"].value = 700
        self.w["t_ig_b"].value = 55
        self.p._save_last_values()
        previous = self.p._figure_records[0]["widget"].value
        before = self.p.to_px()
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()
        restored = Panel(Pelarholk, state_file=self.state)
        self.assertEqual(restored.to_px(), before)
        self.assertEqual(restored._figure_records[0]["widget"].value, previous)
        restored._field_widgets["typ"].value = "pelare"
        self.assertEqual(restored._field_widgets["D"].value, 820)
        self.assertIn("D = 820", restored._figure_records[0]["widget"].value)
        restored._apply_values({"typ":"pelare", "D":600, "bv":250, "fristaende":True})
        self.assertIn('data-standalone="true"', restored._figure_records[0]["widget"].value)
        self.assertIn('data-B="950"', restored._figure_records[0]["widget"].value)
        self.assertNotIn("base64", self.state.read_text())
        self.assertNotIn("<svg", self.state.read_text())

    def test_bottenigjutning_i_skissen_och_aldre_fall(self):
        figure = self.p._figure_records[0]["widget"]
        previous_geometry = figure.value
        self.w["t_ig_b"].value = 60
        self.assertNotEqual(figure.value, previous_geometry)
        self.assertNotIn('data-dimension="a_v_2"', figure.value)
        self.assertNotIn('data-dimension="t_ig_b"', figure.value)
        distance = self.p._figure_records[3]
        self.assertEqual(distance["spec"]["resource"], "figures/pelarholk-lastavstand.svg")
        for free in (False, True):
            self.w["fristaende"].value = free
            self.assertIsNone(distance["widget"].layout.display)
        self.assertAlmostEqual(values(self.calculate())["a_v_2"], 95)
        # Samma sidofält används vid återläsning, med nya synliga index.
        old = self.p._collect_values()
        old.pop("t_ig_b")
        old.update(bh=470, bv=230)
        self.p._apply_values(old)
        self.p._save_last_values()
        Panel._LAST_VALUES.clear()
        reopened = Panel(Pelarholk, state_file=self.state)
        self.assertEqual(reopened._field_widgets["bh"].value, 470)
        self.assertEqual(reopened._field_widgets["bv"].value, 230)
        self.assertEqual(reopened._field_widgets["t_ig_b"].value, 20)
        self.assertIn('data-B="900"', reopened._figure_records[0]["widget"].value)
        contact = reopened._figure_records[2]
        self.assertEqual(contact["spec"]["resource"], "figures/pelarholk-kontaktzoner.png")
        self.assertEqual(contact["widget"].layout.max_width, "780px")

    def test_skissen_kan_rendereas_utan_panel(self):
        v = {f["name"]: f["default"] for f in Pelarholk.panel_schema["fields"]}
        for key in ("h", "H", "t_ig", "t_ig_b"):
            self.assertIn("Skissen kan inte visas", render({**v, key:float("nan")}))
        self.assertIn("Skissen kan inte visas", render({**v,"H":350}))
        self.assertIn("Skissen kan inte visas", render({**v,"fristaende":False,"t_p":1000}))
        self.assertIn("<svg", render({**v,"fristaende":True,"t_p":None}))


if __name__ == "__main__":
    unittest.main()
