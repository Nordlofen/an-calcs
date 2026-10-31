"""Physical contour persistence, opt-in legacy defaults and trusted edits."""
import copy
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(n) for n in ("anywidget", "PIL", "pypdfium2", "pypdf", "reportlab"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestContours(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "drawing.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = Grundplan(self.image); self.addCleanup(self.plan.close)
        self.pad = self.plan.lagg_till(.2, .3, typ="pelarsula", littera="PS.1", indata={"F_vy": 100})
        self.wall = self.plan.lagg_till(.5, .6, littera="VS.1", indata={"F_vy": 100})
        self.calibration = {"start": {"x": .1, "y": .1}, "end": {"x": .6, "y": .1}, "length_m": 10}
        self.position = {"kind": "pad", "center": {"x": .4, "y": .4}, "angle_deg": 30}

    def message(self, action, **payload):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(self.plan, {"action": action, "view": "test", "request": 1, **payload}, [])
        return send.call_args.args[0]

    def test_legacy_is_opt_in_and_preserves_inputs_labels_and_results(self):
        old = self.plan._document(); old["version"] = 28; old.pop("contours")
        before = copy.deepcopy(self.plan.taggar)
        self.plan._load_document(json.dumps(old).encode())
        self.assertFalse(self.plan.sulkonturer["enabled"])
        self.assertEqual(self.plan.sulkonturer["placements"], {})
        self.assertEqual(self.plan.taggar, before)
        self.plan.sulkonturer = {"enabled": True}
        self.assertEqual(self.plan.taggar, before)
        self.assertEqual(self.plan.sulkonturer["placements"], {}, "No placement is inferred from labels")

    def test_roundtrip_geometry_does_not_recalculate_or_move_labels(self):
        self.plan.kalibrering = self.calibration
        before = copy.deepcopy(self.plan.taggar)
        with patch.object(self.plan, "_refresh_tag") as calculate:
            self.plan.placera_sulkontur(self.pad, self.position)
            self.plan.placera_sulkontur(self.wall, {"kind":"wall", "start":{"x":.2,"y":.2}, "end":{"x":.7,"y":.2}})
            self.plan.sulkonturer = {"enabled": True, "fill_opacity": 0}
        calculate.assert_not_called(); self.assertEqual(self.plan.taggar, before)
        document = self.plan._document()
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan._document(), document)
        self.plan.uppdatera(self.pad, indata={"b": 2.5})
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)
        self.plan.uppdatera(self.pad, x=.8, y=.9)
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)

    def test_invalid_or_uncalibrated_placement_is_atomic_and_locks_are_respected(self):
        before = self.plan._document()
        with self.assertRaises(ValueError): self.plan.placera_sulkontur(self.pad, self.position)
        self.assertEqual(self.plan._document(), before)
        self.plan.kalibrering = self.calibration
        for p in [{**self.position, "angle_deg": float("nan")}, {**self.position, "center": {"x": 15,"y": .1}},
                  {"kind":"wall", "start":{"x":.2,"y":.2}, "end":{"x":.2,"y":.2}},
                  {"kind":"wall", "start":{"x":.2,"y":.2}, "end":{"x":.5,"y":.2}}]:
            with self.assertRaises(ValueError): self.plan.placera_sulkontur(self.pad, p)
        self.plan.las_placering([{"type":"tag","id":self.pad}])
        with self.assertRaises(ValueError): self.plan.placera_sulkontur(self.pad, self.position)
        for s in [{"enabled":1},{"fill_opacity":float("nan")},{"fill_opacity":-1},{"fill_opacity":2}]:
            with self.assertRaises(ValueError): self.plan.sulkonturer = s

    def test_history_and_deleted_objects_and_drawing_recalibration(self):
        self.plan.kalibrering = self.calibration
        self.assertTrue(self.message("contour_placement", id=self.pad, placement=self.position)["ok"])
        self.assertTrue(self.message("undo")["ok"])
        self.assertNotIn(self.pad, self.plan.sulkonturer["placements"])
        self.assertTrue(self.message("redo")["ok"])
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)
        self.plan.ritningsunderlag = {"scale": 1.2}
        self.assertIsNone(self.plan.kalibrering)
        self.assertEqual(self.plan.sulkonturer["placements"][self.pad], self.position)
        self.plan.ta_bort(self.pad)
        self.assertNotIn(self.pad, self.plan.sulkonturer["placements"])

    def test_export_snapshots_have_calibration_and_contours(self):
        self.plan.kalibrering = self.calibration
        self.plan.placera_sulkontur(self.pad, self.position)
        self.plan.sulkonturer = {"enabled":True}
        with patch.object(self.plan, "_pdf_bytes", return_value=b""), patch("an_calcs.notebook.grundplan_html.render_html", return_value=b"") as render:
            self.plan._html_bytes()
        self.assertEqual(render.call_args.args[0]["state"]["contours"], self.plan.sulkonturer)
        with patch("an_calcs.notebook.grundplan_pdf.render_pdf", return_value=b"") as render:
            self.plan._pdf_bytes()
        self.assertEqual(render.call_args.kwargs["calibration"], self.calibration)
        self.assertEqual(render.call_args.kwargs["contours"], self.plan.sulkonturer)

    def test_malformed_saved_placements_leave_project_intact(self):
        before = self.plan._document()
        bad = {**before, "contours":{"placements":{"missing":self.position}}}
        with self.assertRaises(ValueError): self.plan._load_document(json.dumps(bad).encode())
        self.assertEqual(self.plan._document(), before)
