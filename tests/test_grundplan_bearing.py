"""Soil resistance uses the same effective area as Grundplan's pressure and sketch."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestBearingArea(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        image = Path(folder.name) / "plan.png"
        Image.new("RGB", (800,600), "white").save(image)
        self.plan = Grundplan(image); self.addCleanup(self.plan.close)

    def test_pressure_resistance_and_utilization_agree_for_all_three_footing_categories(self):
        cases = (("pelarsula",0,2.1,None),("vaggsula",1,2,4),("vaggsula",0,1.4,.6))
        for typ, model, by, source, moment in ((*case,m) for case in cases for m in (0,31)):
            with self.subTest(typ=typ,model=model,moment=moment):
                values = {"lang":model,"b":2.8,"l":by,"t":.3,"F_vy":1227.1,
                    "e_b_plac":.1,"e_l_plac":.4 if not model else 0,"M_insp_b":moment,"isolering":False}
                if source is not None:
                    values.update(lasttyp=1,L_vagg=source,l_override=True)
                ident = self.plan.lagg_till(.3,.4,typ=typ,indata=values)
                tag = self.plan._tag(ident); r = tag["summary"]; a = r["effective_area"]["brott"]
                self.assertAlmostEqual(r["barformaga"],r["q_bd"]*a["area"])
                self.assertAlmostEqual(r["utnyttjandegrad"],r["q_Ed"]/r["q_bd"])
                self.assertAlmostEqual(r["utnyttjandegrad"],r["last"]/r["barformaga"])
                if source is not None:
                    self.assertEqual(tag["values"]["L_vagg"],source)
                    self.assertAlmostEqual(r["load_conversion"]["brott"],1227.1*source)

    def test_old_project_recalculates_bearing_without_changing_inputs_contours_or_labels(self):
        ident = self.plan.lagg_till(.3,.4,typ="pelarsula",indata={"b":2.8,"l":2.1,
            "F_vy":1227.1,"t":.3,"e_l_plac":.4,"isolering":False})
        self.plan.kalibrering = {"start":{"x":.1,"y":.1},"end":{"x":.6,"y":.1},"length_m":10}
        self.plan.placera_sulkontur(ident,{"kind":"pad","center":{"x":.5,"y":.5},"angle_deg":37})
        document = self.plan._document(); expected = copy.deepcopy(self.plan._tag(ident)["summary"])
        document["calculator_version"] = "old-before-effective-area-fix"
        document["tags"][0]["summary"] = {"barformaga":957.61,"utnyttjandegrad":1.35}
        self.plan._load_document(json.dumps(document).encode())
        tag = self.plan._tag(ident)
        self.assertEqual(tag["summary"],expected)
        self.assertEqual(tag["values"],document["tags"][0]["values"])
        self.assertEqual((tag["x"],tag["y"]),(.3,.4))
        self.assertEqual(self.plan.sulkonturer,document["contours"])
        self.assertGreater(tag["summary"]["barformaga"],957.61)
        self.plan.uppdatera(ident,indata={"b":5})
        self.assertEqual(self.plan._tag(ident)["status"],"calculated")
        self.assertGreater(self.plan._tag(ident)["summary"]["barformaga"],0)
