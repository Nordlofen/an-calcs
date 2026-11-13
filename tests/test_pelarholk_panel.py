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
                self.assertAlmostEqual(r["V_Ed"], max(r["F1"],r["F2"]) if free else r["F2"])
                self.assertEqual("As_req" in r, free)
                cb = CalcBlock(d)
                for block in ("MB", "ID", "DR", "EKV", "SR"):
                    getattr(cb, block)(visa=False)
                    self.assertTrue(getattr(cb, "html_"+block.lower()))
                if wall == "vagg":
                    self.assertIn("kN/m", cb.html_sr)
                if not free:
                    self.assertIn("Ej beräknad", cb.html_sr)
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

    def test_fyra_figurer_med_paketerade_resurser(self):
        self.assertEqual(len(self.p._figure_records), 4)
        for record in self.p._figure_records[1:]:
            spec, markup = record["spec"], record["widget"].value
            encoded = re.search(r'data:image/png;base64,([^\"]+)', markup).group(1)
            self.assertEqual(base64.b64decode(encoded), files(spec["package"]).joinpath(spec["resource"]).read_bytes())
            self.assertIn(spec["source"], markup)
            self.assertIn("anp-figure-full", record["layout"]._dom_classes)
        for title in ("Friläggning för böjarmering", "Kontaktzoner och tryckspridning", "EC2 · figur 10.7"):
            self.assertIsNone(self.p._sections[title].layout.display)
            self.p._sections[title].selected_index = 0
        self.assertEqual(self.p._sections["Indata"].selected_index, 0)
        self.assertIsNone(self.p._sections["Beräkningsinställningar"].selected_index)

    def test_bojfigur_visas_endast_for_fristaende_holk(self):
        figure = next(r for r in self.p._figure_records if r["spec"].get("resource") == "figures/pelarholk-bojarmering.png")
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

    def test_skissen_kan_rendereas_utan_panel(self):
        v = {f["name"]: f["default"] for f in Pelarholk.panel_schema["fields"]}
        for key in ("h", "H", "t_ig"):
            self.assertIn("Skissen kan inte visas", render({**v, key:float("nan")}))
        self.assertIn("Skissen kan inte visas", render({**v,"H":350}))
        self.assertIn("Skissen kan inte visas", render({**v,"fristaende":False,"t_p":1000}))
        self.assertIn("<svg", render({**v,"fristaende":True,"t_p":None}))


if __name__ == "__main__":
    unittest.main()
