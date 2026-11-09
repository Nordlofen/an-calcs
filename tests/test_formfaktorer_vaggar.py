import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.common import formfaktorer_vaggar


def _poster(details, section):
    return {item["namn"]: item for item in details[section]["items"]}


class TestFormfaktorerVaggar(unittest.TestCase):
    def test_tabell_1_13_alla_zoner_och_bada_areorna(self):
        # Avlästa tabellrader, i ordningen A10, A1, B10, B1, ..., E10, E1.
        referenser = [
            (0.10, [-1.2, -1.4, -0.8, -1.1, -0.5, -0.5, 0.7, 1.0, -0.3, -0.3]),
            (0.25, [-1.2, -1.4, -0.8, -1.1, -0.5, -0.5, 0.7, 1.0, -0.3, -0.3]),
            (1.00, [-1.2, -1.4, -0.8, -1.1, -0.5, -0.5, 0.8, 1.0, -0.5, -0.5]),
            (5.00, [-1.2, -1.4, -0.8, -1.1, -0.5, -0.5, 0.8, 1.0, -0.7, -0.7]),
        ]
        for h_d, expected in referenser:
            with self.subTest(h_d=h_d):
                sr = _poster(formfaktorer_vaggar([10, 8, 10 * h_d]), "slutresultat")
                names = [f"c_pe_{area}_{zon}" for zon in "ABCDE" for area in (10, 1)]
                self.assertEqual(set(sr), set(names))
                for name, value in zip(names, expected):
                    self.assertAlmostEqual(sr[name]["value"], value, places=14)

    def test_linjar_interpolation_i_bada_intervallen(self):
        # Halva och fjärdedels avståndet mellan avlästa tabellrader.
        for h_d, d_10, e in [(0.4375, 0.725, -0.35), (0.625, 0.75, -0.4),
                            (2.0, 0.8, -0.55), (3.0, 0.8, -0.6)]:
            with self.subTest(h_d=h_d):
                sr = _poster(formfaktorer_vaggar([10, 8, h_d * 10]), "slutresultat")
                self.assertAlmostEqual(sr["c_pe_10_D"]["value"], d_10)
                self.assertEqual(sr["c_pe_1_D"]["value"], 1.0)
                self.assertAlmostEqual(sr["c_pe_10_E"]["value"], e)
                self.assertAlmostEqual(sr["c_pe_1_E"]["value"], e)

    def test_zonlangder_och_granser_enligt_figur_1_6(self):
        # d, b, h, e, (l_A, l_B, l_C), aktiva zoner, geometrifall.
        fall = [
            (20, 10, 10, 10, (2, 8, 10), "A, B, C, D, E", "e < d"),
            (20, 40, 5, 10, (2, 8, 10), "A, B, C, D, E", "e < d"),
            (10, 10, 10, 10, (2, 8, 0), "A, B, D, E", "d <= e < 5d"),
            (10, 30, 20, 30, (6, 4, 0), "A, B, D, E", "d <= e < 5d"),
            (10, 50, 30, 50, (10, 0, 0), "A, D, E", "e >= 5d"),
            (10, 70, 30, 60, (10, 0, 0), "A, D, E", "e >= 5d"),
        ]
        for d, b, h, e, langder, aktiva, zonfall in fall:
            with self.subTest(d=d, b=b, h=h):
                details = formfaktorer_vaggar([d, b, h])
                dr = _poster(details, "delresultat")
                sr = _poster(details, "slutresultat")
                self.assertEqual(dr["e"]["value"], e)
                self.assertEqual(dr["aktiva_zoner"]["value"], aktiva)
                self.assertEqual(dr["zonfall"]["value"], zonfall)
                self.assertEqual(sum(dr[f"l_{zon}"]["value"] for zon in "ABC"), d)
                for zon, langd in zip("ABC", langder):
                    self.assertEqual(dr[f"l_{zon}"]["value"], langd)
                    for area in (10, 1):
                        self.assertEqual("utgår" in sr[f"c_pe_{area}_{zon}"]["etikett"], langd == 0)

    def test_zoner_ar_kontinuerliga_pa_bada_sidor_om_granserna(self):
        # e=10 respektive e=50: pröva strax före/efter d och 5d.
        for b in (9.999999, 10, 10.000001, 49.999999, 50, 50.000001):
            with self.subTest(b=b):
                dr = _poster(formfaktorer_vaggar([10, b, 30]), "delresultat")
                langder = [dr[f"l_{zon}"]["value"] for zon in "ABC"]
                self.assertTrue(all(langd >= 0 for langd in langder))
                self.assertAlmostEqual(sum(langder), 10)
                if b < 10:
                    self.assertGreater(langder[2], 0)
                else:
                    self.assertEqual(langder[2], 0)
                if b < 50:
                    self.assertGreater(langder[1], 0)
                else:
                    self.assertEqual(langder[1], 0)

    def test_geometrisk_skalning_andrar_inte_formfaktorer(self):
        original = formfaktorer_vaggar([20, 10, 10])
        for skala in (0.01, 10, 100):
            details = formfaktorer_vaggar([20 * skala, 10 * skala, 10 * skala])
            self.assertEqual(details["slutresultat"], original["slutresultat"])

    def test_standardiserad_details_och_panel_schema(self):
        schema = formfaktorer_vaggar.panel_schema
        self.assertEqual(schema["px"], ["d", "b", "h"])
        self.assertEqual([f["name"] for f in schema["fields"]], ["d", "b", "h"])
        values = {f["name"]: f["default"] for f in schema["fields"]}
        details = formfaktorer_vaggar([values[name] for name in schema["px"]])
        self.assertEqual(set(details), {"metodbeskrivning", "indata", "delresultat", "slutresultat", "ekvationer"})
        for section in ("indata", "delresultat", "slutresultat"):
            for item in details[section]["items"]:
                self.assertEqual(set(item), {"namn", "latex", "value", "unit", "etikett"})
        self.assertEqual(len(details["slutresultat"]["items"]), 10)
        json.dumps(details, allow_nan=False)
        json.dumps(schema, allow_nan=False)

    def test_godtar_tuple_och_numeriska_strangar(self):
        self.assertEqual(formfaktorer_vaggar(("20", "10", "10")), formfaktorer_vaggar([20, 10, 10]))

    def test_avvisar_ogiltiga_matt(self):
        for index, namn in enumerate(("d", "b", "h")):
            for value in (0, -1, math.inf, -math.inf, math.nan, None, True, False, "fel", [], 10**400):
                with self.subTest(namn=namn, value=value):
                    px = [20, 10, 10]
                    px[index] = value
                    with self.assertRaisesRegex(ValueError, namn):
                        formfaktorer_vaggar(px)

    def test_avvisar_fel_px_format(self):
        for px in (None, "20,10,10", {"d": 20, "b": 10, "h": 10}):
            with self.subTest(px=px), self.assertRaisesRegex(ValueError, "lista eller tuple"):
                formfaktorer_vaggar(px)
        for px in ([], [20, 10], [20, 10, 10, 1]):
            with self.subTest(px=px), self.assertRaisesRegex(ValueError, "exakt 3"):
                formfaktorer_vaggar(px)

    def test_extrapolerar_inte_over_tabellens_intervall(self):
        for px in ([10, 10, 50.00001], [10, 10, 100], [1e-300, 10, 1e300], [1e300, 10, 1e-300]):
            with self.subTest(px=px), self.assertRaisesRegex(ValueError, "h/d"):
                formfaktorer_vaggar(px)


