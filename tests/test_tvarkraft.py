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
    def test_strimla_motsvarar_en_meters_bredd_med_enheter_per_meter(self):
        for method in ("bada", "6.2.2", "6.2.3"):
            for reduction in (False, True):
                for bars in (False, True):
                    with self.subTest(method=method, reduction=reduction, bars=bars):
                        data = _indata(metod=method, V_Ed=100, N_Ed=60, A_c=250000,
                                       z_auto=False, z_manuell=180,
                                       reducera_tvarkraft=reduction, a_v=100, m_eff=2,
                                       A_sl_inmatning="jarn" if bars else "area", n_l=5, phi_l=16)
                        reference = Tvärkraft(data | {"b_w": 1000})
                        strip = Tvärkraft(data | {"plattstrimla": True})
                        for section in ("indata", "delresultat", "slutresultat"):
                            expected = {i["namn"]: i for i in reference[section]["items"]}
                            for item in strip[section]["items"]:
                                if item["namn"] == "plattstrimla":
                                    continue
                                ref = expected[item["namn"]]
                                self.assertEqual(item["value"], ref["value"], item["namn"])
                                self.assertEqual(item["unit"], "kN/m-str" if ref["unit"] == "kN" else ref["unit"])
                                if ref["unit"] == "kN":
                                    self.assertEqual(item["sigfigs"], 3)
                        self.assertEqual(_v(strip, "b_w"), 1000)
                        self.assertEqual(_v(strip, "V_Ed"), 100)
                        self.assertEqual(_v(strip, "V_Ed_red"), 25 if reduction else 100)
                        if method != "6.2.2":
                            self.assertAlmostEqual(_v(strip, "V_Rd_max"), 693.6192)

    def test_strimla_kraver_inte_bredd_och_validerar_flaggan(self):
        data = dict(metod="6.2.2", d=200, f_ck=27, A_sl=2000)
        strip = Tvärkraft(data | {"plattstrimla": True})
        self.assertEqual(_v(strip, "b_w"), 1000)
        self.assertAlmostEqual(_v(strip, "V_Rd_c"), 144)
        for ignored in (None, -1, float("nan")):
            self.assertEqual(strip, Tvärkraft(data | dict(plattstrimla=True, b_w=ignored)))
        with self.assertRaisesRegex(ValueError, "b_w"):
            Tvärkraft(data)
        for flag in (None, 1, "False"):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "plattstrimla"):
                Tvärkraft(_indata(plattstrimla=flag))

    def test_strimla_fullformat_och_tidigare_26_och_27_format(self):
        schema = Tvärkraft.panel_schema
        values = {f["name"]: f["default"] for f in schema["fields"]}
        full = [values[n] for n in schema["px"]]
        self.assertEqual(len(full), 28)
        for size in (26, 27):
            self.assertEqual(Tvärkraft(full[:size]), Tvärkraft(values))
        full[schema["px"].index("plattstrimla")] = True
        self.assertEqual(Tvärkraft(full), Tvärkraft(values | {"plattstrimla": True}))
        self.assertEqual(Tvärkraft(full[:27]), Tvärkraft(full))

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
        self.assertAlmostEqual(_v(b, "theta"), 21.80140948635181)
        self.assertEqual(_v(a, "V_Rd_c"), _v(b, "V_Rd_c"))

    def test_metodval_kraver_bara_aktiva_indata_och_redovisar_vald_metod(self):
        both = Tvärkraft(_indata(V_Ed=50))
        cases = [
            ("6.2.2", dict(A_sl=600),
             ("V_Rd_c", "eta_6_2_2", "status_6_2_2"),
             ("V_Rd_s", "V_Rd_max", "V_Rd", "eta_6_2_3", "A_sw", "f_ywd", "cot_theta")),
            ("6.2.3", dict(phi_w=8, n_skar=2, s=200, f_ywk=500, cot_theta=2),
             ("V_Rd_s", "V_Rd_max", "V_Rd", "eta_6_2_3", "status_6_2_3"),
             ("V_Rd_c", "eta_6_2_2", "A_sl", "rho_l", "sigma_cp", "k")),
        ]
        for method, extra, present, absent in cases:
            with self.subTest(method=method):
                d = Tvärkraft(dict(b_w=300, d=200, f_ck=27, V_Ed=50, metod=method) | extra)
                for name in present:
                    self.assertEqual(_v(d, name), _v(both, name))
                for name in absent:
                    with self.assertRaises(KeyError, msg=name):
                        _v(d, name)
                equations = " ".join(i["latex"] for i in d["ekvationer"]["items"])
                self.assertEqual("V_{Rd,c}" in equations, method == "6.2.2")
                self.assertEqual("V_{Rd,s}" in equations, method == "6.2.3")

    def test_ogiltiga_indata_for_bortvald_metod_ignoreras(self):
        c = _indata(metod="6.2.2")
        self.assertEqual(Tvärkraft(c), Tvärkraft(c | dict(
            phi_w=-1, n_skar=-1, s=0, f_ywk=None, cot_theta=100,
            alpha=None, gamma_s=0, z_auto="fel", z_manuell=float("nan"))))
        s = _indata(metod="6.2.3")
        self.assertEqual(Tvärkraft(s), Tvärkraft(s | dict(
            A_sl=-1, A_sl_inmatning="fel", n_l=-1, phi_l=0, A_c=0)))

    def test_normalkraft_kraver_area_respektive_havarm_for_vald_metod(self):
        c = Tvärkraft(_indata(metod="6.2.2", N_Ed=60, A_c=60000))
        self.assertAlmostEqual(_v(c, "V_Rd_c"), 52.2)
        s = Tvärkraft(_indata(metod="6.2.3", N_Ed=216, z_auto=False, z_manuell=160))
        self.assertAlmostEqual(_v(s, "z"), 160)
        # 6.2.2:s spänningsgräns ska inte begränsa en beräkning med enbart 6.2.3.
        with self.assertRaisesRegex(ValueError, "sigma_cp"):
            Tvärkraft(_indata(N_Ed=216, A_c=60000, z_auto=False, z_manuell=160))
        for method in ("6.2.2", "6.2.3"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                Tvärkraft(_indata(metod=method, N_Ed=60))

    def test_langsarmering_fran_antal_och_diameter_motsvarar_direkt_area(self):
        area = 4 * math.pi * 20**2 / 4
        for method in ("bada", "6.2.2"):
            with self.subTest(method=method):
                bars = Tvärkraft(_indata(metod=method, A_sl_inmatning="jarn", n_l=4, phi_l=20, A_sl=-1))
                direct = Tvärkraft(_indata(metod=method, A_sl=area, n_l=-1, phi_l=0))
                self.assertEqual(_v(bars, "A_sl"), area)
                self.assertEqual(_v(bars, "V_Rd_c"), _v(direct, "V_Rd_c"))
                self.assertEqual(_v(bars, "rho_l"), _v(direct, "rho_l"))
                self.assertIn("A_sl", {i["namn"] for i in bars["delresultat"]["items"]})
                self.assertNotIn("A_sl", {i["namn"] for i in bars["indata"]["items"]})
        minimal = Tvärkraft(dict(metod="6.2.2", b_w=300, d=200, f_ck=27,
                                A_sl_inmatning="jarn", n_l=0, phi_l=20))
        self.assertEqual(_v(minimal, "A_sl"), 0)
        self.assertGreater(_v(minimal, "V_Rd_c"), 0)

    def test_val_och_stangindata_valideras(self):
        for value in ("fel", None, [], 6.2):
            with self.subTest(method=value), self.assertRaises(ValueError):
                Tvärkraft(_indata(metod=value))
        with self.assertRaises(ValueError):
            Tvärkraft(_indata(A_sl_inmatning="fel"))
        for extra in ({"n_l": None}, {"n_l": -1}, {"n_l": 1.5}, {"n_l": True},
                      {"phi_l": None}, {"phi_l": 0}, {"phi_l": -1},
                      {"phi_l": float("nan")}, {"phi_l": 1e308}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Tvärkraft(_indata(A_sl_inmatning="jarn", n_l=4, phi_l=20) | extra)

    def test_cc_och_diameter_avrundar_antalet_nedat_och_ger_ratt_kapacitet(self):
        cases = ((300, 100, 4), (300, 100.001, 3), (300, 99.999, 4),
                 (300, 175, 2), (300, 500, 1), (1000, 200, 6),
                 (1000, 150, 7), (1000, 250, 5))
        for method in ("bada", "6.2.2"):
            for bw, cc, count in cases:
                with self.subTest(method=method, bw=bw, cc=cc):
                    area = count * math.pi * 20**2 / 4
                    data = _indata(metod=method, b_w=bw, V_Ed=100,
                                   reducera_tvarkraft=True, a_v=100, m_eff=2)
                    spaced = Tvärkraft(data | dict(A_sl_inmatning="cc", cc_l=cc,
                                                  phi_l=20, n_l=-1, A_sl=-1))
                    direct = Tvärkraft(data | dict(A_sl=area))
                    self.assertEqual(_v(spaced, "n_l"), count)
                    self.assertEqual(_v(spaced, "cc_l"), cc)
                    self.assertAlmostEqual(_v(spaced, "A_sl"), area)
                    for name in ("rho_l", "V_Rd_c", "eta_6_2_2"):
                        self.assertEqual(_v(spaced, name), _v(direct, name))
                    self.assertFalse({"A_sl", "n_l"} & {i["namn"] for i in spaced["indata"]["items"]})
                    self.assertTrue({"A_sl", "n_l"} <= {i["namn"] for i in spaced["delresultat"]["items"]})

    def test_cc_anvander_strimlans_bredd_och_fullformat(self):
        spaced = Tvärkraft(dict(metod="6.2.2", plattstrimla=True, d=200, f_ck=27,
                                A_sl_inmatning="cc", cc_l=200, phi_l=20))
        self.assertEqual(_v(spaced, "n_l"), 6)
        self.assertAlmostEqual(_v(spaced, "A_sl"), 600 * math.pi)
        schema = Tvärkraft.panel_schema
        values = {f["name"]: f["default"] for f in schema["fields"]}
        values.update(A_sl_inmatning="cc", plattstrimla=True, cc_l=150, phi_l=16)
        self.assertEqual(Tvärkraft([values[n] for n in schema["px"]]), Tvärkraft(values))

    def test_cc_valideras_endast_nar_det_anvands(self):
        for cc in (None, 0, -1, True, "fel", float("nan"), float("inf"), 1e-308):
            with self.subTest(cc=cc), self.assertRaises(ValueError):
                Tvärkraft(_indata(A_sl_inmatning="cc", cc_l=cc, phi_l=20))
        for diameter in (None, 0, -1, True, float("nan")):
            with self.subTest(diameter=diameter), self.assertRaises(ValueError):
                Tvärkraft(_indata(A_sl_inmatning="cc", cc_l=200, phi_l=diameter))
        for extra in ({}, dict(A_sl_inmatning="jarn", n_l=4, phi_l=20),
                      dict(metod="6.2.3", A_sl_inmatning="cc")):
            data = _indata() | extra
            self.assertEqual(Tvärkraft(data), Tvärkraft(data | {"cc_l": -1}))
        with self.assertRaisesRegex(ValueError, "cc_l"):
            Tvärkraft(dict(metod="6.2.2", b_w=300, d=200, f_ck=27, A_sl_inmatning="cc", phi_l=20))

    def test_reduktion_fungerar_for_varje_metod(self):
        for av in (100, 401):
            base = _indata(V_Ed=100, reducera_tvarkraft=True, a_v=av, m_eff=1)
            both = Tvärkraft(base)
            for method in ("6.2.2", "6.2.3"):
                with self.subTest(method=method, av=av):
                    d = Tvärkraft(base | {"metod": method})
                    self.assertEqual(_v(d, "V_Ed_red"), _v(both, "V_Ed_red"))
                    name = "eta_" + method.replace(".", "_")
                    self.assertEqual(_v(d, name), _v(both, name))
            c = Tvärkraft(base | dict(metod="6.2.2", m_eff="inaktivt"))
            with self.assertRaises(KeyError):
                _v(c, "m_eff")

    def test_cot_granser_ar_fasta_aven_for_aldre_fullformat(self):
        legacy = [300, 200, 27, 600, 8, 2, 200, 500,
                  0, None, False, None, False, None, 0,
                  2, 1.5, 2.1, 90, True, None, 1.5, 1.15, 1]
        self.assertEqual(Tvärkraft(legacy), Tvärkraft(_indata()))
        legacy[15:18] = [2.6, 1, 3]
        with self.assertRaises(ValueError):
            Tvärkraft(legacy)
        self.assertNotIn("cot_theta_min", Tvärkraft.panel_schema["px"])
        self.assertNotIn("cot_theta_max", Tvärkraft.panel_schema["px"])

    def test_ekvationernas_vansterled_innehaller_inte_langa_olikheter(self):
        d = Tvärkraft(_indata(cot_theta=2.5, V_Ed=100, reducera_tvarkraft=True, a_v=100, m_eff=1))
        equations = d["ekvationer"]["items"]
        for item in equations:
            left, _, right = item["latex"].partition("=")
            self.assertTrue(right)
            self.assertNotIn(r"\leq", left)
            self.assertNotIn("<", left)
        cot = next(i for i in equations if i["latex"].startswith(r"\cot\theta="))
        self.assertEqual(cot["latex"], r"\cot\theta=2{,}5")
        self.assertIn("1,0", cot["etikett"])
        self.assertIn("2,5", cot["etikett"])

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
        self.assertAlmostEqual(_v(d, "eta_6_2_3"), 100 * 25 / 43.70911518037973)
        self.assertEqual(_v(d, "status_6_2_3"), "Uppfyller")
        # m_eff, inte ett avrundat 0,75a_v/s, styr (6.19).
        other = Tvärkraft(_indata(V_Ed=100, reducera_tvarkraft=True, a_v=100, m_eff=1, s=1000))
        self.assertEqual(_v(other, "eta_6_2_3"), _v(d, "eta_6_2_3"))
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
                self.assertAlmostEqual(_v(d, "V_Rd_max_6_9"), 208.08576)
                self.assertAlmostEqual(_v(d, "eta_6_2_3"), 100 * 250 / 208.08576)

    def test_inga_verksamma_byglar_ger_inte_godkant(self):
        d = Tvärkraft(_indata(V_Ed=1, reducera_tvarkraft=True, a_v=100))
        self.assertEqual(_v(d, "V_Rd_6_19"), 0)
        self.assertEqual(_v(d, "eta_6_2_3"), "Ingen bärförmåga")
        self.assertEqual(_v(d, "status_6_2_3"), "Överskriden")
        self.assertEqual(_v(d, "status_6_2_2"), "Uppfyller")

    def test_av_over_2d_atergar_till_ordinarie_modell(self):
        d = Tvärkraft(_indata(V_Ed=100, reducera_tvarkraft=True, a_v=401, m_eff=None))
        self.assertAlmostEqual(_v(d, "eta_6_2_3"), 100 * 100 / _v(d, "V_Rd"))
        self.assertAlmostEqual(_v(d, "eta_6_2_2"), 100 * 100 / _v(d, "V_Rd_c"))
        with self.assertRaises(KeyError):
            _v(d, "V_Rd_6_19")

    def test_slutkontrollen_styrs_av_storsta_delutnyttjandet(self):
        # Prova både bygel-/betongkapacitet och oreducerad last som styrande,
        # samt nollast och nollkapacitet. Beta ska bara räknas en gång.
        for load in (0, 50, 250):
            for av in (100, 200, 400):
                for m_eff in (0, 1, 10):
                    with self.subTest(load=load, av=av, m_eff=m_eff):
                        d = Tvärkraft(_indata(V_Ed=load, reducera_tvarkraft=True, a_v=av, m_eff=m_eff))
                        for method, branch in (("6_2_2", "c"), ("6_2_3", "s")):
                            partials = [_v(d, f"eta_{branch}_{part}") for part in ("reducerad", "oreducerad")]
                            expected = "Ingen bärförmåga" if "Ingen bärförmåga" in partials else max(partials)
                            actual = _v(d, "eta_" + method)
                            if isinstance(expected, str):
                                self.assertEqual(actual, expected)
                            else:
                                self.assertAlmostEqual(actual, expected)
                            passed = all(_v(d, f"status_{branch}_{part}") == "Uppfyller"
                                         for part in ("reducerad", "oreducerad"))
                            self.assertEqual(_v(d, "status_" + method), "Uppfyller" if passed else "Överskriden")

    def test_redovisningen_saknar_omraknade_kapaciteter_i_alla_lagen(self):
        for method in ("bada", "6.2.2", "6.2.3"):
            for extra in ({}, {"V_Ed": 100},
                          {"V_Ed": 100, "reducera_tvarkraft": True, "a_v": 100, "m_eff": 1},
                          {"V_Ed": 100, "reducera_tvarkraft": True, "a_v": 401}):
                with self.subTest(method=method, extra=extra):
                    d = Tvärkraft(_indata(metod=method) | extra)
                    text = json.dumps(d, ensure_ascii=False)
                    for obsolete in ("V_Rd_c_last", "V_Rd_s_last", "Rd,c,last", "Rd,s,last", "/\\\\beta", "suffixet 'last'"):
                        self.assertNotIn(obsolete, text)
                    equations = {i["latex"].split("=", 1)[0]: i["latex"] for i in d["ekvationer"]["items"]}
                    short = extra.get("a_v", 401) <= 400
                    if extra and method != "6.2.3":
                        self.assertEqual(equations[r"\eta_{6.2.2}"],
                                         r"\eta_{6.2.2}=\max(\eta_{\mathrm{c.reducerad}},\eta_{\mathrm{c.oreducerad}})" if short
                                         else r"\eta_{6.2.2}=100V_{Ed}/V_{Rd,c}\leq100")
                    if extra and method != "6.2.2":
                        self.assertEqual(equations[r"\eta_{6.2.3}"],
                                         r"\eta_{6.2.3}=\max(\eta_{\mathrm{s.reducerad}},\eta_{\mathrm{s.oreducerad}})" if short
                                         else r"\eta_{6.2.3}=100V_{Ed}/V_{Rd}\leq100")
                    for branch, method_active, reduced_cap, unreduced_cap in (
                        ("c", method != "6.2.3", "V_{Rd,c}", "V_{lim,6.5}"),
                        ("s", method != "6.2.2", "V_{Rd,6.19}", "V_{Rd,max,6.9}"),
                    ):
                        if short and method_active:
                            lhs = r"\eta_{\mathrm{" + branch + ".reducerad}}"
                            self.assertEqual(equations[lhs], lhs + "=100V_{Ed,red}/" + reduced_cap + r"\leq100")
                            lhs = r"\eta_{\mathrm{" + branch + ".oreducerad}}"
                            self.assertEqual(equations[lhs], lhs + "=100V_{Ed}/" + unreduced_cap + r"\leq100")

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
