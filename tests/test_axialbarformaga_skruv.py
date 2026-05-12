import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.tra import axialdrag_traskruv


def _hamta_post(section, namn):
    for post in section["items"]:
        if post["namn"] == namn:
            return post
    raise AssertionError(f"Kunde inte hitta post med namn={namn!r}")


def _px(
    gangtyp="helgangad",
    andtra=False,
    V_Ed_kN=10.0,
    d=8.0,
    d_h=16.0,
    L=260.0,
    Lg=None,
    rho_k_1=350.0,
    rho_k_2=420.0,
    t_1=90.0,
    t_2=145.0,
    f_ax_k=11.0,
    f_head_k=14.0,
    f_tens_k=16000.0,
    alpha_ax=45.0,
    rho_a=350.0,
):
    return [
        gangtyp,
        "tra-tra",
        andtra,
        V_Ed_kN,
        d,
        d_h,
        L,
        Lg,
        rho_k_1,
        rho_k_2,
        t_1,
        t_2,
        f_ax_k,
        f_head_k,
        f_tens_k,
        alpha_ax,
        rho_a,
    ]


def _f_ax_w(f_ax_k, d, l_ef, alpha, rho_k, rho_a):
    alpha_factor = 1.2 * math.cos(math.radians(alpha)) ** 2 + math.sin(math.radians(alpha)) ** 2
    return f_ax_k * d * l_ef / alpha_factor * (rho_k / rho_a) ** 0.8


