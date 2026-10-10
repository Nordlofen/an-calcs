"""Object edits must never alter engineering inputs or existing world coordinates."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from an_calcs.notebook import Grundplan


class TestObjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'drawing.png'
        Image.new('RGB', (800, 600), 'white').save(self.path)
        self.plan = Grundplan(self.path); self.addCleanup(self.plan.close)
        self.a = self.plan.lagg_till(.2, .3, indata={'F_vy': 100})
        self.b = self.plan.lagg_till(.6, .5, indata={'F_vy': 120})
        self.objects = [{'type': 'tag', 'id': self.a}, {'type': 'overlay', 'page': 1, 'kind': 'reference'}]
        self.calibration = {'start': {'x': .1, 'y': .2}, 'end': {'x': .6, 'y': .2}, 'length_m': 10}
        self.plan.kalibrering = self.calibration

    def message(self, action, buffers=None, **payload):
        with patch.object(self.plan, 'send') as send:
            self.plan._on_message(self.plan, {'action': action, 'request': 1, **payload}, buffers or [])
        return send.call_args.args[0]

    def test_group_transform_is_atomic_and_preserves_engineering(self):
        before = copy.deepcopy((self.plan.resultat, [t['values'] for t in self.plan.taggar]))
        objects = [{**item, 'x': .4, 'y': .5, 'scale': 1.8} for item in self.objects]
        with patch.object(self.plan, '_refresh_tag') as calculate, patch.object(self.plan, '_publish', wraps=self.plan._publish) as publish:
            self.plan.transformera_objekt(objects)
        calculate.assert_not_called(); publish.assert_called_once()
        self.assertEqual((self.plan.resultat, [t['values'] for t in self.plan.taggar]), before)
        self.assertEqual(self.plan.objektlayout['scales']['tag:' + self.a], 1.8)
        self.assertEqual(self.plan.referens['x'], .4)
        self.assertEqual(self.plan.kalibrering, self.calibration)
        self.plan.las_placering([self.objects[1]])
        document = self.plan._document()
        for invalid in (objects, [{**objects[0], 'scale': float('nan')}], [{**objects[0], 'scale': True}],
                        [{**objects[0], 'x': 12}], [objects[0], objects[0]]):
            with self.assertRaises(ValueError): self.plan.transformera_objekt(invalid)
            self.assertEqual(self.plan._document(), document)

    def test_locked_sizes_and_global_label_slider(self):
        self.plan.las_placering(self.objects)
        with self.assertRaisesRegex(ValueError, 'låst'): self.plan.referens = {'size': 600}
        self.plan.referens = {'enabled': True}
        self.plan.uppdatera(self.a, indata={'kommentar': 'Tillåten kommentar'})
        self.plan.etikettstorlek = 150
        self.assertAlmostEqual(self.plan.objektlayout['scales']['tag:' + self.a] * 150, 100)
        self.assertNotIn('tag:' + self.b, self.plan.objektlayout['scales'])

    def test_underlay_move_scale_and_replacement_use_fixed_world_coordinates(self):
        original = copy.deepcopy((self.plan.taggar, self.plan.resultat, self.plan.ritningsram))
        self.plan.ritningsunderlag = {'x': -.1, 'y': .2}
        self.assertEqual(self.plan.kalibrering, self.calibration)
        self.plan.ritningsunderlag = {'scale': .75}
        self.assertIsNone(self.plan.kalibrering)
        self.plan.kalibrering = self.calibration
        larger = Path(self.tmp.name) / 'large.png'; Image.new('RGB', (1200, 950)).save(larger)
        self.plan.importera_ritning(larger)
        self.assertIsNone(self.plan.kalibrering)
        self.assertEqual((self.plan.background['width'], self.plan.background['height']), (800, 600))
        self.assertEqual((self.plan.background['source_width'], self.plan.background['source_height']), (1200, 950))
        self.assertEqual(self.plan.ritningsunderlag['scale'], .75)
        self.assertEqual((self.plan.taggar, self.plan.resultat, self.plan.ritningsram), original)
        before = self.plan._document()
        for changes in ({'scale': 0}, {'scale': True}, {'x': float('inf')}, {'canvas_width': 1000}, {'z': 1}):
            with self.assertRaises(ValueError): self.plan.ritningsunderlag = changes
            self.assertEqual(self.plan._document(), before)

    def test_drawing_preview_cancel_failure_and_commit(self):
        original = self.plan._document()
        data = io.BytesIO(); Image.new('RGB', (1200, 400), 'red').save(data, format='PNG')
        reply = self.message('drawing', [data.getvalue()], draft=True, name='new.png')
        self.assertTrue(reply['ok']); preview = reply['drawing_preview']
        self.assertEqual(self.plan._document(), original)
        self.assertEqual(preview['background']['width'], 800)
        self.assertEqual(preview['background']['source_width'], 1200)
        bad = self.message('drawing_commit', token=preview['token'], layout={'x': 0, 'y': 0, 'scale': 0})
        self.assertFalse(bad['ok']); self.assertEqual(self.plan._document(), original)
        self.message('drawing_cancel', token=preview['token'])
        self.assertEqual(self.plan._document(), original)
        self.assertFalse(self.message('drawing_commit', token=preview['token'], layout={'x': 0, 'y': 0, 'scale': 1})['ok'])
        reply = self.message('drawing', [data.getvalue()], draft=True, name='new.png')
        self.assertTrue(self.message('drawing_commit', token=reply['drawing_preview']['token'], layout={'x': .2, 'y': .1, 'scale': .8})['ok'])
        self.assertIsNone(self.plan.kalibrering)
        self.assertEqual(self.plan.ritningsunderlag['scale'], .8)
        self.assertEqual(self.plan._filename, 'new.png')
        self.assertEqual(self.plan._document()['tags'], original['tags'])

    def test_layers_all_four_commands_and_underlay_cannot_enter_order(self):
        order = self.plan.objektlayout['order']; a = 'tag:' + self.a
        self.plan.lagerordning([self.objects[0]], 'forward')
        self.assertEqual(self.plan.objektlayout['order'][order.index(a) + 1], a)
        self.plan.lagerordning([self.objects[0]], 'front')
        self.assertEqual(self.plan.objektlayout['order'][-1], a)
        self.plan.lagerordning([self.objects[0]], 'backward')
        self.assertEqual(self.plan.objektlayout['order'][-2], a)
        self.plan.lagerordning([self.objects[0]], 'back')
        self.assertEqual(self.plan.objektlayout['order'][0], a)
        with self.assertRaises(ValueError): self.plan.lagerordning([{'type': 'drawing'}], 'front')
        with self.assertRaises(ValueError): self.plan.lagerordning(self.objects, 'unknown')

    def test_save_open_legacy_and_invalid_layout_are_atomic(self):
        self.plan.transformera_objekt([{**self.objects[0], 'x': .4, 'y': .5, 'scale': 2}])
        self.plan.lagerordning(self.objects, 'front')
        self.plan.ritningsunderlag = {'x': -.1, 'scale': .8}
        self.plan.spara(Path(self.tmp.name) / 'project.json')
        loaded = Grundplan.oppna(Path(self.tmp.name) / 'project.json'); self.addCleanup(loaded.close)
        self.assertEqual(loaded._document(), self.plan._document())
        original = loaded._document()
        for patch_value in ({'order': ['drawing']}, {'scales': {'tag:' + self.a: float('nan')}},
                            {'order': ['tag:' + self.a] * 2}, {'scales': {'missing': 1}}):
            invalid = {**original, 'object_layout': patch_value}
            with self.assertRaises(ValueError): loaded._load_document(json.dumps(invalid).encode())
            self.assertEqual(loaded._document(), original)
        legacy = {**original, 'version': 22}; legacy.pop('object_layout'); legacy.pop('drawing_layout')
        loaded._load_document(json.dumps(legacy).encode())
        self.assertEqual(loaded.objektlayout['scales'], {})
        self.assertEqual(loaded.ritningsunderlag['scale'], 1)
        loaded.ta_bort(self.a)
        self.assertNotIn('tag:' + self.a, loaded.objektlayout['order'])
