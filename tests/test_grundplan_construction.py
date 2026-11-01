"""Construction-part dimensions are persisted annotations, never calculation inputs."""
import copy
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ('anywidget', 'PIL', 'pypdfium2'))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, 'Installera an-calcs[notebook].')
class TestConstructionPart(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); image = self.root / 'drawing.png'
        Image.new('RGB', (800, 600), 'white').save(image)
        self.plan = Grundplan(image); self.addCleanup(self.plan.close)
        self.pad = self.plan.lagg_till(.3, .3, typ='pelarsula', indata={'F_vy': 100, 'b': 2, 'l': 3})
        self.wall = self.plan.lagg_till(.5, .5, typ='vaggsula', indata={
            'F_vy': 100, 'physical_length': True, 'L_vagg': 2.6, 'l': 2.6})

    def message(self, action, **payload):
        with patch.object(self.plan, 'send') as send:
            self.plan._on_message(self.plan, {'action': action, 'view': 'test', 'request': 1, **payload}, [])
        reply = send.call_args.args[0]
        self.assertTrue(reply['ok'], reply)

    def test_visual_updates_preserve_engineering_and_refresh_pad_reference_keys(self):
        self.plan.jordprofil = {'layers': [{'dz': 1, 'Ek': 45, 'gamma_m': 1.3}], 'step': .1}
        reference_before = {g['category']:g['key'] for g in self.plan.referensgrupper['groups']}
        before = copy.deepcopy((self.plan.resultat, self.plan._details,
                                [tag.get('settlement') for tag in self.plan.state['tags']]))
        with patch.object(self.plan, '_refresh_tag', side_effect=AssertionError('Visual data cannot recalculate')):
            self.message('update', id=self.pad, values={'B_x': 300, 'B_y': 400})
            self.message('undo'); self.message('redo')
            report = self.plan.uppdatera_flera([self.pad, self.wall], indata={'B_x': 250})
        self.assertEqual(report['calculated'], 0)
        after = (self.plan.resultat, self.plan._details,
                 [tag.get('settlement') for tag in self.plan.state['tags']])
        self.assertEqual(after, before)
        reference_after = {g['category']:g['key'] for g in self.plan.referensgrupper['groups']}
        self.assertNotEqual(reference_after['pad'],reference_before['pad'])
        self.assertEqual(reference_after['wall'],reference_before['wall'])
        self.assertEqual(self.plan._tag(self.pad)['values']['B_y'], 400)
        self.assertEqual(self.plan._tag(self.wall)['values']['B_y'], 2600)

    def test_wall_length_is_derived_and_follows_length_changes(self):
        self.plan.uppdatera(self.wall, indata={'B_x': 200, 'B_y': 900})
        self.assertEqual(self.plan._tag(self.wall)['values']['B_y'], 2600)
        self.plan.uppdatera(self.wall, indata={'l': 2})
        self.assertEqual(self.plan._tag(self.wall)['values']['B_y'], 2000)
        self.plan.uppdatera(self.wall, indata={'l_override': False})
        self.assertEqual(self.plan._tag(self.wall)['values']['B_y'], 2600)

    def test_validation_is_atomic_optional_and_respects_input_lock(self):
        before = self.plan._document()
        for value in [-1, 0, float('inf'), float('nan'), True, '300']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan.uppdatera_flera([self.pad, self.wall], indata={'B_x': value})
            self.assertEqual(self.plan._document(), before)
        self.plan.uppdatera(self.pad, indata={'B_x': 300, 'B_y': 400})
        self.plan.uppdatera(self.pad, indata={'B_x': None, 'B_y': None})
        self.assertIsNone(self.plan._tag(self.pad)['values']['B_x'])
        self.plan.las_indata([self.pad])
        with self.assertRaisesRegex(ValueError, 'låst'):
            self.plan.uppdatera(self.pad, indata={'B_x': 300})

    def test_copy_roundtrip_and_old_documents_without_dimensions(self):
        self.plan.uppdatera(self.pad, indata={'B_x': 300, 'B_y': 400})
        copied = self.plan.kopiera(self.pad, .6, .6)
        self.assertEqual(self.plan._tag(copied)['values']['B_x'], 300)
        loaded = Grundplan.oppna(self.plan.spara(self.root / 'project.json')); self.addCleanup(loaded.close)
        self.assertEqual(loaded.taggar, self.plan.taggar)
        self.assertEqual(loaded._document()['version'], 35)
        old = self.plan._document(); old['version'] = 32
        for tag in old['tags']:
            tag['values'].pop('B_x'); tag['values'].pop('B_y')
        loaded._load_document(json.dumps(old).encode())
        self.assertIsNone(loaded._tag(self.pad)['values']['B_x'])
        self.assertIsNone(loaded._tag(self.pad)['values']['B_y'])
        self.assertEqual(loaded._tag(self.wall)['values']['B_y'], 2600)
        self.assertEqual(loaded.resultat, self.plan.resultat)

    def test_missing_dimensions_are_optional_even_with_insulation(self):
        self.plan.uppdatera(self.pad, indata={'isolering': True, 'F_vy_bruk': 50,
                                           'f_d_brott': 1000, 'f_d_bruk': 1000})
        self.assertEqual(self.plan._tag(self.pad)['status'], 'calculated')
        self.assertIsNone(self.plan._tag(self.pad)['values']['B_x'])
        self.assertIsNone(self.plan._tag(self.pad)['values']['B_y'])
