import json
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong import Tvärkraft, tvarkraft


def _indata(**extra):
    # Handräkningsfall: k=2, rho_l=0,01 och kubikroten ur 100*rho_l*f_ck=3.
    return dict(b_w=300, d=200, f_ck=27, A_sl=600,
                phi_w=8, n_skar=2, s=200, f_ywk=500, cot_theta=2) | extra


def _v(details, name):
    for section in ("slutresultat", "delresultat", "indata"):
        for item in details[section]["items"]:
            if item["namn"] == name:
                return item["value"]
    raise KeyError(name)


class TestTvarkraft(unittest.TestCase):
    def test_handraknat_grundfall_utan_och_med_byglar(self):
        d = Tvärkraft(_indata(V_Ed=50))
        self.assertAlmostEqual(_v(d, "V_Rd_c"), 43.2)
        self.assertAlmostEqual(_v(d, "V_Rd_s"), 78.67640732468354)
        self.assertAlmostEqual(_v(d, "V_Rd_max"), 208.08576)
        self.assertAlmostEqual(_v(d, "V_Rd"), 78.67640732468354)
        self.assertEqual(_v(d, "status_6_2_2"), "Överskriden")
        self.assertEqual(_v(d, "status_6_2_3"), "Uppfyller")

    def test_tryckstravan_begransar_vid_stor_bygelarea(self):
        d = Tvärkraft(_indata(phi_w=20, s=100))
        self.assertGreater(_v(d, "V_Rd_s"), _v(d, "V_Rd_max"))
        self.assertAlmostEqual(_v(d, "V_Rd"), 208.08576)

    def test_minimibarformaga_och_ingen_summering_av_betong_och_byglar(self):
        d = Tvärkraft(_indata(A_sl=0, n_skar=0, phi_w=0, V_Ed=1))
        self.assertAlmostEqual(_v(d, "V_Rd_c"), 0.035 * math.sqrt(216) * 60)
        self.assertEqual(_v(d, "V_Rd"), 0)
        self.assertEqual(_v(d, "status_6_2_2"), "Uppfyller")
        self.assertEqual(_v(d, "status_6_2_3"), "Överskriden")
        self.assertEqual(_v(d, "eta_6_2_3"), "Ingen bärförmåga")
        json.dumps(d, allow_nan=False)

    def test_hojdfaktor_och_armeringskvot_begransas(self):
        a = Tvärkraft(_indata(d=100, A_sl=600))
        b = Tvärkraft(_indata(d=100, A_sl=1200))
        self.assertEqual(_v(a, "k"), 2)
        self.assertEqual(_v(b, "rho_l"), 0.02)
        self.assertEqual(_v(a, "V_Rd_c"), _v(b, "V_Rd_c"))
        self.assertAlmostEqual(_v(b, "rho_l_obegransad"), 0.04)
        self.assertAlmostEqual(_v(Tvärkraft(_indata(d=800)), "k"), 1.5)

    def test_normalkraft_och_manuell_havarm(self):
        d = Tvärkraft(_indata(N_Ed=60, A_c=60000, z_auto=False, z_manuell=160))
        self.assertAlmostEqual(_v(d, "sigma_cp"), 1)
        self.assertAlmostEqual(_v(d, "V_Rd_c"), 52.2)
        self.assertAlmostEqual(_v(d, "z"), 160)
        self.assertEqual(_v(d, "alpha_cw"), 1)
        self.assertAlmostEqual(_v(d, "V_Rd_s"), 78.67640732468354 * 160 / 180)

    def test_dragkraft_kan_ge_noll_men_aldrig_negativ_barformaga(self):
        d = Tvärkraft(_indata(N_Ed=-600, A_c=60000, z_auto=False, z_manuell=180, V_Ed=1))
        self.assertLess(_v(d, "V_Rd_c_6_2a"), 0)
        self.assertEqual(_v(d, "V_Rd_c"), 0)
        self.assertEqual(_v(d, "status_6_2_2"), "Överskriden")

    def test_materialfaktorer_raknar_om_bade_betong_och_stal(self):
        d = Tvärkraft(_indata(gamma_c=1.2, gamma_s=1, alpha_cc=0.8))
        self.assertAlmostEqual(_v(d, "f_cd"), 18)
        self.assertAlmostEqual(_v(d, "f_ywd"), 500)
        self.assertAlmostEqual(_v(d, "V_Rd_c"), 54)
        self.assertAlmostEqual(_v(d, "V_Rd_s"), 90.47786842338604)

    def test_lutande_byglar_enligt_6_13_och_6_14(self):
        d = Tvärkraft(_indata(alpha=45))
        self.assertAlmostEqual(_v(d, "V_Rd_s"), 83.44893170801802)
        self.assertAlmostEqual(_v(d, "V_Rd_max"), 312.12864)
        zero = Tvärkraft(_indata(alpha=45, cot_theta=1, V_Ed=100))
        self.assertEqual(_v(zero, "Delta_F_td"), 0)

    def test_cot_theta_paverkar_bada_gransbarformagorna(self):
        a = Tvärkraft(_indata(cot_theta=1))
        b = Tvärkraft(_indata(cot_theta=2.5))
        self.assertAlmostEqual(_v(b, "V_Rd_s") / _v(a, "V_Rd_s"), 2.5)
        self.assertLess(_v(b, "V_Rd_max"), _v(a, "V_Rd_max"))
        self.assertAlmostEqual(_v(a, "theta"), 45)
        Tvärkraft(_indata(cot_theta_min=2, cot_theta_max=2))

    def test_reduktionsbildens_1700_300_700_ger_425(self):
        d = Tvärkraft(_indata(d=700, V_Ed=1700, reducera_tvarkraft=True, a_v=300, m_eff=1))
        self.assertEqual(_v(d, "beta"), 0.25)
        self.assertEqual(_v(d, "V_Ed_red"), 425)
        self.assertEqual(_v(d, "V_Ed"), 1700)
        self.assertEqual(_v(d, "l_eff"), 225)

    def test_reduktionsfaktorns_granser(self):
        for av, expected in ((1, 0.25), (350, 0.25), (700, 0.5), (1400, 1), (1401, 1)):
            with self.subTest(av=av):
                d = Tvärkraft(_indata(d=700, V_Ed=100, reducera_tvarkraft=True, a_v=av, m_eff=1))
                self.assertEqual(_v(d, "beta"), expected)
                self.assertEqual(_v(d, "V_Ed_red"), expected * 100)

    def test_kort_skjuvspann_anvander_verkliga_byglar_och_6_19(self):
        d = Tvärkraft(_indata(V_Ed=100, reducera_tvarkraft=True, a_v=100, m_eff=1))
        self.assertAlmostEqual(_v(d, "A_sw_eff"), 32 * math.pi)
        self.assertAlmostEqual(_v(d, "V_Rd_6_19"), 43.70911518037973)
        self.assertAlmostEqual(_v(d, "V_Rd_s_last"), 174.83646072151893)
        self.assertEqual(_v(d, "status_6_2_3"), "Uppfyller")
        # m_eff, inte ett avrundat 0,75a_v/s, styr (6.19).
        other = Tvärkraft(_indata(V_Ed=100, reducera_tvarkraft=True, a_v=100, m_eff=1, s=1000))
        self.assertEqual(_v(other, "V_Rd_s_last"), _v(d, "V_Rd_s_last"))
        self.assertNotEqual(_v(other, "V_Rd_s"), _v(d, "V_Rd_s"))

    def test_reduktion_fritar_inte_betongen_fran_oreducerad_last(self):
        d = Tvärkraft(_indata(f_ck=12, A_sl=1200, V_Ed=150,
                              reducera_tvarkraft=True, a_v=100, m_eff=5))
        self.assertEqual(_v(d, "status_c_reducerad"), "Uppfyller")
        self.assertEqual(_v(d, "status_c_oreducerad"), "Överskriden")
        self.assertEqual(_v(d, "status_6_2_2"), "Överskriden")
        self.assertAlmostEqual(_v(d, "V_lim_6_5"), 137.088)

    def test_reduktion_fritar_inte_tryckstravan_fran_oreducerad_last(self):
        for alpha in (90, 45):
            with self.subTest(alpha=alpha):
                d = Tvärkraft(_indata(V_Ed=250, reducera_tvarkraft=True, a_v=100, m_eff=5, alpha=alpha))
                self.assertEqual(_v(d, "status_s_reducerad"), "Uppfyller")
                self.assertEqual(_v(d, "status_s_oreducerad"), "Överskriden")
                self.assertEqual(_v(d, "status_6_2_3"), "Överskriden")
                self.assertAlmostEqual(_v(d, "V_Rd_s_last"), 208.08576)

    def test_inga_verksamma_byglar_ger_inte_godkant(self):
        d = Tvärkraft(_indata(V_Ed=1, reducera_tvarkraft=True, a_v=100))
        self.assertEqual(_v(d, "V_Rd_s_last"), 0)
        self.assertEqual(_v(d, "status_6_2_3"), "Överskriden")
        self.assertEqual(_v(d, "status_6_2_2"), "Uppfyller")

    def test_av_over_2d_atergar_till_ordinarie_modell(self):
        d = Tvärkraft(_indata(V_Ed=100, reducera_tvarkraft=True, a_v=401, m_eff=None))
        self.assertEqual(_v(d, "V_Rd_s_last"), _v(d, "V_Rd"))
        self.assertEqual(_v(d, "V_Rd_c_last"), _v(d, "V_Rd_c"))
        with self.assertRaises(KeyError):
            _v(d, "V_Rd_6_19")

    def test_nollast_vid_nollkapacitet(self):
        d = Tvärkraft(_indata(n_skar=0, V_Ed=0))
        self.assertEqual(_v(d, "eta_6_2_3"), 0)
        self.assertEqual(_v(d, "status_6_2_3"), "Uppfyller")

    def test_kapacitetslage_utfor_ingen_lastkontroll(self):
        d = Tvärkraft(_indata(V_Ed=999, kontrollera_last=False))
        for name in ("V_Ed", "eta_6_2_2", "eta_6_2_3", "Delta_F_td"):
            with self.assertRaises(KeyError):
                _v(d, name)

    def test_dolda_inaktiva_varden_anvands_inte(self):
        a = Tvärkraft(_indata())
        b = Tvärkraft(_indata(A_c=None, z_manuell=float('nan'), a_v=-10, m_eff=-1))
        self.assertEqual(a, b)

    def test_avvisar_ogiltiga_indata(self):
        cases = [
            {"b_w": 0}, {"d": -1}, {"d": True}, {"d": float('nan')},
            {"f_ck": 11}, {"f_ck": 91}, {"A_sl": -1}, {"phi_w": 0},
            {"n_skar": 1.5}, {"n_skar": -1}, {"s": 0}, {"f_ywk": float('inf')},
            {"cot_theta": 0.9}, {"cot_theta": 2.6}, {"cot_theta_min": 0.5},
            {"cot_theta_min": 2.2, "cot_theta_max": 2.1}, {"cot_theta_max": 3},
            {"cot_theta_max": 1.9}, {"alpha": 44}, {"alpha": 91},
            {"gamma_c": 0}, {"gamma_s": 0.9}, {"alpha_cc": 1.1},
            {"N_Ed": 1}, {"N_Ed": 1, "A_c": 60000},
            {"N_Ed": 216, "A_c": 60000, "z_auto": False, "z_manuell": 180},
            {"z_auto": False}, {"z_auto": False, "z_manuell": 201},
            {"V_Ed": -1}, {"kontrollera_last": True}, {"kontrollera_last": 1},
            {"reducera_tvarkraft": True},
            {"reducera_tvarkraft": True, "V_Ed": 1, "a_v": 0},
            {"reducera_tvarkraft": True, "V_Ed": 1, "a_v": 100, "m_eff": 0.5},
            {"reducera_tvarkraft": True, "V_Ed": 1, "a_v": 100, "m_eff": 1, "n_skar": 0},
            {"okand": 1}, {"b_w": 1e308, "d": 1e308},
        ]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Tvärkraft(_indata(**extra))
        for px in (None, [], [1] * 9, {}, "fel"):
            with self.subTest(px=px), self.assertRaises(ValueError):
                Tvärkraft(px)

    def test_export_kortformat_och_fullformat(self):
        self.assertIs(Tvärkraft, tvarkraft)
        compact = Tvärkraft([300, 200, 27, 600, 8, 2, 200, 500])
        expected = Tvärkraft(_indata(cot_theta=2.5))
        self.assertEqual(compact, expected)
        schema = Tvärkraft.panel_schema
        values = {f["name"]: f["default"] for f in schema["fields"]}
        direct = Tvärkraft(values)
        panel = Tvärkraft([values[n] for n in schema["px"]])
        self.assertEqual(direct, panel)
        self.assertEqual(len(schema["px"]), len(set(schema["px"])))
        self.assertEqual(set(schema["px"]), set(values))
        fields_in_sections = [f for section in schema["sections"] for f in section["fields"]]
        self.assertCountEqual(fields_in_sections, schema["px"])
        self.assertEqual(fields_in_sections.count("d"), 1)

    def test_details_kan_serialiseras_och_har_unika_poster(self):
        d = Tvärkraft(_indata(V_Ed=100, reducera_tvarkraft=True, a_v=100, m_eff=1))
        self.assertEqual(set(d), {"metodbeskrivning", "indata", "delresultat", "slutresultat", "ekvationer"})
        for section in ("indata", "delresultat", "slutresultat"):
            items = d[section]["items"]
            self.assertEqual(len(items), len({i["namn"] for i in items}))
            for item in items:
                self.assertTrue({"namn", "latex", "value", "unit", "etikett"} <= item.keys())
        json.dumps(d, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
