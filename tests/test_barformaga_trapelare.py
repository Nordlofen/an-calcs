import pathlib
import sys
import math
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.tra.barformaga_trapelare import barformaga_trapelare


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestBarformagaTrapelare(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = barformaga_trapelare([45, 145, 2, "y", 1.0, 2400, 21, 7400, 0.2, 1.3, 0.8])

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
                self.assertEqual(set(post), {"namn", "latex", "value", "unit", "etikett"})

        metod = details["metodbeskrivning"]
        self.assertEqual(metod["title"], "Metodbeskrivning")
        self.assertTrue(any("SS_EN_1995_1_1" in item["text"] for item in metod["items"]))
        self.assertTrue(any("6.3.2" in item["text"] for item in metod["items"]))
        self.assertTrue(any("axiellt tryckta träpelare" in item["text"] for item in metod["items"]))

        ekvationer = details["ekvationer"]
        self.assertEqual(ekvationer["title"], "Ekvationer")
        self.assertEqual(len(ekvationer["items"]), 10)
        for post in ekvationer["items"]:
            self.assertEqual(set(post), {"latex", "etikett"})

    def test_beraknar_dimensionerande_barformaga_for_styv_axel(self):
        details = barformaga_trapelare([45, 145, 2, "y", 1.0, 2400, 21, 7400, 0.2, 1.3, 0.8])

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertEqual(_hamta_post(details["indata"], "axel")["value"], "styv")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_y")["value"], 2202187.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_z")["value"], 22864687.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A")["value"], 13050.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I")["value"], 2202187.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "i")["value"], 12.99038105676658))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "L_cr")["value"], 2400.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "lambda")["value"], 184.75208614068023))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "lambda_rel")["value"], 3.1328042967065794))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "k")["value"], 5.690511810402261))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "k_c")["value"], 0.09577595395658774))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "N_R_d")["value"], 16.15224626572484))

    def test_validerar_axel(self):
        with self.assertRaisesRegex(ValueError, "axel måste vara"):
            barformaga_trapelare([45, 145, 2, "x", 1.0, 2400, 21, 7400, 0.2, 1.3, 0.8])

    def test_validerar_beta_c(self):
        with self.assertRaisesRegex(ValueError, "beta_c måste vara > 0."):
            barformaga_trapelare([45, 145, 2, "y", 1.0, 2400, 21, 7400, 0.0, 1.3, 0.8])


if __name__ == "__main__":
    unittest.main()
