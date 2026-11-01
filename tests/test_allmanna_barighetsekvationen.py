import pathlib
import sys
import math
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.geo import allmanna_barighetsekvationen


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


class TestAllmannaBarighetsekvationen(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = allmanna_barighetsekvationen(
            [0.8, 1.0, 1, 0.8, 10.2, 0.4, 0.3999, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
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

        metod = details["metodbeskrivning"]
        self.assertEqual(metod["title"], "Metodbeskrivning")
        self.assertTrue(any("brottgränstillstånd" in item["text"] for item in metod["items"]))
        self.assertTrue(any("ytliga fundament" in item["text"] for item in metod["items"]))

        ekvationer = details["ekvationer"]
        self.assertEqual(ekvationer["title"], "Ekvationer")
        self.assertGreaterEqual(len(ekvationer["items"]), 10)
        for post in ekvationer["items"]:
            self.assertEqual(set(post), {"latex", "etikett"})

    def test_referensfall_for_friktionsjord(self):
        details = allmanna_barighetsekvationen(
            [0.8, 1.0, 1, 0.8, 10.2, 0.4, 0.3999, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "phi_d")["value"], 28.307846294624472))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "EG_k")["value"], 8.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_v")["value"], 326.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "b_ef")["value"], 0.000200000000000089))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "d_c")["value"], 1.7))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_q")["value"], 15.227467114217035))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_c")["value"], 26.414607440205454))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_gamma")["value"], 11.143435669262614))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "xi_q")["value"], 1.7))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "EG_k")["value"], 8.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_v")["value"], 326.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "b_ef")["value"], 0.000200000000000089))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "q_bd")["value"], 372.78845314023766))
        # The nearly exhausted effective width, rather than the full 0.8 m,
        # carries the per-metre resistance. q_bd itself is unchanged.
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_bd")["value"], 0.07455769062808072))
        self.assertEqual(_hamta_post(slutresultat, "F_bd")["unit"], "kN/m")
        with self.assertRaises(AssertionError):
            _hamta_post(slutresultat, "l_ef")

    def test_kohesionsjord_anvander_c_prime(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, -0.5, 0.5, 0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1.0, 20.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        slutresultat = details["slutresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "phi_d")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_ud")["value"], 15.384615384615383))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "gamma_fri")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_q")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_c")["value"], math.pi + 2.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "N_gamma")["value"], 0.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "EG_k")["value"], 75.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_v")["value"], 612.5))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "b_ef")["value"], 2.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "l_ef")["value"], 3.0))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "q_bd")["value"], 105.33673154405756))
        self.assertTrue(math.isclose(_hamta_post(slutresultat, "F_bd")["value"], 632.0203892643454))
        self.assertEqual(_hamta_post(slutresultat, "F_bd")["unit"], "kN")

    def test_c_prime_har_foretrade_framfor_c_uk(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, -0.5, 0.5, 0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1.0, 20.0, 15.0, 0.0, 0.0, 0.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_ud")["value"], 15.384615384615383))

    def test_anvander_c_uk_nar_c_prime_ar_noll(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, -0.5, 0.5, 0.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 15.0, 0.0, 0.0, 0.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "c_ud")["value"], 10.0))

    def test_langstrackt_fundament_anvander_l_ref_1_och_specialfaktorer(self):
        details = allmanna_barighetsekvationen(
            [0.6, 5.0, 1, 0.5, 0.2, 0.3, 0.05, 0.0, 100.0, 10.0, 0.0, 5.0, 0.0, 1.2, 0.0, 0.0, 19.0, 10.0, 32.0, 1.0, 1.25, 1.5, 1.0, 5.0, 3.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ref")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_c")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_q")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "s_gamma")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "i_q")["value"], 1.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "i_gamma")["value"], 1.0))

    def test_grundvatten_inom_effektiv_bredd_ger_blandad_gamma_fri(self):
        details = allmanna_barighetsekvationen(
            [2.0, 3.0, 0, 1.0, 0.5, 0.4, 0.2, 0.1, 400.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 18.0, 9.0, 30.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )

        delresultat = details["delresultat"]
        self.assertTrue(math.isclose(_hamta_post(delresultat, "b_ef")["value"], 1.6))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "gamma_fri")["value"], 11.8125))

    def test_validerar_ogiltig_effektiv_geometri(self):
        with self.assertRaisesRegex(ValueError, "b_ef måste vara > 0."):
            allmanna_barighetsekvationen(
                [0.8, 1.0, 0, 0.8, 10.2, 0.4, 0.4, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
            )

        with self.assertRaisesRegex(ValueError, "l_ef måste vara > 0."):
            allmanna_barighetsekvationen(
                [0.8, 1.0, 0, 0.8, 10.2, 0.4, 0.0, 0.5, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
            )

    def test_validerar_orimliga_indata(self):
        with self.assertRaisesRegex(ValueError, "gamma_Rd måste vara > 0."):
            allmanna_barighetsekvationen(
                [0.8, 1.0, 0, 0.8, 10.2, 0.4, 0.0, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 0.0, 0.0, 0.0]
            )

    def test_tillater_b_storre_an_l_och_l_ref(self):
        details_punkt = allmanna_barighetsekvationen(
            [1.2, 1.0, 0, 0.8, 10.2, 0.4, 0.0, 0.0, 314.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )
        self.assertIn("slutresultat", details_punkt)

        details_lang = allmanna_barighetsekvationen(
            [1.1, 6.0, 1, 0.0, -1.36, 0.2, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 18.0, 9.0, 35.0, 1.0, 1.3, 1.5, 1.0, 0.0, 0.0]
        )
        self.assertIn("slutresultat", details_lang)

    @staticmethod
    def inputs(b=2.1, l=2.1, **updates):
        values = dict(zip(allmanna_barighetsekvationen.panel_schema["px"],
            [b,l,0,.8,10.,.3,0.,0.,1227.1,0.,0.,0.,0.,0.,0.,0.,18.,10.,35.,1.,1.3,1.5,1.,0.,0.]))
        values.update(updates)
        return [values[name] for name in allmanna_barighetsekvationen.panel_schema["px"]]

    @staticmethod
    def results(px, **options):
        details = allmanna_barighetsekvationen(px, **options)
        return {post["namn"]:post["value"] for section in ("delresultat","slutresultat")
                for post in details[section]["items"]}

    def test_centric_squares_match_pre_fix_reference_values_exactly(self):
        # These values were recorded from the previous engine, not recomputed
        # by the new algorithm. No placement eccentricities, moments or H loads.
        cases = [
            (.8,"dry",503.60530152853516,322.30739297826256,1234.3),
            (.8,"wet",495.58202784666605,317.1724978218663,1234.3),
            (.8,"clay",186.02760197630928,119.05766526483795,1234.3),
            (2.1,"dry",508.732793103485,2243.511617586369,1276.7124999999999),
            (2.1,"wet",465.94200013351656,2054.804220588808,1276.7124999999999),
            (2.1,"clay",156.17132017764234,688.7155219834027,1276.7124999999999),
            (3.,"dry",549.3946116579584,4944.551504921626,1328.35),
            (3.,"wet",482.5339976423828,4342.805978781445,1328.35),
            (3.,"clay",150.65939123019615,1355.9345210717654,1328.35),
        ]
        for b,soil,q,capacity,load in cases:
            with self.subTest(b=b,soil=soil):
                options = {"delta_h":.5} if soil=="wet" else {"c_uk":30.,"phi_k":0.} if soil=="clay" else {}
                result = self.results(self.inputs(b,b,**options))
                self.assertEqual((result["q_bd"],result["F_bd"],result["F_v"]),(q,capacity,load))

    def test_axis_exchange_keeps_capacity_and_original_axis_dimensions(self):
        for phi in (0,35):
            with self.subTest(phi=phi):
                a = self.results(self.inputs(2.8,2.1,e_b_plac=.1,e_l_plac=.4,
                    F_hb=10,F_hl=20,delta_h=.5,phi_k=phi,c_uk=30))
                b = self.results(self.inputs(2.1,2.8,e_b_plac=.4,e_l_plac=.1,
                    F_hb=20,F_hl=10,delta_h=.5,phi_k=phi,c_uk=30))
                for name in ("q_bd","F_bd","B_ef","L_ef","s_gamma","d_c","gamma_fri","i_q"):
                    self.assertAlmostEqual(a[name],b[name])
                self.assertAlmostEqual(a["b_ef"],2.6)
                self.assertAlmostEqual(a["l_ef"],1.3)
                self.assertAlmostEqual(a["B_ef"],1.3)
                self.assertAlmostEqual(a["L_ef"],2.6)

    def test_eccentric_capacity_uses_effective_area_for_point_and_line_models(self):
        result = self.results(self.inputs(1.2,2.5,e_b_plac=.1,e_l_plac=.2,d=0,phi_k=0,c_uk=30))
        q = 20*(math.pi+2)*(1+.2/2.1)
        self.assertAlmostEqual(result["q_bd"],q)
        self.assertAlmostEqual(result["F_bd"],q*1.*2.1)
        for length in (1,4):
            result = self.results(self.inputs(1.4,6,lang=1,e_b_plac=.2,d=0,phi_k=0,c_uk=30),remslangd=length)
            self.assertAlmostEqual(result["F_bd"],20*(math.pi+2)*1.)
            self.assertEqual(result["s_gamma"],1)
            self.assertAlmostEqual(result["B_ef"],1.)
            normal=1227.1+1.5*25*1.4*.3
            result = self.results(self.inputs(1.4,6,lang=1,e_b_plac=.2,d=0,phi_k=0,c_uk=30,
                M_insp_b=normal*.1),remslangd=length)
            self.assertAlmostEqual(result["F_bd"],20*(math.pi+2)*(length-.2)/length)

    def test_ps11_width_sweep_stays_positive_and_has_no_spurious_turning_point(self):
        previous = float("inf")
        for step in range(15,101):
            width=step/10
            r=self.results(self.inputs(width,2.1,e_l_plac=.4,d=0,delta_h=1.9,phi_k=45))
            self.assertGreater(r["q_bd"],0)
            self.assertGreater(r["F_bd"],0)
            self.assertGreaterEqual(r["s_gamma"],.6)
            self.assertLessEqual(r["s_gamma"],1)
            utilization=r["F_v"]/r["F_bd"]
            self.assertLessEqual(utilization,previous)
            previous=utilization

    def test_moments_change_the_effective_dimension_on_the_correct_input_axis(self):
        normal=1227.1+1.5*25*2*3*.3
        r=self.results(self.inputs(2,3,e_b_plac=.2,e_l_plac=.05,
            M_insp_l=normal*.1,M_insp_b=-normal*.15))
        self.assertAlmostEqual(r["e_b_last"],.1)
        self.assertAlmostEqual(r["e_l_last"],-.15)
        self.assertAlmostEqual(r["b_ef"],1.4)
        self.assertAlmostEqual(r["l_ef"],2.8)
        self.assertAlmostEqual(r["F_bd"],r["q_bd"]*1.4*2.8)
        # Opposite signs can cancel: reduction uses the signed sum, not |e|+|M/V|.
        normal=1227.1+1.5*25*2*2*.3
        centered=self.results(self.inputs(2,2))
        canceled=self.results(self.inputs(2,2,e_b_plac=.1,e_l_plac=-.2,
            M_insp_l=-normal*.1,M_insp_b=normal*.2))
        self.assertEqual(canceled["b_ef"],2)
        self.assertEqual(canceled["l_ef"],2)
        self.assertEqual(canceled["F_bd"],centered["F_bd"])


if __name__ == "__main__":
    unittest.main()
