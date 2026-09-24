import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.betong import bojstyvhet_betongpalar


EXEMPEL_PX = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2]
PX_NAMN = ["b", "c_nom", "phi_b", "phi_h", "l_0", "N_d",
           "f_ck", "f_cd", "E_cd", "E_s", "phi_eff"]


def _poster(details, section):
    return {post["namn"]: post for post in details[section]["items"]}


def _exempel(**andringar):
    values = dict(zip(PX_NAMN, EXEMPEL_PX))
    values.update(andringar)
    return [values[namn] for namn in PX_NAMN]


class TestBojstyvhetBetongpalar(unittest.TestCase):
    def test_referensfall_med_fyra_hornjarn(self):
        # Handberäknat: l_phi = 102 mm, Ac = 90 000 mm²,
        # Ic = 675 000 000 mm⁴, As = 400*pi mm²,
        # Is = (10 000 + 400*102²)*pi = 4 171 600*pi mm⁴.
        # Referensvärden utvärderade separat med 50 siffrors Decimal-precision.
        details = bojstyvhet_betongpalar(EXEMPEL_PX)
        dr = _poster(details, "delresultat")
        expected = {
            "A_c": 90000.0,
            "I_c": 675000000.0,
            "A_s": 1256.6370614359173,
            "rho": 0.013962634015954637,
            "l_phi": 102.0,
            "I_phi": 7853.981633974483,
            "I_s": 13105467.913715182,
            "i": 86.60254037844386,
            "l_0_mm": 3000.0,
            "N_d_N": 300000.0,
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
            "EI_c": 280.76298664759975,
            "EI_s": 2621.0935827430363,
            "EI": 2901.856569390636,
        }.items():
            with self.subTest(namn=namn):
                self.assertTrue(math.isclose(sr[namn]["value"], value, rel_tol=1e-12))
                self.assertEqual(sr[namn]["unit"], "kN*m^2")

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
        self.assertAlmostEqual(sr["EI_s"]["value"], 2621.0935827430363, places=8)

    def test_krypning_reducerar_endast_betongbidraget(self):
        utan = _poster(bojstyvhet_betongpalar(_exempel(phi_eff=0)), "slutresultat")
        med = _poster(bojstyvhet_betongpalar(EXEMPEL_PX), "slutresultat")
        self.assertAlmostEqual(utan["EI_c"]["value"], 842.2889599427993, places=8)
        self.assertAlmostEqual(utan["EI_c"]["value"], 3 * med["EI_c"]["value"])
        self.assertEqual(utan["EI_s"]["value"], med["EI_s"]["value"])

    def test_materialvarden_anvands_direkt(self):
        # Halverat f_cd fördubblar n och därmed EI_c under k2-taket.
        details = bojstyvhet_betongpalar(_exempel(f_cd=10, E_cd=15000, E_s=100000))
        sr = _poster(details, "slutresultat")
        self.assertAlmostEqual(sr["EI_c"]["value"], 280.76298664759975, places=8)
        self.assertAlmostEqual(sr["EI_s"]["value"], 1310.5467913715181, places=8)
        self.assertEqual(_poster(details, "indata")["f_cd"]["value"], 10)

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
        for px in ([], EXEMPEL_PX[:-1], EXEMPEL_PX + [4]):
            with self.subTest(px=px):
                with self.assertRaisesRegex(ValueError, "exakt 11"):
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
        self.assertEqual(schema["px"], PX_NAMN)
        fields = {field["name"]: field for field in schema["fields"]}
        self.assertEqual(set(fields), set(PX_NAMN))
        self.assertEqual(fields["l_0"]["unit"], "m")
        self.assertEqual(fields["N_d"]["unit"], "kN")
        self.assertTrue(all(field["type"] == "float" for field in fields.values()))
        px = [fields[namn]["default"] for namn in schema["px"]]
        self.assertEqual(px, EXEMPEL_PX)
        self.assertAlmostEqual(
            _poster(bojstyvhet_betongpalar(px), "slutresultat")["EI"]["value"],
            2901.856569390636, places=8,
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
        self.assertIn("2901.857", cb.latex_sr)
        self.assertIn("0.013963", cb.latex_dr)
        self.assertIn("(5.29)", cb.html_ekv)

    @unittest.skipUnless(importlib.util.find_spec("ipywidgets"), "ipywidgets behövs för Panel")
    def test_panel_bygger_falt_beraknar_och_uppdaterar(self):
        from an_print import Panel

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = pathlib.Path(tmpdir) / "panel.json"
            panel = Panel(bojstyvhet_betongpalar, state_file=state_file)
            # Bygg riktiga redovisningsblock utan att skriva till terminalens display.
            for block in panel._block_widgets.values():
                block["visa"].value = False
            self.assertEqual(panel.to_px(), EXEMPEL_PX)
            details = panel.calculate()
            self.assertIs(panel.details, details)
            self.assertIn("2901.857", panel.cb.latex_sr)
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
