import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from an_calcs.notebook.grundplan_settlement import evaluate, validate_profile, _evaluate
from an_calcs.notebook.grundplan_colour import group_data, validate_settings

PROFILE = {'layers': [{'dz': .5, 'Ek': 10, 'gamma_m': 1.5}], 'step': .5}
HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ('anywidget', 'PIL', 'pypdfium2'))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


class TestSettlementCalculation(unittest.TestCase):
    def values(self, **changes):
        return {'lang': 0, 'b': 2, 'l': 3, 't': .25, 'F_vy_bruk': 120, 'lasttyp': 0,
                'L_vagg': None, 'L_vagg_minst_1': True, **changes}

    def test_hand_calculated_pad_and_strip_include_characteristic_self_weight(self):
        for values, load, k, K, spread in [(self.values(), 157.5, 16250, 97500, 2.25 * 3.25),
                (self.values(lang=1, lasttyp=1, l=1), 132.5, 15000, 30000, 2.25)]:
            result = evaluate(values, PROFILE)
            self.assertAlmostEqual(result['load'], load)
            self.assertAlmostEqual(result['k'], k)
            self.assertAlmostEqual(result['K'], K)
            self.assertAlmostEqual(result['s'], load / spread / (10000 / 1.5) * .5 * 1000)
            self.assertFalse(result['settlement_error'])

    def test_line_support_resultants_and_strip_distribution_match_existing_rules(self):
        result = evaluate(self.values(lasttyp=1, L_vagg=.4), PROFILE)
        self.assertAlmostEqual(result['external'], 48)
        self.assertAlmostEqual(result['self_weight'], 37.5)
        self.assertEqual(result['model'], 'PS')
        result = evaluate(self.values(lang=1, lasttyp=1, l=.5, L_vagg=.4, L_vagg_minst_1=False), PROFILE)
        self.assertAlmostEqual(result['external'], 96)
        self.assertAlmostEqual(result['load'], 108.5)
        self.assertEqual(result['model'], 'VS')

    def test_missing_service_or_geometry_affects_only_relevant_new_result(self):
        for changes in ({'F_vy_bruk': None}, {'t': None}, {'F_vy_bruk': -1000}, {'lasttyp': 1}):
            result = evaluate(self.values(**changes), PROFILE)
            self.assertIsNone(result['s'])
            self.assertEqual(result['k'], 16250)
            self.assertTrue(result['settlement_error'])
        result = evaluate(self.values(b=None), PROFILE)
        self.assertIsNone(result['s']); self.assertIsNone(result['k'])
        self.assertTrue(result['stiffness_error'])

    def test_no_profile_inactive_and_only_h_never_call_calculators(self):
        _evaluate.cache_clear()
        with patch('an_calcs.notebook.grundplan_settlement.sattning') as settlement, patch('an_calcs.notebook.grundplan_settlement.baddmodul') as stiffness:
            for values, profile in [(self.values(), None), (self.values(inaktiv=True), PROFILE),
                                    (self.values(endast_h_stabilitet=True), PROFILE)]:
                self.assertIsNone(evaluate(values, profile))
            settlement.assert_not_called(); stiffness.assert_not_called()

    def test_profile_validation_is_strict_bounded_and_copied(self):
        self.assertIsNone(validate_profile(None))
        result = validate_profile(PROFILE); result['layers'][0]['Ek'] = 99
        self.assertEqual(PROFILE['layers'][0]['Ek'], 10)
        bad = [[], {}, {'layers': []}, {**PROFILE, 'step': 0}, {**PROFILE, 'step': .00000001},
               {**PROFILE, 'extra': True}, {'layers': [PROFILE['layers'][0]] * 51}]
        for field in ('dz', 'Ek', 'gamma_m'):
            for value in (None, False, 0, -1, float('nan'), float('inf')):
                bad.append({**PROFILE, 'layers': [{**PROFILE['layers'][0], field: value}]})
        for profile in bad:
            with self.subTest(profile=profile), self.assertRaises(ValueError): validate_profile(profile)

    def test_new_calculations_delegate_to_existing_functions_without_mutating_inputs(self):
        from an_calcs.geo import sattning, baddmodul
        _evaluate.cache_clear()
        values, profile = self.values(), copy.deepcopy(PROFILE)
        before = copy.deepcopy((values, profile))
        with patch('an_calcs.notebook.grundplan_settlement.sattning', wraps=sattning) as settlement, \
             patch('an_calcs.notebook.grundplan_settlement.baddmodul', wraps=baddmodul) as stiffness:
            result = evaluate(values, profile)
            settlement.assert_called_once_with(['PS', .5, [.5], [10], [1.5], 157.5, 2, 3])
            stiffness.assert_called_once()
            self.assertEqual(stiffness.call_args.args[0][2], 'yta')
            result['s'] = -1
            self.assertGreater(evaluate(values, profile)['s'], 0)
        self.assertEqual((values, profile), before)


