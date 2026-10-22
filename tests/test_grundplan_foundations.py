import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from an_calcs.notebook.grundplan_foundations import foundation_result
from an_calcs.notebook.grundplan_settlement import evaluate

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ('anywidget', 'PIL', 'pypdfium2'))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan

PROFILE = {'layers': [{'dz': 1, 'Ek': 45, 'gamma_m': 1.3}, {'dz': .5, 'Ek': 30, 'gamma_m': 1.3}], 'step': .1}


@unittest.skipUnless(HAS_NOTEBOOK, 'Installera an-calcs[notebook].')
class TestCommonFoundations(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'plan.png'
        Image.new('RGB', (800, 600), 'white').save(self.path)
        self.plan = Grundplan(self.path)
        self.addCleanup(self.plan.close)
        self.ids = [self.plan.lagg_till(.1 + i * .2, .4, littera='H-GR.' + str(i + 1),
            indata={'endast_h_stabilitet': True, 'b': .8, 't': .2, 'F_vy_bruk': load, 'L_vagg': length,
                    'glid_x': True, 'V_Ed_EQU': 100, 'glid_mu': .4, 'glid_L': length})
            for i, (load, length) in enumerate([(100, 2), (200, 3), (50, 1), (40, .5)])]
        self.plan.jordprofil = PROFILE

    def create(self, **overrides):
        args = dict(namn='Hissgrop 1', bx=4, by=5, t=.4)
        args.update(overrides)
        return self.plan.satt_gemensamt_fundament(self.ids, **args)

    def command(self, **message):
        with patch.object(self.plan, 'send') as send:
            self.plan._on_message(None, message, [])
        return send.call_args.args[0]

    def payload(self, **changes):
        item = self.plan._common_foundations[0]
        return {'action': 'common_foundation', 'id': item['id'], 'ids': item['members'], 'label': item['label'],
                'values': item['values'], 'soil_profile': item['soil_profile'], 'form': item['form'],
                'show_labels': item['show_labels'], 'label_member': item['label_member'], **changes}

    def test_plate_uses_all_full_line_loads_and_self_weight_exactly_once(self):
        before = [(tag['summary'], tag['sliding']) for tag in self.plan.taggar]
        self.create()
        item = self.plan.gemensamma_fundament[0]
        expected = evaluate({'lang': 0, 'lasttyp': 0, 'b': 4, 'l': 5, 't': .4, 'F_vy_bruk': 870}, PROFILE)
        self.assertEqual(item['external'], 870)
        self.assertEqual(item['settlement']['self_weight'], 200)
        self.assertEqual(item['settlement']['load'], 1070)
        for name in ('s', 'k', 'K'):
            self.assertEqual(item['settlement'][name], expected[name])
        self.assertEqual([load['resultant'] for load in item['loads']], [200, 600, 50, 20])
        self.assertTrue(all('settlement' not in tag for tag in self.plan.taggar))
        self.assertTrue(all(tag['common_foundation_id'] == item['id'] for tag in self.plan.taggar))
        self.assertEqual([(tag['summary'], tag['sliding']) for tag in self.plan.taggar], before)

    def test_unlinked_only_h_remains_independent_and_dissolving_restores_individual_profiles(self):
        self.plan.satt_jordprofil(self.ids[0], {'layers': PROFILE['layers'][:1], 'step': .1})
        before = self.plan.sattningsresultat
        ident = self.create()
        clone = self.plan.kopiera(self.ids[0], .2, .7)
        self.assertNotIn('common_foundation_id', self.plan._tag(clone))
        self.assertIn(clone, self.plan.sattningsresultat)
        self.plan.los_upp_fundament(ident)
        for key, value in before.items():
            self.assertEqual(self.plan.sattningsresultat[key], value)

    def test_profile_changes_load_edits_and_reporting_recompute_the_plate(self):
        ident = self.create()
        old = self.plan.gemensamma_fundament[0]['settlement']
        self.plan.uppdatera(self.ids[0], indata={'F_vy_bruk': 150})
        self.assertEqual(self.plan.gemensamma_fundament[0]['external'], 970)
        self.assertGreater(self.plan.gemensamma_fundament[0]['settlement']['s'], old['s'])
        new_profile = copy.deepcopy(PROFILE)
        for layer in new_profile['layers']:
            layer['Ek'] *= 2
        self.create(ident=ident, jordprofil=new_profile, form='yta')
        item = self.plan.gemensamma_fundament[0]
        self.assertEqual(item['settlement']['display_value'], item['settlement']['k'])
        self.assertEqual(item['settlement']['display_unit'], 'kN/m²/m')
        self.assertAlmostEqual(item['settlement']['K'], old['K'] * 2)
        own = copy.deepcopy(item['settlement'])
        self.plan.jordprofil = None
        self.assertEqual(self.plan.gemensamma_fundament[0]['settlement'], own)

    def test_missing_load_or_full_length_never_produces_partial_settlement(self):
        self.create()
        for changes in ({'F_vy_bruk': None}, {'F_vy_bruk': 100, 'L_vagg': None}):
            self.plan.uppdatera(self.ids[0], indata=changes)
            item = self.plan.gemensamma_fundament[0]
            self.assertIsNone(item['external'])
            self.assertIsNone(item['settlement']['s'])
            self.assertGreater(item['settlement']['K'], 0)
            self.assertIn('H-GR.1', item['settlement']['settlement_error'])
        self.plan.uppdatera(self.ids[0], indata={'inaktiv': True})
        item = self.plan.gemensamma_fundament[0]
        self.assertEqual(item['external'], 670)
        self.assertEqual(item['active_count'], 3)
        self.assertIsNotNone(item['settlement']['s'])
        for ident in self.ids[1:]:
            self.plan.uppdatera(ident, indata={'inaktiv': True})
        self.assertIsNone(self.plan.gemensamma_fundament[0]['settlement'])

    def test_point_and_line_actions_keep_sign_and_do_not_multiply_point_loads(self):
        point = self.plan.lagg_till(.2, .6, typ='pelarsula', littera='PS.1', indata={'F_vy_bruk': -20})
        self.plan.satt_gemensamt_fundament([self.ids[0], point], namn='Mix', bx=4, by=5, t=.4)
        item = self.plan.gemensamma_fundament[0]
        self.assertEqual(item['external'], 180)
        self.assertFalse(item['loads'][1]['line'])

    def test_group_and_member_updates_are_one_atomic_undoable_command(self):
        self.create()
        before = self.plan._document()
        reply = self.command(**self.payload(values={'b': 5, 'l': 6, 't': .5},
            member_updates={self.ids[0]: {'F_vy_bruk': 150, 'L_vagg': 4}}))
        self.assertTrue(reply['ok'])
        self.assertEqual(self.plan.gemensamma_fundament[0]['external'], 1270)
        self.assertTrue(self.plan._tag(self.ids[0])['values']['L_vagg_minst_1'])
        self.assertEqual(self.plan._history.state['undo_count'], 1)
        after = self.plan._document()
        self.plan.angra()
        self.assertEqual(self.plan._document(), before)
        self.plan.gor_om()
        self.assertEqual(self.plan._document(), after)
        self.assertFalse(self.command(**self.payload(values={'b': -1, 'l': 6, 't': .5},
            member_updates={self.ids[0]: {'F_vy_bruk': 999}}))['ok'])
        self.assertEqual(self.plan._document(), after)

    def test_membership_validation_locking_and_old_member_settings_are_atomic(self):
        self.create()
        before = self.plan._document()
        for overrides in ({'taggar': [self.ids[0]], 'namn': 'Other'}, {'form': 'linje'}, {'bx': True}, {'bx': float('inf')}):
            args = dict(taggar=self.ids, namn='Other', bx=3, by=4, t=.3)
            args.update(overrides)
            with self.assertRaises(ValueError):
                self.plan.satt_gemensamt_fundament(**args)
            self.assertEqual(self.plan._document(), before)
        self.assertFalse(self.command(action='soil_profile', id=self.ids[0], profile=PROFILE)['ok'])
        self.assertFalse(self.command(action='settlement_display', id=self.ids[0], settings={'form': 'yta'})['ok'])
        reply = self.command(action='soil_profile_patch', ids=self.ids, field='step', value=.2)
        self.assertEqual(reply['updated'], 0)
        self.plan.las_indata([self.ids[0]])
        self.assertFalse(self.command(**self.payload())['ok'])
        self.assertFalse(self.command(action='common_foundation_delete', id=self.plan._common_foundations[0]['id'])['ok'])

    def test_delete_prunes_members_and_history_restores_links(self):
        self.create()
        self.assertTrue(self.command(action='delete', id=self.ids[0])['ok'])
        self.assertEqual(self.plan._common_foundations[0]['members'], self.ids[1:])
        self.assertEqual(self.plan._common_foundations[0]['label_member'], self.ids[1])
        self.plan.angra()
        self.assertEqual(self.plan._common_foundations[0]['members'], self.ids)
        self.assertTrue(self.command(action='delete_all')['ok'])
        self.assertEqual(self.plan.gemensamma_fundament, [])
        self.plan.angra()
        self.assertEqual(self.plan._common_foundations[0]['members'], self.ids)

    def test_save_roundtrip_legacy_default_and_corrupt_membership(self):
        self.create()
        document = self.plan._document()
        restored = Grundplan.oppna(self.plan.spara(Path(self.folder.name) / 'common.json'))
        self.addCleanup(restored.close)
        self.assertEqual(restored.gemensamma_fundament, self.plan.gemensamma_fundament)
        broken = copy.deepcopy(document)
        broken['common_foundations'][0]['members'].append('missing')
        with self.assertRaises(ValueError):
            self.plan._load_document(json.dumps(broken).encode())
        self.assertEqual(self.plan._document(), document)
        old = copy.deepcopy(document)
        old['version'] = 27
        old.pop('common_foundations')
        restored._load_document(json.dumps(old).encode())
        self.assertEqual(restored.gemensamma_fundament, [])
        self.assertEqual(len(restored.sattningsresultat), 4)

    def test_finite_individual_loads_cannot_overflow_the_total(self):
        self.create()
        tags = copy.deepcopy(self.plan._tags)
        for tag in tags:
            tag['values'].update(lasttyp=0, lang=0, F_vy_bruk=1e308)
        item = foundation_result(self.plan._common_foundations[0], tags, PROFILE)
        self.assertIsNone(item['external'])
        self.assertIsNone(item['settlement']['s'])
        self.assertGreater(item['settlement']['K'], 0)
        json.dumps(item, allow_nan=False)
