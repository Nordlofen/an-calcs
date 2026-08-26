import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong.palfundament import print_palsfundament_resultat, tvapalsfundament_inmätning_efter_slagning


class TestTvapalsfundamentInmatningEfterSlagning(unittest.TestCase):
    def test_bygger_inmatt_tva_palsmodell(self):
        details = tvapalsfundament_inmätning_efter_slagning(
            {
                "h": 650.0,
                "N1_xy": [310.0, 130.0],
                "N2_xy": [410.0, 180.0],
                "N4_xy": [0.0, 0.0],
                "N5_xy": [730.0, 110.0],
                "theo_piles_xy": [[0.0, 0.0], [980.0, 0.0]],
                "Rz": 1100.0,
            }
        )

        self.assertEqual(set(details["geometri"]["nodes"]), {"N1", "N2", "N4", "N5"})
        self.assertEqual(details["geometri"]["members"], [["N1", "N4"], ["N2", "N5"], ["N4", "N5"]])
        self.assertEqual(details["geometri"]["nodes"]["N4"], [0.0, 0.0, -650.0])
        self.assertEqual(details["geometri"]["nodes"]["N5"], [730.0, 110.0, -650.0])
        self.assertEqual(details["geometri"]["theoretical_piles_xy"], [[0.0, 0.0], [980.0, 0.0]])
        self.assertIn("a45", details["geometri"]["angles"])
        self.assertIn("a54", details["geometri"]["angles"])
        self.assertEqual(details["krafter"]["pile_loads"], {"N4": 1100.0, "N5": 1100.0})
        self.assertIn("N14", details["krafter"]["global_equilibrium"]["member_forces"])
        self.assertIn("N4", details["krafter"]["member_forces"])

    def test_printar_med_gemensam_formatter(self):
        details = tvapalsfundament_inmätning_efter_slagning(
            {
                "h": 650.0,
                "N1_xy": (310.0, 130.0),
                "N2_xy": (410.0, 180.0),
                "N4_xy": (0.0, 0.0),
                "N5_xy": (730.0, 110.0),
                "Rz": 1100.0,
            }
        )

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_palsfundament_resultat(details)
        text = buffer.getvalue()
        self.assertIn("a45", text)
        self.assertIn("a54", text)
        self.assertIn("α14", text)
        self.assertIn("α25", text)
        self.assertIn("=== GLOBAL JÄMVIKT (1 kraft per stav) ===", text)
        self.assertIn("=== LOKAL NODJÄMVIKT (pålnoder) ===", text)

    def test_validerar_indata(self):
        with self.assertRaisesRegex(ValueError, "px saknar värden"):
            tvapalsfundament_inmätning_efter_slagning({"h": 650.0})

        with self.assertRaisesRegex(ValueError, "h måste vara > 0"):
            tvapalsfundament_inmätning_efter_slagning(
                {
                    "h": 0.0,
                    "N1_xy": [310.0, 130.0],
                    "N2_xy": [410.0, 180.0],
                    "N4_xy": [0.0, 0.0],
                    "N5_xy": [730.0, 110.0],
                }
            )


if __name__ == "__main__":
    unittest.main()
