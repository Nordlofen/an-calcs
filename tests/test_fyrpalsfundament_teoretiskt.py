import math
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong import (
    fyrpalsfundament_teoretiskt_innan_slagning,
    print_palsfundament_resultat,
    trepalsfundament_teoretiskt_innan_slagning,
)


class TestFyrpalsfundamentTeoretiskt(unittest.TestCase):
    def test_optimerar_kvadratisk_bottengeometri_med_lika_sidavstand(self):
        details = fyrpalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1000.0, 0.0, 0.0],
                "N3": [1000.0, 1000.0, 0.0],
                "N4": [0.0, 1000.0, 0.0],
                "d56": 1200.0,
                "alpha_target": 58.0,
            }
        )

        original_nodes = details["geometri"]["original_nodes"]
        for a, b in (("N5", "N6"), ("N6", "N7"), ("N7", "N8"), ("N8", "N5")):
            distance = math.dist(original_nodes[a], original_nodes[b])
            self.assertTrue(math.isclose(distance, 1200.0, abs_tol=1e-6))

        for angle in details["geometri"]["original_angles"].values():
            self.assertTrue(math.isclose(angle, 58.0, abs_tol=1e-4))

    def test_felslagning_och_krafter_redovisas(self):
        details = fyrpalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1000.0, 0.0, 0.0],
                "N3": [1000.0, 1000.0, 0.0],
                "N4": [0.0, 1000.0, 0.0],
                "d56": 1200.0,
                "alpha_target": 58.0,
                "move_node": "N5",
                "Delta_x": -50.0,
                "Delta_y": 0.0,
                "Rz": 1000.0,
            }
        )

        self.assertEqual(details["geometri"]["move_node"], "N5")
        self.assertEqual(details["krafter"]["pile_loads"], {"N5": 1000.0, "N6": 1000.0, "N7": 1000.0, "N8": 1000.0})
        self.assertIn("N15", details["krafter"]["global_equilibrium"]["member_forces"])
        self.assertIn("N5", details["krafter"]["member_forces"])

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_palsfundament_resultat(details)
        text = buffer.getvalue()
        self.assertIn("=== GLOBAL JÄMVIKT (1 kraft per stav) ===", text)
        self.assertIn("=== LOKAL NODJÄMVIKT (pålnoder) ===", text)
        self.assertIn("N5:", text)

    def test_origin_node_flyttar_redovisad_geometri_till_plan_origo(self):
        details = fyrpalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1000.0, 0.0, 0.0],
                "N3": [1000.0, 1000.0, 0.0],
                "N4": [0.0, 1000.0, 0.0],
                "d56": 1200.0,
                "alpha_target": 58.0,
                "origin_node": "N5",
            }
        )

        geometri = details["geometri"]
        self.assertTrue(math.isclose(geometri["nodes"]["N5"][0], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["nodes"]["N5"][1], 0.0, abs_tol=1e-9))
        self.assertEqual(geometri["origin_node"], "N5")

    def test_origin_mode_original_anvander_teoretisk_position_som_origo(self):
        details = fyrpalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1000.0, 0.0, 0.0],
                "N3": [1000.0, 1000.0, 0.0],
                "N4": [0.0, 1000.0, 0.0],
                "d56": 1200.0,
                "alpha_target": 58.0,
                "move_node": "N5",
                "Delta_x": -50.0,
                "Delta_y": 0.0,
                "origin_node": "N5",
                "origin_mode": "original",
            }
        )

        geometri = details["geometri"]
        self.assertTrue(math.isclose(geometri["original_nodes"]["N5"][0], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["original_nodes"]["N5"][1], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["nodes"]["N5"][0], -50.0, abs_tol=1e-6))
        self.assertTrue(math.isclose(geometri["nodes"]["N5"][1], 0.0, abs_tol=1e-6))

    def test_gemensam_formatter_fungerar_for_3_och_4_palar(self):
        details_3p = trepalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [100.0, 200.0, 0.0],
                "N3": [200.0, 0.0, 0.0],
                "d45": 1080.0,
                "alpha_target": 58.0,
                "Rz": 1000.0,
            }
        )
        details_4p = fyrpalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [1000.0, 0.0, 0.0],
                "N3": [1000.0, 1000.0, 0.0],
                "N4": [0.0, 1000.0, 0.0],
                "d56": 1200.0,
                "alpha_target": 58.0,
                "Rz": 1000.0,
            }
        )

        buffer_3p = StringIO()
        with redirect_stdout(buffer_3p):
            print_palsfundament_resultat(details_3p)
        buffer_4p = StringIO()
        with redirect_stdout(buffer_4p):
            print_palsfundament_resultat(details_4p)

        self.assertIn("a45", buffer_3p.getvalue())
        self.assertIn("a56", buffer_4p.getvalue())


if __name__ == "__main__":
    unittest.main()
