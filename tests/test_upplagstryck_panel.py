"""Verifiera upplagsskisser i den faktiska Panel-kedjan."""

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "an-print" / "src"))

from an_calcs.tra import upplagstryck_tra
from an_print import Panel


def _svg(panel, index):
    markup = panel._figure_records[index]["widget"].value
    return ElementTree.fromstring(markup[markup.index("<svg"):markup.index("</svg>") + len("</svg>")])


def _labels(svg):
    return {"".join(text.itertext()) for text in svg.findall("{*}text")}


class TestUpplagstryckPanel(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(Panel._LAST_VALUES.clear)
        self.addCleanup(Panel._LAST_BY_FUNCTION.clear)
        self.state = Path(tmp.name) / "state.json"
        self.panel = Panel(upplagstryck_tra, state_file=self.state)
        self.fields = self.panel._field_widgets

    def test_skissen_foljer_placering_last_och_beraknad_upplagslangd(self):
        for key, value in dict(l=220, h=630, l_1="1300", a=20, b=95.5, N_c_90_Ed="170,5").items():
            self.fields[key].value = value

        for placering, titel, l_ef in (("mittupplag", "Mittupplag", 280), ("andupplag", "Ändupplag", 270)):
            with self.subTest(placering=placering):
                self.fields["upplagsplacering"].value = placering
                figure = _svg(self.panel, 0)
                labels = _labels(figure)
                self.assertEqual(figure.get("aria-label"), titel)
                self.assertIn(f"lef = {l_ef}", labels)
                self.assertIn("b = 95,5", labels)
                self.assertIn("Fc,90,Ed = 170,5 kN", labels)
                self.assertEqual("a = 20" in labels, placering == "andupplag")
                with contextlib.redirect_stdout(io.StringIO()):
                    details = self.panel.calculate()
                self.assertEqual(details, upplagstryck_tra(self.panel.to_px()))
                length = next(post["value"] for post in details["delresultat"]["items"] if post["namn"] == "l_ef")
                self.assertEqual(length, l_ef)

        self.fields["a"].value = 0
        self.fields["l_1"].value = "lang"
        self.fields["N_c_90_Ed"].value = ""
        figure = _svg(self.panel, 0)
        self.assertIn("a = 0 · xend = 0", _labels(figure))
        self.assertIn("l1 = lång", _labels(figure))
        self.assertIn("Fc,90,Ed", _labels(figure))
        self.assertEqual(figure.find(".//*[@data-part='effektiv-langd']").get("x"),
                         figure.find(".//*[@data-part='fysisk-langd']").get("x"))

    def test_upplagsfall_och_skisser_foljer_sparade_indata(self):
        self.assertIsNotNone(_svg(self.panel, 1).find(".//*[@data-part='kontinuerligt-stod']"))
        self.fields["upplagsfall"].value = "barverksdel_pa_upplag_enkelsidig"
        self.fields["upplagsplacering"].value = "andupplag"
        self.fields["a"].value = 45
        self.assertIsNotNone(_svg(self.panel, 1).find(".//*[@data-part='diskret-stod']"))
        self.panel._save_case("Ändupplag")
        Panel._LAST_VALUES.clear()
        Panel._LAST_BY_FUNCTION.clear()

        restored = Panel(upplagstryck_tra, key="Ändupplag", state_file=self.state)
        self.assertEqual(restored.to_px(), self.panel.to_px())
        self.assertIn("xend = 30", _labels(_svg(restored, 0)))
        self.assertIsNotNone(_svg(restored, 1).find(".//*[@data-part='diskret-stod']"))
        self.assertNotIn("<svg", self.state.read_text())
