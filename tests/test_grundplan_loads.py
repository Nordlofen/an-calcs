import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from an_calcs.notebook.grundplan_loads import read_loads

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


def document():
    return {"schemaVersion": 1, "distribution": "uniform", "model": "/unused/model.str", "component": "z'",
            "supports": [
                {"supportId": label, "type": kind,
                 **({"length": {"value": 6.2, "unit": "m"}} if kind == "line" else {}),
                 "results": [{"category": category, "V": value, "unit": "kN/m" if kind == "line" else "kN",
                              "source": {"kind": "loadCombination", "loadCombination": "1"}}
                             for category, value in zip(("Brott", "Bruk", "EQU"), loads)]}
                for label, kind, loads in [("W1", "line", (80, 25, 30)), ("P1", "point", (120, 50, 60))]]}


def encode(doc):
    return json.dumps(doc).encode()


class TestLoadParser(unittest.TestCase):
    def test_maps_categories_types_and_length_without_multiplying_or_reading_model(self):
        data = document()
        before = copy.deepcopy(data)
        items = read_loads(encode(data))
        self.assertEqual(items, [
            {"label": "W1", "kind": "vaggsula", "values": {"lasttyp": 1, "F_vy": 80, "F_vy_bruk": 25, "V_Ed_EQU": 30, "glid_L": 6.2, "L_vagg": 6.2, "L_vagg_minst_1": True}},
            {"label": "P1", "kind": "pelarsula", "values": {"lasttyp": 0, "F_vy": 120, "F_vy_bruk": 50, "V_Ed_EQU": 60}}])
        self.assertEqual(data, before)
        self.assertEqual(read_loads(b"\xef\xbb\xbf" + encode(data)), items)

    def test_order_zero_negative_signs_and_shuffled_categories_are_preserved(self):
        data = document()
        data["supports"].reverse()
        data["supports"][0]["results"][0]["V"] = -10.5
        data["supports"][0]["results"][1]["V"] = 0
        data["supports"][0]["results"].reverse()
        items = read_loads(encode(data))
        self.assertEqual([item["label"] for item in items], ["P1", "W1"])
        self.assertEqual(items[0]["values"], {"lasttyp": 0, "V_Ed_EQU": 60, "F_vy_bruk": 0, "F_vy": -10.5})

    def test_units_missing_categories_duplicates_and_bad_geometry_are_rejected(self):
        def invalid(field, value):
            data = document()
            target = data
            for part in field[:-1]:
                target = target[part]
            target[field[-1]] = value
            return data
        cases = [
            invalid(["schemaVersion"], True), invalid(["schemaVersion"], 2),
            invalid(["supports"], []), invalid(["supports", 0, "type"], "area"),
            invalid(["supports", 0, "supportId"], ""), invalid(["supports", 1, "supportId"], " W1 "),
            invalid(["supports", 0, "length", "value"], 0),
            invalid(["supports", 0, "length", "value"], float("nan")),
            invalid(["supports", 0, "length", "unit"], "mm"),
            invalid(["distribution"], "variable"),
            invalid(["supports", 0, "results"], []),
            invalid(["supports", 0, "results", 1, "category"], "Brott"),
            invalid(["supports", 0, "results", 0, "unit"], "kN"),
            invalid(["supports", 1, "results", 0, "unit"], "kN/m"),
            invalid(["supports", 1, "results", 0, "V"], True),
            invalid(["supports", 1, "results", 0, "V"], "120"),
            invalid(["supports", 1, "results", 0, "V"], float("inf"))]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                read_loads(encode(data))
        for raw in (b"bad json", b"\xff", b"[]", b'{"schemaVersion":1,"schemaVersion":1}', b""):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_loads(raw)

    def test_existing_labels_capacity_and_file_size_are_checked_before_import(self):
        for args in ({"available": 1}, {"existing_labels": ["W1"], "available": 0}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                read_loads(encode(document()), **args)
        self.assertEqual(len(read_loads(encode(document()), existing_labels=["W1"], available=1)), 2)
        self.assertEqual(len(read_loads(encode(document()), existing_labels=["W1", "P1"], available=0)), 2)
        with self.assertRaises(ValueError):
            read_loads(b" " * (5 * 1024 * 1024 + 1))


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook] för notebooktesterna.")
class TestLoadPlacement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.file = Path(self.tmp.name) / "loads.json"
        self.file.write_bytes(encode(document()))
        self.plan = Grundplan(self.image)
        self.addCleanup(self.plan.close)

    def place_both(self):
        self.plan.importera_lasteffekt(self.file)
        return self.plan.placera_lasteffekt(.2, .3), self.plan.placera_lasteffekt(.6, .7)

    def test_updates_matches_preserving_inputs_placement_and_ids_and_queues_only_new_supports(self):
        wall, pad = self.place_both()
        self.plan.uppdatera(wall, indata={"b": .9, "glid_x": True, "glid_mu": .4, "isolerprodukt": "Kommentar"})
        self.plan.uppdatera(pad, indata={"b": 1.8, "l": 2.1, "M_insp_l": 3})
        self.plan.berakna(wall)
        self.plan.berakna(pad)
        other = self.plan.lagg_till(.1, .1, littera="Other")
        before = {tag["id"]: copy.deepcopy(tag) for tag in self.plan._tags}
        data = document()
        data["supports"][0]["length"]["value"] = 7.5
        for support in data["supports"]:
            for result in support["results"]:
                result["V"] += 10
        new = copy.deepcopy(data["supports"][0]); new["supportId"] = "W2"
        data["supports"].append(new)
        report = self.plan._start_load_import(encode(data), "updated.json")
        self.assertEqual(report, {"updated": 2, "new": 1, "updated_ids": [wall, pad]})
        self.assertEqual(len(self.plan.taggar), 3)
        self.assertEqual(self.plan.lasteffekt_import["total"], 1)
        self.assertEqual(self.plan.lasteffekt_import["next"]["label"], "W2")
        for ident in (wall, pad):
            tag = self.plan._tag(ident)
            for name in ("id", "label", "x", "y", "page"):
                self.assertEqual(tag[name], before[ident][name])
            updated_fields = {"F_vy", "F_vy_bruk", "V_Ed_EQU"} | ({"glid_L", "L_vagg"} if ident == wall else set())
            for name, value in before[ident]["values"].items():
                if name not in updated_fields:
                    self.assertEqual(tag["values"][name], value)
            self.assertEqual(tag["status"], "calculated")
            self.assertIsNotNone(tag["summary"])
            self.assertIn(ident, self.plan.resultat)
        self.assertEqual(self.plan._tag(wall)["values"]["F_vy"], 90)
        self.assertEqual(self.plan._tag(wall)["values"]["F_vy_bruk"], 35)
        self.assertEqual(self.plan._tag(wall)["values"]["V_Ed_EQU"], 40)
        self.assertEqual(self.plan._tag(wall)["values"]["glid_L"], 7.5)
        self.assertEqual(self.plan._tag(other), before[other])
        new_id = self.plan.placera_lasteffekt(.8, .4)
        self.assertEqual(self.plan._tag(new_id)["label"], "W2")
        self.assertEqual(len(self.plan.taggar), 4)

    def test_update_only_and_repeated_identical_import_preserve_current_calculation(self):
        ids = self.place_both()
        for ident in ids:
            self.plan.berakna(ident)
        before = self.plan.taggar, self.plan.resultat
        for _ in range(2):
            self.assertIsNone(self.plan.importera_lasteffekt(self.file))
            self.assertIsNone(self.plan.lasteffekt_import)
            self.assertEqual((self.plan.taggar, self.plan.resultat), before)

    def test_support_length_update_recalculates_soil_and_sliding(self):
        wall, _ = self.place_both()
        self.plan.uppdatera(wall, indata={"glid_x": True, "glid_mu": .4})
        self.plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 100}
        self.plan.berakna(wall)
        before = self.plan._tag(wall)["summary"], self.plan.resultat
        data = document(); data["supports"][0]["length"]["value"] = 10
        data["supports"][0]["results"][2]["V"] = 50
        self.plan._start_load_import(encode(data), "equ.json")
        self.assertNotEqual((self.plan._tag(wall)["summary"], self.plan.resultat), before)
        self.assertEqual(self.plan._tag(wall)["summary"]["load_conversion"]["brott"], 80)
        self.assertAlmostEqual(self.plan.glidningsresultat["x"]["H_Rd"], 200)

    def test_ambiguous_labels_type_conflict_and_invalid_late_support_do_not_partially_update(self):
        self.place_both()
        data = document(); data["supports"][0]["results"][0]["V"] = 999
        duplicate = self.plan.lagg_till(.9, .9, littera="P1", typ="pelarsula")
        before = self.plan.taggar, self.plan.state
        with self.assertRaisesRegex(ValueError, "matchar flera"):
            self.plan._start_load_import(encode(data), "ambiguous.json")
        self.assertEqual((self.plan.taggar, self.plan.state), before)
        self.plan.ta_bort(duplicate)
        wrong_type = copy.deepcopy(data)
        wrong_type["supports"][1] = copy.deepcopy(wrong_type["supports"][0])
        wrong_type["supports"][1]["supportId"] = "P1"
        invalid = copy.deepcopy(data); invalid["supports"][1]["results"][0]["unit"] = "N"
        before = self.plan.taggar, self.plan.state
        for doc in (wrong_type, invalid):
            with self.subTest(doc=doc), self.assertRaises(ValueError):
                self.plan._start_load_import(encode(doc), "bad.json")
            self.assertEqual((self.plan.taggar, self.plan.state), before)
            self.assertIsNone(self.plan.lasteffekt_import)

    def test_capacity_counts_only_new_objects_and_rejects_overflow_before_updates(self):
        self.place_both()
        with patch("an_calcs.notebook.grundplan._MAX_TAGS", 2):
            self.assertIsNone(self.plan.importera_lasteffekt(self.file))
            data = document(); data["supports"][0]["results"][0]["V"] = 999
            new = copy.deepcopy(data["supports"][1]); new["supportId"] = "P2"
            data["supports"].append(new)
            before = self.plan.taggar
            with self.assertRaisesRegex(ValueError, "1 nya stöd"):
                self.plan._start_load_import(encode(data), "overflow.json")
            self.assertEqual(self.plan.taggar, before)

    def test_delete_all_removes_results_and_queue_but_keeps_project_and_drawing(self):
        ident = self.plan.lagg_till(.1, .1, littera="Existing")
        self.plan.berakna(ident)
        self.plan.lagg_till(.2, .2, littera="Second")
        self.plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 150,
                              "placements": {"1": {"symbol": {"x": .1, "y": .5, "size": 160}}}}
        self.plan._set_heading("Projekt", "Underrubrik")
        queue = self.plan.importera_lasteffekt(self.file)
        before = self.plan.background, self.plan._source, self.plan.glidning, self.plan.state["title"], self.plan.state["subtitle"]
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "delete_all", "request": 3, "view": "test"}, [])
            self.assertEqual(send.call_args.args[0], {"request": 3, "view": "test", "ok": True, "deleted": 2})
        self.assertEqual(self.plan.taggar, [])
        self.assertEqual(self.plan.resultat, {})
        self.assertIsNone(self.plan.lasteffekt_import)
        self.assertEqual((self.plan.background, self.plan._source, self.plan.glidning, self.plan.state["title"], self.plan.state["subtitle"]), before)
        self.assertEqual(self.plan.glidningsresultat["x"]["H_Rd"], 0)
        with self.assertRaises(ValueError):
            self.plan._place_load_import(.2, .3, token=queue["token"], index=0)
        self.assertEqual(self.plan.ta_bort_samtliga(), 0)
        self.plan.importera_lasteffekt(self.file)
        self.assertEqual(self.plan.lasteffekt_import["total"], 2)

    def test_import_does_not_create_footings_then_clicks_create_independent_calculated_values(self):
        existing = self.plan.lagg_till(.1, .1, littera="Existing", indata={"F_vy": 100})
        self.plan.berakna(existing)
        before = self.plan.taggar[0]
        queue = self.plan.importera_lasteffekt(self.file)
        self.assertEqual(len(self.plan.taggar), 1)
        self.assertEqual(queue["next"]["label"], "W1")
        queue["next"]["values"]["F_vy"] = 999  # Returned state cannot alter the authoritative queue.
        first = self.plan.placera_lasteffekt(.25, .4)
        self.assertEqual(self.plan.lasteffekt_import["next"]["label"], "P1")
        second = self.plan.placera_lasteffekt(.65, .7, sida=1)
        self.assertIsNone(self.plan.lasteffekt_import)
        self.assertEqual(self.plan.taggar[0], before)
        for ident, label, kind, brott, bruk, equ in [(first, "W1", 1, 80, 25, 30), (second, "P1", 0, 120, 50, 60)]:
            tag = self.plan._tag(ident)
            self.assertEqual((tag["label"], tag["values"]["lang"], tag["values"]["F_vy"],
                              tag["values"]["F_vy_bruk"], tag["values"]["V_Ed_EQU"]), (label, kind, brott, bruk, equ))
            self.assertFalse(tag["values"]["isolering"])
            self.assertFalse(tag["values"]["glid_x"] or tag["values"]["glid_y"])
            self.assertEqual(tag["status"], "calculated")
            self.assertIsNotNone(tag["summary"])
        self.assertEqual(self.plan._tag(first)["values"]["glid_L"], 6.2)
        self.assertNotEqual(self.plan._tag(first)["values"]["l"], 6.2)
        self.assertIsNone(self.plan._tag(second)["values"]["glid_L"])
        self.plan.uppdatera(first, indata={"b": .9})
        self.assertNotEqual(self.plan._tag(second)["values"]["b"], .9)

    def test_bad_import_invalid_coordinates_and_replayed_click_are_atomic(self):
        before = self.plan.state
        bad = document(); bad["supports"][1]["results"][0]["unit"] = "N"
        with self.assertRaises(ValueError):
            self.plan._start_load_import(encode(bad), "bad.json")
        self.assertEqual(self.plan.state, before)
        queue = self.plan.importera_lasteffekt(self.file)
        for kwargs in ({"x": -1, "y": .4}, {"x": .3, "y": .4, "sida": 2},
                       {"x": .3, "y": .4, "token": "old", "index": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.plan._place_load_import(**kwargs)
            self.assertEqual(self.plan.taggar, [])
            self.assertEqual(self.plan.lasteffekt_import, queue)
        self.plan._place_load_import(.3, .4, token=queue["token"], index=0)
        with self.assertRaises(ValueError):
            self.plan._place_load_import(.6, .7, token=queue["token"], index=0)
        self.assertEqual(len(self.plan.taggar), 1)
        self.assertEqual(self.plan.lasteffekt_import["index"], 1)

    def test_pause_resume_cancel_and_mid_queue_save_keep_only_placed_objects(self):
        queue = self.plan.importera_lasteffekt(self.file)
        self.plan.placera_lasteffekt(.2, .3)
        self.plan._control_load_import(queue["token"], "pause")
        with self.assertRaises(ValueError):
            self.plan.placera_lasteffekt(.5, .6)
        saved = self.plan.spara(Path(self.tmp.name) / "project.json")
        reopened = Grundplan.oppna(saved)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.taggar[0]["values"], self.plan.taggar[0]["values"])
        self.assertIsNone(reopened.lasteffekt_import)
        self.plan._control_load_import(queue["token"], "resume")
        self.assertFalse(self.plan.lasteffekt_import["paused"])
        self.plan._control_load_import(queue["token"], "cancel")
        self.assertEqual(len(self.plan.taggar), 1)
        self.assertIsNone(self.plan.lasteffekt_import)

    def test_label_collision_since_import_does_not_skip_pending_support(self):
        self.plan.importera_lasteffekt(self.file)
        ident = self.plan.lagg_till(.1, .1, littera="W1")
        with self.assertRaises(ValueError):
            self.plan.placera_lasteffekt(.3, .3)
        self.assertEqual(self.plan.lasteffekt_import["index"], 0)
        self.plan.uppdatera(ident, littera="Other")
        self.plan.placera_lasteffekt(.3, .3)
        self.assertEqual(self.plan.lasteffekt_import["index"], 1)

    def test_widget_uses_kernel_queue_instead_of_client_supplied_loads(self):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(None, {"action": "import_loads", "name": "loads.json", "request": 1, "view": "test"}, [self.file.read_bytes()])
            self.assertTrue(send.call_args.args[0]["ok"])
            queue = self.plan.lasteffekt_import
            message = {"action": "place_import", "token": queue["token"], "index": 0,
                       "x": .3, "y": .4, "page": 1, "values": {"F_vy": 999}, "request": 2, "view": "test"}
            self.plan._on_message(None, message, [])
            reply = send.call_args.args[0]
            self.assertTrue(reply["ok"])
            self.assertEqual(self.plan._tag(reply["id"])["values"]["F_vy"], 80)
            self.plan._on_message(None, message, [])
            self.assertFalse(send.call_args.args[0]["ok"])
            self.assertEqual(len(self.plan.taggar), 1)
