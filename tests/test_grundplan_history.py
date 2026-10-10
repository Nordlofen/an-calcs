import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan
    from test_grundplan_loads import document, encode
    from test_grundplan_leaders import leader


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image); self.addCleanup(self.plan.close)
        self.ident = self.plan.lagg_till(.2, .3, littera="VS.22", indata={"F_vy": 100, "t": .25, "kommentar": "Foundation"})
        self.date = self.plan.lagg_till_datum("26/10/10")
        self.objects = [{"type": "tag", "id": self.ident},
                        {"type": "overlay", "page": 1, "kind": "reference"},
                        {"type": "overlay", "page": 1, "kind": "text:" + self.date}]

    def message(self, action, buffers=None, **payload):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(self.plan, {"action": action, "view": "view", "request": 1, **payload}, buffers or [])
        self.assertEqual(send.call_count, 1)
        return send.call_args.args[0]

    def ok(self, action, **payload):
        result = self.message(action, **payload); self.assertTrue(result["ok"], result); return result

    def test_mixed_transform_lock_and_layers_restore_without_recalculation(self):
        original = self.plan._document(); results = copy.deepcopy(self.plan.resultat)
        with patch.object(self.plan, "_refresh_tag", side_effect=AssertionError("Geometry cannot recalculate")):
            self.ok("transform_objects", objects=[{**obj, "x": .5, "y": .6, "scale": 1.4} for obj in self.objects])
            scaled = self.plan._document()
            self.ok("placement_lock", objects=self.objects, locked=True)
            locked = self.plan._document()
            self.ok("object_order", objects=self.objects, operation="front")
            self.assertEqual(self.plan.state["history"]["undo_count"], 3)
            self.ok("undo"); self.assertEqual(self.plan._document(), locked)
            self.ok("undo"); self.assertEqual(self.plan._document(), scaled)
            self.ok("undo"); self.assertEqual(self.plan._document(), original)
            for _ in range(3): self.ok("redo")
        self.assertEqual(self.plan.resultat, results)
        self.assertCountEqual(self.plan.placeringslas, self.objects)

    def test_deleted_footing_restores_identity_comment_spline_locks_and_reference(self):
        self.plan.hanvisningslinje(self.ident, leader())
        self.plan.referens = {"enabled": True}
        self.plan.las_placering(self.objects)
        before = self.plan._document(); results = copy.deepcopy(self.plan.resultat)
        self.ok("delete", id=self.ident)
        self.assertEqual(self.plan.state["history"]["undo"], "Radera VS.22")
        self.ok("undo")
        self.assertEqual(self.plan._document(), before)
        self.assertEqual(self.plan.resultat, results)
        self.assertEqual(self.plan.state["reference_data"]["groups"][0]["reference_id"], self.ident)
        self.ok("redo"); self.assertEqual(self.plan.taggar, [])

    def test_inputs_recalculate_and_invalid_results_are_undoable(self):
        before = copy.deepcopy(self.plan.resultat)
        self.ok("update", id=self.ident, values={"F_vy": 200})
        changed = copy.deepcopy(self.plan.resultat); self.assertNotEqual(before, changed)
        with patch.object(self.plan, "_refresh_tag", wraps=self.plan._refresh_tag) as calculate:
            self.ok("undo"); calculate.assert_called_once()
        self.assertEqual(self.plan.resultat, before)
        self.ok("redo"); self.assertEqual(self.plan.resultat, changed)
        self.ok("update", id=self.ident, values={"b": None})
        self.assertEqual(self.plan._tag(self.ident)["status"], "error")
        self.ok("undo"); self.assertEqual(self.plan.resultat, changed)

    def test_typing_coalesces_per_field_session_and_new_edit_clears_redo(self):
        for value in (110, 120, 130):
            self.ok("update", id=self.ident, values={"F_vy": value}, history_group="input-1")
        self.assertEqual(self.plan.state["history"]["undo_count"], 1)
        self.ok("update", id=self.ident, values={"t": .3}, history_group="input-2")
        self.assertEqual(self.plan.state["history"]["undo_count"], 2)
        self.ok("undo"); self.assertEqual(self.plan._tag(self.ident)["values"]["t"], .25)
        self.ok("undo"); self.assertEqual(self.plan._tag(self.ident)["values"]["F_vy"], 100)
        self.ok("update", id=self.ident, values={"F_vy": 150}, history_group="input-1")
        self.assertEqual(self.plan.state["history"]["redo_count"], 0)
        self.assertFalse(self.message("redo")["ok"])

    def test_reverting_a_typing_group_removes_its_empty_step_and_rejected_changes_do_not_record(self):
        self.ok("text_update", id=self.date, changes={"text": "26/10/11"}, history_group="date")
        self.ok("text_update", id=self.date, changes={"text": "26/10/10"}, history_group="date")
        self.assertEqual(self.plan.state["history"]["undo_count"], 0)
        self.assertFalse(self.message("move_objects", objects=[{**self.objects[0], "x": 100, "y": .2}])["ok"])
        self.assertFalse(self.message("undo")["ok"])

    def test_drawing_scale_update_and_calibration_restore_together(self):
        calibration = {"start": {"x": .1, "y": .2}, "end": {"x": .6, "y": .2}, "length_m": 10}
        self.plan.kalibrering = calibration
        before = self.plan._document(); source = self.plan._source
        self.ok("drawing_commit", layout={"x": .1, "y": -.1, "scale": .8})
        self.assertIsNone(self.plan.kalibrering)
        self.ok("undo"); self.assertEqual(self.plan._document(), before)
        replacement = self.root / "new.png"; Image.new("RGB", (1000, 800), "green").save(replacement)
        preview = self.ok("drawing", buffers=[replacement.read_bytes()], name="new.png", draft=True)
        self.assertEqual(self.plan.state["history"]["undo_count"], 0)
        self.ok("drawing_commit", token=preview["drawing_preview"]["token"],
                layout={k: preview["drawing_preview"]["layout"][k] for k in ("x", "y", "scale")})
        updated = self.plan._document()
        self.assertIs(self.plan._history.undo[-1]["patch"]["_source"][0], source)
        self.ok("undo"); self.assertEqual(self.plan._document(), before)
        self.ok("redo"); self.assertEqual(self.plan._document(), updated)

    def test_import_placement_undo_restores_queue_without_duplicate_footings(self):
        self.ok("import_loads", buffers=[encode(document())], name="loads.json")
        queue = self.plan.lasteffekt_import
        reply = self.ok("place_import", token=queue["token"], index=queue["index"], x=.5, y=.6, page=1)
        self.assertEqual(len(self.plan.taggar), 2)
        self.ok("undo"); self.assertEqual(len(self.plan.taggar), 1)
        self.assertEqual(self.plan.lasteffekt_import["index"], 0)
        self.assertTrue(self.plan.lasteffekt_import["paused"])
        self.ok("redo"); self.assertEqual(self.plan.taggar[-1]["id"], reply["id"])
        self.ok("undo"); self.ok("undo"); self.assertIsNone(self.plan.lasteffekt_import)

    def test_history_limit_and_geometry_entries_do_not_copy_drawing_or_unchanged_tags(self):
        for i in range(105): self.ok("update", id=self.ident, x=.2 + (i + 1) / 1000)
        self.assertEqual(self.plan.state["history"]["undo_count"], 100)
        for entry in self.plan._history.undo:
            self.assertEqual(set(entry["patch"]), {"tag:" + self.ident})

    def test_open_resets_history_save_does_not_and_external_python_edits_start_a_new_baseline(self):
        original = json.dumps(self.plan._document()).encode()
        self.ok("update", id=self.ident, x=.4)
        self.ok("export_json"); self.assertEqual(self.plan.state["history"]["undo_count"], 1)
        self.assertNotIn("history", self.plan._document())
        self.assertFalse(self.message("open", buffers=[b"invalid"])["ok"])
        self.assertEqual(self.plan.state["history"]["undo_count"], 1)
        self.ok("open", buffers=[original]); self.assertEqual(self.plan.state["history"]["undo_count"], 0)
        self.ok("update", id=self.ident, x=.4)
        self.plan.uppdatera(self.ident, indata={"F_vy": 150})
        self.assertEqual(self.plan.state["history"]["undo_count"], 0)

    def test_replay_failure_is_atomic_and_does_not_consume_the_step(self):
        self.ok("update", id=self.ident, values={"F_vy": 200})
        before = self.plan._document(); history = copy.deepcopy(self.plan.state["history"])
        with patch.object(self.plan, "_refresh_tag", side_effect=RuntimeError("Calculation failed")):
            self.assertFalse(self.message("undo")["ok"])
        self.assertEqual(self.plan._document(), before); self.assertEqual(self.plan.state["history"], history)
        self.ok("undo"); self.assertEqual(self.plan._tag(self.ident)["values"]["F_vy"], 100)


if __name__ == "__main__": unittest.main()
