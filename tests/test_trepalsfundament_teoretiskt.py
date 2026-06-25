import math
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong.palfundament import print_palsfundament_resultat, trepalsfundament_teoretiskt_innan_slagning


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestTrepalsfundamentTeoretiskt(unittest.TestCase):
    def test_returnerar_details_och_geometri(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            [
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [2.0, 0.0, 0.0],
                2.0,
                1.0,
                0.0,
                1.0,
                2.0,
                1.0,
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
                "geometri",
                "krafter",
            },
        )
        self.assertEqual(details["geometri"]["nodes"]["N4"], [0.0, 0.0, -1.0])
        self.assertEqual(details["geometri"]["nodes"]["N5"], [2.0, 0.0, -1.0])
        self.assertEqual(details["geometri"]["nodes"]["N6"], [1.0, 2.0, -1.0])
        self.assertEqual(len(details["geometri"]["members"]), 6)
        self.assertEqual(_hamta_post(details["indata"], "N1")["unit"], "mm")
        self.assertEqual(_hamta_post(details["indata"], "d45")["unit"], "mm")
        self.assertEqual(_hamta_post(details["delresultat"], "N4")["unit"], "mm")

    def test_beraknar_vinklar(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1.0, 1.0, 0.0],
                "N3": [2.0, 0.0, 0.0],
                "d45": 2.0,
                "x_mid": 1.0,
                "y0": 0.0,
                "x6": 1.0,
                "y6": 2.0,
                "h": 1.0,
            }
        )

        slutresultat = details["slutresultat"]
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "a45")["value"], 90.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "a54")["value"], 90.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "a64")["value"], 50.768479516407744))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "a65")["value"], 50.768479516407744))

    def test_felslagning_flyttar_vald_bottennod_och_beraknar_delta(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1.0, 1.0, 0.0],
                "N3": [2.0, 0.0, 0.0],
                "d45": 2.0,
                "x_mid": 1.0,
                "y0": 0.0,
                "x6": 1.0,
                "y6": 2.0,
                "h": 1.0,
                "move_node": "N4",
                "delta_x": -0.1,
                "delta_y": 0.2,
            }
        )

        geometri = details["geometri"]
        self.assertEqual(geometri["original_nodes"]["N4"], [0.0, 0.0, -1.0])
        self.assertEqual(geometri["nodes"]["N4"], [-0.1, 0.2, -1.0])
        self.assertEqual(geometri["move_node"], "N4")
        self.assertTrue(geometri["angle_deltas"]["a45"] != 0.0)
        self.assertTrue(math.isclose(_hamta_post(details["slutresultat"], "da45")["value"], geometri["angle_deltas"]["a45"]))

    def test_origin_node_flyttar_redovisad_geometri_till_plan_origo(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [100.0, 200.0, 0.0],
                "N3": [200.0, 0.0, 0.0],
                "d45": 1080.0,
                "alpha_target": 58.0,
                "move_node": "N4",
                "Delta_x": -100.0,
                "Delta_y": 0.0,
                "origin_node": "N4",
            }
        )

        geometri = details["geometri"]
        self.assertTrue(math.isclose(geometri["nodes"]["N4"][0], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["nodes"]["N4"][1], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["original_nodes"]["N4"][0], 100.0, abs_tol=1e-6))
        self.assertTrue(math.isclose(geometri["original_nodes"]["N4"][1], 0.0, abs_tol=1e-6))

    def test_origin_mode_original_anvander_teoretisk_position_som_origo(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [100.0, 200.0, 0.0],
                "N3": [200.0, 0.0, 0.0],
                "d45": 1080.0,
                "alpha_target": 58.0,
                "move_node": "N4",
                "Delta_x": -100.0,
                "Delta_y": 0.0,
                "origin_node": "N4",
                "origin_mode": "original",
            }
        )

        geometri = details["geometri"]
        self.assertTrue(math.isclose(geometri["original_nodes"]["N4"][0], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["original_nodes"]["N4"][1], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["nodes"]["N4"][0], -100.0, abs_tol=1e-6))
        self.assertTrue(math.isclose(geometri["nodes"]["N4"][1], 0.0, abs_tol=1e-6))

    def test_optimerar_bottennoder_fran_topnoder_malvinkel_och_d45(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [100.0, 200.0, 0.0],
                "N3": [200.0, 0.0, 0.0],
                "d45": 1080.0,
                "alpha_target": 58.0,
                "move_node": "N4",
                "Delta_x": -100.0,
                "Delta_y": 0.0,
            }
        )

        geometri = details["geometri"]
        original_angles = geometri["original_angles"]
        self.assertEqual(_hamta_post(details["indata"], "d45")["unit"], "mm")
        self.assertEqual(_hamta_post(details["indata"], "alpha_target")["value"], 58.0)
        self.assertLess(geometri["opt_error"], 1e-8)
        for angle in original_angles.values():
            self.assertTrue(math.isclose(angle, 58.0, abs_tol=1e-4))
        self.assertTrue(math.isclose(geometri["angles"]["a45"], 52.515938496025086, abs_tol=1e-4))
        self.assertTrue(math.isclose(geometri["angle_deltas"]["a45"], -5.484061503986531, abs_tol=1e-4))

    def test_beraknar_stavkrafter_nar_palaster_anges(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [100.0, 200.0, 0.0],
                "N3": [200.0, 0.0, 0.0],
                "d45": 1080.0,
                "alpha_target": 58.0,
                "Rz": 1000.0,
            }
        )

        forces = details["krafter"]["member_forces"]
        global_equilibrium = details["krafter"]["global_equilibrium"]
        self.assertEqual(details["krafter"]["pile_loads"], {"N4": 1000.0, "N5": 1000.0, "N6": 1000.0})
        self.assertLess(forces["N4"]["N1-N4"], 0.0)
        self.assertLess(forces["N5"]["N3-N5"], 0.0)
        self.assertLess(forces["N6"]["N2-N6"], 0.0)
        self.assertGreater(forces["N4"]["N4-N5"], 0.0)
        self.assertIn("N45", global_equilibrium["member_forces"])
        self.assertIn("R1z", global_equilibrium["top_reactions"])
        self.assertEqual(_hamta_post(details["slutresultat"], "N1-N4")["unit"], "kN")

    def test_formaterar_printtext(self):
        details = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [100.0, 200.0, 0.0],
                "N3": [200.0, 0.0, 0.0],
                "d45": 1080.0,
                "alpha_target": 58.0,
                "Rz": 1000.0,
            }
        )

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_palsfundament_resultat(details)
        text = buffer.getvalue()
        self.assertIn("=== VINKLAR mellan sträva och dragband  ===", text)
        self.assertIn("=== STRÄVOR: VINKEL MOT HORISONTALPLAN (xy) ===", text)
        self.assertIn("=== GLOBAL JÄMVIKT (1 kraft per stav) ===", text)
        self.assertIn("=== LOKAL NODJÄMVIKT (pålnoder) ===", text)
        self.assertIn("Rz per påle = 1000.0", text)
        self.assertIn("residual-norm", text)
        self.assertIn("N4:", text)
        self.assertIn("N1-N4:", text)

    def test_validerar_indata(self):
        with self.assertRaisesRegex(ValueError, "d45 måste vara > 0"):
            trepalsfundament_teoretiskt_innan_slagning(
                [[0, 0, 0], [1, 1, 0], [2, 0, 0], 0, 1, 0, 1, 2, 1]
            )

        with self.assertRaisesRegex(ValueError, "N1 måste innehålla 3 koordinater"):
            trepalsfundament_teoretiskt_innan_slagning(
                [[0, 0], [1, 1, 0], [2, 0, 0], 2, 1, 0, 1, 2, 1]
            )

        with self.assertRaisesRegex(ValueError, "move_node måste vara"):
            trepalsfundament_teoretiskt_innan_slagning(
                [[0, 0, 0], [1, 1, 0], [2, 0, 0], 2, 1, 0, 1, 2, 1, "N1", 0.1, 0.0]
            )


if __name__ == "__main__":
    unittest.main()
