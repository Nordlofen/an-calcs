"""Referensfall och verifiering av nya Betongtvärsnitt."""
import copy
import json
import math
from pathlib import Path
import unittest

import importlib
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
bt = importlib.import_module("an_calcs.betong.betongtvarsnitt")


def beam(**changes):
    p = {"geometri": "balk", "stadium": "II", "b": 300, "h": 600,
         "N_d": 500, "M": 180,
         "armeringsrader": [{"namn": "ÖK", "y": 50, "phi": 20, "antal": 3},
                             {"namn": "UK", "y": 550, "phi": 25, "antal": 4}]}
    p.update(changes)
    return p


class LegacyTests(unittest.TestCase):
    def test_frozen_original_results_and_schema(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' / 'betongtvarsnitt_legacy.json').read_text(encoding='utf-8'))
        for case in fixture['cases']:
            with self.subTest(px=case['px']):
                self.assertEqual(bt.bojstyvhet_betongpalar(case['px']), case['result'])
                self.assertEqual(bt.betongtvarsnitt(case['px']), case['result'])
        self.assertEqual(bt.bojstyvhet_betongpalar.panel_schema, fixture['panel_schema'])

    def test_original_example_numeric(self):
        px = [235, 25, 5, 16, 2.5, 700, 50, 33.3, 37000, 200000, 0, 18.9, True, 1, False, 1]
        result = bt.bojstyvhet_betongpalar(px)
        values = {r['namn']: r['value'] for r in result['slutresultat']['items']}
        self.assertAlmostEqual(values['EI'], 10422.734849390321, places=8)
        self.assertEqual(values['x'], 235)


class ElasticTests(unittest.TestCase):
    def test_closed_form_single_reinforcement_row(self):
        p = beam(b=1000, h=300, N_d=0, M=50,
                 armeringsrader=[{'y': 250, 'phi': 16, 's': 150}])
        raw = bt.berakna_betongtvarsnitt(p)
        r = raw['stadium_II']
        area = 1000 / 150 * math.pi * 16**2 / 4
        alpha = 200000 / 33000
        x = (-alpha * area + math.sqrt((alpha * area)**2 + 2 * 1000 * alpha * area * 250)) / 1000
        self.assertAlmostEqual(r['x'], x, places=7)
        self.assertAlmostEqual(r['F_s_drag'], 50e6 / (250 - x / 3), places=4)
        self.assertAlmostEqual(r['sigma_c_max'], 2 * r['F_c'] / (1000 * x), places=8)
        self.assertAlmostEqual(r['z'], 250 - x / 3, places=7)

    def test_nm_equilibrium_asymmetric_section(self):
        for n, moment in [(0, 180), (500, 180), (500, -180), (900, 20), (100, -200), (0, 0)]:
            with self.subTest(n=n, m=moment):
                r = bt.berakna_betongtvarsnitt(beam(N_d=n, M=moment))['stadium_II']
                self.assertAlmostEqual(r['N_calc'] / 1000, n, places=6)
                self.assertAlmostEqual(r['M_calc'] / 1e6, moment, places=6)

    def test_load_scaling_does_not_change_elastic_cracked_depth(self):
        a = bt.berakna_betongtvarsnitt(beam())['stadium_II']
        b = bt.berakna_betongtvarsnitt(beam(N_d=2500, M=900))['stadium_II']
        self.assertAlmostEqual(a['x'], b['x'], places=7)
        self.assertAlmostEqual(b['epsilon_c_max'], 5 * a['epsilon_c_max'], places=12)

    def test_mirror_changes_sign_and_preserves_response(self):
        original = beam(N_d=250, M=180)
        mirrored = copy.deepcopy(original)
        mirrored['M'] *= -1
        for row in mirrored['armeringsrader']:
            row['y'] = 600 - row['y']
        a = bt.berakna_betongtvarsnitt(original)['stadium_II']
        b = bt.berakna_betongtvarsnitt(mirrored)['stadium_II']
        self.assertAlmostEqual(a['x'], b['x'], places=7)
        self.assertAlmostEqual(a['epsilon_top'], b['epsilon_bottom'], places=12)
        self.assertAlmostEqual(a['kappa'], -b['kappa'], places=12)

    def test_all_three_warning_categories(self):
        raw = bt.berakna_betongtvarsnitt(beam(N_d=0, M=20000))
        codes = {w['kod'] for w in raw['varningar']}
        self.assertIn('II_EPSILON_C_LIM', codes)
        self.assertIn('II_BETONG_BROTTTOJNING', codes)
        self.assertTrue(any(code.startswith('II_STALFLYTNING') for code in codes))
        self.assertEqual(raw['indata']['stadium'], 'II')
        self.assertIsNone(raw['stadium_III'])

    def test_manual_epsilon_and_used_modulus(self):
        a = bt.berakna_betongtvarsnitt(beam(E_cd=30000))
        self.assertAlmostEqual(a['indata']['epsilon_c_lim'], 15.2 / 30000)
        b = bt.berakna_betongtvarsnitt(beam(epsilon_c_lim=0.0003, E_cd=30000))
        self.assertEqual(b['indata']['epsilon_c_lim'], .0003)
        self.assertIn('manuellt', b['indata']['epsilon_c_lim_kalla'])

    def test_fully_compressed_uses_pivot_not_3_5_promille(self):
        p = beam(b=300, h=300, N_d=0, M=0,
                 armeringsrader=[{'y': 50, 'phi': 16, 'antal': 2}, {'y': 250, 'phi': 16, 'antal': 2}])
        as_total = 4 * math.pi * 16**2 / 4
        p['N_d'] = (33000 * (90000 - as_total) + 200000 * as_total) * .002 / 1000
        raw = bt.berakna_betongtvarsnitt(p)
        r = raw['stadium_II']
        self.assertTrue(r['fullt_tryckt'])
        self.assertAlmostEqual(r['epsilon_cu_tillaten'], .00175)
        self.assertIn('II_BETONG_BROTTTOJNING', {w['kod'] for w in raw['varningar']})

    def test_arbitrary_number_of_rows(self):
        rows = [{'y': y, 'phi': 12, 'antal': 2} for y in [40, 180, 300, 420, 560]]
        r = bt.berakna_betongtvarsnitt(beam(armeringsrader=rows))['stadium_II']
        self.assertEqual(len(r['rader']), 5)
        self.assertAlmostEqual(r['M_calc'] / 1e6, 180, places=6)


class UltimateTests(unittest.TestCase):
    def test_yielding_single_row_rectangular_block_closed_form(self):
        p = beam(stadium='III', N_d=0, M=50,
                 armeringsrader=[{'y': 550, 'phi': 16, 'antal': 2}])
        raw = bt.berakna_betongtvarsnitt(p)
        r = raw['stadium_III']['vald']
        area = 2 * math.pi * 16**2 / 4
        force = area * 500 / 1.15
        x = force / (.8 * 300 * 20)
        moment = force * (550 - .4 * x)
        self.assertAlmostEqual(r['x'], x, places=7)
        self.assertAlmostEqual(r['M_Rd'] / 1e6, moment / 1e6, places=7)
        self.assertAlmostEqual(r['z'], 550 - .4 * x, places=7)

    def test_concrete_governed_previous_plate_reference(self):
        h = 253.98797900667077
        p = beam(stadium='III', b=1000, h=h, N_d=0, M=323.22402636059974,
                 armeringsrader=[{'y': h - 57.5, 'phi': 25, 's': 50}])
        r = bt.berakna_betongtvarsnitt(p)['stadium_III']['vald']
        self.assertAlmostEqual(r['M_Rd'] / 1e6, 323.22402636059974, places=6)
        self.assertAlmostEqual(r['x'], 146.5115121621663, places=6)
        self.assertAlmostEqual(abs(r['rader'][0]['sigma']), 238.77664133608556, places=5)

    def test_independent_parabolic_numerical_integration(self):
        p = bt._bt_indata(beam(tryckblock='parabel', stadium='III'))
        r = bt._bt_brottprofil(p, .6, False)
        count = 20000
        h = p['h']; dy = h / count
        fn = qn = 0
        for i in range(count + 1):
            y = i * dy
            eps = r['epsilon_top'] - r['kappa'] * y
            ratio = min(1, max(0, eps / .002))
            sigma = p['f_cd'] * (2 * ratio - ratio**2)
            weight = 1 if i in (0, count) else 4 if i % 2 else 2
            fn += weight * sigma
            qn += weight * sigma * y
        fn *= dy / 3 * p['b']; qn *= dy / 3 * p['b']
        for row in p['rader']:
            ratio = min(1, max(0, (r['epsilon_top'] - r['kappa'] * row['y']) / .002))
            force = row['A_s'] * p['f_cd'] * (2 * ratio - ratio**2)
            fn -= force; qn -= force * row['y']
        force_steel = sum(s['F'] for s in r['rader'])
        moment_steel = sum(s['F'] * (h / 2 - s['y']) for s in r['rader'])
        self.assertAlmostEqual((fn + force_steel) / 1000, r['N_calc'] / 1000, places=5)
        self.assertAlmostEqual((fn * h / 2 - qn + moment_steel) / 1e6, r['M_Rd'] / 1e6, places=5)

    def test_circle_segment_half_area_and_first_moment(self):
        row = {'phi': 20, 'A_s': 2 * math.pi * 10**2}
        area, first = bt._bt_cirkel_segment(row, 100, 100)
        self.assertAlmostEqual(area, row['A_s'] / 2)
        self.assertAlmostEqual(first, 100 * area - 2 * 2 / 3 * 10**3)

    def test_mirror_ultimate_capacity_with_asymmetric_reinforcement(self):
        p = beam(stadium='III', N_d=300, M=100)
        mirror = copy.deepcopy(p)
        mirror['M'] *= -1
        for row in mirror['armeringsrader']:
            row['y'] = 600 - row['y']
        a = bt.berakna_betongtvarsnitt(p)['stadium_III']
        b = bt.berakna_betongtvarsnitt(mirror)['stadium_III']
        self.assertAlmostEqual(a['M_Rd_max'], -b['M_Rd_min'], places=3)
        self.assertAlmostEqual(a['M_Rd_min'], -b['M_Rd_max'], places=3)

    def test_capacity_exceedance_is_critical(self):
        r = bt.berakna_betongtvarsnitt(beam(stadium='III', M=10000))
        self.assertTrue(r['kritisk_varning'])
        self.assertIn('III_MOMENTKAPACITET_OVERSKRIDS', {w['kod'] for w in r['varningar']})

    def test_impossible_normal_force_does_not_publish_capacity(self):
        r = bt.berakna_betongtvarsnitt(beam(stadium='III', N_d=10000000))
        self.assertFalse(r['stadium_III']['jamvikt'])
        self.assertIsNone(r['stadium_III']['M_Rd_max'])
        self.assertTrue(r['kritisk_varning'])

    def test_pure_compression_profile_uses_model_specific_strain(self):
        for block, strain in [('rektangel', .00175), ('parabel', .002)]:
            p = bt._bt_indata(beam(stadium='III', tryckblock=block))
            r = bt._bt_brottprofil(p, None, False)
            self.assertEqual(r['epsilon_top'], strain)
            self.assertEqual(r['epsilon_bottom'], strain)

    def test_normal_equilibrium_on_pile_beam_and_strip(self):
        cases = [beam(stadium='III'),
                 {'geometri': 'pale', 'stadium': 'III', 'b': 300, 'N_d': 300, 'M': 30},
                 beam(geometri='plattremsa', b=1000, stadium='III', N_d=0, M=100)]
        for case in cases:
            for block in ['rektangel', 'parabel']:
                raw = bt.berakna_betongtvarsnitt(dict(case, tryckblock=block))
                self.assertTrue(raw['stadium_III']['jamvikt'])
                for r in raw['stadium_III']['profiler']:
                    self.assertAlmostEqual(r['N_calc'] / 1000, case['N_d'], places=5)
                    high = max(r['epsilon_top'], r['epsilon_bottom'])
                    low = min(r['epsilon_top'], r['epsilon_bottom'])
                    if low <= 0:
                        self.assertLessEqual(high, .0035 + 1e-12)
                    else:
                        c0 = .00175 if block == 'rektangel' else .002
                        pivot = 1 - c0 / .0035
                        self.assertLessEqual((1 - pivot) * high + pivot * low, c0 + 1e-12)


class PanelAndInputTests(unittest.TestCase):
    def test_warning_text_in_known_panel_sections(self):
        p = beam(M=20000)
        raw = bt.berakna_betongtvarsnitt(p)
        report = bt.betongtvarsnitt(p)
        self.assertEqual(set(report), {'indata', 'delresultat', 'ekvationer', 'metodbeskrivning', 'slutresultat'})
        final_labels = ' '.join(r['etikett'] for r in report['slutresultat']['items'])
        method_texts = ' '.join(r['text'] for r in report['metodbeskrivning']['items'])
        for warning in raw['varningar']:
            self.assertIn(warning['text'], final_labels)
            self.assertIn(warning['text'], method_texts)
        for key in ['indata', 'delresultat', 'slutresultat']:
            for item in report[key]['items']:
                self.assertIsInstance(item['value'], (float, int))
                self.assertTrue(item['etikett'])
        json.dumps(report, ensure_ascii=False, allow_nan=False)

    def test_panel_default_and_each_geometry_model_combination(self):
        schema = bt.betongtvarsnitt.panel_schema
        defaults = {f['name']: f['default'] for f in schema['fields']}
        for geometry in [1, 2, 3]:
            for stage in [2, 3]:
                data = dict(defaults, geometri=geometry, stadium=stage)
                result = bt.betongtvarsnitt([data[key] for key in schema['px']])
                self.assertIn('slutresultat', result)

    def test_panel_manual_strain_and_auto_strength_limit(self):
        schema = bt.betongtvarsnitt.panel_schema
        data = {f['name']: f['default'] for f in schema['fields']}
        data.update(epsilon_c_lim_manuell=True, epsilon_c_lim_pm=.4, f_ck=50)
        p = bt._bt_indata(bt._bt_fran_panel([data[key] for key in schema['px']]))
        self.assertAlmostEqual(p['epsilon_c_lim'], .0004)
        self.assertAlmostEqual(p['sigma_c_lim'], .4 * 58)

    def test_input_not_modified(self):
        p = beam()
        before = copy.deepcopy(p)
        bt.betongtvarsnitt(p)
        self.assertEqual(p, before)

    def test_reject_invalid_values_instead_of_silently_assuming(self):
        for changes in [dict(stadium='I'), dict(N_d=-1), dict(f_ck=90), dict(E_cd=float('nan')),
                        dict(epsilon_c_lim=.46), dict(invented=1), dict(gamma_s=True),
                        dict(armeringsrader=[{'y': 600, 'phi': 25, 'antal': 2}])]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                bt.betongtvarsnitt(beam(**changes))

    def test_ny_palberakning_ger_enbart_elastiskt_ei_eller_momentkapacitet(self):
        data = {'geometri': 'pale', 'b': 235, 'c_nom': 25, 'phi_b': 5, 'phi_h': 16,
                'N_d': 700, 'M': 30, 'f_ck': 50, 'f_cd': 33.3, 'E_cd': 37000}
        raw = bt.berakna_betongtvarsnitt(data)['stadium_II']
        self.assertAlmostEqual(raw['x'], 226.80510345101908, places=7)
        for stage in ['II', 'III']:
            with self.subTest(stage=stage):
                report = bt.betongtvarsnitt(dict(data, stadium=stage))
                values = {item['namn']: item['value'] for item in report['slutresultat']['items']}
                self.assertNotIn('pal_EI', values)
                self.assertNotIn('EI', values)
                if stage == 'II':
                    self.assertAlmostEqual(values['EI_II'], 37000 * raw['I_II'] / 1e9)
                else:
                    self.assertTrue(values['M_Rd_min'] < values['M_Rd_max'])
                    self.assertNotIn('EI_II', values)

    def test_lagerdjup_beraknas_fran_tackskikt_och_bygel(self):
        data = dict(geometri='balk', b=300, h=600, c_nom_ok=35, c_nom_uk=40,
                    phi_b=8, n_ok=2, phi_ok=16, n_uk=4, phi_uk=20)
        for geo, expected_y in [('balk', [51, 542]), ('plattremsa', [43, 550])]:
            with self.subTest(geometri=geo):
                raw = bt.berakna_betongtvarsnitt(dict(data, geometri=geo))
                self.assertEqual([row['y'] for row in raw['indata']['rader']], expected_y)
                data_rows = bt.betongtvarsnitt(dict(data, geometri=geo))['indata']['items']
                self.assertFalse(any(item['namn'].startswith('y_') for item in data_rows))
        with self.assertRaisesRegex(ValueError, 'Bygeldiameter'):
            bt.betongtvarsnitt(dict(data, phi_b=0))
        with self.assertRaisesRegex(ValueError, 'höjdled'):
            bt.betongtvarsnitt(dict(data, h=100))

    def test_ett_lager_och_inaktiva_modellfalt(self):
        raw = bt.berakna_betongtvarsnitt({'geometri': 'balk', 'n_ok': 0,
                                        'phi_ok': None, 'f_cd': None})
        self.assertEqual([row['namn'] for row in raw['indata']['rader']], ['UK'])
        raw = bt.berakna_betongtvarsnitt({'stadium': 'III', 'E_cd': None,
                                        'sigma_c_lim': None, 'epsilon_c_lim': 'inaktiv'})
        self.assertTrue(raw['stadium_III']['jamvikt'])
        self.assertIsNone(raw['stadium_II'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
