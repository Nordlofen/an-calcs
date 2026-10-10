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


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestPlacement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(self.path)
        self.plan = Grundplan(self.path)
        self.addCleanup(self.plan.close)
        self.ident = self.plan.lagg_till(.2, .3, indata={"F_vy": 100})
        self.text = self.plan.lagg_till_rubrik("Rubrik")
        self.objects = [{"type": "tag", "id": self.ident},
                        *[{"type": "overlay", "page": 1, "kind": kind}
                          for kind in ("symbol", "legend", "colour", "insulation", "comments", "reference", "text:" + self.text)]]

    def test_mixed_movement_publishes_once_and_preserves_calculations_and_sizes(self):
        before = copy.deepcopy((self.plan._tag(self.ident)["values"], self.plan.resultat,
                                self.plan._tag(self.ident)["summary"]))
        positions = [{**item, "x": .5, "y": .6} for item in self.objects]
        with patch.object(self.plan, "_refresh_tag") as calculate, patch.object(self.plan, "_publish", wraps=self.plan._publish) as publish:
            self.plan.flytta_objekt(positions)
        calculate.assert_not_called(); publish.assert_called_once()
        self.assertEqual((self.plan._tag(self.ident)["values"], self.plan.resultat,
                          self.plan._tag(self.ident)["summary"]), before)
        self.assertEqual(self.plan._tag(self.ident)["x"], .5)
        for widget in (self.plan.isoleringswidget, self.plan.kommentarwidget, self.plan.referens,
                       self.plan.farggruppering["legend"], *self.plan.glidning["placements"]["1"].values(), self.plan.textobjekt[0]):
            self.assertEqual((widget["x"], widget["y"]), (.5, .6))
        self.assertEqual(self.plan.referens["size"], 410)
        self.assertEqual(self.plan.textobjekt[0]["size"], 20)

    def test_invalid_or_locked_batch_never_moves_or_locks_a_subset(self):
        before = self.plan._document()
        first = {**self.objects[0], "x": .5, "y": .6}
        for invalid in ({"type": "overlay", "page": 2, "kind": "reference", "x": .5, "y": .6},
                        {**self.objects[1], "x": float("nan"), "y": .5},
                        {**self.objects[1], "x": True, "y": .5}, first):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.plan.flytta_objekt([first, invalid])
            self.assertEqual(self.plan._document(), before)
        with self.assertRaises(ValueError):
            self.plan.las_placering([self.objects[0], {"type": "overlay", "kind": "unknown", "page": 1}])
        self.assertEqual(self.plan.placeringslas, [])
        self.plan.las_placering([self.objects[1]])
        before = self.plan._document()
        with self.assertRaisesRegex(ValueError, "låst"):
            self.plan.flytta_objekt([first, {**self.objects[1], "x": .5, "y": .6}])
        self.assertEqual(self.plan._document(), before)

    def test_locks_block_position_and_size_but_allow_inputs_and_text(self):
        self.plan.las_placering(self.objects)
        actions = [lambda: self.plan.uppdatera(self.ident, x=.5),
                   lambda: self.plan.flytta_flera([{"id": self.ident, "x": .5, "y": .6}]),
                   lambda: setattr(self.plan, "referens", {"x": .5}),
                   lambda: setattr(self.plan, "isoleringswidget", {"y": .6}),
                   lambda: setattr(self.plan, "kommentarwidget", {"x": .6}),
                   lambda: setattr(self.plan, "farggruppering", {"legend": {"x": .6}}),
                   lambda: setattr(self.plan, "glidning", {"placements": {"1": {"symbol": {"x": .5, "y": .6, "size": 160}}}}),
                   lambda: self.plan.uppdatera_text(self.text, x=.5)]
        before = self.plan._document()
        for action in actions:
            with self.assertRaisesRegex(ValueError, "låst"):
                action()
            self.assertEqual(self.plan._document(), before)
        self.plan.uppdatera(self.ident, indata={"F_vy": 120, "kommentar": "Kommentar"})
        self.plan.uppdatera_text(self.text, text="Ny rubrik")
        self.plan.referens = {"enabled": True}
        with self.assertRaisesRegex(ValueError, "låst"):
            self.plan.uppdatera_text(self.text, size=24)
        with self.assertRaisesRegex(ValueError, "låst"):
            self.plan.uppdatera_text(self.text, width=600)
        with self.assertRaisesRegex(ValueError, "låst"):
            self.plan.referens = {"size": 600}
        self.assertEqual(self.plan.placeringslas, self.plan.state["placement_locks"])
        self.plan.las_placering(self.objects, last=False)
        self.plan.flytta_objekt([{**item, "x": .5, "y": .6} for item in self.objects])
        self.assertEqual(self.plan.placeringslas, [])

    def test_save_open_migration_and_invalid_saved_locks_are_atomic(self):
        self.plan.las_placering(self.objects)
        document = self.plan._document()
        self.assertEqual(document["version"], 23)
        loaded = Grundplan.oppna(self.plan.spara(Path(self.tmp.name) / "project.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.placeringslas, self.plan.placeringslas)
        before = loaded._document()
        invalid = copy.deepcopy(document)
        invalid["placement_locks"].append({"type": "tag", "id": "missing"})
        with self.assertRaises(ValueError):
            loaded._load_document(json.dumps(invalid).encode())
        self.assertEqual(loaded._document(), before)
        document["version"] = 20; document.pop("placement_locks")
        loaded._load_document(json.dumps(document).encode())
        self.assertEqual(loaded.placeringslas, [])
        self.assertEqual(loaded.resultat, self.plan.resultat)

    def test_copy_is_unlocked_and_deleting_objects_removes_only_their_locks(self):
        self.plan.las_placering(self.objects)
        duplicate = self.plan.kopiera(self.ident, .6, .7)
        self.plan.uppdatera(duplicate, x=.7)
        self.plan.ta_bort(self.ident)
        self.plan.ta_bort_text(self.text)
        self.assertEqual(len(self.plan.placeringslas), 6)
        self.plan.ta_bort_samtliga()
        self.assertEqual(len(self.plan.placeringslas), 6)
        self.plan.importera_ritning(self.path)
        self.assertEqual(len(self.plan.placeringslas), 6)


if __name__ == "__main__":
    unittest.main()
