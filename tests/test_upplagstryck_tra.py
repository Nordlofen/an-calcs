import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.tra.upplagstryck_tra import upplagstryck_tra


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestUpplagstryckTra(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
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
        self.assertTrue(any("SS_EN_1995_1_1" in item["text"] for item in metod["items"]))
        self.assertTrue(any("6.1.5" in item["text"] for item in metod["items"]))

        ekvationer = details["ekvationer"]
        self.assertEqual(ekvationer["title"], "Ekvationer")
        self.assertEqual(len(ekvationer["items"]), 7)
        for post in ekvationer["items"]:
            self.assertEqual(set(post), {"latex", "etikett"})

    def test_beraknar_x_end_och_x_in_lang(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_in")["value"], 30.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 6750.0))

    def test_beraknar_x_end_och_x_in_numeriskt(self):
        details = upplagstryck_tra(
            [90, 45, 12, 40, 30, "barverksdel_pa_upplag_enkelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 12.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_in")["value"], 20.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 6930.0))

    def test_beraknar_kapacitet_for_dubbelsidigt_understodd_konstruktionsvirke(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "k_c_90")["value"], 1.25))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_c_90_d")["value"], 1.5384615384615383))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "N_c_90_Rd")["value"], 12.980769230769228))

    def test_beraknar_kapacitet_for_enkelsidigt_upplag_limtra(self):
        details = upplagstryck_tra(
            [115, 200, 15, 80, 120, "barverksdel_pa_upplag_enkelsidig", "limtra", 3.0, 1.0, 1.25, False]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 15.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_in")["value"], 30.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 28175.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "k_c_90")["value"], 1.75))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "N_c_90_Rd")["value"], 118.335))

    def test_eks_flagga_satter_dimensionerande_hallfasthet_till_karakteristiskt_varde(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, True]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]
        indata = details["indata"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_c_90_d")["value"], 2.5))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "N_c_90_Rd")["value"], 21.09375))
        self.assertTrue(math.isclose(_hamta_post(indata, "k_mod")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(indata, "gamma_M")["value"], 1.0))

    def test_beraknar_kontroll_nar_last_anges(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False, 10.0]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "sigma_c_90_d")["value"], 1.4814814814814814))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "eta")["value"], 0.7703703703703705))
        self.assertTrue(_hamta_post(slutresultat, "kontroll_ok")["value"])

    def test_validerar_l_1(self):
        with self.assertRaisesRegex(ValueError, "l_1 måste vara"):
            upplagstryck_tra(
                [90, 45, 0, "kort", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
            )

    def test_validerar_upplagsfall(self):
        with self.assertRaisesRegex(ValueError, "upplagsfall måste vara"):
            upplagstryck_tra(
                [90, 45, 0, "lang", 220, "okant", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
            )

    def test_validerar_materialtyp(self):
        with self.assertRaisesRegex(ValueError, "materialtyp måste vara"):
            upplagstryck_tra(
                [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "lvl", 2.5, 0.8, 1.3, False]
            )

    def test_validerar_geometri_for_dubbelsidigt_understodd_fall(self):
        with self.assertRaisesRegex(ValueError, "l_1 >= 2h"):
            upplagstryck_tra(
                [90, 45, 0, 300, 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
            )

    def test_validerar_geometri_for_enkelsidigt_upplag(self):
        with self.assertRaisesRegex(ValueError, "l <= 2h"):
            upplagstryck_tra(
                [115, 260, 15, 80, 120, "barverksdel_pa_upplag_enkelsidig", "konstruktionsvirke", 3.0, 1.0, 1.25, False]
            )

    def test_validerar_limtra_langd_for_hogre_k_c_90(self):
        with self.assertRaisesRegex(ValueError, "l <= 400 mm"):
            upplagstryck_tra(
                [115, 401, 15, 80, 250, "barverksdel_pa_upplag_enkelsidig", "limtra", 3.0, 1.0, 1.25, False]
            )

    def test_utelamnad_last_visas_inte_i_indata(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        with self.assertRaises(AssertionError):
            _hamta_post(details["indata"], "N_c_90_Ed")

    def test_validerar_antal_inparametrar(self):
        with self.assertRaisesRegex(ValueError, "11 eller 12 värden"):
            upplagstryck_tra([90, 45, 0])


if __name__ == "__main__":
    unittest.main()
