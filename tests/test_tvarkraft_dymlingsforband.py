import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.tra import tvarkraft_dymlingsforband


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestTvarkraftDymlingsforband(unittest.TestCase):
    def test_returnerar_standardiserad_details_for_spik(self):
        details = tvarkraft_dymlingsforband(
            [
                "spik",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                45,
                95,
                350,
                350,
                0,
                0,
                4.0,
                8.0,
                75.0,
                600.0,
                "slat",
                2,
                4,
                False,
                False,
            ]
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
        self.assertGreaterEqual(len(ekvationer["items"]), 10)

    def test_spik_auto_valjer_8_3_och_redovisar_t_min(self):
        details = tvarkraft_dymlingsforband(
            [
                "spik",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                45,
                95,
                350,
                350,
                0,
                0,
                4.0,
                8.0,
                75.0,
                600.0,
                "slat",
                1,
                1,
                False,
                False,
            ]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]
        self.assertEqual(_hamta_post(delresultat, "normativ_tvarkraftsgren")["value"], "8.3")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "d_eff")["value"], 4.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "t_min_utan_forborrning")["value"], 28.0))
        self.assertEqual(_hamta_post(slutresultat, "brottmod_styrande")["value"], "f")

    def test_traskruv_anvander_deff_0_8d_i_8_7(self):
        details = tvarkraft_dymlingsforband(
            [
                "traskruv",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                40,
                80,
                350,
                350,
                0,
                0,
                8.0,
                12.0,
                120.0,
                50.0,
                800.0,
                False,
                1,
                1,
                False,
                False,
            ]
        )

        delresultat = details["delresultat"]
        self.assertEqual(_hamta_post(delresultat, "normativ_tvarkraftsgren")["value"], "8.7")
        self.assertTrue(math.isclose(_hamta_post(delresultat, "d_eff")["value"], 6.4))

    def test_andtra_reducerar_baddhallfasthet_till_en_tredjedel_for_tra_del(self):
        details = tvarkraft_dymlingsforband(
            [
                "skruv",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                45,
                95,
                350,
                350,
                0,
                0,
                "andtra",
                "sidotra",
                12.0,
                36.0,
                160.0,
                400.0,
                1,
                1,
                False,
                True,
            ]
        )

        fh_1_k = _hamta_post(details["delresultat"], "f_h_1_k")["value"]
        fh_2_k = _hamta_post(details["delresultat"], "f_h_2_k")["value"]
        self.assertTrue(math.isclose(fh_1_k * 2.5, fh_2_k, rel_tol=1e-9))
        self.assertEqual(_hamta_post(details["indata"], "infastning_1")["value"], "andtra")

    def test_fastener_designer_benchmark_for_traskruv_i_andtra(self):
        fu_for_my = 10500.0 / (0.30 * 6.0**2.6)
        details = tvarkraft_dymlingsforband(
            [
                "traskruv",
                "skruvregler",
                "tra-tra",
                "lvl",
                "konstruktionsvirke",
                90,
                45,
                350,
                350,
                0,
                0,
                "sidotra",
                "andtra",
                6.0,
                14.0,
                220.0,
                70.0,
                fu_for_my,
                False,
                6,
                1,
                False,
                True,
            ]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "t_1_eff")["value"], 90.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "t_2_eff")["value"], 130.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_h_1_k")["value"], 26.978, rel_tol=1e-4))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "f_h_2_k")["value"], 10.7912, rel_tol=1e-4))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "M_y_Rk")["value"], 10500.0, rel_tol=1e-9))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_Rk")["value"], 2730.0, rel_tol=1e-9))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "brottmod_a")["value"], 14568.0, rel_tol=1e-3))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "brottmod_b")["value"], 8417.0, rel_tol=1e-3))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "brottmod_c")["value"], 5163.0, rel_tol=1e-3))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "brottmod_d")["value"], 4970.0, rel_tol=1e-3))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "brottmod_f")["value"], 2285.0, rel_tol=1e-3))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_v_Rk_enkel")["value"], 2285.0, rel_tol=1e-3))

    def test_traskruv_med_infastning_sist_i_px_stods(self):
        fu_for_my = 10500.0 / (0.30 * 6.0**2.6)
        details = tvarkraft_dymlingsforband(
            [
                "traskruv",
                "skruvregler",
                "tra-tra",
                "lvl",
                "konstruktionsvirke",
                90,
                45,
                350,
                350,
                0,
                0,
                6.0,
                14.0,
                220.0,
                70.0,
                fu_for_my,
                False,
                6,
                1,
                False,
                True,
                "sidotra",
                "andtra",
            ]
        )

        self.assertEqual(_hamta_post(details["indata"], "infastning_1")["value"], "sidotra")
        self.assertEqual(_hamta_post(details["indata"], "infastning_2")["value"], "andtra")
        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "t_2_eff")["value"], 130.0))

    def test_traskruv_auto_med_slat_hals_och_d_over_6_valjer_skruvgren(self):
        details = tvarkraft_dymlingsforband(
            [
                "traskruv",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                120,
                120,
                350,
                350,
                0,
                0,
                8.0,
                12.0,
                160.0,
                60.0,
                800.0,
                True,
                1,
                1,
                False,
                False,
            ]
        )

        self.assertEqual(_hamta_post(details["delresultat"], "normativ_tvarkraftsgren")["value"], "8.5")

    def test_traskruv_override_spikregler_anvands_aven_for_d_over_6(self):
        details = tvarkraft_dymlingsforband(
            [
                "traskruv",
                "spikregler",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                40,
                120,
                350,
                350,
                0,
                0,
                8.0,
                12.0,
                160.0,
                60.0,
                800.0,
                True,
                1,
                1,
                False,
                False,
            ]
        )

        self.assertEqual(_hamta_post(details["delresultat"], "normativ_tvarkraftsgren")["value"], "8.3")

    def test_skruv_auto_valjer_8_5(self):
        details = tvarkraft_dymlingsforband(
            [
                "skruv",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                45,
                95,
                350,
                350,
                30,
                30,
                12.0,
                36.0,
                160.0,
                400.0,
                2,
                3,
                False,
                True,
            ]
        )

        self.assertEqual(_hamta_post(details["delresultat"], "normativ_tvarkraftsgren")["value"], "8.5")
        self.assertEqual(_hamta_post(details["slutresultat"], "tvarkraftsgren")["value"], "8.5")

    def test_tvarforskjuten_1d_paverkar_effektivt_antal_for_spik(self):
        base_px = [
            "spik",
            "auto",
            "tra-tra",
            "konstruktionsvirke",
            "konstruktionsvirke",
            45,
            95,
            350,
            350,
            0,
            0,
            4.0,
            8.0,
            75.0,
            600.0,
            "slat",
            1,
            4,
            False,
            False,
        ]

        details_rak = tvarkraft_dymlingsforband(base_px)
        details_sicksack = tvarkraft_dymlingsforband(base_px[:-2] + [True, False])

        self.assertTrue(_hamta_post(details_rak["delresultat"], "n_ef_rad")["value"] < 4.0)
        self.assertTrue(math.isclose(_hamta_post(details_sicksack["delresultat"], "n_ef_rad")["value"], 4.0))
        self.assertTrue(
            _hamta_post(details_sicksack["slutresultat"], "F_v_Rk_total")["value"]
            > _hamta_post(details_rak["slutresultat"], "F_v_Rk_total")["value"]
        )

    def test_total_ar_lika_med_enkel_nar_antal_ar_ett(self):
        details = tvarkraft_dymlingsforband(
            [
                "skruv",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                45,
                95,
                350,
                350,
                0,
                0,
                10.0,
                30.0,
                140.0,
                400.0,
                1,
                1,
                False,
                True,
            ]
        )

        enkel = _hamta_post(details["slutresultat"], "F_v_Rk_enkel")["value"]
        total = _hamta_post(details["slutresultat"], "F_v_Rk_total")["value"]
        self.assertTrue(math.isclose(enkel, total))

    def test_beraknar_minimiavstand_for_skruvgren(self):
        details = tvarkraft_dymlingsforband(
            [
                "skruv",
                "auto",
                "tra-tra",
                "konstruktionsvirke",
                "konstruktionsvirke",
                45,
                95,
                350,
                350,
                0,
                0,
                12.0,
                36.0,
                160.0,
                400.0,
                1,
                1,
                False,
                True,
            ]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a1_min")["value"], 60.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a2_min")["value"], 48.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a3_t_min")["value"], 84.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a4_c_min")["value"], 36.0))

    def test_validerar_format_for_spik(self):
        with self.assertRaisesRegex(ValueError, "20 eller 22 värden"):
            tvarkraft_dymlingsforband(["spik"])


if __name__ == "__main__":
    unittest.main()
