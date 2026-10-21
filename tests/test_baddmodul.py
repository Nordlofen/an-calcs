from copy import deepcopy
import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from an_calcs.geo import baddmodul, sattning


HUS1 = ["Hus1", "PS", 1163.0, 3.8, 2.7, [0.8, 1.5], [45.0, 30.0], [1.3, 1.3], 0.1]

HUS1_UTAN_LAST = [HUS1[0], HUS1[1], "yta", *HUS1[3:]]


def _poster(details, section):
    return {post["namn"]: post for post in details[section]["items"]}


class TestBaddmodul(unittest.TestCase):
    def test_lastfria_styvhetsformer_handraknat(self):
        # Ed=10000/1,5 kN/m², mittdjup 0,25 m, dz=0,5 m.
        # PS: K=Ed*2,25*3,25/0,5=97500 kN/m; k=K/6.
        # VS: K=Ed*2,25/0,5=30000 kN/m/m; k=K/2.
        for typ, form, name, value, unit in [
            ("PS", "yta", "k", 16250, "kN/m^2/m"),
            ("PS", "punkt", "K_punkt", 97500, "kN/m"),
            ("VS", "yta", "k", 15000, "kN/m^2/m"),
            ("VS", "linje", "K_linje", 30000, "kN/m/m"),
        ]:
            with self.subTest(typ=typ, form=form):
                px = ["Handkontroll", typ, form, 2, 3, [0.5], [10], [1.5], 0.5]
                with patch("an_calcs.geo.baddmodul.sattning") as settlement:
                    details = baddmodul(px)
                settlement.assert_not_called()  # Inte heller en dold referenslast.
                sr = _poster(details, "slutresultat")
                self.assertEqual(list(sr), [name])
                self.assertAlmostEqual(sr[name]["value"], value)
                self.assertEqual(sr[name]["unit"], unit)
                self.assertEqual(sr[name]["format"], "scientific")
                self.assertEqual(sr[name]["decimals"], 2)
                for section in ("indata", "delresultat", "slutresultat"):
                    self.assertFalse({"F", "F_remsa", "q", "s", "s_m"} & _poster(details, section).keys())
                if typ == "VS":
                    self.assertEqual(_poster(details, "indata")["by"]["value"], 1)
                self.assertNotIn("F", str(details["ekvationer"]))
                json.dumps(details, allow_nan=False)

    def test_lastfri_modell_motsvarar_aldre_flerlagersberakning(self):
        # Olika moduler, restskikt, tunt lager och båda spridningsmodellerna.
        for typ in ("PS", "VS"):
            for step in (0.1, 0.3, 2.0):
                old = ["Lager", typ, 1357, 2.55, 2.93, [0.07, 0.55, 1.3], [45, 30, 12], [1.3, 1.2, 1.4], step]
                new = [*old[:2], "yta", *old[3:]]
                before = _poster(baddmodul(old), "slutresultat")["k"]["value"]
                after = _poster(baddmodul(new), "slutresultat")["k"]["value"]
                self.assertTrue(math.isclose(before, after, rel_tol=1e-14))
                implicit = [*new[:2], *new[3:]]
                self.assertEqual(baddmodul(implicit), baddmodul(new))
                scaled = deepcopy(new)
                scaled[6] = [2 * E for E in scaled[6]]
                self.assertAlmostEqual(_poster(baddmodul(scaled), "slutresultat")["k"]["value"], 2 * after)

    def test_lastfri_modell_validerar_form_och_indata(self):
        for typ, form in [("PS", "linje"), ("VS", "punkt"), ("PS", "annat")]:
            with self.subTest(typ=typ, form=form), self.assertRaisesRegex(ValueError, "tillåter"):
                baddmodul(["Fel", typ, form, *HUS1[3:]])
        cases = [(0, None), (1, "XX"), (5, []), (6, [45]), (7, [1.3]), (5, "lager")]
        for index in (3, 4, 8):
            cases.extend((index, value) for value in (0, -1, True, None, float("nan"), float("inf")))
        for index in (5, 6, 7):
            cases.extend((index, [value, 1]) for value in (0, -1, True, None, float("nan"), float("inf")))
        for index, value in cases:
            px = deepcopy(HUS1_UTAN_LAST)
            px[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                baddmodul(px)

    def test_referensfall_fran_notebook(self):
        cases = [
            ("Hus1", 1163.0, [0.8, 1.5], [45.0, 30.0], 5.5006411692012245, 20607.20251039058),
            ("Hus2", 1597.0, [0.35], [45.0], 1.416593682423052, 109878.3817645255),
            ("Hus3", 669.0, [1.0, 1.1], [45.0, 30.0], 2.8526317992628223, 22857.72681192971),
        ]
        for namn, F, dz, E, s, k in cases:
            with self.subTest(namn=namn):
                result = baddmodul([namn, "PS", F, 3.8, 2.7, dz, E, [1.3] * len(dz), 0.1])
                sr = _poster(result, "slutresultat")
                self.assertAlmostEqual(sr["s"]["value"], s, places=10)
                self.assertAlmostEqual(sr["k"]["value"], k, places=7)
                self.assertEqual(sr["k"]["unit"], "kN/m^2/m")
                self.assertEqual(sr["s"]["unit"], "mm")

    def test_handraknat_delskikt_ps_och_vs(self):
        # Ett 0,5 m-skikt: z_mitt=0,25 m, Ed=10/1,5 MPa.
        # PS: s=120/(2,25*3,25)/(10000/1,5)*0,5 m, q=20 kPa.
        # VS: s=120/2,25/(10000/1,5)*0,5=0,004 m, q=60 kPa.
        for typ, s_mm, k in [("PS", 1.2307692307692308, 16250.0), ("VS", 4.0, 15000.0)]:
            with self.subTest(typ=typ):
                details = baddmodul(["Handkontroll", typ, 120, 2, 3, [0.5], [10], [1.5], 0.5])
                sr = _poster(details, "slutresultat")
                self.assertAlmostEqual(sr["s"]["value"], s_mm)
                self.assertAlmostEqual(sr["k"]["value"], k)

    def test_vs_anvander_enmetersremsa_och_ignorerar_by(self):
        for by in [None, 2.7, 0, -1, float("nan")]:
            with self.subTest(by=by):
                details = baddmodul(["Vägg", "vs", 120, 2, by, [0.5], [10], [1.5], 0.5])
                inputs = _poster(details, "indata")
                dr = _poster(details, "delresultat")
                self.assertEqual(inputs["typ"]["value"], "VS")
                self.assertEqual(inputs["F"]["unit"], "kN/m")
                self.assertEqual(inputs["by"]["value"], 1)
                self.assertEqual(dr["A"]["value"], 2)
                self.assertEqual(dr["F_remsa"]["value"], 120)
                self.assertEqual(dr["F_remsa"]["unit"], "kN")
                self.assertEqual(dr["q"]["value"], 60)

    def test_delegerar_sattningen_och_bevarar_indata_och_schema(self):
        px = deepcopy(HUS1)
        schema = deepcopy(sattning.panel_schema)
        with patch("an_calcs.geo.baddmodul.sattning", wraps=sattning) as calculate:
            details = baddmodul(px)
        calculate.assert_called_once_with(["PS", 0.1, [0.8, 1.5], [45.0, 30.0], [1.3, 1.3], 1163.0, 3.8, 2.7])
        self.assertEqual(px, HUS1)
        self.assertEqual(schema, sattning.panel_schema)
        sr = _poster(details, "slutresultat")
        dr = _poster(details, "delresultat")
        self.assertAlmostEqual(dr["s_m"]["value"], sr["s"]["value"] / 1000)
        self.assertAlmostEqual(sr["s"]["value"], sum(post["value"] for name, post in dr.items() if name.startswith("s_lager_")))
        self.assertEqual(dr["antal_delskikt"]["value"], 23)

    def test_linjar_modell_ger_samma_baddmodul_vid_lastskalning(self):
        original = _poster(baddmodul(HUS1), "slutresultat")
        doubled = deepcopy(HUS1)
        doubled[2] *= 2
        result = _poster(baddmodul(doubled), "slutresultat")
        self.assertAlmostEqual(result["s"]["value"], 2 * original["s"]["value"])
        self.assertAlmostEqual(result["k"]["value"], original["k"]["value"])

    def test_redovisningskontrakt_och_endast_anvanda_ekvationer(self):
        for typ in ("PS", "VS"):
            px = deepcopy(HUS1)
            px[1] = typ
            details = baddmodul(px)
            self.assertEqual(set(details), {"metodbeskrivning", "indata", "delresultat", "slutresultat", "ekvationer"})
            for section in details.values():
                self.assertIsInstance(section["title"], str)
                self.assertTrue(section["items"])
            for key in ("indata", "delresultat", "slutresultat"):
                posts = details[key]["items"]
                self.assertEqual(len(posts), len({post["namn"] for post in posts}))
                for post in posts:
                    self.assertTrue({"namn", "latex", "value", "unit", "etikett"} <= set(post))
            eq = details["ekvationer"]["items"]
            self.assertEqual(len(eq), len({item["latex"] for item in eq}))
            self.assertEqual([p["etikett"] for p in eq if "spänningsökning" in p["etikett"]], [f"spänningsökning för {typ}"])
            self.assertNotIn("b_1", str(eq))
            self.assertNotIn("b_2", str(eq))
            self.assertIn("E_{d,kPa}", str(eq))
            self.assertIn("k =", str(eq))
            json.dumps(details, allow_nan=False)

    def test_ogiltiga_indata_avvisas_fore_berakning(self):
        for px in (None, [], HUS1 + [1]):
            with self.subTest(px=px), self.assertRaisesRegex(ValueError, "9 värden"):
                baddmodul(px)
        cases = [(0, None), (1, "XX"), (1, None), (5, []), (6, []), (7, []),
                 (5, [1]), (6, [1]), (7, [1]), (5, "jordlager")]
        for index in (2, 3, 4, 8):
            cases.extend((index, value) for value in (0, -1, None, True, float("nan"), float("inf")))
        for index in (5, 6, 7):
            cases.extend((index, [value, 1]) for value in (0, -1, None, True, float("nan"), float("inf")))
        for index, value in cases:
            with self.subTest(index=index, value=value):
                px = deepcopy(HUS1)
                px[index] = value
                with patch("an_calcs.geo.baddmodul.sattning") as calculate:
                    with self.assertRaises(ValueError):
                        baddmodul(px)
                    calculate.assert_not_called()

    def test_schema_defaults_kan_beraknas(self):
        schema = baddmodul.panel_schema
        values = {}
        for field in schema["fields"]:
            if field["type"] == "table":
                for column in field["columns"]:
                    values[column["output"]] = [row[column["name"]] for row in field["default_rows"]]
            else:
                values[field["name"]] = field["default"]
        px = [values[name] for name in schema["px"]]
        self.assertEqual(px, HUS1_UTAN_LAST)
        self.assertTrue(math.isfinite(_poster(baddmodul(px), "slutresultat")["k"]["value"]))
        json.dumps(schema, allow_nan=False)


@unittest.skipUnless(importlib.util.find_spec("an_print"), "an-print behövs för integrationstest")
class TestBaddmodulPresentation(unittest.TestCase):
    def test_lastfria_former_redovisas_med_ratt_enhet_och_potensform(self):
        from an_print import CalcBlock

        for typ, form, rendered, unit in [
            ("PS", "yta", r"1.62 \cdot 10^{4}", "kN/m<sup>2</sup>/m"),
            ("PS", "punkt", r"9.75 \cdot 10^{4}", "kN/m"),
            ("VS", "yta", r"1.50 \cdot 10^{4}", "kN/m<sup>2</sup>/m"),
            ("VS", "linje", r"3.00 \cdot 10^{4}", "kN/m/m"),
        ]:
            cb = CalcBlock(baddmodul(["Kontroll", typ, form, 2, 3, [0.5], [10], [1.5], 0.5]))
            for block in ("MB", "ID", "DR", "EKV", "SR"):
                getattr(cb, block)(visa=False)
                self.assertTrue(getattr(cb, "latex_" + block.lower()))
            self.assertIn(rendered, cb.latex_sr)
            self.assertIn(unit, cb.html_sr)

    @unittest.skipUnless(importlib.util.find_spec("ipywidgets"), "ipywidgets behövs för Panel")
    def test_aldre_sparade_fall_och_dynamiska_styvhetsval(self):
        from an_print import Panel

        base = "an_calcs.geo.baddmodul.baddmodul"
        old = dict(zip(["namn", "typ", "F", "bx", "by", "dz_lista", "Ek_lista", "gamma_m_lista", "t_skikt"], HUS1))
        for name in ("dz_lista", "Ek_lista", "gamma_m_lista"):
            old.pop(name)
        old["jordlager"] = [{"dz": .8, "Ek": 45, "gamma_m": 1.3}, {"dz": 1.5, "Ek": 30, "gamma_m": 1.3}]
        wall = {**old, "typ": "VS", "F": 77.0, "by": 1.0, "__unfixed_values__": {"by": 4.2}}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "old.json"
            original = json.dumps({base + ":PS": old, base + ":VS": wall})
            path.write_text(original)
            panel = Panel(baddmodul, key="PS", state_file=path)
            self.assertEqual(path.read_text(), original)  # Läsning migrerar inte filen.
            self.assertEqual(panel.to_px(), HUS1_UTAN_LAST)
            self.assertNotIn("F", panel._field_widgets)
            form = panel._field_widgets["form"]
            self.assertEqual([v for _, v in form.options], ["yta", "punkt"])
            form.value = "punkt"
            panel._save_last_values()
            self.assertEqual(json.loads(path.read_text())[base + ":PS"]["F"], 1163)
            panel._case_combo.value = "VS"
            self.assertEqual(form.value, "yta")
            self.assertEqual([v for _, v in form.options], ["yta", "linje"])
            form.value = "linje"
            panel._save_last_values()
            self.assertEqual(json.loads(path.read_text())[base + ":VS"]["F"], 77)
            Panel._LAST_VALUES.clear()
            Panel._LAST_BY_FUNCTION.clear()
            loaded = Panel(baddmodul, key="VS", state_file=path)
            self.assertEqual(loaded._field_widgets["form"].value, "linje")
            loaded._case_combo.value = "PS"
            self.assertEqual(loaded._field_widgets["form"].value, "punkt")
            loaded._case_combo.value = "VS"
            loaded._field_widgets["typ"].value = "PS"
            self.assertEqual(loaded._field_widgets["form"].value, "yta")
            self.assertEqual(loaded._field_widgets["by"].value, 4.2)
            # Ett nytt fall får ingen påhittad last i state-filen.
            fresh = Panel(baddmodul, key="Nytt", state_file=path.parent / "new.json")
            self.assertNotIn("F", fresh._collect_values())

    def test_k_redovisas_i_potensform_med_tva_decimaler(self):
        from an_print import CalcBlock

        details = baddmodul(["26017 - Hus1 TRH1", "PS", 1500, 2.55, 2.93, [0.5], [45], [1.3], 0.1])
        k = _poster(details, "slutresultat")["k"]
        self.assertAlmostEqual(k["value"], 81945.514, places=3)
        cb = CalcBlock(details)
        cb.SR(etikett=True)
        self.assertIn(r"8.19 \cdot 10^{4}", cb.latex_sr)
        self.assertIn("8.19 &middot; 10<sup>4</sup>", cb.html_sr)
        self.assertIn(r"\mathrm{kN/m}^{2}\mathrm{/m}", cb.latex_sr)
        self.assertIn("kN/m<sup>2</sup>/m", cb.html_sr)

    def test_calcblock_renderar_alla_fem_block(self):
        from an_print import CalcBlock

        for typ in ("PS", "VS"):
            px = deepcopy(HUS1)
            px[1] = typ
            cb = CalcBlock(baddmodul(px))
            for name in ("MB", "ID", "DR", "EKV", "SR"):
                getattr(cb, name)(visa=False, **({} if name == "MB" else {"etikett": True}))
                self.assertTrue(getattr(cb, "html_" + name.lower()))
                self.assertTrue(getattr(cb, "latex_" + name.lower()))
            self.assertIn("bäddmodul", cb.html_sr)
            self.assertIn("sättningsbidrag", cb.html_dr)

    @unittest.skipUnless(importlib.util.find_spec("ipywidgets"), "ipywidgets behövs för Panel")
    def test_riktig_panel_med_tabell_lasning_grupp_och_sparade_fall(self):
        from an_print import Panel
        import ipywidgets as widgets

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "panel.json"
            panel = Panel(baddmodul, key="A", state_file=path)
            for block in panel._block_widgets.values():
                block["visa"].value = False
            self.assertEqual(panel.to_px(), HUS1_UTAN_LAST)
            self.assertAlmostEqual(_poster(panel.calculate(), "slutresultat")["k"]["value"], 20607.20251039058)
            settings = panel._sections["Beräkningsinställningar"]
            self.assertIsInstance(settings, widgets.Accordion)
            self.assertEqual(settings.get_title(0), "Beräkningsinställningar")
            self.assertIsNone(settings.selected_index)
            panel._field_widgets["by"].value = 4.2
            panel._field_widgets["typ"].value = "VS"
            self.assertTrue(panel._field_widgets["by"].disabled)
            self.assertEqual(panel.to_px()[4], 1)
            self.assertNotIn("F", panel._field_widgets)
            self.assertEqual(_poster(panel.calculate(), "indata")["by"]["value"], 1)
            panel._save_last_values()
            Panel._LAST_VALUES.clear()
            Panel._LAST_BY_FUNCTION.clear()
            loaded = Panel(baddmodul, key="A", state_file=path)
            self.assertEqual(loaded.to_px()[4], 1)
            self.assertTrue(loaded._field_widgets["by"].disabled)
            loaded._field_widgets["typ"].value = "PS"
            self.assertEqual(loaded.to_px()[4], 4.2)
            self.assertFalse(loaded._field_widgets["by"].disabled)
            loaded._table_widgets["jordlager"].set_rows([{"dz": 0.35, "Ek": 45, "gamma_m": 1.3}])
            loaded._field_widgets["by"].value = 2.7
            self.assertAlmostEqual(_poster(loaded.calculate(), "slutresultat")["k"]["value"], 109878.3817645255)


if __name__ == "__main__":
    unittest.main()
