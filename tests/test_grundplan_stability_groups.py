"""Separate building systems reuse the existing EQU sliding calculation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(n) for n in ('anywidget','PIL','pypdfium2'))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK,'Installera an-calcs[notebook].')
class TestStabilityGroups(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);image=self.root/'plan.png'
        Image.new('RGB',(800,600),'white').save(image)
        self.plan=Grundplan(image);self.addCleanup(self.plan.close)
        self.a=self.plan.lagg_till(.2,.2,typ='pelarsula',indata={'V_Ed_EQU':100,'glid_mu':.4,'glid_x':True})
        self.b=self.plan.lagg_till(.4,.4,typ='pelarsula',indata={'V_Ed_EQU':200,'glid_mu':.5,'glid_y':True})
        self.plan.glidning={'enabled':True,'check_x':True,'check_y':True,'H_x_Ed':20,'H_y_Ed':50}

    def ok(self,action,**content):
        with patch.object(self.plan,'send') as send:
            self.plan._on_message(self.plan,{'action':action,'view':'test','request':1,**content},[])
        reply=send.call_args.args[0];self.assertTrue(reply['ok'],reply);return reply

    def test_houses_only_sum_their_members_in_selected_house_directions(self):
        second=self.plan.skapa_stabilitetsgrupp('Hus 2')
        self.plan.uppdatera(self.b,indata={'stability_group':second})
        self.plan.andra_stabilitetsgrupp(second,{'check_x':True,'check_y':True,'H_x_Ed':15,'H_y_Ed':80,'angle_deg':30})
        data={g['id']:g['results'] for g in self.plan.state['stability_results']}
        self.assertEqual(data[0]['x']['H_Rd'],40);self.assertEqual(data[0]['y']['H_Rd'],0)
        self.assertEqual(data[second]['x']['H_Rd'],0);self.assertEqual(data[second]['y']['H_Rd'],100)
        self.assertEqual(data[second]['y']['utilization'],.8)
        self.assertEqual(data[0]['x']['contributors'][0]['id'],self.a)
        self.assertEqual(data[second]['y']['contributors'][0]['id'],self.b)
        self.plan.uppdatera(self.b,indata={'glid_x':True})
        self.assertEqual(self.plan.state['stability_results'][1]['results']['x']['H_Rd'],100)
        self.assertEqual(self.plan.glidningsresultat['x']['H_Rd'],40)

    def test_legacy_reopens_identical_demands_membership_placement_and_results(self):
        self.plan.glidning={'placements':{'1':{'symbol':{'x':.2,'y':.3,'size':140},'legend':{'x':.5,'y':.2,'size':410}}}}
        before=copy.deepcopy((self.plan.glidningsresultat,self.plan.resultat,self.plan.glidning['placements']))
        old=self.plan._document();old['version']=34
        for name in ('groups','name','angle_deg','group_mode','next_group_id'):old['sliding'].pop(name)
        for tag in old['tags']:tag['values'].pop('stability_group')
        self.plan._load_document(json.dumps(old).encode())
        self.assertEqual((self.plan.glidningsresultat,self.plan.resultat,self.plan.glidning['placements']),before)
        self.assertTrue(all(tag['values']['stability_group']==0 for tag in self.plan.taggar))
        self.assertEqual(self.plan.glidning['groups'],[]);self.assertFalse(self.plan.glidning['group_mode'])

    def test_membership_bulk_and_rotation_are_undoable_without_bearing_recalculation(self):
        before=copy.deepcopy(self.plan.resultat)
        second=self.ok('stability_create',name='Annex')['id']
        with patch.object(self.plan,'_refresh_tag',side_effect=AssertionError('No engineering changes')):
            self.ok('bulk_update',ids=[self.a,self.b],values={'stability_group':second})
            self.ok('stability_update',id=second,settings={'angle_deg':-30,'H_y_Ed':70,'check_y':True})
            self.ok('undo');self.assertEqual(self.plan.glidning['groups'][0]['angle_deg'],0)
            self.ok('redo');self.assertEqual(self.plan.glidning['groups'][0]['angle_deg'],330)
            self.ok('undo');self.ok('undo')
        self.assertTrue(all(tag['values']['stability_group']==0 for tag in self.plan.taggar))
        self.assertEqual(self.plan.resultat,before)

    def test_extra_symbols_use_existing_move_scale_lock_and_save(self):
        group=self.plan.skapa_stabilitetsgrupp('Hus 2')
        symbol={'type':'overlay','kind':f'stability:{group}:symbol','page':1}
        legend={**symbol,'kind':f'stability:{group}:legend'}
        self.plan.flytta_objekt([{**symbol,'x':.25,'y':.4}])
        self.plan.transformera_objekt([{**legend,'x':.6,'y':.2,'scale':1.5}])
        self.plan.las_placering([symbol,legend])
        with self.assertRaisesRegex(ValueError,'låst'):self.plan.andra_stabilitetsgrupp(group,{'angle_deg':30})
        loaded=Grundplan.oppna(self.plan.spara(self.root/'multi.json'));self.addCleanup(loaded.close)
        self.assertEqual(loaded.glidning,self.plan.glidning);self.assertEqual(loaded.objektlayout,self.plan.objektlayout)
        self.assertEqual(loaded.placeringslas,self.plan.placeringslas)
        with self.assertRaises(ValueError):self.plan.las_placering([{**symbol,'kind':'stability:999:symbol'}])

    def test_unknown_groups_duplicate_names_and_invalid_angles_are_atomic(self):
        second=self.plan.skapa_stabilitetsgrupp('Hus 2')
        before=self.plan._document()
        for settings in ({'name':'Hus 1'},{'name':' '},{'angle_deg':float('nan')},{'angle_deg':True},{'angle_deg':36001}):
            with self.subTest(settings=settings),self.assertRaises(ValueError):self.plan.andra_stabilitetsgrupp(second,settings)
            self.assertEqual(self.plan._document(),before)
        for value in (None,True,-1,999,.5):
            with self.subTest(value=value),self.assertRaises(ValueError):self.plan.uppdatera_flera([self.a,self.b],indata={'stability_group':value})
            self.assertEqual(self.plan._document(),before)
        with self.assertRaises(ValueError):self.plan.lagg_till(.5,.5,indata={'stability_group':999})
        self.assertEqual(self.plan._document(),before)

    def test_locked_inputs_are_skipped_and_nonempty_groups_cannot_be_deleted(self):
        second=self.plan.skapa_stabilitetsgrupp('Hus 2');self.plan.las_indata([self.a])
        report=self.plan.uppdatera_flera([self.a,self.b],indata={'stability_group':second})
        self.assertEqual(report['locked'],1);self.assertEqual(self.plan._tag(self.a)['values']['stability_group'],0)
        with self.assertRaises(ValueError):self.plan.ta_bort_stabilitetsgrupp(second)
        self.plan.uppdatera(self.b,indata={'stability_group':0});self.ok('stability_delete',id=second)
        self.assertFalse(self.plan.glidning['groups']);self.ok('undo');self.assertEqual(self.plan.glidning['groups'][0]['id'],second)
        copied=self.plan.kopiera(self.b,.8,.8);self.assertEqual(self.plan._tag(copied)['values']['stability_group'],0)
