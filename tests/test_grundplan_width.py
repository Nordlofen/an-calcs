import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from an_calcs.notebook.grundplan_width import allowed_widths, propose, validate_settings
HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan
    from an_calcs.notebook.grundplan import _calculate
    from test_grundplan_loads import document, encode


class TestWidthSearch(unittest.TestCase):
    def tag(self, **values):
        return {"id": "a", "label": "VS.1", "values": {"b": 1, "inaktiv": False, "endast_h_stabilitet": False, **values}}

    def test_grid_uses_absolute_multiples_without_rounding_a_result_upward(self):
        settings = validate_settings({"step_mm": 200, "b_min": .21, "b_max": 1.19})
        self.assertEqual(allowed_widths(settings), [.4, .6, .8, 1.0])
        def calculate(values):
            return {}, {"utnyttjandegrad": .59 / values["b"]}
        report, _ = propose([self.tag()], {"step_mm": 200, "b_min": .21, "b_max": 1.19,
                                          "u_min": 90, "u_max": 99}, calculate)
        self.assertEqual(report["rows"][0]["b_after"], .6)
        self.assertLessEqual(report["rows"][0]["u_after"], .99)

    def test_lower_is_a_goal_and_has_no_special_status_if_grid_skips_the_interval(self):
        def calculate(values):
            return {}, {"utnyttjandegrad": .54 / values["b"]}
        report, _ = propose([self.tag()], {"step_mm": 500, "b_min": .5, "b_max": 2,
                                          "u_min": 90, "u_max": 99}, calculate)
        row = report["rows"][0]
        self.assertEqual((row["b_after"], row["u_after"], row["status"], row["reason"]), (1, .54, "unchanged", ""))

    def test_nonmonotonic_utilization_prefers_first_width_in_interval_and_skips_invalid_widths(self):
        def calculate(values):
            if values["b"] == .5:
                raise ValueError("Invalid effective area")
            return {}, {"utnyttjandegrad": {1: .6, 1.5: .93, 2: .95}[values["b"]]}
        report, _ = propose([self.tag()], {"step_mm": 500, "b_min": .5, "b_max": 2,
                                          "u_min": 90, "u_max": 99}, calculate)
        self.assertEqual(report["rows"][0]["b_after"], 1.5)

    def test_validation_rejects_unsafe_or_empty_searches(self):
        for settings in [{"step_mm": 0}, {"step_mm": True}, {"step_mm": 99.5}, {"step_mm": 1},
                         {"u_min": 99, "u_max": 90}, {"u_max": 101}, {"u_min": -1},
                         {"b_min": 2, "b_max": 1}, {"b_max": float("inf")},
                         {"step_mm": 500, "b_min": .21, "b_max": .49}, {"extra": 1}, []]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_settings(settings)


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestAutoWidthAndInputLocks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        image = self.root / "drawing.png"; Image.new("RGB", (800, 600), "white").save(image)
        self.plan = Grundplan(image); self.addCleanup(self.plan.close)
        self.wall = self.plan.lagg_till(.2, .3, littera="W1", indata={"F_vy": 180, "b": 2})
        self.pad = self.plan.lagg_till(.4, .5, typ="pelarsula", littera="P1", indata={"F_vy": 350, "b": 2, "l": 2})

    def msg(self, action, **payload):
        with patch.object(self.plan, "send") as send:
            self.plan._on_message(self.plan, {"action": action, "view": "qa", "request": 1, **payload}, [])
        return send.call_args.args[0]

    def test_preview_does_not_mutate_and_matches_full_recalculation_for_mixed_models(self):
        self.plan.uppdatera(self.wall, indata={"isolering": True, "F_vy_bruk": 120,
                                            "f_d_brott": 200, "f_d_bruk": 90})
        before = self.plan._document(), self.plan.resultat, copy.deepcopy(self.plan.state)
        settings = {"step_mm": 100, "u_min": 70, "u_max": 99}
        report = self.plan.forhandsvisa_auto_bx([self.wall, self.pad], installningar=settings)
        self.assertEqual((self.plan._document(), self.plan.resultat, self.plan.state), before)
        self.assertEqual(report["skipped"], 0)
        self.assertEqual(report["changed"], 2)
        for row in report["rows"]:
            tag = self.plan._tag(row["id"])
            _, summary = _calculate({**tag["values"], "b": row["b_after"]})
            self.assertAlmostEqual(row["u_after"], summary["utnyttjandegrad"])
            self.assertLessEqual(row["u_after"], .99 + 1e-12)
        self.plan.tilldela_auto_bx(report["token"])
        for row in report["rows"]:
            tag = self.plan._tag(row["id"])
            self.assertEqual(tag["values"], {**before[0]["tags"][[self.wall, self.pad].index(tag["id"])]["values"], "b": row["b_after"]})
            details, summary = _calculate(tag["values"])
            self.assertEqual((self.plan.resultat[tag["id"]], tag["summary"]), (details, summary))

    def test_batch_application_is_one_undo_step_and_client_cannot_replace_results(self):
        original = self.plan._document()
        preview = self.msg("auto_bx_preview", ids=[self.wall, self.pad], settings={})["preview"]
        self.assertIsNone(self.plan.state["history"]["undo"])
        reply = self.msg("auto_bx_apply", token=preview["token"], values={"b": 100}, summary={"utnyttjandegrad": 0})
        self.assertTrue(reply["ok"])
        changed = self.plan._document()
        self.assertEqual(self.plan.state["history"]["undo_count"], 1)
        self.assertIn("bₓ", self.plan.state["history"]["undo"])
        self.assertTrue(self.msg("undo")["ok"]); self.assertEqual(self.plan._document(), original)
        self.assertTrue(self.msg("redo")["ok"]); self.assertEqual(self.plan._document(), changed)
        self.assertFalse(self.msg("auto_bx_apply", token=preview["token"])["ok"])

    def test_stale_preview_rejected_atomically_after_input_lock_rename_or_project_open(self):
        for mutate in [lambda: self.plan.uppdatera(self.wall, indata={"b": 2.1}),
                       lambda: self.plan.las_indata([self.pad]),
                       lambda: self.plan.uppdatera(self.pad, littera="P2"),
                       lambda: self.plan._load_document(json.dumps(self.plan._document()).encode())]:
            with self.subTest(mutate=mutate):
                self.plan.las_indata([self.wall, self.pad], last=False)
                report = self.plan.forhandsvisa_auto_bx([self.wall, self.pad])
                mutate(); before = self.plan._document(), self.plan.resultat
                with self.assertRaises(ValueError): self.plan.tilldela_auto_bx(report["token"])
                self.assertEqual((self.plan._document(), self.plan.resultat), before)

    def test_skipped_objects_and_no_valid_width_keep_all_existing_inputs(self):
        self.plan.las_indata([self.wall])
        inactive = self.plan.lagg_till(.1, .2, indata={"inaktiv": True})
        only_h = self.plan.lagg_till(.1, .3, indata={"endast_h_stabilitet": True})
        bad = self.plan.lagg_till(.1, .4, indata={"b": None})
        before = copy.deepcopy(self.plan._tags)
        report = self.plan.forhandsvisa_auto_bx([self.wall, inactive, only_h, bad, self.pad],
                                              installningar={"b_min": .2, "b_max": .2, "u_max": 1, "u_min": 0})
        self.assertEqual(report["skipped"], 5)
        self.assertEqual([r["reason"] for r in report["rows"][:3]], ["Låsta indata", "Inaktiv", "Endast H"])
        self.assertEqual(self.plan.tilldela_auto_bx(report["token"])["changed"], 0)
        self.assertEqual(self.plan._tags, before)

    def test_input_lock_enforces_all_inputs_but_keeps_calculation_position_and_copy_available(self):
        before = self.plan.resultat
        self.plan.las_indata([self.wall])
        for change in [{"indata": {"b": 1}}, {"indata": {"kommentar": "Edit"}},
                       {"indata": {"glid_x": True}}, {"indata": {"inaktiv": True}},
                       {"indata": {"lang": 0}}, {"littera": "Other"}]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "indata är låsta"):
                self.plan.uppdatera(self.wall, **change)
        self.plan.uppdatera(self.wall, x=.7, y=.8)
        self.plan.berakna(self.wall)
        self.assertEqual(self.plan.resultat, before)
        copied = self.plan.kopiera(self.wall, .3, .5)
        self.assertFalse(self.plan._tag(copied)["input_locked"])
        self.assertEqual(self.plan._tag(copied)["values"], self.plan._tag(self.wall)["values"])
        self.plan.las_indata([self.wall], last=False)
        self.plan.uppdatera(self.wall, indata={"kommentar": "Now editable"})

    def test_bulk_and_load_import_skip_locked_objects_instead_of_overwriting_them(self):
        self.plan.las_indata([self.wall])
        locked = copy.deepcopy(self.plan._tag(self.wall)), self.plan.resultat[self.wall]
        report = self.plan.uppdatera_flera([self.wall, self.pad], indata={"b": 2.5})
        self.assertEqual((report["updated"], report["locked"]), (1, 1))
        self.assertEqual((self.plan._tag(self.wall), self.plan.resultat[self.wall]), locked)
        report = self.plan._start_load_import(encode(document()), "loads.json")
        self.assertEqual((report["updated"], report["skipped_locked"]), (1, 1))
        self.assertEqual((self.plan._tag(self.wall), self.plan.resultat[self.wall]), locked)
        self.assertEqual(self.plan._tag(self.pad)["values"]["F_vy"], 120)

    def test_lock_roundtrip_legacy_defaults_and_undo_redo(self):
        before = self.plan._document()
        reply = self.msg("input_lock", ids=[self.wall, self.pad], locked=True)
        self.assertTrue(reply["ok"])
        self.assertTrue(all(t["input_locked"] for t in self.plan._tags))
        saved = self.plan.spara(self.root / "locked.json")
        restored = Grundplan.oppna(saved); self.addCleanup(restored.close)
        self.assertEqual(restored.taggar, self.plan.taggar)
        self.assertTrue(self.msg("undo")["ok"]); self.assertEqual(self.plan._document(), before)
        self.assertTrue(self.msg("redo")["ok"])
        legacy = self.plan._document(); legacy["version"] = 23
        for tag in legacy["tags"]: del tag["input_locked"]
        self.plan._load_document(json.dumps(legacy).encode())
        self.assertTrue(all(not t["input_locked"] for t in self.plan._tags))
        invalid = self.plan._document(); invalid["tags"][0]["input_locked"] = "yes"
        with self.assertRaises(ValueError): self.plan._load_document(json.dumps(invalid).encode())

    def test_invalid_lock_selection_is_atomic(self):
        for ids, locked in [([self.wall, "missing"], True), ([self.wall, self.wall], True), ([self.wall], 1), ([], True)]:
            with self.subTest(ids=ids, locked=locked), self.assertRaises(ValueError): self.plan.las_indata(ids, last=locked)
        self.assertFalse(self.plan._tag(self.wall)["input_locked"])
