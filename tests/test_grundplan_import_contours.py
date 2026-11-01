"""Guided load import saves a footing and its physical placement together."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_grundplan_loads import document, encode

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestImportContours(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        source = Path(folder.name) / "plan.png"
        Image.new("RGB", (800, 600), "white").save(source)
        self.plan = Grundplan(source); self.addCleanup(self.plan.close)
        self.plan.kalibrering = {"start": {"x": .1, "y": .1}, "end": {"x": .6, "y": .1}, "length_m": 10}

    def command(self, action, buffers=None, **values):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(self.plan, {"action": action, "view": "test", "request": 1, **values}, buffers or [])
        reply = send.call_args.args[0]
        self.assertTrue(reply["ok"], reply)
        return reply

    def start(self):
        return self.command("import_loads", buffers=[encode(document())], name="loads.json", define_contours=True)["report"]

    def place(self, placement, **extra):
        queue = self.plan.lasteffekt_import
        return self.command("place_import", token=queue["token"], index=queue["index"], page=1, x=.7, y=.8,
                            placement=placement, **extra)

    def test_new_footing_label_and_contour_are_one_undo_step_and_keep_source_loads(self):
        self.start(); self.assertEqual(self.plan.taggar, [])
        reply = self.place({"kind": "wall", "start": {"x": .2, "y": .4}, "angle_deg": 0}, values={"F_vy": 999})
        tag = self.plan._tag(reply["id"])
        self.assertEqual((tag["x"], tag["y"]), (.7, .8))
        self.assertEqual(tag["values"]["F_vy"], 80)
        self.assertEqual(tag["values"]["l"], 6.2)
        contour = self.plan.sulkonturer["placements"][tag["id"]]
        self.assertEqual(contour["start"], {"x": .2, "y": .4})
        self.assertTrue(self.plan.sulkonturer["enabled"])
        self.assertEqual(self.plan.lasteffekt_import["index"], 1)
        self.command("undo")
        self.assertEqual(self.plan.taggar, [])
        self.assertEqual(self.plan.sulkonturer["placements"], {})
        self.assertEqual(self.plan.lasteffekt_import["index"], 0)
        self.command("redo")
        self.assertEqual(self.plan.sulkonturer["placements"][tag["id"]], contour)
        self.plan._control_load_import(self.plan.lasteffekt_import["token"], "resume")
        self.place({"kind": "pad", "center": {"x": .5, "y": .6}, "angle_deg": 30})
        self.assertIsNone(self.plan.lasteffekt_import)
        restored = Grundplan(); self.addCleanup(restored.close)
        import json
        restored._load_document(json.dumps(self.plan._document()).encode())
        self.assertEqual(restored.sulkonturer, self.plan.sulkonturer)
        self.assertEqual(len(restored.taggar), 2)

    def test_update_only_queues_missing_contours_and_preserves_existing_labels_and_placements(self):
        self.plan._start_load_import(encode(document()), "loads.json")
        wall, pad = self.plan.placera_lasteffekt(.15, .25), self.plan.placera_lasteffekt(.65, .75)
        self.plan.placera_sulkontur(pad, {"kind": "pad", "center": {"x": .5, "y": .5}, "angle_deg": 27})
        saved = copy.deepcopy(self.plan.sulkonturer["placements"][pad])
        report = self.start()
        self.assertEqual((report["new"], report["contours"]), (0, 1))
        self.assertEqual(self.plan.lasteffekt_import["next"]["existing_id"], wall)
        self.place({"kind": "wall", "start": {"x": .2, "y": .3}, "angle_deg": 0})
        self.assertEqual(len(self.plan.taggar), 2)
        self.assertEqual((self.plan._tag(wall)["x"], self.plan._tag(wall)["y"]), (.15, .25))
        self.assertEqual(self.plan.sulkonturer["placements"][pad], saved)
        self.assertIsNone(self.plan.lasteffekt_import)
        self.command("undo")
        self.assertNotIn(wall, self.plan.sulkonturer["placements"])
        self.assertEqual(self.plan.lasteffekt_import["next"]["existing_id"], wall)

    def test_validation_failure_cannot_create_half_a_footing_or_consume_queue(self):
        self.start()
        for placement in (None, {"kind": "pad", "center": {"x": .2, "y": .3}, "angle_deg": 0},
                          {"kind": "wall", "start": {"x": .2, "y": .3}, "angle_deg": float("nan")}):
            before = copy.deepcopy((self.plan._document(), self.plan.lasteffekt_import))
            with self.assertRaises(ValueError):
                self.plan._place_load_import(.7, .8, placement=placement)
            self.assertEqual((self.plan._document(), self.plan.lasteffekt_import), before)
        self.plan.kalibrering = None
        with self.assertRaisesRegex(ValueError, "Kalibrera"):
            self.plan._place_load_import(.7, .8, placement={"kind": "wall", "start": {"x": .2, "y": .3}, "angle_deg": 0})
        self.assertEqual(self.plan.taggar, [])

    def test_locked_or_inactive_existing_supports_are_not_added_to_contour_queue(self):
        self.plan._start_load_import(encode(document()), "loads.json")
        wall, pad = self.plan.placera_lasteffekt(.2, .3), self.plan.placera_lasteffekt(.6, .7)
        self.plan.las_placering([{"type": "tag", "id": wall}], last=True)
        self.plan.uppdatera(pad, indata={"inaktiv": True})
        report = self.start()
        self.assertEqual(report["contours"], 0)
        self.assertIsNone(self.plan.lasteffekt_import)
        self.assertEqual(self.plan.sulkonturer["placements"], {})

    def test_wall_with_pad_model_uses_its_existing_model_and_no_new_footing_is_created(self):
        self.plan._start_load_import(encode(document()), "loads.json")
        wall, pad = self.plan.placera_lasteffekt(.2, .3), self.plan.placera_lasteffekt(.6, .7)
        self.plan.uppdatera(wall, indata={"lang": 0, "l": 2})
        self.plan.placera_sulkontur(pad, {"kind": "pad", "center": {"x": .5, "y": .5}, "angle_deg": 0})
        self.start()
        self.assertEqual(self.plan.lasteffekt_import["next"]["values"]["lang"], 0)
        self.place({"kind": "pad", "center": {"x": .2, "y": .35}, "angle_deg": 0})
        self.assertEqual(self.plan._tag(wall)["values"]["l"], 2)
        self.assertEqual(self.plan.sulkonturer["placements"][wall]["kind"], "pad")
        self.assertEqual(len(self.plan.taggar), 2)
