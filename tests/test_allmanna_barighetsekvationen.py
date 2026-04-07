import pathlib
import sys
import math
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.geo import allmanna_barighetsekvationen


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestAllmannaBarighetsekvationen(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = allmanna_barighetsekvationen(
            [0.8, 1.0, 1, 0.8, 10.2, 0.4, 0.3999, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

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
        self.assertTrue(any("brottgränstillstånd" in item["text"] for item in metod["items"]))
        self.assertTrue(any("ytliga fundament" in item["text"] for item in metod["items"]))

        ekvationer = details["ekvationer"]
        self.assertEqual(ekvationer["title"], "Ekvationer")
        self.assertGreaterEqual(len(ekvationer["items"]), 10)
        for post in ekvationer["items"]:
            self.assertEqual(set(post), {"latex", "etikett"})

    def test_referensfall_for_friktionsjord(self):
        details = allmanna_barighetsekvationen(
            [0.8, 1.0, 1, 0.8, 10.2, 0.4, 0.3999, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "phi_d")["value"], 28.307846294624472))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "EG_k")["value"], 8.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_v")["value"], 326.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "b_ef")["value"], 0.000200000000000089))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "d_c")["value"], 1.7))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_q")["value"], 15.227467114217035))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_c")["value"], 26.414607440205454))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_gamma")["value"], 11.143435669262614))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "xi_q")["value"], 1.7))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "q_bd")["value"], 372.78845314023766))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_bd")["value"], 298.23076251219013))
        self.assertEqual(_hamta_post(slutresultat, "F_bd")["unit"], "kN/m")

    def test_kohesionsjord_anvander_c_prime(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, -0.5, 0.5, 0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1.0, 20.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "phi_d")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_ud")["value"], 15.384615384615383))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "gamma_fri")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_q")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_c")["value"], math.pi + 2.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_gamma")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "q_bd")["value"], 105.33673154405756))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_bd")["value"], 632.0203892643454))
        self.assertEqual(_hamta_post(slutresultat, "F_bd")["unit"], "kN")

    def test_c_prime_har_foretrade_framfor_c_uk(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, -0.5, 0.5, 0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1.0, 20.0, 15.0, 0.0, 0.0, 0.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_ud")["value"], 15.384615384615383))

    def test_anvander_c_uk_nar_c_prime_ar_noll(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, -0.5, 0.5, 0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 15.0, 0.0, 0.0, 0.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_ud")["value"], 10.0))

    def test_langstrackt_fundament_anvander_l_ref_1_och_specialfaktorer(self):
        details = allmanna_barighetsekvationen(
            [0.6, 5.0, 1, 0.5, 0.2, 0.3, 0.05, 0.0, 100.0, 10.0, 0.0, 5.0, 0.0, 1.2, 0.0, 0.0, 19.0, 10.0, 32.0, 1.0, 1.25, 1.5, 1.0, 5.0, 3.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ref")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_c")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_q")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_gamma")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "i_q")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "i_gamma")["value"], 1.0))

    def test_grundvatten_inom_effektiv_bredd_ger_blandad_gamma_fri(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, 0.5, 0.4, 0.2, 0.1, 400.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 18.0, 9.0, 30.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "b_ef")["value"], 1.6))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "gamma_fri")["value"], 11.8125))

    def test_validerar_ogiltig_effektiv_geometri(self):
        with self.assertRaisesRegex(ValueError, "b_ef måste vara > 0."):
            allmanna_barighetsekvationen(
                [0.8, 1.0, 0, 0.8, 10.2, 0.4, 0.4, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
            )

        with self.assertRaisesRegex(ValueError, "l_ef måste vara > 0."):
            allmanna_barighetsekvationen(
                [0.8, 1.0, 0, 0.8, 10.2, 0.4, 0.0, 0.5, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
            )

    def test_validerar_orimliga_indata(self):
        with self.assertRaisesRegex(ValueError, "gamma_Rd måste vara > 0."):
            allmanna_barighetsekvationen(
                [0.8, 1.0, 0, 0.8, 10.2, 0.4, 0.0, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 0.0, 0.0, 0.0]
            )

        with self.assertRaisesRegex(ValueError, "b måste vara <= l_ref."):
            allmanna_barighetsekvationen(
                [1.2, 1.0, 0, 0.8, 10.2, 0.4, 0.0, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
            )


if __name__ == "__main__":
    unittest.main()