class TestAxialdragTraskruv(unittest.TestCase):
    def test_returnerar_standardiserad_details(self):
        details = axialdrag_traskruv(_px())

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
            for post in section["items"]:
                self.assertEqual(set(post), {"namn", "latex", "value", "unit", "etikett"})

    def test_slat_hals_redovisar_endast_l_ef_2_och_anvander_huvudgenomdragning_i_del_1(self):
        details = axialdrag_traskruv(_px(gangtyp="slat-hals", Lg=120.0))
        delresultat = details["delresultat"]
        namn = {item["namn"] for item in delresultat["items"]}

        self.assertIn("l_ef_2", namn)
        self.assertNotIn("l_ef_1", namn)
        self.assertNotIn("F_ax_w_1", namn)
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_1")["value"], _hamta_post(delresultat, "F_ax_h")["value"]))

    def test_helgangad_redovisar_l_ef_1_och_del_1_som_max_av_utdragning_och_huvud(self):
        details = axialdrag_traskruv(_px(gangtyp="helgangad"))
        delresultat = details["delresultat"]

        f_ax_w_1 = _hamta_post(delresultat, "F_ax_w_1")["value"]
        f_ax_h = _hamta_post(delresultat, "F_ax_h")["value"]
        self.assertIn("l_ef_1", {item["namn"] for item in delresultat["items"]})
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_1")["value"], max(f_ax_w_1, f_ax_h)))

    def test_andtra_true_har_ratt_vinklar_och_l_ef_2(self):
        details = axialdrag_traskruv(_px(andtra=True, alpha_ax=30.0, L=300.0, t_1=90.0))
        delresultat = details["delresultat"]

        expected_l_ef_2 = 300.0 - 90.0 / math.cos(math.radians(30.0)) - 15.0
        self.assertTrue(math.isclose(_hamta_post(delresultat, "alpha_1")["value"], 90.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "alpha_2")["value"], 30.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef_2")["value"], expected_l_ef_2))

    def test_andtra_false_har_ratt_vinklar_och_t2_begransar_l_ef_2(self):
        details = axialdrag_traskruv(_px(andtra=False, alpha_ax=45.0, L=400.0, t_1=90.0, t_2=80.0))
        delresultat = details["delresultat"]

        expected_l_ef_2 = min(
            400.0 - 90.0 / math.cos(math.radians(45.0)) - 15.0,
            80.0 / math.cos(math.radians(45.0)) - 15.0,
        )
        self.assertTrue(math.isclose(_hamta_post(delresultat, "alpha_1")["value"], 45.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "alpha_2")["value"], 45.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef_2")["value"], expected_l_ef_2))

    def test_l_ef_2_under_6d_ger_fel(self):
        with self.assertRaisesRegex(ValueError, "l_ef_2 måste vara minst 6d"):
            axialdrag_traskruv(_px(L=150.0, t_1=90.0, alpha_ax=45.0, d=8.0))

    def test_alpha_ax_utanf_or_tillat_intervall_ger_fel(self):
        with self.assertRaisesRegex(ValueError, "andtra=True"):
            axialdrag_traskruv(_px(andtra=True, alpha_ax=50.0))
        with self.assertRaisesRegex(ValueError, "andtra=False"):
            axialdrag_traskruv(_px(andtra=False, alpha_ax=65.0))

    def test_v_ed_konverteras_till_f_t_ed_i_n(self):
        details = axialdrag_traskruv(_px(V_Ed_kN=12.0, alpha_ax=45.0))
        expected = 12.0 * 1000.0 / math.sin(math.radians(45.0))

        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "F_t_Ed")["value"], expected))

    def test_v_ed_none_eller_noll_skippar_f_t_ed(self):
        for V_Ed_kN in (None, 0.0):
            details = axialdrag_traskruv(_px(V_Ed_kN=V_Ed_kN, alpha_ax=0.0, andtra=False))
            delresultat_namn = {item["namn"] for item in details["delresultat"]["items"]}
            slutresultat_namn = {item["namn"] for item in details["slutresultat"]["items"]}
            ekvationer = [item["latex"] for item in details["ekvationer"]["items"]]

            self.assertNotIn("F_t_Ed", delresultat_namn)
            self.assertNotIn("F_t_Ed", slutresultat_namn)
            self.assertFalse(any("F_{t,Ed}" in ekvation for ekvation in ekvationer))

    def test_negativt_v_ed_ger_fel(self):
        with self.assertRaisesRegex(ValueError, "V_Ed_kN måste vara >= 0"):
            axialdrag_traskruv(_px(V_Ed_kN=-1.0))

    def test_f_ax_rk_begransas_av_minsta_av_delar_och_skruvdragbrott(self):
        details = axialdrag_traskruv(_px(f_tens_k=1000.0))
        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_Rk")["value"], 1000.0))
        self.assertEqual(_hamta_post(delresultat, "brottmod_styrande")["value"], "dragbrott skruv")

    def test_minimiavstand_enligt_ec5_tabell_8_6(self):
        details = axialdrag_traskruv(_px(d=8.0))
        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "a_1")["value"], 56.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a_2")["value"], 40.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a_1_CG")["value"], 80.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "a_2_CG")["value"], 32.0))
        self.assertIn("3d", _hamta_post(delresultat, "a_2_CG")["etikett"])

    def test_f_ax_w_2_anvander_ec5_8_40a_med_densitetsfaktor(self):
        px = _px(gangtyp="slat-hals", Lg=120.0, rho_k_2=420.0, rho_a=350.0, alpha_ax=45.0, t_2=145.0)
        details = axialdrag_traskruv(px)
        delresultat = details["delresultat"]

        l_ef_2 = _hamta_post(delresultat, "l_ef_2")["value"]
        expected = _f_ax_w(11.0, 8.0, l_ef_2, 45.0, 420.0, 350.0)
        self.assertTrue(math.isclose(_hamta_post(delresultat, "F_ax_w_2")["value"], expected))

    def test_fel_antal_indata_ger_tydligt_fel(self):
        with self.assertRaisesRegex(ValueError, "16 eller 17"):
            axialdrag_traskruv(["helgangad", "tra-tra"])

    def test_slat_hals_kraver_lg_och_begransar_l_ef_2(self):
        with self.assertRaisesRegex(ValueError, "Lg måste anges"):
            axialdrag_traskruv(_px(gangtyp="slat-hals", Lg=None))

        details = axialdrag_traskruv(_px(gangtyp="slat-hals", Lg=80.0, L=400.0, t_1=90.0, t_2=145.0))
        self.assertTrue(math.isclose(_hamta_post(details["delresultat"], "l_ef_2")["value"], 80.0))

    def test_dubbelgangad_kraver_lg_och_begransar_bada_effektiva_langder(self):
        with self.assertRaisesRegex(ValueError, "Lg måste anges"):
            axialdrag_traskruv(_px(gangtyp="dubbelgangad", Lg=None))

        details = axialdrag_traskruv(_px(gangtyp="dubbelgangad", Lg=80.0, L=400.0, t_1=90.0, t_2=145.0))
        delresultat = details["delresultat"]

        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef_1")["value"], 80.0))
        self.assertTrue(math.isclose(_hamta_post(delresultat, "l_ef_2")["value"], 80.0))
        self.assertIn("F_ax_w_1", {item["namn"] for item in delresultat["items"]})

    def test_helgangad_behover_inte_lg(self):
        details = axialdrag_traskruv(_px(gangtyp="helgangad", Lg=None))
        self.assertIn("l_ef_1", {item["namn"] for item in details["delresultat"]["items"]})

    def test_panel_schema_har_ratt_px_ordning_och_default_kan_beraknas(self):
        schema = axialdrag_traskruv.panel_schema
        values = {field["name"]: field["default"] for field in schema["fields"]}
        px = [values[name] for name in schema["px"]]

        self.assertEqual(
            schema["px"],
            [
                "gangtyp",
                "anslutningstyp",
                "andtra",
                "V_Ed_kN",
                "d",
                "d_h",
                "L",
                "Lg",
                "rho_k_1",
                "rho_k_2",
                "t_1",
                "t_2",
                "f_ax_k",
                "f_head_k",
                "f_tens_k",
                "alpha_ax",
                "rho_a",
            ],
        )
        details = axialdrag_traskruv(px)
        self.assertIn("F_ax_Rk", {item["namn"] for item in details["slutresultat"]["items"]})

    def test_panel_schema_visar_lg_for_relevanta_gangtyper(self):
        lg_field = next(field for field in axialdrag_traskruv.panel_schema["fields"] if field["name"] == "Lg")

        self.assertEqual(lg_field["visible_if"], {"field": "gangtyp", "in": ["slat-hals", "dubbelgangad"]})


if __name__ == "__main__":
    unittest.main()