@unittest.skipUnless(importlib.util.find_spec("an_print"), "an-print behövs för integrationstest")
class TestFormfaktorerVaggarPanel(unittest.TestCase):
    def test_calcblock_kan_bygga_alla_fem_redovisningsblock(self):
        from an_print import CalcBlock

        cb = CalcBlock(formfaktorer_vaggar([10, 60, 30]))
        for block in ("MB", "ID", "DR", "EKV", "SR"):
            getattr(cb, block)(visa=False)
            self.assertTrue(getattr(cb, f"latex_{block.lower()}"))
            self.assertTrue(getattr(cb, f"html_{block.lower()}"))
        cb.SR(visa=False, etikett=True)
        self.assertIn("utgår för vald geometri", cb.html_sr)
        self.assertIn(r"c_{pe,10,D}", cb.latex_sr)

    @unittest.skipUnless(importlib.util.find_spec("ipywidgets"), "ipywidgets behövs för Panel")
    def test_panel_beraknar_och_uppdaterar_med_exakt_tre_indata(self):
        from an_print import Panel

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = pathlib.Path(tmpdir) / "panel.json"
            panel = Panel(formfaktorer_vaggar, state_file=state_file)
            for block in panel._block_widgets.values():
                block["visa"].value = False
            self.assertEqual(panel.to_px(), [20, 10, 10])
            self.assertEqual(set(panel._field_widgets), {"d", "b", "h"})
            sr = _poster(panel.calculate(), "slutresultat")
            self.assertAlmostEqual(sr["c_pe_10_D"]["value"], 11 / 15)
            self.assertAlmostEqual(sr["c_pe_10_E"]["value"], -11 / 30)
            panel._field_widgets["h"].value = 60
            sr = _poster(panel.calculate(), "slutresultat")
            self.assertAlmostEqual(sr["c_pe_10_E"]["value"], -0.6)
            panel._field_widgets["b"].value = 120
            dr = _poster(panel.calculate(), "delresultat")
            self.assertEqual(dr["aktiva_zoner"]["value"], "A, D, E")
            panel._field_widgets["d"].value = 0
            with self.assertRaisesRegex(ValueError, "d måste"):
                panel.calculate()
            self.assertFalse(state_file.exists())


if __name__ == "__main__":
    unittest.main()
