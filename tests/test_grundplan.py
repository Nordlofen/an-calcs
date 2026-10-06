import copy
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
            values[name] for name in allmanna_barighetsekvationen.panel_schema["px"]
        ])
        self.assertEqual(details, expected)
        self.assertEqual(self.plan.taggar[0]["summary"]["lastenhet"], "kN/m")
        self.assertEqual(self.plan.taggar[1]["status"], "new")
        self.plan.berakna(second)
        summary = self.plan.taggar[1]["summary"]
        self.assertEqual(summary["lastenhet"], "kN")
        self.assertAlmostEqual(summary["utnyttjandegrad"], summary["last"] / summary["barformaga"])
        self.plan.uppdatera(first, indata={"b": 1.1})
        self.assertEqual(self.plan.taggar[1]["values"]["b"], 2)
        self.assertIn(second, self.plan.resultat)
        self.assertNotIn(first, self.plan.resultat)
        self.assertIsNone(self.plan.taggar[0]["summary"])

    def test_vaggsula_ar_en_meters_remsa_och_egentyngd_ingår(self):
        ident = self.add(indata={"F_vy": 100, "b": 0.8, "t": 0.4, "l": 25})
        self.plan.berakna(ident)
        first = self.plan.taggar[0]["summary"]
        self.assertAlmostEqual(first["last"], 100 + 1.5 * 25 * 0.8 * 0.4)
        self.plan.uppdatera(ident, indata={"l": 1})
        self.plan.berakna(ident)
        self.assertEqual(first, self.plan.taggar[0]["summary"])

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

    def test_annan_berakningsversion_kraver_ny_berakning(self):
        ident = self.add()
        self.plan.berakna(ident)
        document = self.plan._document()
        document["calculator_version"] = "old"
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan.taggar[0]["status"], "stale")
        self.assertEqual(self.plan.resultat, {})

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
        self.assertIsNone(self.plan.taggar[0]["summary"])
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
