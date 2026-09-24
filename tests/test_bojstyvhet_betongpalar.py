import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong import bojstyvhet_betongpalar


EXEMPEL_PX = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2, 30]
PX_NAMN = ["b", "c_nom", "phi_b", "phi_h", "l_0", "N_d",
           "f_ck", "f_cd", "E_cd", "E_s", "phi_eff", "M"]
OVERRIDE_NAMN = ["K_c_override", "K_c_manuell", "K_s_override", "K_s_manuell"]
PANEL_PX = EXEMPEL_PX + [False, 1.0, False, 1.0]


def _poster(details, section):
    return {post["namn"]: post for post in details[section]["items"]}


def _exempel(**andringar):
    values = dict(zip(PX_NAMN, EXEMPEL_PX))
    values.update(andringar)
    return [values[namn] for namn in PX_NAMN]


class TestBojstyvhetBetongpalar(unittest.TestCase):
    def test_referensfall_med_fyra_hornjarn(self):
        # Oberoende referens: integrera sigma(y)=k*(x-y) över 0..x
        # och addera två koncentrerade armeringsrader. Lös kubiken
        # N*integral(sigma*(b/2-y)) - M*integral(sigma) = 0 med Newton.
        # Referensen utvärderades separat med 50 siffrors Decimal-precision.
        details = bojstyvhet_betongpalar(EXEMPEL_PX)
        dr = _poster(details, "delresultat")
        expected = {
            "A_c": 90000.0,
            "x": 184.30045300397799587,
            "x_tp": 100.27818382146582968,
            "A_II": 63039.39778004822208,
            "I_II": 266309122.40185443063,
            "I_c": 160154427.10805486604,
            "d_prim": 48.0,
            "d": 252.0,
            "A_s_rad": 628.3185307179586,
            "alpha": 6.666666666666667,
            "A_s": 1256.6370614359173,
            "rho": 0.013962634015954637,
            "l_phi": 102.0,
            "I_phi": 7853.981633974483,
            "I_s": 16212200.20372576736,
            "i": 86.60254037844386,
            "l_0_mm": 3000.0,
            "N_d_N": 300000.0,
            "M_Nmm": 30000000.0,
            "lambda": 34.64101615137755,
            "n": 0.16666666666666667,
            "k_1": 1.224744871391589,
            "k_2": 0.03396178054056622,
            "K_c": 0.01386483884679505,
            "K_s": 1.0,
        }
        for namn, value in expected.items():
            with self.subTest(namn=namn):
                self.assertTrue(math.isclose(dr[namn]["value"], value, rel_tol=1e-12))

        sr = _poster(details, "slutresultat")
        for namn, value in {
            "EI_c": 66.61545967361896,
            "EI_s": 3242.4400407451535,
            "EI": 3309.0555004187724,
        }.items():
            with self.subTest(namn=namn):
                self.assertTrue(math.isclose(sr[namn]["value"], value, rel_tol=1e-12))
                self.assertEqual(sr[namn]["unit"], "kN*m^2")

    def test_helt_tryckt_snitt_aterger_tidigare_styvhet(self):
        for M in (0, 1, -10):
            details = bojstyvhet_betongpalar(_exempel(M=M))
            dr = _poster(details, "delresultat")
            sr = _poster(details, "slutresultat")
            self.assertEqual(dr["x"]["value"], 300)
            self.assertEqual(dr["x_tp"]["value"], 150)
            self.assertEqual(dr["iterationer"]["value"], 0)
            self.assertEqual(dr["I_c"]["value"], 675000000)
            self.assertAlmostEqual(sr["EI"]["value"], 2901.856569390636, places=8)

    def test_sigma_min_b_avser_hela_snittet_aven_efter_reduktion(self):
        # Hela snittet: Ac=90000, As=400*pi, alpha=20/3, hävarm=102.
        area = 90000 + (20 / 3 - 1) * 400 * math.pi
        inertia = 675000000 + (20 / 3 - 1) * 400 * math.pi * 102**2
        for N_d, M in ((300, 0), (300, 30), (300, -30), (0, 30), (0, 0)):
            with self.subTest(N_d=N_d, M=M):
                dr = _poster(bojstyvhet_betongpalar(_exempel(N_d=N_d, M=M)), "delresultat")
                sigma = dr["sigma_min_b"]
                expected = N_d * 1000 / area - abs(M) * 1e6 * 150 / inertia
                self.assertAlmostEqual(sigma["value"], expected, places=12)
                self.assertEqual(sigma["unit"], "MPa")
                self.assertEqual(sigma["latex"], r"\sigma_{min}(x=b)")
                if expected < 0:
                    self.assertLess(dr["x"]["value"], 300)
                    # Slutliga tryckzonens kantspänning är nära noll, men
                    # sigma_min_b ska fortfarande visa det negativa startvärdet.
                    sigma_x = N_d * 1000 / dr["A_II"]["value"] - (
                        dr["M_tp"]["value"] / dr["I_II"]["value"]
                        * (dr["x"]["value"] - dr["x_tp"]["value"])
                    )
                    self.assertAlmostEqual(sigma_x, 0, places=9)
                else:
                    self.assertEqual(dr["x"]["value"], 300)

    def test_betong_och_armering_kring_samma_axel_med_bibehallen_kc(self):
        details = bojstyvhet_betongpalar(EXEMPEL_PX)
        dr = {k: p["value"] for k, p in _poster(details, "delresultat").items()}
        sr = {k: p["value"] for k, p in _poster(details, "slutresultat").items()}
        self.assertNotAlmostEqual(dr["x"], dr["x_tp"])
        self.assertGreater(dr["I_c_steiner"], 0)
        self.assertAlmostEqual(dr["I_c"], dr["I_c_egen"] + dr["I_c_steiner"])
        # Flytta armeringens tidigare mittaxeltröghet med Steiners sats.
        old_I_s = 4171600 * math.pi
        self.assertAlmostEqual(dr["I_s"], old_I_s + dr["A_s"] * (150 - dr["x_tp"])**2)
        self.assertAlmostEqual(sr["EI_c"], dr["K_c"] * 30000 * dr["I_c"] / 1e9)
        self.assertAlmostEqual(sr["EI_s"], 200000 * dr["I_s"] / 1e9)
        # I_II får inte användas som betongens Ic eller läggas till i EI.
        self.assertNotAlmostEqual(dr["I_c"], dr["I_II"])
        self.assertAlmostEqual(sr["EI"], sr["EI_c"] + sr["EI_s"])

    def test_jamvikt_mot_integrerad_spanningsfordelning(self):
        # Kontrollera N och M kring geometrisk mittaxel utan att använda
        # lösarens A_II, x_tp eller I_II i kontrollberäkningen.
        for N_d, M, phi_h in ((300, 30, 20), (500, 40, 20), (0, 30, 20), (0, 10, 8)):
            with self.subTest(N_d=N_d, M=M, phi_h=phi_h):
                details = bojstyvhet_betongpalar(_exempel(N_d=N_d, M=M, phi_h=phi_h))
                dr = {k: p["value"] for k, p in _poster(details, "delresultat").items()}
                x = dr["x"]
                # Triangulärt betongtryck har resultant bx²/2 vid x/3.
                N_enhet = 300 * x**2 / 2
                M_enhet = N_enhet * (150 - x / 3)
                for y in (dr["d_prim"], dr["d"]):
                    # Betong som undanträngs av järnen räknas bort endast i tryck.
                    F = dr["A_s_rad"] * (dr["alpha"] * (x - y) - max(x - y, 0))
                    N_enhet += F
                    M_enhet += F * (150 - y)
                lutning = M * 1e6 / M_enhet
                self.assertAlmostEqual(lutning * N_enhet, N_d * 1000, delta=1e-6)
                self.assertAlmostEqual(lutning * M_enhet, M * 1e6, delta=1e-6)

    def test_bada_armeringsraderna_i_tryckzonen(self):
        # Välj x=280 mm och bestäm lasten direkt från triangulär spänning.
        x = 280.0
        N_enhet = 300 * x**2 / 2
        M_enhet = N_enhet * (150 - x / 3)
        for y in (48, 252):
            F = (20 / 3 - 1) * 200 * math.pi * (x - y)
            N_enhet += F
            M_enhet += F * (150 - y)
        M = 300000 * M_enhet / N_enhet / 1e6
        dr = _poster(bojstyvhet_betongpalar(_exempel(M=M)), "delresultat")
        self.assertAlmostEqual(dr["x"]["value"], x, places=8)
        self.assertAlmostEqual(dr["beta_1"]["value"], 20 / 3 - 1)
        self.assertAlmostEqual(dr["beta_2"]["value"], 20 / 3 - 1)

    def test_bada_armeringsraderna_utanfor_tryckzonen(self):
        dr = _poster(bojstyvhet_betongpalar(_exempel(N_d=0, phi_h=8)), "delresultat")
        # Ren böjning med båda raderna i drag: bx²/2 + alpha*As*(x-b/2)=0.
        a = (20 / 3) * 64 * math.pi
        expected_x = (-a + math.sqrt(a*a + 300**2*a)) / 300
        self.assertAlmostEqual(dr["x"]["value"], expected_x, places=8)
        self.assertLess(dr["x"]["value"], dr["d_prim"]["value"])
        self.assertEqual(dr["beta_1"]["value"], dr["alpha"]["value"])
        self.assertEqual(dr["beta_2"]["value"], dr["alpha"]["value"])

    def test_overgang_mellan_helt_och_delvis_tryckt_snitt(self):
        area = 90000 + (20 / 3 - 1) * 400 * math.pi
        inertia = 675000000 + (20 / 3 - 1) * 400 * math.pi * 102**2
        M_grans = 300000 * inertia / (area * 150) / 1e6
        for faktor in (1 - 1e-7, 1 + 1e-7):
            dr = _poster(bojstyvhet_betongpalar(_exempel(M=M_grans*faktor)), "delresultat")
            if faktor < 1:
                self.assertEqual(dr["x"]["value"], 300)
                self.assertEqual(dr["iterationer"]["value"], 0)
            else:
                self.assertLess(dr["x"]["value"], 300)
                self.assertGreater(dr["iterationer"]["value"], 0)
                self.assertAlmostEqual(dr["x"]["value"], 300, delta=1e-4)

    def test_momenttecken_och_gemensam_lastskalning(self):
        original = bojstyvhet_betongpalar(EXEMPEL_PX)
        negativt = bojstyvhet_betongpalar(_exempel(M=-30))
        self.assertEqual(original["delresultat"], negativt["delresultat"])
        self.assertEqual(original["slutresultat"], negativt["slutresultat"])
        self.assertEqual(_poster(negativt, "indata")["M"]["value"], -30)
        ref = _poster(original, "delresultat")
        for faktor in (1e-6, 10, 1e6):
            dr = _poster(bojstyvhet_betongpalar(_exempel(N_d=300*faktor, M=30*faktor)), "delresultat")
            for namn in ("x", "x_tp", "I_c", "I_s"):
                self.assertAlmostEqual(dr[namn]["value"], ref[namn]["value"])

    def test_obelastat_snitt_anvander_hela_betonghojden(self):
        details = bojstyvhet_betongpalar(_exempel(N_d=0, M=0))
        dr = _poster(details, "delresultat")
        self.assertEqual(dr["x"]["value"], 300)
        self.assertEqual(dr["iterationer"]["value"], 0)
        self.assertIn("Obelastat", str(details["metodbeskrivning"]))
        self.assertAlmostEqual(_poster(details, "slutresultat")["EI"]["value"], 2621.0935827430363)

    def test_k2_begransas_och_styvheten_planar_ut(self):
        values = []
        for N_d in (2000, 4000):
            details = bojstyvhet_betongpalar(_exempel(N_d=N_d))
            dr = _poster(details, "delresultat")
            self.assertGreater(dr["k_2_obegransad"]["value"], 0.20)
            self.assertEqual(dr["k_2"]["value"], 0.20)
            values.append(_poster(details, "slutresultat")["EI"]["value"])
        self.assertEqual(values[0], values[1])
        self.assertAlmostEqual(values[0], 4274.499159121682, places=8)

    def test_noll_tryckkraft_ger_endast_armeringsbidrag(self):
        details = bojstyvhet_betongpalar(_exempel(N_d=0))
        sr = _poster(details, "slutresultat")
        self.assertEqual(sr["EI_c"]["value"], 0)
        self.assertEqual(sr["EI"]["value"], sr["EI_s"]["value"])
        self.assertAlmostEqual(sr["EI_s"]["value"], 4302.359891917, places=8)
        dr = _poster(details, "delresultat")
        self.assertAlmostEqual(dr["x"]["value"], dr["x_tp"]["value"], places=8)
        # För N=0 gäller Ic=bx³/3 kring neutralaxeln.
        self.assertAlmostEqual(dr["I_c"]["value"], 300 * dr["x"]["value"]**3 / 3, delta=1e-4)

    def test_krypning_reducerar_endast_betongbidraget(self):
        utan = _poster(bojstyvhet_betongpalar(_exempel(phi_eff=0)), "slutresultat")
        med = _poster(bojstyvhet_betongpalar(EXEMPEL_PX), "slutresultat")
        self.assertAlmostEqual(utan["EI_c"]["value"], 3 * med["EI_c"]["value"])
        self.assertEqual(utan["EI_s"]["value"], med["EI_s"]["value"])

    def test_materialvarden_anvands_direkt(self):
        # Halverat f_cd fördubblar n och därmed EI_c under k2-taket.
        details = bojstyvhet_betongpalar(_exempel(f_cd=10, E_cd=15000, E_s=100000))
        sr = _poster(details, "slutresultat")
        self.assertAlmostEqual(sr["EI_c"]["value"], 66.61545967361896, places=8)
        self.assertAlmostEqual(sr["EI_s"]["value"], 1621.2200203725767, places=8)
        self.assertEqual(_poster(details, "indata")["f_cd"]["value"], 10)

    def test_manuella_faktorer_ersatter_varje_bidrag_utan_att_andra_tryckzonen(self):
        ref = _poster(bojstyvhet_betongpalar(EXEMPEL_PX), "delresultat")
        # Enskilda val, noll, bråktal och värden över 1 ska användas direkt.
        for K_c, K_s in ((0.3, None), (None, 0.5), (0, None), (None, 0), (0, 0), (2, 1.5)):
            with self.subTest(K_c=K_c, K_s=K_s):
                px = EXEMPEL_PX + [K_c is not None, K_c, K_s is not None, K_s]
                details = bojstyvhet_betongpalar(px)
                dr = _poster(details, "delresultat")
                sr = _poster(details, "slutresultat")
                valt_K_c = ref["K_c"]["value"] if K_c is None else K_c
                valt_K_s = 1 if K_s is None else K_s
                self.assertEqual(dr["K_c"]["value"], valt_K_c)
                self.assertEqual(dr["K_s"]["value"], valt_K_s)
                self.assertEqual(dr["K_c_auto"]["value"], ref["K_c"]["value"])
                self.assertEqual(dr["K_s_auto"]["value"], 1)
                for namn in ("x", "x_tp", "I_c", "I_s", "A_II", "I_II"):
                    self.assertEqual(dr[namn]["value"], ref[namn]["value"])
                expected_c = valt_K_c * 30000 * ref["I_c"]["value"] / 1e9
                expected_s = valt_K_s * 200000 * ref["I_s"]["value"] / 1e9
                self.assertAlmostEqual(sr["EI_c"]["value"], expected_c)
                self.assertAlmostEqual(sr["EI_s"]["value"], expected_s)
                self.assertAlmostEqual(sr["EI"]["value"], expected_c + expected_s)
                idata = _poster(details, "indata")
                self.assertEqual("K_c_manuell" in idata, K_c is not None)
                self.assertEqual("K_s_manuell" in idata, K_s is not None)

    def test_manuellt_kc_ersatter_aven_vid_noll_normalkraft_och_krypning(self):
        for N_d in (0, 4000):
            bidrag = []
            for phi_eff in (0, 5):
                details = bojstyvhet_betongpalar(
                    _exempel(N_d=N_d, phi_eff=phi_eff) + [True, 1.25, False, None]
                )
                dr = _poster(details, "delresultat")
                sr = _poster(details, "slutresultat")
                self.assertEqual(dr["K_c"]["value"], 1.25)
                self.assertGreater(sr["EI_c"]["value"], 0)
                bidrag.append(sr["EI_c"]["value"])
            self.assertEqual(bidrag[0], bidrag[1])

    def test_inaktiva_overridevarden_ignoreras_och_tolv_varden_fungerar(self):
        expected = bojstyvhet_betongpalar(EXEMPEL_PX)
        for tail in ([False, 1, False, 1], [False, None, False, "ignoreras"],
                     [False, math.nan, False, -5]):
            self.assertEqual(bojstyvhet_betongpalar(EXEMPEL_PX + tail), expected)

    def test_ogiltiga_manuella_faktorer_och_aktiveringsflaggor(self):
        for index, namn in ((0, "K_c"), (2, "K_s")):
            for value in (math.nan, math.inf, -math.inf, None, "fel", True, 10**1000):
                tail = [False, 1, False, 1]
                tail[index:index + 2] = [True, value]
                with self.subTest(namn=namn, value=str(value)[:20]):
                    with self.assertRaisesRegex(ValueError, namn + "_manuell måste vara ett ändligt tal"):
                        bojstyvhet_betongpalar(EXEMPEL_PX + tail)
            tail[index:index + 2] = [True, -0.1]
            with self.assertRaisesRegex(ValueError, namn + "_manuell måste vara >= 0"):
                bojstyvhet_betongpalar(EXEMPEL_PX + tail)
            for flag in (0, 1, "False", None):
                tail[index:index + 2] = [flag, 1]
                with self.assertRaisesRegex(ValueError, namn + "_override måste vara True eller False"):
                    bojstyvhet_betongpalar(EXEMPEL_PX + tail)

    def test_armeringsinnehall_vid_och_under_gransen(self):
        phi_grans = 300 * math.sqrt(0.002 / math.pi)
        details = bojstyvhet_betongpalar(_exempel(phi_h=phi_grans))
        self.assertAlmostEqual(_poster(details, "delresultat")["rho"]["value"], 0.002)
        for phi_h in (phi_grans * (1 - 1e-8), 6):
            with self.subTest(phi_h=phi_h):
                with self.assertRaisesRegex(ValueError, "rho >= 0,002"):
                    bojstyvhet_betongpalar(_exempel(phi_h=phi_h))

    def test_ogiltig_geometri_avvisas(self):
        with self.assertRaisesRegex(ValueError, "positiv hävarm"):
            bojstyvhet_betongpalar(_exempel(c_nom=132))
        # Positiv hävarm, men de fyra järnen skulle överlappa varandra.
        with self.assertRaisesRegex(ValueError, "överlappar"):
            bojstyvhet_betongpalar(_exempel(c_nom=127))

    def test_positiva_och_icke_negativa_indata(self):
        for namn in ("b", "phi_b", "phi_h", "l_0", "f_ck", "f_cd", "E_cd", "E_s"):
            for value in (0, -1):
                with self.subTest(namn=namn, value=value):
                    with self.assertRaisesRegex(ValueError, namn + " måste vara > 0"):
                        bojstyvhet_betongpalar(_exempel(**{namn: value}))
        for namn in ("c_nom", "N_d", "phi_eff"):
            with self.subTest(namn=namn):
                with self.assertRaisesRegex(ValueError, namn + " måste vara >= 0"):
                    bojstyvhet_betongpalar(_exempel(**{namn: -1}))
        bojstyvhet_betongpalar(_exempel(c_nom=0, N_d=0, phi_eff=0))

    def test_icke_andliga_och_icke_numeriska_indata_avvisas(self):
        for namn in PX_NAMN:
            for value in (math.nan, math.inf, -math.inf, None, "fel", True, 10**1000):
                with self.subTest(namn=namn, value=str(value)[:20]):
                    with self.assertRaisesRegex(ValueError, namn + " måste vara ett ändligt tal"):
                        bojstyvhet_betongpalar(_exempel(**{namn: value}))

    def test_px_format_och_antal(self):
        for px in (None, {}, "fel", 42):
            with self.subTest(px=px):
                with self.assertRaisesRegex(ValueError, "lista eller tuple"):
                    bojstyvhet_betongpalar(px)
        for px in ([], EXEMPEL_PX[:-1], EXEMPEL_PX + [4], PANEL_PX[:-1], PANEL_PX + [1]):
            with self.subTest(px=px):
                with self.assertRaisesRegex(ValueError, "exakt 12"):
                    bojstyvhet_betongpalar(px)
        self.assertEqual(bojstyvhet_betongpalar(tuple(EXEMPEL_PX)),
                         bojstyvhet_betongpalar(EXEMPEL_PX))

    def test_details_uppfyller_kontraktet(self):
        details = bojstyvhet_betongpalar(EXEMPEL_PX)
        self.assertEqual(set(details), {
            "metodbeskrivning", "indata", "delresultat", "slutresultat", "ekvationer",
        })
        for section in details.values():
            self.assertIsInstance(section["title"], str)
            self.assertTrue(section["items"])
        for section in ("indata", "delresultat", "slutresultat"):
            items = details[section]["items"]
            self.assertEqual(len(items), len({post["namn"] for post in items}))
            for post in items:
                self.assertTrue({"namn", "latex", "value", "unit", "etikett"} <= set(post))
                self.assertTrue(math.isfinite(post["value"]))
        self.assertEqual(_poster(details, "indata")["n_phi"]["value"], 4)
        self.assertIn("(5.29)", str(details["ekvationer"]))
        self.assertNotIn("(5.28)", str(details["ekvationer"]))
        json.dumps(details, allow_nan=False)

    def test_panel_schema_ger_ratt_px_och_berakningsbara_defaultvarden(self):
        schema = bojstyvhet_betongpalar.panel_schema
        self.assertEqual(schema["title"], "Böjstyvhet - Betongpålar")
        self.assertEqual(schema["px"], PX_NAMN + OVERRIDE_NAMN)
        fields = {field["name"]: field for field in schema["fields"]}
        self.assertEqual(set(fields), set(PX_NAMN + OVERRIDE_NAMN))
        self.assertEqual(fields["l_0"]["unit"], "m")
        self.assertEqual(fields["N_d"]["unit"], "kN")
        self.assertEqual(fields["M"]["unit"], "kN*m")
        for namn, field in fields.items():
            self.assertEqual(field["type"], "bool" if namn.endswith("_override") else "float")
        px = [fields[namn]["default"] for namn in schema["px"]]
        self.assertEqual(px, PANEL_PX)
        self.assertAlmostEqual(
            _poster(bojstyvhet_betongpalar(px), "slutresultat")["EI"]["value"],
            3309.0555004187724, places=8,
        )
        json.dumps(schema, allow_nan=False)


