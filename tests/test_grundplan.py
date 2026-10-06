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
                self.assertEqual(copied["status"], "new")
                self.assertIsNone(copied["summary"])
                self.assertEqual(copied["error"], "")
                self.assertNotIn(copied_id, self.plan.resultat)
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
        self.assertEqual(self.plan._tag(from_error)["status"], "new")
        self.assertEqual(self.plan._tag(from_error)["error"], "")
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
            self.assertNotIn(ident, loaded.resultat)
            self.assertNotEqual(loaded._tag(ident)["status"], "calculated")

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
            self.assertEqual(self.plan._tag(reply["id"])["status"], "new")
            self.assertEqual(self.plan.taggar[0], source)
            self.plan._on_message(None, {
                "action": "copy", "id": original, "x": 0.1, "y": 0.2, "page": 2,
                "values": draft, "view": "test", "request": 12,
            }, [])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertEqual(len(self.plan.taggar), 2)
            self.assertEqual(self.plan.resultat, results)

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
