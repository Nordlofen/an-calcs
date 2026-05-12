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
    0.8,
    1.3,
    4.0,
    24.0,
    0.4,
    2.08,
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
        self.assertGreaterEqual(len(details["ekvationer"]["items"]), 20)
        ekvationstexter = {item["latex"] for item in details["ekvationer"]["items"]}
        self.assertNotIn(r"x \geq \max(300, 1.5h)", ekvationstexter)
        self.assertNotIn(r"l_z \geq \max(300, 1.5h)", ekvationstexter)
        self.assertNotIn(r"l_A \geq 0.5h", ekvationstexter)
        self.assertNotIn(r"l_v \geq h", ekvationstexter)
        self.assertNotIn(r"h_{ro}, h_{ru} \geq 0.35h", ekvationstexter)
        self.assertNotIn(r"h_d \leq 0.15h", ekvationstexter)
        self.assertIn(r"\mu_{skruv} = F_{t,90}/F_{ax,Rd}", ekvationstexter)
        self.assertNotIn(r"U_{skruv} = F_{t,90}/F_{ax,Rd}", ekvationstexter)
        self.assertNotIn(r"\mu_{skruv} = F_{t,90}/F_{t,Rd}", ekvationstexter)
        self.assertIn(
            r"I_{y,V} = 2\left(\frac{b_{ef}h_{ro}^3}{12} + b_{ef}h_{ro}(0.5h_{ro}+d/2)^2\right)",
            ekvationstexter,
        )
        self.assertIn(r"\tau_{d2} = \frac{V_d S_y}{I_{y,V} b_{ef}}", ekvationstexter)
        self.assertIn(
            r"I_{y,M} = 2\left(\frac{b h_{ro}^3}{12} + b h_{ro}(0.5h_{ro}+d/2)^2\right)",
            ekvationstexter,
        )
        self.assertIn(r"\sigma_{m,d} = \frac{M_d}{I_{y,M}}\frac{h}{2}", ekvationstexter)
        self.assertIn(r"F_{t,90} = F_{t,90,V} + F_{t,90,M}", ekvationstexter)
        self.assertIn(r"V_d = |q_d(L/2 - x)|", ekvationstexter)
        self.assertNotIn(r"V_d = q_d(L/2 - x)", ekvationstexter)
        self.assertIn(r"\mu_{t,90} = \frac{\sigma_{t,90}}{k_{t,90}f_{t,90,d}}", ekvationstexter)
        self.assertIn(r"f_{v,g,d} = \frac{k_{mod} f_{v,g,k}}{\gamma_m}", ekvationstexter)
        self.assertIn(r"F_{ax,Rd} = \frac{k_{mod}}{\gamma_m}F_{ax,Rk}", ekvationstexter)

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
        with self.assertRaises(AssertionError):
            _hamta_post(slutresultat, "placering_ok")

    def test_beraknar_laster_och_tvarsnitt(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "q_d")["value"], 2.4048))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "V_d")["value"], 3.96792))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "M_d")["value"], 1.298592))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "b_ef")["value"], 30.15))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "S_y")["value"], 132565.78125))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_y_skjuv")["value"], 22931901.5625))
        self.assertEqual(_hamta_post(delresultat, "I_y_skjuv")["latex"], r"I_{y,V}")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "tau_d2")["value"], 0.7607937877))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_v_g_d")["value"], 2.4615384615))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_v")["value"], 0.3090724763))

    def test_beraknar_moment_interaktion_och_drag_vinkelratt_fibrer(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_y_moment")["value"], 34226718.75))
        self.assertEqual(_hamta_post(delresultat, "I_y_moment")["latex"], r"I_{y,M}")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "I_kvot")["value"], 1.1666324281))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "sigma_m_d")["value"], 4.1734973499))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "k_h")["value"], 1.1))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_m_g_d")["value"], 16.2461538462))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_m")["value"], 0.2568914088))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_vm")["value"], 0.5659638851))

        self.assertTrue(math.isclose(_hamta_post(delresultat, "h_r")["value"], 69.75))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_t_90")["value"], 150.25))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_t_90")["value"], 1.5628609769))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "sigma_t_90")["value"], 0.4622994201))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_t_90_d")["value"], 0.2461538462))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_t_90")["value"], 1.8780913940))
        self.assertEqual(_hamta_post(slutresultat, "drag_t_90_ok")["value"], "EJ OK")

    def test_beraknar_skruvforstarkning(self):
        details = haltagning_limtrabalk(EXEMPEL_PX)
        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(details["indata"], "F_ax_Rk")["value"], 2.08))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_Rd")["value"], 1.28))
        with self.assertRaises(AssertionError):
            _hamta_post(delresultat, "F_t_Rd")
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "mu_skruv")["value"], 1.2209851382))
        self.assertEqual(_hamta_post(slutresultat, "forstarkning_ok")["value"], "EJ OK")

    def test_validerar_px_langd(self):
        with self.assertRaisesRegex(ValueError, "kräver 19 värden"):
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

    def test_tvarkraft_anvander_absolutbelopp(self):
        px = list(EXEMPEL_PX)
        px[4] = 3700.0

        details = haltagning_limtrabalk(px)

        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "V_d")["value"], 4.2084))
        self.assertGreater(_hamta_post(details["delresultat"], "tau_d2")["value"], 0)
        self.assertGreater(_hamta_post(details["delresultat"], "F_t_90_V")["value"], 0)
        self.assertGreater(_hamta_post(details["slutresultat"], "mu_v")["value"], 0)

    def test_direkt_tvarkraft_far_anges_negativt(self):
        px = list(EXEMPEL_PX)
        px[7] = True
        px[10] = -5.0
        px[11] = 2.0

        details = haltagning_limtrabalk(px)
        ekvationstexter = {item["latex"] for item in details["ekvationer"]["items"]}

        self.assertTrue(math.isclose(_hamta_post(details["indata"], "V_Ed")["value"], -5.0))
        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "V_d")["value"], 5.0))
        self.assertIn(r"V_d = |V_{Ed}|", ekvationstexter)


if __name__ == "__main__":
    unittest.main()
