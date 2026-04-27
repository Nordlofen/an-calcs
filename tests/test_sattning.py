import math
import pathlib
import sys
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

    def test_validerar_indata(self):
        with self.assertRaisesRegex(ValueError, "typ måste vara 'PS' eller 'VS'."):
            sattning(["XX", 0.5, [1.0], [10.0], [1.5], 300.0, 2.0, 3.0])

        with self.assertRaisesRegex(ValueError, "För PS måste b2 anges"):
            sattning(["PS", 0.5, [1.0], [10.0], [1.5], 300.0, 2.0, None])

        with self.assertRaisesRegex(ValueError, "samma längd"):
            sattning(["VS", 0.5, [1.0], [10.0, 12.0], [1.5], 300.0, 2.0, None])


if __name__ == "__main__":
    unittest.main()
