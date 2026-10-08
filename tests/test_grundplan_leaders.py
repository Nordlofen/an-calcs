import copy
import importlib.util
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
    from an_calcs.notebook import Grundplan
from an_calcs.notebook.grundplan_leaders import validate_leader


def leader():
    return {"enabled": True, "attachment": {"side": "left", "offset": .4},
            "nodes": [{"x": .1, "y": .7, "in": {"x": 0, "y": 0}, "out": {"x": .1, "y": .02}},
                      {"x": .3, "y": .5, "in": {"x": -.04, "y": .1}, "out": {"x": .04, "y": -.1}}],
            "end_handle": {"x": -.1, "y": 0}}


class TestLeaderValidation(unittest.TestCase):
    def test_validation_copies_data_and_rejects_invalid_geometry(self):
        original = leader()
        validated = validate_leader(original)
        original["nodes"][0]["x"] = .8
        self.assertEqual(validated["nodes"][0]["x"], .1)
        bad = [None, {**leader(), "enabled": 1}, {**leader(), "nodes": []},
               {**leader(), "nodes": leader()["nodes"] * 33},
               {**leader(), "attachment": {"side": "center", "offset": .5}},
               {**leader(), "attachment": {"side": "left", "offset": 2}},
               {**leader(), "end_handle": {"x": float("nan"), "y": 0}},
               {**leader(), "end_handle": {"x": True, "y": 0}},
               {**leader(), "nodes": [{**leader()["nodes"][0], "x": 1.1}]},
               {**leader(), "unexpected": 123}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_leader(value)


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestGrundplanLeaders(unittest.TestCase):
    def test_leader_persists_when_hidden_or_label_moves_and_does_not_recalculate(self):
        with tempfile.TemporaryDirectory() as folder:
            drawing = Path(folder) / "drawing.png"
            Image.new("RGB", (800, 600), "white").save(drawing)
            plan = Grundplan(drawing)
            self.addCleanup(plan.close)
            ident = plan.lagg_till(.6, .2, indata={"F_vy": 100})
            before = copy.deepcopy(plan.resultat)
            with patch.object(plan, "_refresh_tag", side_effect=AssertionError("No recalculation")):
                plan.hanvisningslinje(ident, leader())
                plan.uppdatera(ident, x=.7, y=.3)
                plan.hanvisningslinje(ident, {**leader(), "enabled": False})
            self.assertEqual(plan.resultat, before)
            saved = plan._document()
            restored = Grundplan()
            self.addCleanup(restored.close)
            restored._load_document(json.dumps(saved).encode())
            self.assertEqual(restored.taggar, plan.taggar)
            restored.hanvisningslinje(ident, {**restored.taggar[0]["leader"], "enabled": True})
            self.assertEqual(restored.taggar[0]["leader"], leader())
            # Older projects still load without any leader state.
            saved["version"] = 15
            del saved["tags"][0]["leader"]
            restored._load_document(json.dumps(saved).encode())
            self.assertNotIn("leader", restored.taggar[0])

    def test_invalid_update_or_import_is_atomic_and_ui_reports_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            drawing = Path(folder) / "drawing.png"
            Image.new("RGB", (800, 600), "white").save(drawing)
            plan = Grundplan(drawing)
            self.addCleanup(plan.close)
            ident = plan.lagg_till(.6, .2)
            with patch.object(plan, "send") as send:
                plan._on_message(None, {"action": "leader", "id": ident, "leader": leader()}, [])
                self.assertTrue(send.call_args.args[0]["ok"])
            before = plan._document()
            bad = {**leader(), "nodes": []}
            with patch.object(plan, "send") as send:
                plan._on_message(None, {"action": "leader", "id": ident, "leader": bad}, [])
                self.assertFalse(send.call_args.args[0]["ok"])
            invalid = copy.deepcopy(before)
            invalid["tags"][0]["leader"] = bad
            with self.assertRaises(ValueError):
                plan._load_document(json.dumps(invalid).encode())
            self.assertEqual(plan._document(), before)
