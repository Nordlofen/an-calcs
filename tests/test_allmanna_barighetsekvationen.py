import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.geo import allmanna_barighetsekvationen


class TestAllmannaBarighetsekvationen(unittest.TestCase):
    def test_funktionen_ar_initierad_men_inte_implementerad(self):
        with self.assertRaisesRegex(NotImplementedError, "inte implementerade annu"):
            allmanna_barighetsekvationen([])


if __name__ == "__main__":
    unittest.main()
