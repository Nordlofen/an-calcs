import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.tra.haltagning_limtrabalk import haltagning_limtrabalk


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


EXEMPEL_PX = [
    3900,
    45,
    220,
    600,
    300,
    115,
    300,
    False,
    0.84,
    2.0,
    4.0,
    1.3,
    2.5,
    16.2,
    0.2,
    1.3,
    1.2,
    650,
    6,
    200,
    350,
    0.8,
    90,
    True,
]


class TestHaltagningLimtrabalk(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)

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

        self.assertEqual(details["ekvationer"]["title"], "Ekvationer")
        self.assertGreaterEqual(len(details["ekvationer"]["items"]), 25)
        ekvationstexter = {item["latex"] for item in details["ekvationer"]["items"]}
        self.assertNotIn(r"x \geq \max(300, 1.5h)", ekvationstexter)
        self.assertNotIn(r"l_z \geq \max(300, 1.5h)", ekvationstexter)
        self.assertNotIn(r"l_A \geq 0.5h", ekvationstexter)
        self.assertNotIn(r"l_v \geq h", ekvationstexter)
        self.assertNotIn(r"h_{ro}, h_{ru} \geq 0.35h", ekvationstexter)
        self.assertNotIn(r"h_d \leq 0.15h", ekvationstexter)

    def test_beraknar_geometri_och_placeringskrav(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_A")["value"], 242.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_v")["value"], 342.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "h_ro")["value"], 52.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "h_ru")["value"], 52.5))
        with self.assertRaises(AssertionError):
            _hamta_post(delresultat, "krav_x")
        with self.assertRaises(AssertionError):
            _hamta_post(slutresultat, "krav_x")
        self.assertEqual(_hamta_post(slutresultat, "krav_l_A")["value"], "OK")
        self.assertEqual(_hamta_post(slutresultat, "krav_h_ro")["value"], "EJ OK")
        with self.assertRaises(AssertionError):
            _hamta_post(slutresultat, "krav_h_d")
        self.assertEqual(_hamta_post(slutresultat, "placering_ok")["value"], "EJ OK")

    def test_beraknar_laster_och_tvarsnitt_enligt_metod_2(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "q_d")["value"], 2.4048))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "V_d")["value"], 3.96792))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "M_d")["value"], 1.298592))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "b_ef")["value"], 30.15))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "S_y")["value"], 132565.78125))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_y_skjuv")["value"], 22931901.5625))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "tau_d2")["value"], 0.7607937877))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_v")["value"], 0.3043175151))

    def test_beraknar_moment_interaktion_och_drag_vinkelratt_fibrer(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_y_moment")["value"], 34226718.75))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_kvot")["value"], 1.1666324281))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "sigma_m_d")["value"], 4.1734973499))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_m")["value"], 0.2576232932))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_vm")["value"], 0.5619408083))

        self.assertTrue(math.isclose(_hamta_post(delresultat, "h_r")["value"], 69.75))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_t_90")["value"], 150.25))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_t_90")["value"], 1.5628609769))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "sigma_t_90")["value"], 0.4622994201))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_t_90")["value"], 2.3114971003))
        self.assertEqual(_hamta_post(slutresultat, "drag_t_90_ok")["value"], "EJ OK")

    def test_beraknar_skruvforstarkning(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef_skruv")["value"], 147.5))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_ax_k")["value"], 13.9734276906))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_k_Rk")["value"], 9.2748626296))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_t_Rk")["value"], 16.5404853212))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_t_Rd")["value"], 5.7076077721))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "U_skruv")["value"], 0.2738206687))
        self.assertEqual(_hamta_post(slutresultat, "forstarkning_ok")["value"], "OK")

    def test_validerar_px_langd(self):
        with self.assertRaisesRegex(ValueError, "kräver 24 värden"):
            haltagning_limtrabalk(EXEMPEL_PX[:-1])

    def test_direkta_snittkrafter_skippar_lastindata_och_q_d(self):
        px = list(EXEMPEL_PX)
        px[7] = True
        px[10] = 5.0
        px[11] = 2.0

        details = haltagning_limtrabalk(px)

        self.assertEqual(_hamta_post(details["indata"], "anvand_direkta_snittkrafter")["value"], True)
        self.assertTrue(math.isclose(_hamta_post(details["indata"], "V_Ed")["value"], 5.0))
        self.assertTrue(math.isclose(_hamta_post(details["indata"], "M_Ed")["value"], 2.0))
        with self.assertRaises(AssertionError):
            _hamta_post(details["indata"], "E_g")
        with self.assertRaises(AssertionError):
            _hamta_post(details["delresultat"], "q_d")
        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "V_d")["value"], 5.0))
        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "M_d")["value"], 2.0))


if __name__ == "__main__":
    unittest.main()
