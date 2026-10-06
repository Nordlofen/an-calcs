import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.geo import allmanna_barighetsekvationen
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, 'Installera an-calcs[notebook] för notebooktesterna.')
class TestGrundplan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "plan.png"
        Image.new("RGB", (800, 600), "white").save(self.path)
        self.plan = Grundplan(self.path)
        self.addCleanup(self.plan.close)

    def add(self, **kwargs):
        return self.plan.lagg_till(0.3, 0.4, **kwargs)

    def test_taggar_ar_oberoende_och_resultatet_anvander_befintlig_motor(self):
        first = self.add(littera="VS2", indata={"F_vy": 100, "b": 0.8})
        second = self.add(typ="pelarsula", indata={"F_vy": 600, "b": 2, "l": 3})
        details = self.plan.berakna(first)
        values = self.plan.taggar[0]["values"]
        expected = allmanna_barighetsekvationen([
            0.0 if name == "l_h" else values[name] for name in allmanna_barighetsekvationen.panel_schema["px"]
        ])
        self.assertEqual(details, expected)
        self.assertEqual(self.plan.taggar[0]["summary"]["lastenhet"], "kN/m")
        self.assertEqual(self.plan.taggar[1]["status"], "calculated")
        self.plan.berakna(second)
        summary = self.plan.taggar[1]["summary"]
        self.assertEqual(summary["lastenhet"], "kN")
        self.assertAlmostEqual(summary["utnyttjandegrad"], summary["last"] / summary["barformaga"])
        self.plan.uppdatera(first, indata={"b": 1.1})
        self.assertEqual(self.plan.taggar[1]["values"]["b"], 2)
        self.assertIn(second, self.plan.resultat)
        self.assertIn(first, self.plan.resultat)
        self.assertEqual(self.plan.taggar[0]["summary"]["b"], 1.1)

    def test_vaggsula_ar_en_meters_remsa_och_egentyngd_ingår(self):
        ident = self.add(indata={"F_vy": 100, "b": 0.8, "t": 0.4, "l": 25})
        self.plan.berakna(ident)
        first = self.plan.taggar[0]["summary"]
        self.assertAlmostEqual(first["last"], 100 + 1.5 * 25 * 0.8 * 0.4)
        self.plan.uppdatera(ident, indata={"l": 1})
        self.plan.berakna(ident)
        self.assertEqual(first, self.plan.taggar[0]["summary"])

    def insulated(self):
        return self.add(indata={
            "isolering": True, "b": 1, "t": 0.4, "F_vy": 100,
            "F_vy_bruk": 70, "f_d_brott": 200, "f_d_bruk": 50,
        })

    def test_isolering_bruk_kan_styra_trots_godkand_jord_och_brott(self):
        ident = self.insulated()
        details = self.plan.berakna(ident)
        summary = self.plan._tag(ident)["summary"]
        checks = {check["id"]: check["utnyttjandegrad"] for check in summary["kontroller"]}
        self.assertLess(checks["jord_brott"], 1)
        self.assertAlmostEqual(checks["isolering_brott"], 115 / 200)
        self.assertAlmostEqual(checks["isolering_bruk"], 80 / 50)
        self.assertAlmostEqual(summary["utnyttjandegrad"], 1.6)
        self.assertEqual(summary["styrande"], "Isolering · bruk")
        self.assertAlmostEqual(summary["isolering"]["isolering_A_eff_bruk"], 1)
        outputs = {item["namn"]: item["value"] for item in details["slutresultat"]["items"]}
        self.assertEqual(outputs["isolering_U_bruk"], summary["utnyttjandegrad"])
        self.assertIn("F_bd", outputs)

    def test_avstangd_isolering_behaller_indata_men_anvander_bara_jord(self):
        ident = self.insulated()
        self.plan.berakna(ident)
        self.plan.uppdatera(ident, indata={"isolering": False})
        self.assertNotIn("isolering", self.plan._tag(ident)["summary"])
        details = self.plan.berakna(ident)
        tag = self.plan._tag(ident)
        expected = allmanna_barighetsekvationen([
            0.0 if name == "l_h" else tag["values"][name] for name in allmanna_barighetsekvationen.panel_schema["px"]
        ])
        self.assertEqual(details, expected)
        self.assertEqual(tag["values"]["f_d_bruk"], 50)
        self.assertEqual(len(tag["summary"]["kontroller"]), 1)
        self.assertNotIn("isolering", tag["summary"])
        self.assertLess(tag["summary"]["utnyttjandegrad"], 1)

    def test_isoleringsfel_tar_bort_tidigare_godkant_resultat(self):
        ident = self.insulated()
        for invalid in ({"f_d_bruk": None}, {"F_vy_bruk": None}, {"f_d_brott": 0},
                        {"f_d_bruk": -1}, {"M_insp_l_bruk": 1000}):
            with self.subTest(invalid=invalid):
                self.plan.uppdatera(ident, indata={
                    "f_d_brott": 200, "f_d_bruk": 150, "F_vy_bruk": 70, "M_insp_l_bruk": 0,
                })
                self.plan.berakna(ident)
                self.assertLess(self.plan._tag(ident)["summary"]["utnyttjandegrad"], 1)
                self.plan.uppdatera(ident, indata=invalid)
                with self.assertRaises(ValueError):
                    self.plan.berakna(ident)
                self.assertEqual(self.plan._tag(ident)["status"], "error")
                self.assertIsNone(self.plan._tag(ident)["summary"])
                self.assertNotIn(ident, self.plan.resultat)
        with self.assertRaisesRegex(ValueError, "True eller False"):
            self.plan.uppdatera(ident, indata={"isolering": 1})

    def test_isolering_kopieras_sparas_och_ateroppnas_oberoende(self):
        ident = self.insulated()
        self.plan.berakna(ident)
        results = self.plan.resultat
        summary = self.plan._tag(ident)["summary"]
        self.plan.uppdatera(ident, indata={"isolerprodukt": "EPS S200, 100 mm – entré"})
        self.assertEqual(self.plan.resultat, results)
        self.assertEqual(self.plan._tag(ident)["summary"], summary)
        self.assertEqual(self.plan._tag(ident)["status"], "calculated")
        original = self.plan.taggar[0]
        copied_id = self.plan.kopiera(ident, 0.8, 0.8)
        self.assertEqual(self.plan._tag(copied_id)["values"], original["values"])
        self.plan.uppdatera(copied_id, indata={"isolerprodukt": "XPS 300"})
        self.plan.uppdatera(copied_id, indata={"F_vy_bruk": 50, "f_d_bruk": 200})
        self.plan.berakna(copied_id)
        self.assertEqual(self.plan.taggar[0], original)
        loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "isolering.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.taggar, self.plan.taggar)
        self.assertEqual(loaded.resultat, self.plan.resultat)
        self.assertEqual(loaded._document()["version"], 4)
        legacy = self.plan._document()
        del legacy["tags"][0]["values"]["isolerprodukt"]
        loaded._load_document(json.dumps(legacy).encode())
        self.assertEqual(loaded._tag(ident)["values"]["isolerprodukt"], "")
        self.assertEqual(loaded._tag(ident)["summary"], summary)

    def test_aldre_projekt_far_isolering_avstangd_och_beraknas_automatiskt(self):
        ident = self.add()
        details = self.plan.berakna(ident)
        document = self.plan._document()
        document["version"] = 1
        soil_file = Path(__file__).resolve().parents[1] / "src/an_calcs/geo/allmanna_barighetsekvationen.py"
        document["calculator_version"] = hashlib.sha256(soil_file.read_bytes()).hexdigest()
        old_values = document["tags"][0]["values"]
        document["tags"][0]["values"] = {
            name: 1.0 if name == "l_h" else old_values[name]
            for name in allmanna_barighetsekvationen.panel_schema["px"]
        }
        self.plan._load_document(json.dumps(document).encode())
        tag = self.plan._tag(ident)
        self.assertIs(tag["values"]["isolering"], False)
        self.assertIsNone(tag["values"]["F_vy_bruk"])
        self.assertIsNone(tag["values"]["f_d_brott"])
        self.assertIsNone(tag["values"]["f_d_bruk"])
        self.assertEqual(tag["status"], "calculated")
        self.assertIsNotNone(tag["summary"])
        self.assertIn(ident, self.plan.resultat)
        self.plan.berakna(ident)
        self.assertEqual(self.plan.resultat[ident], details)

    def test_direkta_moment_i_brott_och_bruk_utan_dolda_havarmsbidrag(self):
        removed = {"l_h", "l_h_bruk", "F_hb_bruk", "F_hl_bruk"}
        for kind, length in (("vaggsula", 1), ("pelarsula", 3)):
            with self.subTest(kind=kind):
                ident = self.add(typ=kind, indata={
                    "b": 2, "l": 3, "t": .4, "F_vy": 600, "F_vy_bruk": 300,
                    "F_hb": 12, "F_hl": -8, "M_insp_l": 69, "M_insp_b": -34.5,
                    "M_insp_l_bruk": -36, "M_insp_b_bruk": 18,
                    "e_b_plac": .1, "e_l_plac": -.02,
                    "isolering": True, "f_d_brott": 200, "f_d_bruk": 100,
                    # Deprecated API/project inputs must not restore lever-arm moments.
                    "l_h": 100, "l_h_bruk": 200, "F_hb_bruk": 500, "F_hl_bruk": 600,
                })
                details = self.plan.berakna(ident)
                self.assertFalse(removed & self.plan._tag(ident)["values"].keys())
                result = {item["namn"]: item["value"] for item in details["delresultat"]["items"]}
                for phase, normal, moment_b, moment_l in (
                    ("brott", 600 + 1.5 * 25 * 2 * length * .4, 69, -34.5),
                    ("bruk", 300 + 25 * 2 * length * .4, -36, 18),
                ):
                    b_eff = 2 - 2 * abs(.1 + moment_b / normal)
                    l_eff = length - 2 * abs(-.02 + moment_l / normal)
                    self.assertAlmostEqual(result[f"isolering_b_eff_{phase}"], b_eff)
                    self.assertAlmostEqual(result[f"isolering_l_eff_{phase}"], l_eff)
                    if phase == "brott":
                        self.assertAlmostEqual(result["b_ef"], b_eff)
                        self.assertAlmostEqual(result["l_ef"], l_eff)
                    summary = self.plan._tag(ident)["summary"]
                    self.assertAlmostEqual(summary["isolering"][f"isolering_q_Ed_{phase}"], normal / (b_eff * l_eff))
                    area = summary["effective_area"][phase]
                    self.assertEqual((area["Mx"], area["My"]), (moment_l, moment_b))
                    self.assertEqual((area["bx"], area["by"]), (2, length))
                    self.assertAlmostEqual(area["V"], normal)
                    self.assertAlmostEqual(area["ex_moment"], moment_b / normal)
                    self.assertAlmostEqual(area["ey_moment"], moment_l / normal)
                    self.assertAlmostEqual(area["ex"], .1 + moment_b / normal)
                    self.assertAlmostEqual(area["ey"], -.02 + moment_l / normal)
                    self.assertAlmostEqual(area["bx_eff"], b_eff)
                    self.assertAlmostEqual(area["by_eff"], l_eff)
                    self.assertAlmostEqual(area["area"], b_eff * l_eff)
                    # The resultant is the effective rectangle's center and
                    # its edges stay inside the original footing, in either direction.
                    for axis in ("x", "y"):
                        self.assertLessEqual(abs(area["e" + axis]) + area["b" + axis + "_eff"] / 2,
                                             area["b" + axis] / 2 + 1e-12)
                with_horizontal = copy.deepcopy(summary)
                self.plan.uppdatera(ident, indata={"F_hb": 0, "F_hl": 0})
                self.plan.berakna(ident)
                without_horizontal = self.plan._tag(ident)["summary"]
                self.assertEqual(with_horizontal["b_ef"], without_horizontal["b_ef"])
                self.assertEqual(with_horizontal["isolering"], without_horizontal["isolering"])
                self.assertEqual(with_horizontal["effective_area"], without_horizontal["effective_area"])
                if kind == "pelarsula":
                    self.assertLess(with_horizontal["barformaga"], without_horizontal["barformaga"])

    def test_effektiv_area_moment_byter_riktning_och_kan_motverka_placering(self):
        for kind in ("vaggsula", "pelarsula"):
            ident = self.add(typ=kind, indata={"b": 2, "l": 3, "t": .4, "F_vy": 600,
                                               "e_b_plac": .1, "e_l_plac": -.1})
            self.plan.berakna(ident)
            normal = self.plan._tag(ident)["summary"]["last"]
            for dx, dy in ((0, 0), (.2, 0), (0, .2), (-.3, .3), (-.1, .1)):
                with self.subTest(kind=kind, dx=dx, dy=dy):
                    self.plan.uppdatera(ident, indata={"M_insp_l": dx * normal, "M_insp_b": dy * normal})
                    self.plan.berakna(ident)
                    phases = self.plan._tag(ident)["summary"]["effective_area"]
                    self.assertEqual(set(phases), {"brott"})
                    a = phases["brott"]
                    self.assertAlmostEqual(a["ex"], .1 + dx)
                    self.assertAlmostEqual(a["ey"], -.1 + dy)
                    self.assertAlmostEqual(a["bx_eff"], 2 - 2 * abs(.1 + dx))
                    self.assertAlmostEqual(a["by_eff"], (1 if kind == "vaggsula" else 3) - 2 * abs(-.1 + dy))
            loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "axes.json"))
            self.addCleanup(loaded.close)
            self.assertEqual(loaded._tag(ident)["summary"], self.plan._tag(ident)["summary"])

    def test_version_2_tar_bort_havarmar_bevarar_moment_och_beraknas_automatiskt(self):
        ident = self.insulated()
        self.plan.uppdatera(ident, indata={"F_hb": 10, "M_insp_l": 5, "M_insp_l_bruk": -3})
        self.plan.berakna(ident)
        original_values = copy.deepcopy(self.plan._tag(ident)["values"])
        document = self.plan._document()
        document["version"] = 2
        document["tags"][0]["values"].update(l_h=2, l_h_bruk=3, F_hb_bruk=100, F_hl_bruk=200)
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan._tag(ident)["values"], original_values)
        self.assertEqual(self.plan._tag(ident)["status"], "calculated")
        self.assertIsNotNone(self.plan._tag(ident)["summary"])
        self.assertIn(ident, self.plan.resultat)
        self.plan.berakna(ident)
        copied = self.plan.kopiera(ident, .8, .8)
        self.assertEqual(self.plan._tag(copied)["values"], original_values)
        reopened = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "direct-moments.json"))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened._tag(ident), self.plan._tag(ident))
        fields = {field["name"] for field in reopened.schema["fields"]}
        self.assertFalse({"l_h", "l_h_bruk", "F_hb_bruk", "F_hl_bruk"} & fields)

    def test_ui_isolering_beraknas_och_saknad_brukslast_ger_fel(self):
        ident = self.insulated()
        with patch.object(self.plan, "send") as send:
            command = {"action": "calculate", "id": ident, "label": "VS1",
                       "values": self.plan._tag(ident)["values"], "request": 1}
            self.plan._on_message(None, command, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.assertEqual(self.plan._tag(ident)["summary"]["styrande"], "Isolering · bruk")
            command["values"] = {**command["values"], "F_vy_bruk": None}
            self.plan._on_message(None, command, [])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertIn("F_vy_bruk", send.call_args.args[0]["error"])
            self.assertIsNone(self.plan._tag(ident)["summary"])

    def test_fel_ersatter_gammalt_resultat_och_kan_repareras(self):
        ident = self.add()
        self.plan.berakna(ident)
        self.plan.uppdatera(ident, indata={"b": 0})
        with self.assertRaises(ValueError):
            self.plan.berakna(ident)
        self.assertEqual(self.plan.taggar[0]["status"], "error")
        self.assertNotIn(ident, self.plan.resultat)
        self.assertIsNone(self.plan.taggar[0]["summary"])
        self.plan.uppdatera(ident, indata={"b": 1})
        self.plan.berakna(ident)
        self.assertEqual(self.plan.taggar[0]["status"], "calculated")

    def test_ofullstandigt_falt_far_sparas_men_inte_beraknas(self):
        ident = self.add()
        self.plan.uppdatera(ident, indata={"phi_k": None})
        with self.assertRaisesRegex(ValueError, "phi_k"):
            self.plan.berakna(ident)
        file = self.plan.spara(Path(self.tmp.name) / "draft.json")
        loaded = Grundplan.oppna(file)
        self.addCleanup(loaded.close)
        self.assertIsNone(loaded.taggar[0]["values"]["phi_k"])
        self.assertEqual(loaded.resultat, {})

    def test_nan_och_ogiltiga_taggar_avvisas_atomart(self):
        ident = self.add()
        old = self.plan.taggar
        for value in (float("nan"), float("inf"), True, "123"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan.uppdatera(ident, indata={"F_vy": value}, littera="ny")
        self.assertEqual(old, self.plan.taggar)
        for coords in ((-0.1, 0.4), (0.4, 1.1)):
            with self.assertRaises(ValueError):
                self.plan.lagg_till(*coords)
        with self.assertRaises(ValueError):
            self.add(sida=2)
        with self.assertRaises(ValueError):
            self.add(indata={"lang": 3})
        with self.assertRaises(ValueError):
            self.add(littera="")

    def test_noll_barformaga_visar_inte_godkant_resultat(self):
        ident = self.add(indata={"phi_k": 0, "c_prime": 0, "c_uk": 0, "d": 0})
        with self.assertRaisesRegex(ValueError, "inte positiv"):
            self.plan.berakna(ident)
        self.assertIsNone(self.plan.taggar[0]["summary"])

    def test_byta_namn_och_flytta_behaller_resultat(self):
        ident = self.add()
        self.plan.berakna(ident)
        old = self.plan.resultat
        self.plan.uppdatera(ident, littera="VS99", x=0.9, y=0.1)
        self.assertEqual(old, self.plan.resultat)
        self.assertEqual(self.plan.taggar[0]["label"], "VS99")
        self.plan.ta_bort(ident)
        self.assertEqual(self.plan.taggar, [])
        self.assertEqual(self.plan.resultat, {})

    def test_kopia_behaller_alla_indata_och_ar_oberoende_av_originalet(self):
        for typ, prefix in (("vaggsula", "VS"), ("pelarsula", "PS")):
            with self.subTest(typ=typ):
                ident = self.add(typ=typ, indata={
                    "phi_k": 37, "gamma": 19, "gamma_prime": 11,
                    "gamma_m": 1.4, "gamma_Rd": 1.2, "d": 0.5,
                    "F_vy": 230, "b": 1.8, "l": 2.4,
                })
                details = self.plan.berakna(ident)
                source = self.plan._tag(ident)
                snapshot = copy.deepcopy(source)
                copied_id = self.plan.kopiera(ident, 0.8, 0.9)
                copied = self.plan._tag(copied_id)
                self.assertNotEqual(copied_id, ident)
                self.assertEqual(copied["label"], f"{prefix}2")
                self.assertEqual(copied["values"], source["values"])
                self.assertIsNot(copied["values"], source["values"])
                self.assertEqual((copied["x"], copied["y"]), (0.8, 0.9))
                self.assertEqual(copied["status"], "calculated")
                self.assertEqual(copied["summary"], source["summary"])
                self.assertEqual(copied["error"], "")
                self.assertEqual(self.plan.resultat[copied_id], details)
                self.assertEqual(source, snapshot)
                self.assertEqual(self.plan.resultat[ident], details)
                self.plan.uppdatera(copied_id, indata={"F_vy": 400, "b": 2.1})
                self.assertEqual(source, snapshot)
                self.plan.berakna(copied_id)
                self.assertEqual(self.plan.resultat[ident], details)

    def test_kopia_anvander_draft_och_nasta_lediga_littera(self):
        ident = self.add(littera="VS1")
        self.add(littera="VS3")
        source = self.plan.taggar[0]
        draft = {**source["values"], "F_vy": 168, "b": 0.6, "phi_k": None}
        copied_id = self.plan.kopiera(ident, 0.1, 0.2, indata=draft)
        copied = self.plan._tag(copied_id)
        self.assertEqual(copied["values"], draft)
        self.assertEqual(copied["label"], "VS2")
        self.assertEqual(self.plan.taggar[0], source)
        draft["F_vy"] = 999
        self.assertEqual(copied["values"]["F_vy"], 168)
        explicit_id = self.plan.kopiera(ident, 0.5, 0.5, littera="Entrésula", indata={"lang": 0})
        self.assertEqual(self.plan._tag(explicit_id)["label"], "Entrésula")
        self.assertEqual(self.plan._tag(explicit_id)["values"]["lang"], 0)
        with self.assertRaisesRegex(ValueError, "phi_k"):
            self.plan.berakna(copied_id)
        from_error = self.plan.kopiera(copied_id, 0.7, 0.8)
        self.assertEqual(self.plan._tag(from_error)["status"], "error")
        self.assertIn("phi_k", self.plan._tag(from_error)["error"])
        self.assertIsNone(self.plan._tag(from_error)["values"]["phi_k"])

    def test_ogiltig_kopia_andrar_inte_projektet(self):
        ident = self.add()
        self.plan.berakna(ident)
        tags, results = self.plan.taggar, self.plan.resultat
        invalid = [
            {"x": -0.1}, {"y": 1.1}, {"x": float("nan")}, {"sida": 2},
            {"indata": {"F_vy": float("inf")}}, {"indata": {"lang": 3}},
            {"indata": {"unknown": 10}}, {"littera": ""}, {"tagg": "missing"},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.plan.kopiera(**{"tagg": ident, "x": 0.5, "y": 0.6, **kwargs})
            self.assertEqual(self.plan.taggar, tags)
            self.assertEqual(self.plan.resultat, results)

    def test_export_import_med_inbaddad_ritning_och_omraknade_resultat(self):
        ident = self.add(littera="Vägg 2", indata={"F_vy": 120})
        self.plan.berakna(ident)
        path = self.plan.spara(Path(self.tmp.name) / "projekt.json")
        self.path.unlink()
        loaded = Grundplan.oppna(path)
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.taggar, self.plan.taggar)
        self.assertEqual(loaded.resultat, self.plan.resultat)
        self.assertEqual(loaded.background, self.plan.background)

    def test_annan_berakningsversion_beraknas_automatiskt(self):
        ident = self.add()
        self.plan.berakna(ident)
        document = self.plan._document()
        document["calculator_version"] = "old"
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan.taggar[0]["status"], "calculated")
        self.assertIn(ident, self.plan.resultat)

    def test_trasigt_projekt_forstor_inte_oppet_projekt(self):
        ident = self.add()
        self.plan.berakna(ident)
        snapshot = self.plan._document()
        document = copy.deepcopy(snapshot)
        document["tags"].append(copy.deepcopy(document["tags"][0]))
        with self.assertRaises(ValueError):
            self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(snapshot, self.plan._document())

    def test_klientens_resultat_ignoreras(self):
        ident = self.add()
        self.plan.state = {"tags": [{"id": ident, "summary": {"utnyttjandegrad": 0}}]}
        self.assertGreater(self.plan.taggar[0]["summary"]["utnyttjandegrad"], 0)
        self.plan.berakna(ident)
        self.assertGreater(self.plan.taggar[0]["summary"]["utnyttjandegrad"], 0)
        copied = self.plan.taggar
        copied[0]["values"]["b"] = 0
        self.assertGreater(self.plan.taggar[0]["values"]["b"], 0)

    def test_pdf_sidbyte_och_taggar_pa_flera_sidor(self):
        pdf_path = Path(self.tmp.name) / "plan.pdf"
        first = Image.new("RGB", (400, 300), "white")
        second = Image.new("RGB", (300, 400), "gray")
        first.save(pdf_path, save_all=True, append_images=[second])
        plan = Grundplan(pdf_path)
        self.addCleanup(plan.close)
        self.assertEqual(plan.background["page_count"], 2)
        ident = plan.lagg_till(0.2, 0.3)
        first_background = plan.background
        plan.visa_sida(2)
        self.assertNotEqual(first_background["url"], plan.background["url"])
        plan.lagg_till(0.8, 0.4, typ="pelarsula")
        plan.berakna(ident)
        self.assertEqual([tag["page"] for tag in plan.taggar], [1, 2])
        with self.assertRaises(ValueError):
            plan.visa_sida(3)
        self.assertEqual(plan.background["page"], 2)

    def test_kopiera_till_kallans_eller_vald_sida_och_spara_position(self):
        pdf_path = Path(self.tmp.name) / "copy.pdf"
        Image.new("RGB", (400, 300), "white").save(
            pdf_path, save_all=True, append_images=[Image.new("RGB", (300, 400), "gray")]
        )
        plan = Grundplan(pdf_path)
        self.addCleanup(plan.close)
        original = plan.lagg_till(0.2, 0.3)
        plan.berakna(original)
        plan.visa_sida(2)
        same_page = plan.kopiera(original, 0.7, 0.8)
        other_page = plan.kopiera(original, 0.4, 0.5, sida=2)
        plan.uppdatera(original, x=0.1, y=0.9)
        self.assertEqual([tag["page"] for tag in plan.taggar], [1, 1, 2])
        loaded = Grundplan.oppna(plan.spara(Path(self.tmp.name) / "copy.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.background["page"], 2)
        self.assertEqual(loaded._tag(original), plan._tag(original))
        for ident in (same_page, other_page):
            for field in ("id", "label", "x", "y", "page", "values", "summary"):
                self.assertEqual(loaded._tag(ident)[field], plan._tag(ident)[field])
            self.assertIn(ident, loaded.resultat)
            self.assertEqual(loaded._tag(ident)["status"], "calculated")

    def test_ui_flytta_och_kopiera_med_osparade_indata(self):
        original = self.add()
        self.plan.berakna(original)
        results = self.plan.resultat
        draft = {**self.plan.taggar[0]["values"], "F_vy": 168, "b": 0.6}
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {
                "action": "update", "id": original, "x": 0.7, "y": 0.8,
                "view": "test", "request": 10,
            }, [])
            self.assertEqual(send.call_args.args[0], {"ok": True, "view": "test", "request": 10})
            self.assertEqual((self.plan.taggar[0]["x"], self.plan.taggar[0]["y"]), (0.7, 0.8))
            self.assertEqual(self.plan.taggar[0]["status"], "calculated")
            self.assertEqual(self.plan.resultat, results)
            source = self.plan.taggar[0]
            self.plan._on_message(None, {
                "action": "copy", "id": original, "x": 0.1, "y": 0.2, "page": 1,
                "values": draft, "view": "test", "request": 11,
            }, [])
            reply = send.call_args.args[0]
            self.assertTrue(reply["ok"])
            self.assertEqual((reply["view"], reply["request"]), ("test", 11))
            self.assertEqual(self.plan._tag(reply["id"])["values"], draft)
            self.assertEqual(self.plan._tag(reply["id"])["status"], "calculated")
            self.assertEqual(self.plan.taggar[0], source)
            self.plan._on_message(None, {
                "action": "copy", "id": original, "x": 0.1, "y": 0.2, "page": 2,
                "values": draft, "view": "test", "request": 12,
            }, [])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertEqual(len(self.plan.taggar), 2)
            self.assertEqual(self.plan.resultat[original], results[original])
            self.assertIn(reply["id"], self.plan.resultat)

    def test_etikettstorlek_sparas_utan_att_paverka_berakningar(self):
        self.assertEqual(self.plan.etikettstorlek, 100)
        self.assertEqual(self.plan.state["label_size"], 100)
        ident = self.add()
        self.plan.berakna(ident)
        tags, results = self.plan.taggar, self.plan.resultat
        self.plan.etikettstorlek = 140
        self.assertEqual(self.plan.etikettstorlek, 140)
        self.assertEqual(self.plan.state["label_size"], 140)
        self.assertEqual(self.plan.taggar, tags)
        self.assertEqual(self.plan.resultat, results)
        loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "size.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.etikettstorlek, 140)
        self.assertEqual(loaded.taggar, tags)
        self.assertEqual(loaded.resultat, results)
        old_document = self.plan._document()
        del old_document["label_size"]
        loaded._load_document(json.dumps(old_document).encode())
        self.assertEqual(loaded.etikettstorlek, 100)
        self.assertEqual(loaded.state["label_size"], 100)

    def test_ogiltig_etikettstorlek_avvisas_atomart(self):
        ident = self.add()
        self.plan.berakna(ident)
        self.plan.etikettstorlek = 120
        snapshot, state, results = self.plan._document(), copy.deepcopy(self.plan.state), self.plan.resultat
        for value in (59, 181, float("nan"), float("inf"), True, None, "120"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.plan.etikettstorlek = value
                document = {**snapshot, "label_size": value}
                with self.assertRaises(ValueError):
                    self.plan._load_document(json.dumps(document).encode())
                self.assertEqual(self.plan.etikettstorlek, 120)
                self.assertEqual(self.plan.state, state)
                self.assertEqual(self.plan._document(), snapshot)
                self.assertEqual(self.plan.resultat, results)
        for value in (60, 180):
            self.plan.etikettstorlek = value
            self.assertEqual(self.plan.etikettstorlek, value)

    def test_ui_etikettstorlek_andrar_bara_presentationen(self):
        ident = self.add()
        self.plan.berakna(ident)
        tags, results = self.plan.taggar, self.plan.resultat
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {
                "action": "label_size", "value": 80, "view": "test", "request": 20,
            }, [])
            self.assertEqual(send.call_args.args[0], {"ok": True, "view": "test", "request": 20})
            self.assertEqual(self.plan.state["label_size"], 80)
            self.plan._on_message(None, {
                "action": "label_size", "value": 0, "view": "test", "request": 21,
            }, [])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertEqual(self.plan.etikettstorlek, 80)
            self.assertEqual(self.plan.taggar, tags)
            self.assertEqual(self.plan.resultat, results)

    def test_ui_meddelanden_berakna_spara_och_upload(self):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {
                "action": "add", "x": 0.4, "y": 0.5, "kind": "vaggsula",
                "view": "test", "request": 1,
            }, [])
            reply = send.call_args.args[0]
            self.assertTrue(reply["ok"])
            ident = reply["id"]
            self.plan._on_message(None, {
                "action": "calculate", "id": ident, "label": "VS2",
                "values": self.plan.taggar[0]["values"], "request": 2,
            }, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.plan._on_message(None, {"action": "save", "request": 3}, [])
            payload = send.call_args.args[0]["download"].encode()
            self.plan._on_message(None, {"action": "open", "request": 4}, [memoryview(payload)])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.assertEqual(self.plan.taggar[0]["status"], "calculated")
            self.plan._on_message(None, {"action": "drawing", "name": "other.png"}, [self.path.read_bytes()])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertEqual(self.plan.taggar[0]["label"], "VS2")


if __name__ == "__main__":
    unittest.main()
