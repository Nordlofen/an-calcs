import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))
HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook] för notebooktesterna.")
class TestGrundplanState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve()
        self.drawing = self.folder / "plan.png"
        self.store = self.folder / "projects.json"
        Image.new("RGB", (800, 600), "white").save(self.drawing)

    def plan(self, *args, **kwargs):
        plan = Grundplan(*args, **kwargs)
        self.addCleanup(plan.close)
        return plan

    def command(self, plan, **message):
        with patch.object(plan, "send") as send:
            plan._on_message(None, message, [])
            return send.call_args.args[0]

    def test_first_ui_save_binds_destination_and_generates_pasteable_arguments(self):
        plan = self.plan(self.drawing)
        ident = plan.lagg_till(.2, .3, littera="VS1")
        plan.berakna(ident)
        key = "Fall '1' \\ ÅÄÖ"
        filename = "Projekt 'A'.json"
        with patch("os.getcwd", return_value=str(self.folder)):
            reply = self.command(plan, action="save", key=key, state_file=filename)
            self.assertTrue(reply["ok"])
            self.assertEqual(plan.state_file, self.folder / filename)
            args = {item.arg: ast.literal_eval(item.value) for item in
                    ast.parse("Grundplan(" + reply["storage"]["arguments"] + ")", mode="eval").body.keywords}
            self.assertEqual(args, {"key": key, "state_file": filename})
            restored = self.plan(**args)
        self.assertEqual(restored.taggar, plan.taggar)
        self.assertEqual(plan.key, key)
        self.assertNotIn("download", reply)

    def test_ui_destination_validation_and_write_failure_do_not_change_binding(self):
        plan = self.plan(self.drawing, key="Original", state_file=self.store)
        plan.spara()
        before = self.store.read_bytes()
        for payload in ({"key": "", "state_file": "new.json"}, {"key": "Ny", "state_file": ""},
                        {"key": "Ny"}, {"state_file": "new.json"}, {"key": "Ny", "state_file": "x.pdf"}):
            reply = self.command(plan, action="save", **payload)
            self.assertFalse(reply["ok"])
        destination = self.folder / "new.json"
        with patch.object(Path, "replace", side_effect=OSError("Skrivfel")):
            reply = self.command(plan, action="save", key="Ny", state_file=str(destination))
        self.assertFalse(reply["ok"])
        self.assertEqual((plan.key, plan.state_file), ("Original", self.store))
        self.assertEqual(self.store.read_bytes(), before)
        self.assertFalse(destination.exists())

    def test_ui_existing_destination_requires_confirmation_and_preserves_other_keys(self):
        old = self.plan(self.drawing, key="A", state_file=self.store)
        old.titel = "Tidigare A"
        old.spara()
        other = self.plan(self.drawing, key="B", state_file=self.store)
        other.titel = "Behåll B"
        other.spara()
        new = self.plan(self.drawing)
        new.titel = "Nytt A"
        before = self.store.read_bytes()
        reply = self.command(new, action="save", key="A", state_file=str(self.store))
        self.assertTrue(reply["conflict"])
        self.assertFalse(reply["ok"])
        self.assertIsNone(new.key)
        self.assertEqual(self.store.read_bytes(), before)
        reply = self.command(new, action="save", key="A", state_file=str(self.store), overwrite=True)
        self.assertTrue(reply["ok"])
        projects = json.loads(self.store.read_text())["projects"]
        self.assertEqual(projects["A"]["title"], "Nytt A")
        self.assertEqual(projects["B"]["title"], "Behåll B")
        new.titel = "Ändra samma projekt"
        reply = self.command(new, action="save", key="A", state_file=str(self.store))
        self.assertTrue(reply["ok"], "Normal save to the current destination needs no collision confirmation")

    def test_save_choices_include_known_file_and_local_projects_only(self):
        known = self.plan(self.drawing, key="B", state_file=self.store)
        known.spara()
        self.plan(self.drawing, key="A", state_file=self.store).spara()
        nearby = self.folder / "nearby"
        nearby.mkdir()
        (nearby / "unrelated.json").write_text('{"unrelated":true}')
        (nearby / "corrupt.json").write_text("invalid JSON")
        self.plan(self.drawing, key="C", state_file=nearby / "hus_c.json").spara()
        with patch("os.getcwd", return_value=str(nearby)):
            reply = self.command(known, action="save_choices")
        self.assertTrue(reply["ok"])
        by_file = {item["state_file"]: item for item in reply["choices"]}
        self.assertEqual(set(by_file), {str(self.store), "hus_c.json"})
        self.assertEqual(by_file[str(self.store)]["keys"], ["A", "B"])
        self.assertEqual(by_file["hus_c.json"]["keys"], ["C"])
        self.assertNotIn("projects", by_file["hus_c.json"], "Choice metadata omits drawings and calculation inputs")

    def test_key_restores_drawing_results_and_metadata_without_original_file(self):
        plan = self.plan(self.drawing, key="Hus A", state_file=self.store)
        ident = plan.lagg_till(.2, .7, littera="VS3", indata={"F_vy": 120})
        plan.berakna(ident)
        plan.titel = "Projekt A"
        plan.underrubrik = "Revision B"
        plan.etikettstorlek = 140
        self.assertFalse(self.store.exists(), "Lagring sker först när Spara används")
        self.assertEqual(plan.spara(), self.store)
        self.drawing.unlink()
        restored = self.plan("Hus A", state_file=self.store)
        self.assertEqual(restored.key, "Hus A")
        self.assertEqual(restored.background, plan.background)
        self.assertEqual(restored.taggar, plan.taggar)
        self.assertEqual(restored.resultat, plan.resultat)
        self.assertEqual((restored.titel, restored.underrubrik, restored.etikettstorlek),
                         ("Projekt A", "Revision B", 140))
        seed = self.plan(self.drawing, key="Hus A", state_file=self.store, titel="Ignorera")
        self.assertEqual(seed.taggar, plan.taggar, "Sparat projekt går före en startritning")

    def test_keys_are_independent_and_saved_only_on_request(self):
        first = self.plan(self.drawing, key="A", state_file=self.store)
        second = self.plan(self.drawing, key="B", state_file=self.store)
        a = first.lagg_till(.1, .2, indata={"F_vy": 100})
        b = second.lagg_till(.5, .6, indata={"F_vy": 200})
        first.spara()
        second.spara()
        previous = self.store.read_bytes()
        first.uppdatera(a, indata={"F_vy": None})
        self.assertEqual(self.store.read_bytes(), previous)
        first.spara()
        restored_a = self.plan("A", state_file=self.store)
        restored_b = self.plan("B", state_file=self.store)
        self.assertIsNone(restored_a._tag(a)["values"]["F_vy"])
        self.assertEqual(restored_b._tag(b)["values"]["F_vy"], 200)
        self.assertEqual(self.plan("C", state_file=self.store).taggar, [], "En ny key är ett eget tomt projekt")
        copy = first.spara(self.folder / "portable.json")
        portable = Grundplan.oppna(copy)
        self.addCleanup(portable.close)
        self.assertIsNone(portable.key)
        self.assertEqual(portable.taggar, restored_a.taggar)
        self.assertEqual(set(json.loads(self.store.read_text())["projects"]), {"A", "B"})

    def test_state_file_configuration_priority_and_legacy_constructor(self):
        with patch.object(Grundplan, "_STATE_FILE", None), patch.object(Grundplan, "STATE_FILENAME", str(self.store)):
            self.assertEqual(self.plan("A").state_file, self.store)
            configured = self.folder / "configured.json"
            Grundplan.configure_state_file(configured)
            self.assertEqual(self.plan("A").state_file, configured)
            self.assertEqual(self.plan("A", state_file=self.store).state_file, self.store)
            Grundplan.configure_state_file(None)
            self.assertEqual(self.plan("A").state_file, self.store)
        legacy = self.plan(str(self.drawing))
        self.assertIsNone(legacy.key)
        self.assertIsNone(legacy.state_file)
        self.assertEqual(legacy.background["name"], "plan.png")
        with self.assertRaisesRegex(ValueError, "key"):
            self.plan(state_file=self.store)
        with self.assertRaisesRegex(ValueError, "tom"):
            self.plan(key=" ")

    def test_fresh_python_process_loads_default_store_near_notebook(self):
        code = """
from pathlib import Path
from an_calcs.notebook import Grundplan
plan = Grundplan(Path('plan.png'), key='grundA')
tag = plan.lagg_till(.2, .3, littera='VS7', indata={'F_vy': 120})
plan.berakna(tag)
plan.spara()
assert plan.state_file == Path('.an_calcs_grundplan_state.json').resolve()
plan.close()
"""
        env = {**os.environ, "PYTHONPATH": str(SOURCE)}
        subprocess.run([sys.executable, "-c", code], cwd=self.folder, env=env, check=True, capture_output=True, text=True)
        self.drawing.unlink()
        code = """
from an_calcs.notebook import Grundplan
plan = Grundplan('grundA')
assert plan.taggar[0]['label'] == 'VS7'
assert plan.taggar[0]['status'] == 'calculated'
assert plan.taggar[0]['values']['F_vy'] == 120
assert plan.background['name'] == 'plan.png'
plan.close()
"""
        subprocess.run([sys.executable, "-c", code], cwd=self.folder, env=env, check=True, capture_output=True, text=True)

    def test_corrupt_store_and_failed_write_preserve_existing_data(self):
        plan = self.plan(self.drawing, key="A", state_file=self.store)
        plan.spara()
        previous = self.store.read_bytes()
        plan.titel = "Ändrad"
        with patch.object(Path, "replace", side_effect=OSError("Skrivfel")):
            with self.assertRaisesRegex(OSError, "Skrivfel"):
                plan.spara()
        self.assertEqual(self.store.read_bytes(), previous)
        self.assertEqual(set(self.folder.iterdir()), {self.drawing, self.store}, "Temporär skrivfil städas bort")
        for invalid in (b"not json", b'{}', b'{"format":"an-calcs-grundplan-state","version":1,"projects":{"A":null}}'):
            self.store.write_bytes(invalid)
            with self.assertRaises(ValueError):
                self.plan("A", state_file=self.store)
            self.assertEqual(self.store.read_bytes(), invalid)
        self.store.write_bytes(b"not json")
        with self.assertRaises(ValueError):
            plan.spara()
        self.assertEqual(self.store.read_bytes(), b"not json")

    def test_ui_saves_locally_and_json_export_stays_portable(self):
        plan = self.plan(self.drawing, key="A", state_file=self.store)
        ident = plan.lagg_till(.2, .3)
        plan.berakna(ident)
        with patch.object(plan, "send") as send:
            plan._on_message(None, {"action": "save", "request": 1}, [])
            reply = send.call_args.args[0]
            self.assertTrue(reply["ok"])
            self.assertEqual(reply["saved_file"], str(self.store))
            self.assertNotIn("download", reply)
            plan._on_message(None, {"action": "export_json", "request": 2}, [])
            reply = send.call_args.args[0]
            self.assertEqual(json.loads(reply["download"])["format"], "an-calcs-grundplan")
            self.assertNotIn("storage", json.loads(reply["download"]))
        self.assertEqual(plan.state["storage"]["path"], str(self.store))
        self.assertNotIn(str(self.store).encode(), plan._html_bytes(), "Resultat-HTML innehåller inga lokala lagringssökvägar")


if __name__ == "__main__":
    unittest.main()
