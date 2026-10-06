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
            {"label": "W1", "kind": "vaggsula", "values": {"F_vy": 80, "F_vy_bruk": 25, "V_Ed_EQU": 30, "glid_L": 6.2}},
            {"label": "P1", "kind": "pelarsula", "values": {"F_vy": 120, "F_vy_bruk": 50, "V_Ed_EQU": 60}}])
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
        self.assertEqual(items[0]["values"], {"V_Ed_EQU": 60, "F_vy_bruk": 0, "F_vy": -10.5})

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
        for args in ({"existing_labels": ["W1"]}, {"available": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                read_loads(encode(document()), **args)
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

    def test_import_does_not_create_footings_then_clicks_create_independent_uncomputed_values(self):
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
            self.assertEqual(tag["status"], "new")
            self.assertIsNone(tag["summary"])
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
