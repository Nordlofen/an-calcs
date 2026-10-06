import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from an_calcs.geo import allmanna_barighetsekvationen, isolering_under_sula


class TestIsoleringUnderSula(unittest.TestCase):
    def values(self, **updates):
        values = {field["name"]: field["default"] for field in isolering_under_sula.panel_schema["fields"]}
        values.update(b=2.0, l=3.0, lang=0, t=0.4, F_vy=600.0, F_vy_bruk=300.0,
                      f_d_brott=200.0, f_d_bruk=80.0)
        values.update(updates)
        return values

    def calculate(self, **updates):
        values = self.values(**updates)
        return isolering_under_sula([values[name] for name in isolering_under_sula.panel_schema["px"]])

    def results(self, details):
        return {item["namn"]: item["value"] for section in ("delresultat", "slutresultat")
                for item in details[section]["items"]}

    def test_centrisk_pelarsula_och_egentyngdsfaktorer(self):
        details = self.calculate()
        r = self.results(details)
        # 2 x 3 x 0.4 m concrete: 60 kN; N_ULS=690 kN, N_SLS=360 kN.
        self.assertEqual(r["isolering_EG_k"], 60)
        self.assertEqual(r["isolering_N_brott"], 690)
        self.assertEqual(r["isolering_N_bruk"], 360)
        self.assertEqual(r["isolering_q_Ed_brott"], 115)
        self.assertEqual(r["isolering_q_Ed_bruk"], 60)
        self.assertAlmostEqual(r["isolering_U_brott"], 0.575)
        self.assertAlmostEqual(r["isolering_U_bruk"], 0.75)

    def test_separata_effektiva_areor_och_tecken_for_moment_och_horisontallast(self):
        r = self.results(self.calculate(e_b_plac=0.1, M_insp_l=69, M_insp_b=69,
                                       F_hb_bruk=36, M_insp_b_bruk=18))
        self.assertAlmostEqual(r["isolering_b_eff_brott"], 1.6)
        self.assertAlmostEqual(r["isolering_l_eff_brott"], 2.8)
        self.assertAlmostEqual(r["isolering_A_eff_brott"], 4.48)
        self.assertAlmostEqual(r["isolering_q_Ed_brott"], 154.01785714285714)
        self.assertAlmostEqual(r["isolering_b_eff_bruk"], 2)
        self.assertAlmostEqual(r["isolering_l_eff_bruk"], 2.9)
        self.assertAlmostEqual(r["isolering_q_Ed_bruk"], 62.06896551724138)

    def test_brottgeometri_och_last_overensstammer_med_jordberakningen(self):
        values = {field["name"]: field["default"] for field in allmanna_barighetsekvationen.panel_schema["fields"]}
        values.update(self.values(e_b_plac=-0.1, e_l_plac=0.1, F_hb=12, F_hl=-8,
                                 M_insp_l=60, M_insp_b=-30, l_h=1.8))
        soil = allmanna_barighetsekvationen([values[name] for name in allmanna_barighetsekvationen.panel_schema["px"]])
        soil_r = {p["namn"]: p["value"] for p in soil["slutresultat"]["items"]}
        insulation = isolering_under_sula([values[name] for name in isolering_under_sula.panel_schema["px"]])
        r = self.results(insulation)
        self.assertEqual(r["isolering_N_brott"], soil_r["F_v"])
        self.assertEqual(r["isolering_b_eff_brott"], soil_r["b_ef"])
        self.assertEqual(r["isolering_l_eff_brott"], soil_r["l_ef"])

    def test_vaggsula_beraknas_pa_en_meters_remsa(self):
        details = self.calculate(b=0.8, l=10, lang=1, F_vy=100, F_vy_bruk=60,
                                 f_d_brott=160, f_d_bruk=100)
        r = self.results(details)
        self.assertEqual(r["isolering_N_brott"], 112)
        self.assertEqual(r["isolering_N_bruk"], 68)
        self.assertAlmostEqual(r["isolering_q_Ed_brott"], 140)
        self.assertAlmostEqual(r["isolering_q_Ed_bruk"], 85)
        other = self.calculate(b=0.8, l=300, lang=1, F_vy=100, F_vy_bruk=60,
                               f_d_brott=160, f_d_bruk=100)
        self.assertEqual(r, self.results(other))
        n = next(p for p in details["delresultat"]["items"] if p["namn"] == "isolering_N_bruk")
        self.assertEqual(n["unit"], "kN/m")

    def test_overlast_returneras_som_utnyttjandegrad_over_ett(self):
        r = self.results(self.calculate(f_d_brott=100, f_d_bruk=30))
        self.assertAlmostEqual(r["isolering_U_brott"], 1.15)
        self.assertEqual(r["isolering_U_bruk"], 2)

    def test_ogiltiga_hallfastheter_och_ofullstandiga_laster(self):
        for name in ("f_d_brott", "f_d_bruk", "b", "l", "t", "l_h", "l_h_bruk"):
            for value in (0, -1, None, True, float("nan"), float("inf")):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    self.calculate(**{name: value})
        for name in ("F_vy_bruk", "M_insp_l_bruk", "e_b_plac"):
            for value in (None, "100", True, float("nan")):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    self.calculate(**{name: value})

    def test_ogiltig_area_eller_lyft_i_endast_bruk_avvisas(self):
        for updates in ({"F_vy_bruk": -60}, {"M_insp_l_bruk": 360}, {"M_insp_b_bruk": 540}):
            with self.subTest(updates=updates), self.assertRaisesRegex(ValueError, "bruk"):
                self.calculate(**updates)
        with self.assertRaisesRegex(ValueError, "brott"):
            self.calculate(M_insp_l=690)

    def test_details_kan_anvandas_for_redovisning(self):
        details = self.calculate()
        self.assertEqual(set(details), {"metodbeskrivning", "indata", "delresultat", "slutresultat", "ekvationer"})
        for section in ("indata", "delresultat", "slutresultat"):
            names = []
            for item in details[section]["items"]:
                self.assertEqual(set(item), {"namn", "latex", "value", "unit", "etikett"})
                self.assertTrue(math.isfinite(item["value"]))
                names.append(item["namn"])
            self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
