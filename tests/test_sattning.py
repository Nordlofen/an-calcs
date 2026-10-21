import math
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.geo import sattning


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestSattning(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = sattning(["PS", 0.5, [1.0], [10.0], [1.5], 300.0, 2.0, 3.0])

        self.assertEqual(
            set(details),
            {
                "metodbeskrivning",
                "indata",
                "delresultat",
                "slutresultat",
                "ekvationer",
            },
        )

        for section_namn in ("indata", "delresultat", "slutresultat"):
            section = details[section_namn]
            self.assertIn("title", section)
            self.assertIsInstance(section["items"], list)
            self.assertTrue(section["items"])
            for post in section["items"]:
                self.assertTrue({"namn", "latex", "value", "unit", "etikett"}.issubset(post))

        self.assertEqual(details["metodbeskrivning"]["title"], "Metodbeskrivning")
        self.assertTrue(any("2:1-metoden" in item["text"] for item in details["metodbeskrivning"]["items"]))
        self.assertEqual(details["ekvationer"]["title"], "Ekvationer")
        for post in details["ekvationer"]["items"]:
            self.assertEqual(set(post), {"latex", "etikett"})

    def test_pelarsula_referensfall(self):
        details = sattning(["PS", 0.5, [1.0, 2.0], [10.0, 20.0], [1.5, 1.25], 300.0, 2.0, 3.0])

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(slutresultat, "s")["value"], 7.227207575033662))
        self.assertEqual(_hamta_post(slutresultat, "s")["unit"], "mm")
        self.assertEqual(_hamta_post(slutresultat, "s")["decimals"], 2)
        self.assertEqual(len(slutresultat["items"]), 1)
        self.assertTrue(math.isclose(_hamta_post(delresultat, "Ed_1")["value"], 6.666666666666667))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "delta_sigma_medel_1")["value"], 35.05827505827506))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_lager_1")["value"], 5.258741258741259))
        self.assertEqual(_hamta_post(delresultat, "antal_delskikt")["value"], 6)
        self.assertEqual(_hamta_post(delresultat, "n_delskikt_1")["value"], 2)

    def test_vaggsula_referensfall(self):
        details = sattning(["VS", 0.5, [1.0, 1.5], [8.0, 12.0], [1.4, 1.2], 150.0, 1.2, None])

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(slutresultat, "s")["value"], 23.560003783330377))
        self.assertEqual(_hamta_post(details["indata"], "F")["unit"], "kN/m")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "delta_sigma_medel_1")["value"], 90.18567639257294))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_lager_1")["value"], 15.782493368700264))
        self.assertEqual(_hamta_post(delresultat, "antal_delskikt")["value"], 5)

    def test_enhetliga_beteckningar_och_enheter(self):
        for typ in ("PS", "VS"):
            details = sattning([typ, .5, [1], [10], [1.5], 300, 2, 3])
            inputs = details["indata"]
            self.assertEqual(_hamta_post(inputs, "b1")["latex"], "b_x")
            self.assertEqual(_hamta_post(inputs, "b2")["latex"], "b_y")
            self.assertEqual(_hamta_post(inputs, "b2")["value"], 3 if typ == "PS" else 1)
            self.assertEqual(_hamta_post(inputs, "F")["unit"], "kN" if typ == "PS" else "kN/m")
            equations = details["ekvationer"]["items"]
            stress = [item for item in equations if item["etikett"].startswith("spänningsökning")]
            self.assertEqual(len(stress), 1)
            self.assertEqual(stress[0]["etikett"], f"spänningsökning för {typ}")
            latex = [item["latex"] for item in equations]
            self.assertEqual(len(latex), len(set(latex)))
            self.assertIn(r"E_{d,kPa} = 1000 E_d", latex)
            self.assertIn(r"s = 1000 s_m", latex)
            self.assertIn(r"\epsilon_i = \frac{\Delta\sigma_i}{E_{d,kPa}}", latex)
            self.assertNotIn("b_1", str(latex))
            self.assertNotIn("b_2", str(latex))

    def test_validerar_indata(self):
        with self.assertRaisesRegex(ValueError, "typ måste vara 'PS' eller 'VS'."):
            sattning(["XX", 0.5, [1.0], [10.0], [1.5], 300.0, 2.0, 3.0])

        with self.assertRaisesRegex(ValueError, "För PS måste by anges"):
            sattning(["PS", 0.5, [1.0], [10.0], [1.5], 300.0, 2.0, None])

        with self.assertRaisesRegex(ValueError, "samma längd"):
            sattning(["VS", 0.5, [1.0], [10.0, 12.0], [1.5], 300.0, 2.0, None])


@unittest.skipUnless(importlib.util.find_spec("an_print") and importlib.util.find_spec("ipywidgets"), "an-print och ipywidgets behövs")
class TestSattningPanel(unittest.TestCase):
    def test_aldre_panelfall_bevarar_matt_och_sattning(self):
        from an_print import Panel

        base = "an_calcs.geo.sattning.sattning"
        original = {"typ": "PS", "t_skikt": .5, "F": 300, "b1": 2, "b2": 3,
                    "jordlager": [{"dz": 1, "Ek": 10, "gamma_m": 1.5}, {"dz": 2, "Ek": 20, "gamma_m": 1.25}]}
        wall = {**original, "typ": "VS", "b2": 4.2}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "state.json"
            contents = json.dumps({base + ":PS": original, base + ":VS": wall})
            path.write_text(contents)
            panel = Panel(sattning, key="PS", state_file=path)
            self.assertEqual(path.read_text(), contents)
            self.assertEqual(panel.to_px(), ["PS", .5, [1, 2], [10, 20], [1.5, 1.25], 300, 2, 3])
            self.assertEqual(_hamta_post(sattning(panel.to_px())["slutresultat"], "s")["value"], 7.227207575033662)
            self.assertIsNone(panel._sections["Beräkningsinställningar"].selected_index)
            self.assertEqual(panel._field_widgets["F"].description, "Resultantlast [kN]")
            panel._case_combo.value = "VS"
            self.assertEqual(panel._field_widgets["F"].description, "Linjelast [kN/m]")
            self.assertTrue(panel._field_widgets["b2"].disabled)
            self.assertEqual(panel.to_px()[-1], 1)
            panel._save_last_values()
            Panel._LAST_VALUES.clear()
            Panel._LAST_BY_FUNCTION.clear()
            loaded = Panel(sattning, key="VS", state_file=path)
            self.assertEqual(loaded.to_px()[-1], 1)
            loaded._field_widgets["typ"].value = "PS"
            self.assertEqual(loaded.to_px()[-1], 4.2)
            loaded._case_combo.value = "PS"
            self.assertEqual(loaded.to_px()[-1], 3)


if __name__ == "__main__":
    unittest.main()