@unittest.skipUnless(importlib.util.find_spec("an_print"), "an-print behövs för integrationstest")
class TestBojstyvhetPresentation(unittest.TestCase):
    def test_calcblock_bygger_samtliga_redovisningsblock(self):
        from an_print import CalcBlock

        cb = CalcBlock(bojstyvhet_betongpalar(EXEMPEL_PX))
        for namn in ("MB", "ID", "DR", "EKV", "SR"):
            with self.subTest(block=namn):
                kwargs = {} if namn == "MB" else {"etikett": True}
                getattr(cb, namn)(visa=False, **kwargs)
                self.assertTrue(getattr(cb, "latex_" + namn.lower()))
                self.assertTrue(getattr(cb, "html_" + namn.lower()))
        self.assertIn("3309.056", cb.latex_sr)
        self.assertIn("184.300", cb.latex_dr)
        self.assertIn("100.278", cb.latex_dr)
        self.assertIn(r"\sigma_{min}(x=b)", cb.latex_dr)
        self.assertIn("σ<sub>min</sub>(x=b)", cb.html_dr)
        self.assertIn("x_{tp}", cb.latex_ekv)
        self.assertIn("ytterligare reduktion", cb.html_mb)
        self.assertIn("0.013963", cb.latex_dr)
        self.assertIn("(5.29)", cb.html_ekv)

        cb = CalcBlock(bojstyvhet_betongpalar(EXEMPEL_PX + [True, 0.25, True, 0.75]))
        cb.ID(visa=False, etikett=True)
        cb.DR(visa=False, etikett=True)
        cb.EKV(visa=False, etikett=True)
        self.assertIn("0.75000", cb.latex_dr)
        self.assertIn("manuellt angiven", cb.html_dr)
        self.assertIn(r"K_c & = & K_{c,man}", cb.latex_ekv)
        self.assertIn(r"K_s & = & K_{s,man}", cb.latex_ekv)
        self.assertIn("0.25000", cb.html_id)

    @unittest.skipUnless(importlib.util.find_spec("ipywidgets"), "ipywidgets behövs för Panel")
    def test_panel_bygger_falt_beraknar_och_uppdaterar(self):
        from an_print import Panel

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = pathlib.Path(tmpdir) / "panel.json"
            panel = Panel(bojstyvhet_betongpalar, state_file=state_file)
            # Bygg riktiga redovisningsblock utan att skriva till terminalens display.
            for block in panel._block_widgets.values():
                block["visa"].value = False
            self.assertEqual(panel.to_px(), PANEL_PX)
            details = panel.calculate()
            self.assertIs(panel.details, details)
            self.assertIn("3309.056", panel.cb.latex_sr)
            panel._field_widgets["M"].value = 0
            panel.calculate()
            self.assertEqual(panel.px[11], 0)
            self.assertIn("2901.857", panel.cb.latex_sr)
            panel._field_widgets["M"].value = -30
            panel.calculate()
            self.assertIn("3309.056", panel.cb.latex_sr)
            fields = {f["name"]: f for f in panel.schema["fields"]}
            self.assertFalse(panel._field_is_visible(fields["K_c_manuell"]))
            self.assertFalse(panel._field_is_visible(fields["K_s_manuell"]))
            panel._field_widgets["K_c_override"].value = True
            panel._field_widgets["K_c_manuell"].value = 0.25
            panel._field_widgets["K_s_override"].value = True
            panel._field_widgets["K_s_manuell"].value = 0.75
            details = panel.calculate()
            self.assertTrue(panel._field_is_visible(fields["K_c_manuell"]))
            self.assertTrue(panel._field_is_visible(fields["K_s_manuell"]))
            self.assertEqual(panel.px[12:], [True, 0.25, True, 0.75])
            dr = _poster(details, "delresultat")
            sr = _poster(details, "slutresultat")
            self.assertAlmostEqual(sr["EI_c"]["value"], 0.25 * 30000 * dr["I_c"]["value"] / 1e9)
            self.assertAlmostEqual(sr["EI_s"]["value"], 0.75 * 200000 * dr["I_s"]["value"] / 1e9)
            self.assertIn(r"K_s & = & K_{s,man}", panel.cb.latex_ekv)
            panel._field_widgets["K_c_override"].value = False
            panel._field_widgets["K_s_override"].value = False
            panel.calculate()
            self.assertIn("3309.056", panel.cb.latex_sr)
            panel._field_widgets["N_d"].value = 2000
            panel.calculate()
            self.assertEqual(panel.px[5], 2000)
            self.assertIn("4274.499", panel.cb.latex_sr)
            panel._field_widgets["phi_h"].value = 6
            with self.assertRaisesRegex(ValueError, "rho >= 0,002"):
                panel.calculate()
            self.assertFalse(state_file.exists())


if __name__ == "__main__":
    unittest.main()