@unittest.skipUnless(HAS_NOTEBOOK, 'Installera notebookberoenden.')
class TestSettlementProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name); self.image = self.folder / 'plan.png'
        Image.new('RGB', (1400, 1000), 'white').save(self.image)
        self.plan = self.new_plan()
        self.ident = self.plan.lagg_till(.3, .3, typ='pelarsula', indata={'b': 2, 'l': 3, 't': .25, 'F_vy_bruk': 120})

    def new_plan(self):
        plan = Grundplan(self.image); self.addCleanup(plan.close); return plan

    def command(self, **message):
        with patch.object(self.plan, 'send') as send:
            self.plan._on_message(None, message, [])
        return send.call_args.args[0]

    def test_profiles_never_change_bearing_utilization_or_sliding(self):
        before = copy.deepcopy((self.plan._tags, self.plan.resultat, self.plan.glidningsresultat))
        self.assertNotIn('settlement', self.plan.taggar[0])
        self.plan.jordprofil = PROFILE
        self.assertEqual((self.plan._tags, self.plan.resultat, self.plan.glidningsresultat), before)
        self.assertAlmostEqual(self.plan.sattningsresultat[self.ident]['load'], 157.5)
        self.plan.jordprofil = None
        self.assertEqual(self.plan.sattningsresultat, {})
        self.assertNotIn('settlement', self.plan.taggar[0])

    def test_shared_and_individual_profiles_update_automatically_and_copy_independently(self):
        self.plan.jordprofil = PROFILE
        custom = copy.deepcopy(PROFILE); custom['layers'][0]['Ek'] = 20
        self.plan.satt_jordprofil(self.ident, custom)
        self.assertEqual(self.plan.sattningsresultat[self.ident]['k'], 32500)
        copied = self.plan.kopiera(self.ident, .6, .5)
        self.assertEqual(self.plan.sattningsresultat[copied]['k'], 32500)
        self.plan.satt_jordprofil(self.ident)
        self.assertEqual(self.plan.sattningsresultat[self.ident]['k'], 16250)
        self.plan.uppdatera(self.ident, indata={'F_vy_bruk': 240})
        self.assertAlmostEqual(self.plan.sattningsresultat[self.ident]['load'], 277.5)
        self.plan.uppdatera(self.ident, indata={'b': 3})
        self.assertNotEqual(self.plan.sattningsresultat[self.ident]['k'], 16250)
        self.assertEqual(self.plan.sattningsresultat[copied]['k'], 32500)

    def test_round_trip_recomputes_results_and_legacy_project_omits_new_results(self):
        legacy = self.plan._document(); legacy['version'] = 24; legacy.pop('soil_profile')
        old = self.plan.taggar[0]['summary']
        legacy_file = self.folder / 'legacy.json'; legacy_file.write_text(json.dumps(legacy))
        restored = Grundplan.oppna(legacy_file); self.addCleanup(restored.close)
        self.assertIsNone(restored.jordprofil)
        self.assertEqual(restored.taggar[0]['summary'], old)
        self.assertNotIn('settlement', restored.taggar[0])
        self.plan.jordprofil = PROFILE
        custom = copy.deepcopy(PROFILE); custom['layers'][0]['Ek'] = 20
        self.plan.satt_jordprofil(self.ident, custom)
        filename = self.plan.spara(self.folder / 'new.json')
        restored = Grundplan.oppna(filename); self.addCleanup(restored.close)
        self.assertEqual(restored.sattningsresultat, self.plan.sattningsresultat)
        self.assertEqual(restored.jordprofil, self.plan.jordprofil)
        self.assertEqual(restored._tag(self.ident)['soil_profile'], custom)

    def test_history_profiles_and_dimensions_recalculate_together(self):
        self.assertTrue(self.command(action='soil_profile', profile=PROFILE)['ok'])
        value = self.plan.sattningsresultat[self.ident]['s']
        self.plan.angra(); self.assertEqual(self.plan.sattningsresultat, {})
        self.plan.gor_om(); self.assertEqual(self.plan.sattningsresultat[self.ident]['s'], value)
        custom = copy.deepcopy(PROFILE); custom['layers'][0]['Ek'] = 20
        self.command(action='soil_profile', id=self.ident, profile=custom)
        self.assertAlmostEqual(self.plan.sattningsresultat[self.ident]['s'], value / 2)
        self.plan.angra(); self.assertEqual(self.plan.sattningsresultat[self.ident]['s'], value)
        self.command(action='update', id=self.ident, values={'b': 3})
        self.assertNotEqual(self.plan.sattningsresultat[self.ident]['s'], value)
        self.plan.angra(); self.assertEqual(self.plan.sattningsresultat[self.ident]['s'], value)

    def test_inactive_and_locked_profile_edits_are_blocked_without_affecting_other_results(self):
        self.plan.jordprofil = PROFILE
        self.plan.las_indata([self.ident])
        self.assertFalse(self.command(action='soil_profile', id=self.ident, profile=PROFILE)['ok'])
        self.plan.las_indata([self.ident], last=False)
        self.plan.uppdatera(self.ident, indata={'inaktiv': True})
        self.assertNotIn(self.ident, self.plan.sattningsresultat)
        self.assertFalse(self.command(action='soil_profile', id=self.ident, profile=PROFILE)['ok'])
        self.plan.uppdatera(self.ident, indata={'inaktiv': False})
        self.assertIn(self.ident, self.plan.sattningsresultat)

    def test_invalid_profile_and_corrupt_saved_profile_are_atomic(self):
        self.plan.jordprofil = PROFILE
        before = self.plan._document(), self.plan.taggar
        self.assertFalse(self.command(action='soil_profile', profile={'layers': []})['ok'])
        self.assertEqual((self.plan._document(), self.plan.taggar), before)
        for own in (False, True):
            document = self.plan._document()
            if own: document['tags'][0]['soil_profile'] = {'layers': []}
            else: document['soil_profile'] = {'layers': []}
            with self.assertRaises(ValueError): self.plan._load_document(json.dumps(document).encode())
            self.assertEqual((self.plan._document(), self.plan.taggar), before)

    def test_result_colours_intervals_units_missing_data_and_combinations(self):
        self.plan.jordprofil = PROFILE
        wall = self.plan.lagg_till(.6, .3, indata={'b': 2, 't': .25, 'F_vy_bruk': None})
        for category in ('s', 'k', 'K'):
            settings = validate_settings({'category': category})
            data = group_data(self.plan.taggar, settings)
            self.assertEqual(len(data['assignments']), 1 if category == 's' else 2)
            if category == 'K':
                self.assertEqual(data['assignments'][wall]['unit'], 'kN/m²')
                self.assertEqual(data['assignments'][self.ident]['unit'], 'kN/m')
            self.plan.farggruppering = {'enabled': True, 'categories': ['sultyp', 't', category]}
            self.assertTrue(self.plan.farggruppering['styles'])
        for bounds in ([], [5, 2], [0, 5], [float('nan')]):
            with self.assertRaises(ValueError): self.plan.farggruppering = {'result_bounds': {'s': bounds}}

    def test_python_and_javascript_result_colours_agree(self):
        self.plan.jordprofil = PROFILE
        self.plan.lagg_till(.6, .3, indata={'b': 2, 't': .25, 'F_vy_bruk': None})
        for categories in (['s'], ['k'], ['K'], ['sultyp', 't', 's', 'k', 'K']):
            settings = validate_settings({'categories': categories})
            source = Path(__file__).resolve().parents[1] / 'src/an_calcs/notebook/grundplan.js'
            code = '''import fs from 'node:fs'; const {colourGroups}=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(process.argv[1],'utf8')).toString('base64'));const data=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(colourGroups(data.tags,data.settings).groups));'''
            actual = subprocess.run(['node', '--input-type=module', '-e', code, str(source)], input=json.dumps({'tags': self.plan.taggar, 'settings': settings}), capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(actual.stdout), group_data(self.plan.taggar, settings)['groups'])
