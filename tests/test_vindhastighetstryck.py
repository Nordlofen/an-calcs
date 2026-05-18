import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.common import vindhastighetstryck


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestVindhastighetstryck(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = vindhastighetstryck(["II", 10, 24])

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

        ekvationer = details["ekvationer"]
        self.assertEqual(ekvationer["title"], "Ekvationer")
        self.assertTrue(any(r"q_{pk}(z)" in item["latex"] for item in ekvationer["items"]))

    def test_panel_schema_har_ratt_px_ordning_och_default_kan_beraknas(self):
        schema = vindhastighetstryck.panel_schema
        values = {field["name"]: field["default"] for field in schema["fields"]}
        px = [values[name] for name in schema["px"]]

        self.assertEqual(schema["title"], "Vindhastighetstryck")
        self.assertEqual(schema["px"], ["terrangtyp", "z", "v_b"])
        self.assertEqual(len(schema["fields"]), 3)
        self.assertEqual(schema["fields"][0]["type"], "choice")

        details = vindhastighetstryck(px)
        self.assertTrue(math.isclose(_hamta_post(details["slutresultat"], "q_pk")["value"], 0.7779674762229217))

    def test_beraknar_kant_exempel_for_terrangtyp_ii(self):
        details = vindhastighetstryck(["II", 10, 24])

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertEqual({item["namn"] for item in details["indata"]["items"]}, {"terrangtyp", "z", "v_b"})
        self.assertTrue(math.isclose(_hamta_post(delresultat, "z_0")["value"], 0.05))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "z_min")["value"], 2.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "z_eff")["value"], 10.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "z_ref")["value"], 0.05))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "k_p")["value"], 3.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_0")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "q_b")["value"], 0.36))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "q_pk")["value"], 0.7779674762229217))

    def test_k_i_redovisas_inte(self):
        details = vindhastighetstryck(["II", 10, 24])

        for section_namn in ("indata", "delresultat"):
            self.assertNotIn("k_I", {item["namn"] for item in details[section_namn]["items"]})
            self.assertNotIn(r"k_I", {item["latex"] for item in details[section_namn]["items"]})

        self.assertFalse(any("k_I" in item["latex"] for item in details["ekvationer"]["items"]))

    def test_terrangtyper_ger_ratt_z0_och_zmin(self):
        expected = {
            0: (0.003, 1.0),
            "0": (0.003, 1.0),
            "I": (0.01, 1.0),
            "II": (0.05, 2.0),
            "III": (0.30, 5.0),
            "IV": (1.00, 10.0),
        }

        for terrangtyp, (z_0, z_min) in expected.items():
            with self.subTest(terrangtyp=terrangtyp):
                details = vindhastighetstryck([terrangtyp, 20, 24])
                delresultat = details["delresultat"]
                self.assertTrue(math.isclose(_hamta_post(delresultat, "z_0")["value"], z_0))
                self.assertTrue(math.isclose(_hamta_post(delresultat, "z_min")["value"], z_min))

    def test_z_under_zmin_anvander_z_eff(self):
        details = vindhastighetstryck(["IV", 4, 24])

        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "z_eff")["value"], 10.0))

    def test_validerar_terrangtyp(self):
        with self.assertRaisesRegex(ValueError, "terrangtyp måste vara"):
            vindhastighetstryck(["V", 10, 24])

    def test_validerar_z(self):
        with self.assertRaisesRegex(ValueError, "z måste vara > 0"):
            vindhastighetstryck(["II", 0, 24])

    def test_validerar_v_b(self):
        with self.assertRaisesRegex(ValueError, "v_b måste vara > 0"):
            vindhastighetstryck(["II", 10, 0])

    def test_validerar_antal_indata(self):
        with self.assertRaisesRegex(ValueError, "exakt 3"):
            vindhastighetstryck(["II", 10])


if __name__ == "__main__":
    unittest.main()
