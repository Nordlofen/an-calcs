import math
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong.palfundament import print_palsfundament_resultat, tvapalsfundament_teoretiskt_innan_slagning


class TestTvapalsfundamentTeoretiskt(unittest.TestCase):
    def test_bygger_tva_topnoder_och_tva_palnoder(self):
        details = tvapalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [350.0, 0.0, 0.0],
                "d": 1200.0,
                "alpha_target": 58.0,
            }
        )

        nodes = details["geometri"]["nodes"]
        self.assertEqual(set(nodes), {"N1", "N2", "N3", "N4"})
        self.assertEqual(details["geometri"]["members"], [["N1", "N3"], ["N2", "N4"], ["N3", "N4"]])
        self.assertTrue(math.isclose(math.dist(nodes["N3"], nodes["N4"]), 1200.0, abs_tol=1e-9))
        for angle in details["geometri"]["original_angles"].values():
            self.assertTrue(math.isclose(angle, 58.0, abs_tol=1e-9))

    def test_felslagning_origin_och_krafter_redovisas(self):
        details = tvapalsfundament_teoretiskt_innan_slagning(
            {
                "N1": [0.0, 0.0, 0.0],
                "N2": [350.0, 0.0, 0.0],
                "d": 1200.0,
                "alpha_target": 58.0,
                "move_node": "N3",
                "Delta_x": -50.0,
                "Delta_y": -50.0,
                "origin_node": "N3",
                "origin_mode": "original",
                "Rz": 450.0,
            }
        )

        geometri = details["geometri"]
        self.assertTrue(math.isclose(geometri["original_nodes"]["N3"][0], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["original_nodes"]["N3"][1], 0.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["nodes"]["N3"][0], -50.0, abs_tol=1e-9))
        self.assertTrue(math.isclose(geometri["nodes"]["N3"][1], -50.0, abs_tol=1e-9))
        self.assertEqual(details["krafter"]["pile_loads"], {"N3": 450.0, "N4": 450.0})
        self.assertIn("N13", details["krafter"]["global_equilibrium"]["member_forces"])
        self.assertIn("N3", details["krafter"]["member_forces"])

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_palsfundament_resultat(details)
        text = buffer.getvalue()
        self.assertIn("a34", text)
        self.assertIn("a43", text)
        self.assertIn("=== GLOBAL JÄMVIKT (1 kraft per stav) ===", text)
        self.assertIn("=== LOKAL NODJÄMVIKT (pålnoder) ===", text)

    def test_validerar_indata(self):
        with self.assertRaisesRegex(ValueError, "d måste vara större"):
            tvapalsfundament_teoretiskt_innan_slagning(
                {
                    "N1": [0.0, 0.0, 0.0],
                    "N2": [350.0, 0.0, 0.0],
                    "d": 300.0,
                    "alpha_target": 58.0,
                }
            )

        with self.assertRaisesRegex(ValueError, "move_node måste vara"):
            tvapalsfundament_teoretiskt_innan_slagning(
                {
                    "N1": [0.0, 0.0, 0.0],
                    "N2": [350.0, 0.0, 0.0],
                    "d": 1200.0,
                    "alpha_target": 58.0,
                    "move_node": "N5",
                }
            )


if __name__ == "__main__":
    unittest.main()
