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
from an_calcs.notebook.grundplan_settlement import (evaluate, validate_profile, _evaluate,
    validate_display, display_result, DEFAULT_DISPLAY, DISPLAY_FORMS, FORM_UNITS)
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

    def test_no_profile_and_inactive_never_call_calculators(self):
        _evaluate.cache_clear()
        with patch('an_calcs.notebook.grundplan_settlement.sattning') as settlement, patch('an_calcs.notebook.grundplan_settlement.baddmodul') as stiffness:
            for values, profile in [(self.values(), None), (self.values(inaktiv=True), PROFILE)]:
                self.assertIsNone(evaluate(values, profile))
            settlement.assert_not_called(); stiffness.assert_not_called()

    def test_only_h_uses_the_same_settlement_and_stiffness_models_and_loads(self):
        for values in (self.values(), self.values(lang=1, lasttyp=1, l=1),
                       self.values(lasttyp=1, L_vagg=.4),
                       self.values(lang=1, lasttyp=1, l=.5, L_vagg=.4, L_vagg_minst_1=False)):
            with self.subTest(values=values):
                self.assertEqual(evaluate({**values, 'endast_h_stabilitet': True}, PROFILE), evaluate(values, PROFILE))
        result = evaluate(self.values(endast_h_stabilitet=True, F_vy_bruk=None), PROFILE)
        self.assertIsNone(result['s'])
        self.assertEqual(result['K'], 97500)
        self.assertEqual(result['settlement_error'], 'Ange Brukslast.')

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

    def test_reporting_forms_are_limited_by_physical_footing_category(self):
        for kind, allowed in DISPLAY_FORMS.items():
            for form in ('yta', 'linje', 'punkt'):
                settings = {'forms': {kind: form}}
                if form in allowed:
                    self.assertEqual(validate_display(settings)['forms'][kind], form)
                else:
                    with self.assertRaises(ValueError): validate_display(settings)
        for settings in (None, {'show_labels': 1}, {'forms': []}, {'forms': {'other': 'yta'}}, {'extra': True}):
            with self.assertRaises(ValueError): validate_display(settings)
        settings = validate_display({}); settings['forms']['wall'] = 'yta'
        self.assertEqual(DEFAULT_DISPLAY['forms']['wall'], 'linje')

    def test_reporting_conversion_preserves_ps_model_and_raw_results(self):
        tag = {'footing_type': 'vaggsula', 'values': self.values(lasttyp=1, L_vagg=.4)}
        raw = evaluate(tag['values'], PROFILE)
        for form, expected in [('yta', 16250), ('punkt', 97500), ('linje', 243750)]:
            result = display_result(raw, tag, validate_display({'forms': {'wall_pad': form}}))
            self.assertEqual(result['display_value'], expected)
            self.assertEqual(result['display_unit'], FORM_UNITS[form])
            self.assertEqual({key: result[key] for key in raw}, raw)
            self.assertFalse(result['display_error'])
        # Missing wall length blocks only the selected line result, not PS stiffness.
        tag['values']['L_vagg'] = None
        result = display_result(raw, tag, validate_display({'forms': {'wall_pad': 'linje'}}))
        self.assertIsNone(result['display_value'])
        self.assertEqual(result['K'], 97500)
        self.assertEqual(result['s'], raw['s'])
        self.assertIn('L_vägg', result['display_error'])


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

    def test_only_h_allows_profiles_and_display_without_enabling_bearing_or_changing_sliding(self):
        self.plan.jordprofil = PROFILE
        expected = self.plan.sattningsresultat[self.ident]
        self.plan.uppdatera(self.ident, indata={'endast_h_stabilitet': True,
                            'glid_x': True, 'V_Ed_EQU': 120, 'glid_mu': .4})
        before_sliding = self.plan.taggar[0]['sliding']
        self.assertEqual(self.plan.sattningsresultat[self.ident], expected)
        custom = copy.deepcopy(PROFILE)
        custom['layers'][0]['Ek'] *= 2
        reply = self.command(action='soil_profile', id=self.ident, profile=custom)
        self.assertTrue(reply['ok'])
        self.assertAlmostEqual(self.plan.sattningsresultat[self.ident]['s'], expected['s'] / 2)
        self.assertTrue(self.command(action='settlement_display', id=self.ident,
                                    settings={'form': 'yta', 'show_labels': False})['ok'])
        self.assertEqual(self.plan.sattningsresultat[self.ident]['display_form'], 'yta')
        self.assertTrue(self.command(action='soil_profile_patch', ids=[self.ident], field='dz', layer=0, value=1)['ok'])
        self.assertEqual(self.plan.taggar[0]['sliding'], before_sliding)
        self.assertTrue(self.plan.taggar[0]['summary']['endast_h_stabilitet'])
        self.assertIsNone(self.plan.taggar[0]['summary']['utnyttjandegrad'])
        restored = self.new_plan()
        restored._load_document(json.dumps(self.plan._document()).encode())
        self.assertEqual(restored.sattningsresultat, self.plan.sattningsresultat)
        self.plan.uppdatera(self.ident, indata={'b': None, 't': None, 'F_vy_bruk': None})
        self.assertIsNone(self.plan.sattningsresultat[self.ident]['s'])
        self.assertTrue(self.plan.taggar[0]['summary']['endast_h_stabilitet'])
        self.assertEqual(self.plan.taggar[0]['sliding'], before_sliding)

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

    def test_reporting_choices_persist_undo_and_do_not_change_calculations(self):
        self.plan.jordprofil = PROFILE
        before = copy.deepcopy((self.plan._tag(self.ident)['values'], self.plan.resultat, self.plan.glidningsresultat))
        raw = self.plan.sattningsresultat[self.ident]
        self.assertTrue(self.command(action='settlement_display', id=self.ident, settings={
            'show_labels': False, 'form': 'yta'})['ok'])
        self.assertFalse(self.plan.taggar[0]['settlement_display']['show_labels'])
        result = self.plan.sattningsresultat[self.ident]
        self.assertEqual(result['display_value'], raw['k'])
        for key in ('s', 'k', 'K', 'load'): self.assertEqual(result[key], raw[key])
        self.assertEqual((self.plan._tag(self.ident)['values'], self.plan.resultat, self.plan.glidningsresultat), before)
        self.plan.angra(); self.assertTrue(self.plan.taggar[0]['settlement_display']['show_labels'])
        self.plan.gor_om(); self.assertFalse(self.plan.taggar[0]['settlement_display']['show_labels'])
        filename = self.plan.spara(self.folder / 'display.json')
        restored = Grundplan.oppna(filename); self.addCleanup(restored.close)
        self.assertEqual(restored.sattningsvisning, self.plan.sattningsvisning)
        self.assertEqual(restored.sattningsresultat, self.plan.sattningsresultat)
        document = self.plan._document(); document['version'] = 25; document.pop('settlement_display')
        for tag in document['tags']: tag.pop('settlement_display')
        restored._load_document(json.dumps(document).encode())
        self.assertEqual(restored.sattningsvisning, DEFAULT_DISPLAY)
        self.assertEqual(restored.jordprofil, PROFILE)

    def test_individual_and_bulk_display_do_not_modify_other_footings_or_profiles(self):
        self.plan.jordprofil = PROFILE
        other = self.plan.kopiera(self.ident, .6, .4)
        wall = self.plan.lagg_till(.2, .5)
        self.plan.satt_jordprofil(other, {'layers': PROFILE['layers'] * 3, 'step': .2})
        before = copy.deepcopy(self.plan._tag(other))
        self.plan.satt_sattningsvisning(self.ident, {'show_labels': False, 'form': 'yta'})
        self.assertEqual(self.plan._tag(other), before)
        self.plan.las_indata([other])
        self.assertTrue(self.command(action='settlement_display', ids=[self.ident, other, wall], settings={'form': 'yta'})['ok'])
        self.assertTrue(all(tag['settlement_display']['form'] == 'yta' for tag in self.plan.taggar))
        self.assertEqual(self.plan._tag(other)['soil_profile'], before['soil_profile'])
        snapshot = self.plan._document()
        self.assertFalse(self.command(action='settlement_display', ids=[self.ident, wall], settings={'form': 'punkt'})['ok'])
        self.assertEqual(self.plan._document(), snapshot)
        self.plan.angra()
        self.assertEqual(self.plan.taggar[-1]['settlement_display']['form'], 'linje')
        self.plan.gor_om()
        self.assertEqual(self.plan.taggar[-1]['settlement_display']['form'], 'yta')

    def test_v26_migrates_project_display_and_copies_keep_individual_choices(self):
        document = self.plan._document(); document['version'] = 26
        document['settlement_display'] = {'show_labels': False, 'forms': {'wall': 'yta', 'pad': 'yta', 'wall_pad': 'linje'}}
        for tag in document['tags']: tag.pop('settlement_display')
        self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan.taggar[0]['settlement_display'], {'show_labels': False, 'form': 'yta'})
        copied = self.plan.kopiera(self.ident, .6, .6)
        self.plan.satt_sattningsvisning(copied, {'show_labels': True})
        self.assertFalse(self.plan.taggar[0]['settlement_display']['show_labels'])
        self.assertTrue(self.plan.taggar[1]['settlement_display']['show_labels'])
        bad = self.plan._document(); bad['tags'][0]['settlement_display']['form'] = 'linje'
        before = self.plan._document()
        with self.assertRaises(ValueError): self.plan._load_document(json.dumps(bad).encode())
        self.assertEqual(self.plan._document(), before)

    def test_multilayer_profile_batch_is_atomic_independent_and_undoable(self):
        self.plan.jordprofil = PROFILE
        other = self.plan.kopiera(self.ident, .6, .6)
        self.plan.satt_jordprofil(other, {'layers': PROFILE['layers'] * 3, 'step': .25})
        before = self.plan._document()
        profile = {'layers': [{**PROFILE['layers'][0], 'Ek': 20}, PROFILE['layers'][0]], 'step': .1}
        self.assertTrue(self.command(action='soil_profile', ids=[self.ident, other], profile=profile)['ok'])
        self.assertIsNot(self.plan._tag(self.ident)['soil_profile']['layers'], self.plan._tag(other)['soil_profile']['layers'])
        for tag in self.plan._tags: self.assertEqual(tag['soil_profile'], profile)
        self.plan.angra(); self.assertEqual(self.plan._document(), before)
        self.plan.gor_om()
        self.plan.las_indata([other]); before = self.plan._document()
        self.assertFalse(self.command(action='soil_profile', ids=[self.ident, other], profile=None)['ok'])
        self.assertEqual(self.plan._document(), before)
        self.plan.las_indata([other], last=False)
        self.assertTrue(self.command(action='soil_profile', ids=[self.ident, other], profile=None)['ok'])
        self.assertTrue(all('soil_profile' not in tag for tag in self.plan._tags))

    def test_cell_edit_only_changes_the_matching_layer_in_distinct_profiles(self):
        self.plan.jordprofil = PROFILE
        two = self.plan.kopiera(self.ident, .5, .5)
        three = self.plan.kopiera(self.ident, .6, .6)
        outside = self.plan.kopiera(self.ident, .7, .7)
        self.plan.satt_jordprofil(two, {'layers': [PROFILE['layers'][0], {'dz': 1, 'Ek': 30, 'gamma_m': 1.3}], 'step': .2})
        self.plan.satt_jordprofil(three, {'layers': [PROFILE['layers'][0], {'dz': .5, 'Ek': 20, 'gamma_m': 1.4},
            {'dz': 2, 'Ek': 50, 'gamma_m': 1.6}], 'step': .1})
        before = copy.deepcopy(self.plan._document())
        reply = self.command(action='soil_profile_patch', ids=[self.ident, two, three], field='Ek', layer=1, value=40)
        self.assertTrue(reply['ok']); self.assertEqual(reply['updated'], 2)
        self.assertEqual(reply['skipped'], [{'id': self.ident, 'label': self.plan._tag(self.ident)['label'], 'reason': 'Saknar lager 2'}])
        expected = copy.deepcopy(before)
        for tag in expected['tags']:
            if tag['id'] in (two, three): tag['soil_profile']['layers'][1]['Ek'] = 40
        self.assertEqual(self.plan._document(), expected)
        self.assertNotIn('soil_profile', self.plan._tag(outside))
        self.plan.angra(); self.assertEqual(self.plan._document(), before)
        self.plan.gor_om(); self.assertEqual(self.plan._document(), expected)

    def test_cell_edit_copies_inherited_profiles_and_step_applies_to_all_layer_counts(self):
        self.plan.jordprofil = PROFILE
        other = self.plan.kopiera(self.ident, .6, .6)
        outside = self.plan.kopiera(self.ident, .7, .7)
        reply = self.command(action='soil_profile_patch', ids=[self.ident, other], field='dz', layer=0, value=1)
        self.assertTrue(reply['ok']); self.assertEqual(reply['updated'], 2)
        self.assertEqual(self.plan.jordprofil, PROFILE)
        self.assertNotIn('soil_profile', self.plan._tag(outside))
        self.assertIsNot(self.plan._tag(self.ident)['soil_profile'], self.plan._tag(other)['soil_profile'])
        self.plan.satt_jordprofil(other, {'layers': PROFILE['layers'] * 3, 'step': .5})
        layers = [copy.deepcopy(self.plan._tag(ident)['soil_profile']['layers']) for ident in (self.ident, other)]
        reply = self.command(action='soil_profile_patch', ids=[self.ident, other], field='step', value=.1)
        self.assertTrue(reply['ok']); self.assertEqual(reply['updated'], 2)
        for ident, expected in zip((self.ident, other), layers):
            self.assertEqual(self.plan._tag(ident)['soil_profile']['layers'], expected)
            self.assertEqual(self.plan._tag(ident)['soil_profile']['step'], .1)
        restored = self.new_plan(); restored._load_document(json.dumps(self.plan._document()).encode())
        self.assertEqual(restored.taggar, self.plan.taggar)

    def test_cell_edit_skips_protected_and_missing_profiles_without_inventing_soil(self):
        self.plan.jordprofil = PROFILE
        locked, inactive, horizontal = [self.plan.kopiera(self.ident, x, .6) for x in (.4, .5, .6)]
        self.plan.las_indata([locked])
        self.plan.uppdatera(inactive, indata={'inaktiv': True})
        self.plan.uppdatera(horizontal, indata={'endast_h_stabilitet': True})
        ids = [self.ident, locked, inactive, horizontal]
        reply = self.command(action='soil_profile_patch', ids=ids, field='gamma_m', layer=0, value=1.3)
        self.assertTrue(reply['ok']); self.assertEqual(reply['updated'], 2)
        self.assertEqual([item['reason'] for item in reply['skipped']], ['Låsta indata', 'Inaktiv'])
        self.assertTrue(all('soil_profile' not in self.plan._tag(ident) for ident in (locked, inactive)))
        self.assertEqual(self.plan._tag(horizontal)['soil_profile']['layers'][0]['gamma_m'], 1.3)
        self.plan.satt_jordprofil(self.ident); self.plan.jordprofil = None
        before = self.plan._document()
        reply = self.command(action='soil_profile_patch', ids=[self.ident], field='step', value=.1)
        self.assertTrue(reply['ok']); self.assertEqual(reply['updated'], 0)
        self.assertEqual(reply['skipped'][0]['reason'], 'Saknar jordprofil')
        self.assertEqual(self.plan._document(), before)

    def test_invalid_cell_edit_is_atomic_even_when_only_one_profile_exceeds_layer_limit(self):
        self.plan.jordprofil = PROFILE
        other = self.plan.kopiera(self.ident, .6, .6)
        self.plan.satt_jordprofil(other, {'layers': [{'dz': 600, 'Ek': 20, 'gamma_m': 1.3}], 'step': 1})
        before = self.plan._document(), self.plan.taggar, copy.deepcopy(self.plan.state['history'])
        for edit in ({'field': 'step', 'value': .1}, {'field': 'step', 'value': 0},
                     {'field': 'step', 'value': .5, 'layer': 0}, {'field': 'Ek', 'layer': True, 'value': 40},
                     {'field': 'Ek', 'layer': -1, 'value': 40}, {'field': 'Ek', 'layer': 0, 'value': float('nan')},
                     {'field': 'bad', 'layer': 0, 'value': 1}, {'field': 'Ek', 'layer': 0, 'value': '40'}):
            with self.subTest(edit=edit):
                self.assertFalse(self.command(action='soil_profile_patch', ids=[self.ident, other], **edit)['ok'])
                self.assertEqual((self.plan._document(), self.plan.taggar, self.plan.state['history']), before)

    def test_unchanged_cell_does_not_create_overrides_or_history(self):
        self.plan.jordprofil = PROFILE
        before = self.plan._document(), copy.deepcopy(self.plan.state['history'])
        reply = self.command(action='soil_profile_patch', ids=[self.ident], field='Ek', layer=0, value=10)
        self.assertTrue(reply['ok']); self.assertEqual(reply['updated'], 0)
        self.assertEqual(reply['unchanged'], [self.ident])
        self.assertEqual((self.plan._document(), self.plan.state['history']), before)

    def test_invalid_reporting_choices_are_atomic_and_unavailable_line_has_no_colour(self):
        self.plan.jordprofil = PROFILE
        before = self.plan._document(), self.plan.taggar
        self.assertFalse(self.command(action='settlement_display', settings={'forms': {'pad': 'linje'}})['ok'])
        self.assertEqual((self.plan._document(), self.plan.taggar), before)
        document = self.plan._document(); document['settlement_display'] = {'show_labels': 'false'}
        with self.assertRaises(ValueError): self.plan._load_document(json.dumps(document).encode())
        self.assertEqual((self.plan._document(), self.plan.taggar), before)
        wall_pad = self.plan.lagg_till(.5, .4, indata={'lang': 0, 'lasttyp': 1, 'L_vagg': None})
        self.plan.sattningsvisning = {'forms': {'wall_pad': 'linje', 'pad': 'yta'}}
        data = group_data(self.plan.taggar, validate_settings({'category': 'K'}))
        self.assertNotIn(wall_pad, data['assignments'])
        self.assertEqual(data['assignments'][self.ident]['result_kind'], 'K_area')
        self.assertEqual(data['assignments'][self.ident]['unit'], 'kN/m²/m')

    def test_result_colours_intervals_units_missing_data_and_combinations(self):
        self.plan.jordprofil = PROFILE
        wall = self.plan.lagg_till(.6, .3, indata={'b': 2, 't': .25, 'F_vy_bruk': None})
        for category in ('s', 'k', 'K'):
            settings = validate_settings({'category': category})
            data = group_data(self.plan.taggar, settings)
            self.assertEqual(len(data['assignments']), 1 if category == 's' else 2)
            if category == 'K':
                self.assertEqual(data['assignments'][wall]['unit'], 'kN/m/m')
                self.assertEqual(data['assignments'][self.ident]['unit'], 'kN/m')
            self.plan.farggruppering = {'enabled': True, 'categories': ['sultyp', 't', category]}
            self.assertTrue(self.plan.farggruppering['styles'])
        for bounds in ([], [5, 2], [0, 5], [float('nan')]):
            with self.assertRaises(ValueError): self.plan.farggruppering = {'result_bounds': {'s': bounds}}

    def test_python_and_javascript_result_colours_agree(self):
        self.plan.jordprofil = PROFILE
        self.plan.lagg_till(.6, .3, indata={'b': 2, 't': .25, 'F_vy_bruk': None})
        self.plan.lagg_till(.5, .5, indata={'lang': 0, 'lasttyp': 1, 'L_vagg': .4, 'b': 2, 'l': 3})
        for categories, forms in [(['s'], {}), (['k'], {}), (['K'], {}),
                (['K'], {'wall': 'yta', 'wall_pad': 'linje'}),
                (['sultyp', 't', 's', 'k', 'K'], {'wall_pad': 'linje', 'pad': 'yta'})]:
            self.plan.sattningsvisning = {'forms': forms}
            settings = validate_settings({'categories': categories})
            source = Path(__file__).resolve().parents[1] / 'src/an_calcs/notebook/grundplan.js'
            code = '''import fs from 'node:fs'; const {colourGroups}=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(process.argv[1],'utf8')).toString('base64'));const data=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(colourGroups(data.tags,data.settings).groups));'''
            actual = subprocess.run(['node', '--input-type=module', '-e', code, str(source)], input=json.dumps({'tags': self.plan.taggar, 'settings': settings}), capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(actual.stdout), group_data(self.plan.taggar, settings)['groups'])
