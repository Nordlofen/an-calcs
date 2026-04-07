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
    def test_returnerar_standardiserad_details_i_direktformat(self):
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

        ekvationer = details["ekvationer"]
        self.assertEqual(ekvationer["title"], "Ekvationer")
        self.assertGreaterEqual(len(ekvationer["items"]), 11)
        latex_items = {item["latex"] for item in ekvationer["items"]}
        self.assertIn(r"l_1 \geq 2h", latex_items)
        self.assertTrue(any(r"k_{c,90} = \begin{cases}" in latex for latex in latex_items))

    def test_direktformat_beraknar_x_end_och_x_in_lang(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_in")["value"], 30.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef")["value"], 75.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 6750.0))

    def test_direktformat_beraknar_kapacitet_for_dubbelsidigt_understodd_konstruktionsvirke(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "k_c_90")["value"], 1.25))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_c_90_d")["value"], 1.5384615384615383))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "N_c_90_Rd")["value"], 12.980769230769228))

    def test_direktformat_eks_visar_effektiva_indata(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, True]
        )

        indata = details["indata"]
        self.assertTrue(math.isclose(_hamta_post(indata, "k_mod")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(indata, "gamma_M")["value"], 1.0))

    def test_direktformat_last_ar_valfri(self):
        details = upplagstryck_tra(
            [90, 45, 0, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        with self.assertRaises(AssertionError):
            _hamta_post(details["indata"], "N_c_90_Ed")

    def test_mittupplag_kort_format_utan_last(self):
        details = upplagstryck_tra(
            [90, 45, "mittupplag", "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        indata = details["indata"]
        delresultat = details["delresultat"]

        self.assertEqual(_hamta_post(indata, "upplagsplacering")["value"], "mittupplag")
        with self.assertRaises(AssertionError):
            _hamta_post(indata, "a")
        with self.assertRaises(AssertionError):
            _hamta_post(delresultat, "x_end")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_in")["value"], 30.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef")["value"], 105.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 9450.0))

    def test_mittupplag_kort_format_med_last(self):
        details = upplagstryck_tra(
            [90, 45, "mittupplag", "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False, 10.0]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "sigma_c_90_d")["value"], 1.0582010582010581))
        self.assertEqual(_hamta_post(slutresultat, "eta")["value"], "55.026 %")
        self.assertEqual(_hamta_post(slutresultat, "eta")["latex"], r"\mu")
        self.assertEqual(_hamta_post(slutresultat, "eta")["unit"], "")

    def test_mittupplag_redundant_none_plats_utan_last(self):
        details = upplagstryck_tra(
            [90, 45, "mittupplag", None, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "A_ef")["value"], 9450.0))

    def test_mittupplag_redundant_numeriskt_a_ignoreras(self):
        details = upplagstryck_tra(
            [90, 45, "mittupplag", 999, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "A_ef")["value"], 9450.0))

    def test_andupplag_explicit_format(self):
        details = upplagstryck_tra(
            [90, 45, "andupplag", 12, 40, 20, "barverksdel_pa_upplag_enkelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        indata = details["indata"]
        delresultat = details["delresultat"]

        self.assertEqual(_hamta_post(indata, "upplagsplacering")["value"], "andupplag")
        self.assertTrue(math.isclose(_hamta_post(indata, "a")["value"], 12.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 12.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 6930.0))

    def test_andupplag_accepterar_a_none_som_noll(self):
        details = upplagstryck_tra(
            [90, 45, "andupplag", None, "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        indata = details["indata"]
        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(indata, "a")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 6750.0))

    def test_andupplag_accepterar_utelamnat_a_som_noll(self):
        details = upplagstryck_tra(
            [90, 45, "andupplag", "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
        )

        indata = details["indata"]
        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(indata, "a")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "x_end")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "A_ef")["value"], 6750.0))

    def test_andupplag_accepterar_utelamnat_a_med_last(self):
        details = upplagstryck_tra(
            [90, 45, "andupplag", "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False, 10.0]
        )

        indata = details["indata"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(indata, "a")["value"], 0.0))
        self.assertEqual(_hamta_post(slutresultat, "eta")["value"], "77.037 %")
        self.assertEqual(_hamta_post(slutresultat, "eta")["latex"], r"\mu")
        self.assertEqual(_hamta_post(slutresultat, "eta")["unit"], "")

    def test_om_tredje_parametern_ar_text_maste_den_vara_upplagsplacering(self):
        with self.assertRaisesRegex(ValueError, "mittupplag' eller 'andupplag"):
            upplagstryck_tra(
                [90, 45, "okant", "lang", 220, "understodd_barverksdel_dubbelsidig", "konstruktionsvirke", 2.5, 0.8, 1.3, False]
            )

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
        with self.assertRaisesRegex(ValueError, "l_1 >= 2h"):
            upplagstryck_tra(
                [115, 260, 15, 80, 120, "barverksdel_pa_upplag_enkelsidig", "konstruktionsvirke", 3.0, 1.0, 1.25, False]
            )

    def test_limtra_med_l_storre_an_400_faller_tillbaka_till_k_c_90_1_5(self):
        details = upplagstryck_tra(
            [115, 401, 15, "lang", 250, "barverksdel_pa_upplag_enkelsidig", "limtra", 3.0, 1.0, 1.25, False]
        )

        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "k_c_90")["value"], 1.5))

    def test_validerar_antal_inparametrar(self):
        with self.assertRaisesRegex(ValueError, "Stödda format"):
            upplagstryck_tra([90, 45, 0])


if __name__ == "__main__":
    unittest.main()
