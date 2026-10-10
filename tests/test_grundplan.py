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

    def test_drawing_text_commands_are_independent_of_footings_and_calculations(self):
        self.add()
        before = self.plan.taggar, self.plan.resultat
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("No calculation")), patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "text_add", "kind": "heading", "x": .1, "y": .2}, [])
            ident = send.call_args.args[0]["id"]
            with patch("an_calcs.notebook.grundplan.today_text", return_value="26/10/08"):
                self.plan._on_message(None, {"action": "text_add", "kind": "date"}, [])
            date_id = send.call_args.args[0]["id"]
            self.assertEqual(self.plan.textobjekt[1]["text"], "26/10/08")
            self.plan._on_message(None, {"action": "text_update", "id": ident,
                "changes": {"text": "Grundsulor – Hus 1", "subtitle": "Revision A\nKontroll av bärighet", "x": .3, "y": .4, "size": 42}}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.assertEqual(self.plan.textobjekt[0]["text"], "Grundsulor – Hus 1")
            self.assertEqual(self.plan.textobjekt[0]["subtitle"], "Revision A\nKontroll av bärighet")
            self.assertEqual(self.plan.state["text_objects"][0]["size"], 42)
            copied = self.plan.textobjekt; copied[0]["text"] = "Ändrat"
            self.assertNotEqual(self.plan.textobjekt, copied)
            self.plan._on_message(None, {"action": "text_delete", "id": date_id}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
            self.assertEqual(len(self.plan.textobjekt), 1)
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)

    def test_drawing_text_roundtrip_replacement_and_legacy_project(self):
        ident = self.plan.lagg_till_rubrik("Rubrik med åäö", underrubrik="Underrubrik\n" + "Lång text " * 40, x=.25, y=.35, storlek=40, bredd=1150)
        self.plan.lagg_till_datum("25/12/31", x=.6, y=.7, storlek=24)
        self.plan.uppdatera_text(ident, text="Revision B", size=48)
        loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "text.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.textobjekt, self.plan.textobjekt)
        loaded.importera_ritning(self.path)
        self.assertEqual(loaded.textobjekt, self.plan.textobjekt)
        without_subtitle = self.plan._document()
        without_subtitle["version"] = 13
        for item in without_subtitle["text_objects"]:
            del item["subtitle"]
            del item["width"]
        loaded._load_document(json.dumps(without_subtitle).encode())
        self.assertEqual([item["subtitle"] for item in loaded.textobjekt], ["", ""])
        self.assertEqual([item["width"] for item in loaded.textobjekt], [420, 420])
        legacy = self.plan._document(); legacy["version"] = 12; del legacy["text_objects"]
        loaded._load_document(json.dumps(legacy).encode())
        self.assertEqual(loaded.textobjekt, [])

    def test_add_heading_copies_existing_text_and_protocol_can_capture_pending_header_edits(self):
        self.plan.titel = "Grundläggningssulor - Hus 1"
        self.plan.underrubrik = "26017 - Norrbodahöjden\nKontroller: bärighet, isolering och glidning\n" + "Kommentar " * 40
        self.plan.lagg_till_rubrik(bredd=1300)
        copied = self.plan.textobjekt[0]
        self.assertEqual((copied["text"], copied["subtitle"], copied["size"], copied["width"]),
                         (self.plan.titel, self.plan.underrubrik, 20, 1300))
        self.plan.titel = "Revision B"
        self.assertEqual(self.plan.textobjekt[0], copied, "A placed copy keeps its saved contents")
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "text_add", "kind": "heading", "text": "Ny rubrik",
                "subtitle": "Senast skriven text\nRad två", "width": 1200}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
        self.assertEqual(self.plan.textobjekt[-1]["text"], "Ny rubrik")
        self.assertEqual(self.plan.textobjekt[-1]["subtitle"], "Senast skriven text\nRad två")
        self.assertEqual(self.plan.textobjekt[-1]["width"], 1200)

    def test_default_drawing_date_uses_stockholm_timezone_and_two_digit_year(self):
        from datetime import datetime
        from an_calcs.notebook.grundplan_text import today_text
        with patch("an_calcs.notebook.grundplan_text.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 8, 0, 1)
            self.assertEqual(today_text(), "26/10/08")
            self.assertEqual(clock.now.call_args.args[0].key, "Europe/Stockholm")

    def test_invalid_text_updates_and_project_leave_existing_text_intact(self):
        ident = self.plan.lagg_till_rubrik()
        original = self.plan._document()
        for changes in ({"x": -1}, {"y": float("nan")}, {"size": True}, {"size": 0}, {"text": 12}, {"subtitle": 12},
                        {"kind": "date"}, {"width": 0}, {"width": True}, {"width": float("inf")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan.uppdatera_text(ident, **changes)
            self.assertEqual(self.plan._document(), original)
        invalid = copy.deepcopy(original); invalid["text_objects"].append(copy.deepcopy(invalid["text_objects"][0]))
        with self.assertRaises(ValueError):
            self.plan._load_document(json.dumps(invalid).encode())
        self.assertEqual(self.plan._document(), original)
        empty = Grundplan(); self.addCleanup(empty.close)
        with self.assertRaisesRegex(ValueError, "ritning"):
            empty.lagg_till_datum()
        date = self.plan.lagg_till_datum()
        with self.assertRaisesRegex(ValueError, "Underrubrik"):
            self.plan.uppdatera_text(date, subtitle="Ej en rubrik")

    def test_calibration_is_saved_restored_and_does_not_change_calculations(self):
        self.add()
        tags, results = self.plan.taggar, self.plan.resultat
        value = {"start": {"x": .1, "y": .2}, "end": {"x": .6, "y": .2}, "length_m": 10}
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("No calculation")), patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "calibration", "calibration": value, "request": 9}, [])
            self.assertTrue(send.call_args.args[0]["ok"])
        self.assertEqual(self.plan.kalibrering, value)
        self.assertEqual(self.plan.state["calibration"], value)
        self.assertEqual((self.plan.taggar, self.plan.resultat), (tags, results))
        value["start"]["x"] = .8
        copied = self.plan.kalibrering
        copied["end"]["x"] = .9
        self.assertEqual(self.plan.kalibrering["start"]["x"], .1)
        self.assertEqual(self.plan.kalibrering["end"]["x"], .6)
        loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "measurement.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.kalibrering, self.plan.kalibrering)
        legacy = self.plan._document()
        del legacy["calibration"]
        loaded._load_document(json.dumps(legacy).encode())
        self.assertIsNone(loaded.kalibrering)
        self.plan._set_source(self.path.read_bytes(), self.path.name)
        self.plan._publish()
        self.assertIsNone(self.plan.state["calibration"])

    def test_invalid_calibration_does_not_replace_project_or_previous_reference(self):
        self.add()
        valid = {"start": {"x": .1, "y": .2}, "end": {"x": .6, "y": .2}, "length_m": 10}
        self.plan.kalibrering = valid
        original = self.plan._document()
        invalid = [None, "10", 0, -1, float("nan"), float("inf"), True]
        candidates = [{**valid, "length_m": length} for length in invalid]
        candidates += [[], {}, {**valid, "start": None}, {**valid, "end": valid["start"]},
                       {**valid, "end": {"x": 12, "y": .2}},
                       {**valid, "end": {"x": False, "y": .2}},
                       {**valid, "end": {"x": .6, "y": float("nan")}}]
        for value in candidates:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.plan.kalibrering = value
                self.assertEqual(self.plan._document(), original)
                with self.assertRaises(ValueError):
                    self.plan._load_document(json.dumps({**original, "calibration": value}).encode())
                self.assertEqual(self.plan._document(), original)
        empty = Grundplan()
        self.addCleanup(empty.close)
        with self.assertRaisesRegex(ValueError, "ritning"):
            empty.kalibrering = valid

    def test_taggar_ar_oberoende_och_resultatet_anvander_befintlig_motor(self):
        first = self.add(littera="VS2", indata={"F_vy": 100, "b": 0.8})
        second = self.add(typ="pelarsula", indata={"F_vy": 600, "b": 2, "l": 3})
        details = self.plan.berakna(first)
        values = self.plan.taggar[0]["values"]
        expected = allmanna_barighetsekvationen([
            0.0 if name == "l_h" else values[name] for name in allmanna_barighetsekvationen.panel_schema["px"]
        ])
        for section in ("indata", "delresultat", "slutresultat", "ekvationer"):
            self.assertEqual(details[section], expected[section])
        self.assertEqual(self.plan.taggar[0]["summary"]["lastenhet"], "kN")
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
        ident = self.add(indata={"F_vy": 100, "b": 0.8, "t": 0.4})
        self.plan.berakna(ident)
        first = self.plan.taggar[0]["summary"]
        self.assertAlmostEqual(first["last"], 100 + 1.5 * 25 * 0.8 * 0.4)
        self.assertEqual(self.plan._tag(ident)["values"]["l"], 1)
        self.plan.uppdatera(ident, indata={"l": 2.5})
        self.plan.berakna(ident)
        second = self.plan.taggar[0]["summary"]
        for name in ("lastenhet", "q_bd", "b_ef"):
            self.assertEqual(first[name], second[name])
        self.assertAlmostEqual(second["last"], 100 + 1.5 * 25 * .8 * .4 * 2.5)
        self.assertAlmostEqual(second["barformaga"], first["barformaga"] * 2.5)
        self.assertLess(second["utnyttjandegrad"], first["utnyttjandegrad"])
        self.assertEqual(second["load_conversion"]["brott"], 100)
        self.assertEqual(second["effective_area"]["brott"]["by"], 2.5)

    def test_wall_by_override_changes_effective_area_without_scaling_line_loads_or_sliding(self):
        ident = self.add(indata={"b": 1, "t": .4, "F_vy": 100, "F_vy_bruk": 60,
                                "isolering": True, "f_d_brott": 200, "f_d_bruk": 100,
                                "M_insp_b": 11.5, "M_insp_b_bruk": 7,
                                "V_Ed_EQU": 80, "glid_mu": .4, "glid_L": 3, "glid_x": True})
        original = self.plan._tag(ident)["summary"]
        sliding = self.plan.taggar[0]["sliding"]
        self.plan.uppdatera(ident, indata={"l": 2.5})
        summary = self.plan._tag(ident)["summary"]
        for phase, normal, moment in (("brott", 137.5, 11.5), ("bruk", 85, 7)):
            area = summary["effective_area"][phase]
            self.assertAlmostEqual(area["by"], 2.5)
            self.assertAlmostEqual(area["ey_moment"], moment / normal)
            self.assertAlmostEqual(area["by_eff"], 2.5 - 2 * moment / normal)
            self.assertAlmostEqual(summary["isolering"]["isolering_q_Ed_" + phase], normal / area["by_eff"])
            self.assertLess(summary["isolering"]["isolering_q_Ed_" + phase], original["isolering"]["isolering_q_Ed_" + phase])
        self.assertEqual(summary["load_conversion"]["brott"], original["load_conversion"]["brott"])
        self.assertEqual(self.plan.taggar[0]["sliding"], sliding)
        copied = self.plan.kopiera(ident, .7, .8)
        self.assertEqual(self.plan._tag(copied)["values"]["l"], 2.5)
        reopened = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "by.json"))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.taggar, self.plan.taggar)
        self.assertEqual(reopened.resultat, self.plan.resultat)
        self.plan.uppdatera(ident, indata={"l": 0})
        self.assertEqual(self.plan._tag(ident)["status"], "error")
        self.assertIsNone(self.plan._tag(ident)["summary"])

    def test_wall_by_override_spreads_fixed_resultant_and_changes_centred_insulation_pressure(self):
        ident = self.insulated()
        first = self.plan._tag(ident)["summary"]
        self.plan.uppdatera(ident, indata={"l": .5})
        second = self.plan._tag(ident)["summary"]
        self.assertEqual(second["load_conversion"]["brott"], first["load_conversion"]["brott"])
        self.assertEqual(second["load_conversion"]["bruk"], first["load_conversion"]["bruk"])
        self.assertAlmostEqual(second["isolering"]["isolering_q_Ed_brott"], 100 / .5 + 15)
        self.assertAlmostEqual(second["isolering"]["isolering_q_Ed_bruk"], 70 / .5 + 10)
        self.assertGreater(second["utnyttjandegrad"], first["utnyttjandegrad"])

    def test_old_projects_keep_one_metre_wall_reference_instead_of_unused_pad_length(self):
        wall = self.add()
        pad = self.add(typ="pelarsula", indata={"l": 3})
        original = self.plan.taggar, self.plan.resultat
        for version in (1, 2, 3, 4):
            document = self.plan._document()
            document["version"] = version
            document["tags"][0]["values"]["l"] = 12
            self.plan._load_document(json.dumps(document).encode())
            self.assertEqual(self.plan._tag(wall)["values"]["l"], 1)
            self.assertEqual(self.plan._tag(pad)["values"]["l"], 3)
            self.assertEqual((self.plan.taggar, self.plan.resultat), original)

    def test_default_by_depends_on_model_and_physical_pad_cannot_use_wall_model(self):
        with self.assertRaisesRegex(ValueError, "bara väljas"):
            self.add(typ="pelarsula", indata={"lang": 1})
        wall = self.add(typ="vaggsula", indata={"lang": 1})
        pad = self.add(indata={"lang": 0})
        self.assertEqual(self.plan._tag(wall)["values"]["l"], 1)
        self.assertEqual(self.plan._tag(pad)["values"]["l"],
                         allmanna_barighetsekvationen.panel_schema["fields"][1]["default"])

    def test_wall_own_length_toggle_resets_calculation_and_survives_copy_and_reload(self):
        ident = self.insulated()
        original = copy.deepcopy(self.plan._tag(ident)["summary"])
        self.assertIs(self.plan._tag(ident)["values"]["l_override"], False)
        self.plan.uppdatera(ident, indata={"l_override": True, "l": 2.5})
        self.assertEqual(self.plan._tag(ident)["summary"]["effective_area"]["brott"]["by"], 2.5)
        copied = self.plan.kopiera(ident, .6, .5)
        self.assertIs(self.plan._tag(copied)["values"]["l_override"], True)
        self.plan.uppdatera(ident, indata={"l_override": False})
        self.assertEqual(self.plan._tag(ident)["values"]["l"], 1)
        self.assertEqual(self.plan._tag(ident)["summary"], original)
        self.plan.uppdatera(copied, indata={"l_override": False, "l": 9})
        self.assertEqual(self.plan._tag(copied)["values"]["l"], 1)
        reopened = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "by-checkbox.json"))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.taggar, self.plan.taggar)
        for value in (1, "true", None):
            with self.assertRaises(ValueError):
                self.plan.uppdatera(ident, indata={"l_override": value})

    def test_version_five_activates_checkbox_for_existing_custom_wall_length(self):
        ident = self.add(indata={"l": 2.5})
        pad = self.add(typ="pelarsula", indata={"l": 3})
        original = self.plan.taggar
        document = self.plan._document()
        document["version"] = 5
        for tag in document["tags"]:
            del tag["values"]["l_override"]
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan.taggar, original)
        self.assertIs(self.plan._tag(ident)["values"]["l_override"], True)
        self.assertIs(self.plan._tag(pad)["values"]["l_override"], False)

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
        for section in ("indata", "delresultat", "slutresultat", "ekvationer"):
            self.assertEqual(details[section], expected[section])
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
        self.assertEqual(loaded._document()["version"], 24)
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
                    "b": 2, "l": length, "t": .4, "F_vy": 600, "F_vy_bruk": 300,
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
            ident = self.add(typ=kind, indata={"b": 2, "l": 1 if kind == "vaggsula" else 3, "t": .4, "F_vy": 600,
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

    def test_pdf_pages_use_independent_cells_and_keys(self):
        pdf_path = Path(self.tmp.name) / "plan.pdf"
        first = Image.new("RGB", (400, 300), "white")
        second = Image.new("RGB", (300, 400), "gray")
        first.save(pdf_path, save_all=True, append_images=[second])
        state_file = Path(self.tmp.name) / "pages.json"
        plan = Grundplan(pdf_path, key="Sida 1", state_file=state_file)
        self.addCleanup(plan.close)
        self.assertEqual(plan.background["page_count"], 2)
        ident = plan.lagg_till(0.2, 0.3, indata={"glid_x": True, "V_Ed_EQU": 100,
                                               "glid_mu": .4, "glid_L": 3})
        other = Grundplan(pdf_path, key="Sida 2", state_file=state_file, sida=2)
        self.addCleanup(other.close)
        other_id = other.lagg_till(0.8, 0.4, typ="pelarsula",
                                  indata={"glid_x": True, "V_Ed_EQU": 240, "glid_mu": .4})
        self.assertNotEqual(plan.background["url"], other.background["url"])
        self.assertEqual([tag["page"] for tag in plan.taggar], [1])
        self.assertEqual([tag["page"] for tag in other.taggar], [2])
        self.assertEqual(plan.glidningsresultat["x"]["H_Rd"], 120)
        self.assertEqual(other.glidningsresultat["x"]["H_Rd"], 96)
        for operation in (lambda: plan.visa_sida(2), lambda: plan.lagg_till(.5, .5, sida=2),
                          lambda: plan.kopiera(ident, .5, .5, sida=2)):
            with self.assertRaisesRegex(ValueError, "en enda ritningssida"):
                operation()
        plan.spara()
        other.spara()
        for key, page, tag_id in (("Sida 1", 1, ident), ("Sida 2", 2, other_id)):
            loaded = Grundplan(key=key, state_file=state_file)
            self.addCleanup(loaded.close)
            self.assertEqual(loaded.background["page"], page)
            self.assertEqual([tag["id"] for tag in loaded.taggar], [tag_id])

    def test_ui_upload_uses_page_selected_by_constructor(self):
        pdf_path = Path(self.tmp.name) / "upload.pdf"
        Image.new("RGB", (400, 300), "white").save(
            pdf_path, save_all=True, append_images=[Image.new("RGB", (300, 400), "gray")])
        state_file = Path(self.tmp.name) / "empty.json"
        empty = Grundplan(sida=2, key="Sida 2", state_file=state_file)
        self.addCleanup(empty.close)
        empty.spara()
        plan = Grundplan(key="Sida 2", state_file=state_file)
        self.addCleanup(plan.close)
        plan._on_message(None, {"action": "drawing", "name": "upload.pdf"}, [pdf_path.read_bytes()])
        self.assertEqual(plan.background["page"], 2)
        self.assertEqual(plan.background["width"], 600)

    def test_drawing_replacement_preserves_footings_results_and_overlays(self):
        self.add(indata={"b": .8, "F_vy": 100, "glid_x": True, "V_Ed_EQU": 80,
                         "glid_mu": .4, "glid_L": 5})
        self.add(typ="pelarsula", littera="PS1", indata={"F_vy": 200, "b": 1.5, "l": 2})
        self.plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 100,
                             "placements": {"1": {"symbol": {"x": .2, "y": .7, "size": 180},
                                                    "legend": {"x": .5, "y": .1, "size": 350}}}}
        self.plan.kalibrering = {"start": {"x": .1, "y": .1}, "end": {"x": .6, "y": .1}, "length_m": 10}
        self.plan.underrubrik = "Revision B\nGrundläggning"
        self.plan.etikettstorlek = 120
        tags, results, gliding = self.plan.taggar, self.plan.resultat, self.plan.glidning
        replacement = Path(self.tmp.name) / "revision_b.png"
        Image.new("RGB", (1200, 500), "#d3eadc").save(replacement)
        with patch("an_calcs.notebook.grundplan._calculate", side_effect=AssertionError("Must not recalculate")):
            self.plan.importera_ritning(replacement)
        self.assertEqual((self.plan.taggar, self.plan.resultat, self.plan.glidning), (tags, results, gliding))
        self.assertIsNone(self.plan.kalibrering)
        self.assertEqual(self.plan.background["name"], replacement.name)
        self.assertEqual((self.plan.background["width"], self.plan.background["height"]), (800, 600))
        self.assertEqual((self.plan.background["source_width"], self.plan.background["source_height"]), (1200, 500))
        self.assertEqual(self.plan._source, replacement.read_bytes())
        restored = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "updated.json"))
        self.addCleanup(restored.close)
        self.assertEqual(restored._document(), self.plan._document())

    def test_invalid_drawing_replacement_leaves_project_and_results_intact(self):
        self.add()
        self.plan.kalibrering = {"start": {"x": .1, "y": .1}, "end": {"x": .6, "y": .1}, "length_m": 10}
        original = self.plan._document(), self.plan.resultat, copy.deepcopy(self.plan.background)
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "drawing", "name": "broken.pdf"}, [b"broken"])
            self.assertFalse(send.call_args.args[0]["ok"])
        self.assertEqual((self.plan._document(), self.plan.resultat, self.plan.background), original)

    def test_drawing_update_keeps_selected_page_or_moves_overlays_and_footings_to_first_page(self):
        pdf_path = Path(self.tmp.name) / "two-pages.pdf"
        Image.new("RGB", (400, 300), "white").save(
            pdf_path, save_all=True, append_images=[Image.new("RGB", (300, 400), "gray")])
        plan = Grundplan(pdf_path, sida=2)
        self.addCleanup(plan.close)
        ident = plan.lagg_till(.2, .3)
        position = {"x": .1, "y": .7, "size": 190}
        plan.glidning = {"placements": {"2": {"symbol": position}}}
        plan.importera_ritning(pdf_path)
        self.assertEqual(plan.background["page"], 2)
        plan.importera_ritning(self.path)
        self.assertEqual(plan.background["page"], 1)
        self.assertEqual(plan._tag(ident)["page"], 1)
        self.assertEqual((plan._tag(ident)["x"], plan._tag(ident)["y"]), (.2, .3))
        self.assertEqual(plan.glidning["placements"], {"1": {"symbol": position}})
        restored = Grundplan.oppna(plan.spara(Path(self.tmp.name) / "single-page.json"))
        self.addCleanup(restored.close)
        self.assertEqual(restored._document(), plan._document())

    def test_old_multi_page_project_is_rejected_without_losing_current_data(self):
        pdf_path = Path(self.tmp.name) / "old.pdf"
        Image.new("RGB", (400, 300), "white").save(
            pdf_path, save_all=True, append_images=[Image.new("RGB", (300, 400), "gray")])
        plan = Grundplan(pdf_path)
        self.addCleanup(plan.close)
        plan.lagg_till(.2, .3)
        before = plan._document()
        old = copy.deepcopy(before)
        extra = copy.deepcopy(old["tags"][0])
        extra.update(id="other-page", page=2)
        old["tags"].append(extra)
        with self.assertRaisesRegex(ValueError, "separat projekt per sida"):
            plan._load_document(json.dumps(old).encode())
        self.assertEqual(plan._document(), before)

    def test_copies_stay_on_the_selected_page_and_restore_positions(self):
        pdf_path = Path(self.tmp.name) / "copy.pdf"
        Image.new("RGB", (400, 300), "white").save(
            pdf_path, save_all=True, append_images=[Image.new("RGB", (300, 400), "gray")]
        )
        plan = Grundplan(pdf_path, sida=2)
        self.addCleanup(plan.close)
        original = plan.lagg_till(0.2, 0.3)
        plan.berakna(original)
        same_page = plan.kopiera(original, 0.7, 0.8)
        explicit_page = plan.kopiera(original, 0.4, 0.5, sida=2)
        plan.uppdatera(original, x=0.1, y=0.9)
        self.assertEqual([tag["page"] for tag in plan.taggar], [2, 2, 2])
        loaded = Grundplan.oppna(plan.spara(Path(self.tmp.name) / "copy.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.background["page"], 2)
        self.assertEqual(loaded._tag(original), plan._tag(original))
        for ident in (same_page, explicit_page):
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
        for value in (19, 181, float("nan"), float("inf"), True, None, "120"):
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
        for value in (20, 180):
            self.plan.etikettstorlek = value
            self.assertEqual(self.plan.etikettstorlek, value)
            loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "size-limit.json"))
            self.addCleanup(loaded.close)
            self.assertEqual(loaded.etikettstorlek, value)

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
            self.assertTrue(send.call_args.args[0]["ok"])
            self.assertTrue(send.call_args.args[0]["updated"])
            self.assertEqual(self.plan.taggar[0]["label"], "VS2")


if __name__ == "__main__":
    unittest.main()
