import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong import trepalsfundament_teoretiskt_innan_slagning


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
            },
        )
        self.assertEqual(details["geometri"]["nodes"]["N4"], [0.0, 0.0, -1.0])
        self.assertEqual(details["geometri"]["nodes"]["N5"], [2.0, 0.0, -1.0])
        self.assertEqual(details["geometri"]["nodes"]["N6"], [1.0, 2.0, -1.0])
        self.assertEqual(len(details["geometri"]["members"]), 6)

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

    def test_validerar_indata(self):
        with self.assertRaisesRegex(ValueError, "d45 måste vara > 0"):
            trepalsfundament_teoretiskt_innan_slagning(
                [[0, 0, 0], [1, 1, 0], [2, 0, 0], 0, 1, 0, 1, 2, 1]
            )

        with self.assertRaisesRegex(ValueError, "N1 måste innehålla 3 koordinater"):
            trepalsfundament_teoretiskt_innan_slagning(
                [[0, 0], [1, 1, 0], [2, 0, 0], 2, 1, 0, 1, 2, 1]
            )


if __name__ == "__main__":
    unittest.main()
