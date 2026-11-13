"""Oberoende jämviktsfall och modellgränser för Pelarholk."""

import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from an_calcs.betong import Pelarholk, pelarholk


def data(**changes):
    # Valda reaktioner 240, 90, 600 kN ger nedanstående yttre laster för mu=0.2.
    base = dict(typ="pelare", fristaende=True, M=98.4, Fv=630., Fh=30., h=300.,
                l=500., D=400., t_ig=20., bh=300., c_nom=35., phi=16.,
                f_cd_ig=25., f_cd_c=20., f_yd=400., mu=.2)
    return {**base, **changes}


def values(details):
    return {item["namn"]: item["value"] for section in ("indata", "delresultat", "slutresultat") for item in details[section]["items"]}


class TestPelarholk(unittest.TestCase):
    def test_handfall_krafter_tryck_och_bojarmering(self):
        d = Pelarholk(data())
        r = values(d)
        for name, expected in {"F1": 240, "F2": 90, "F3": 600, "V_Ed": 240,
                               "a_c": 150, "a1": 450, "a2": 50, "d": 237,
                               "z": 213.3, "M_holk": 108, "sigma_ig_1_max": 8,
                               "sigma_ig_2_max": 3, "sigma_3_mean": 5}.items():
            self.assertAlmostEqual(r[name], expected, places=9, msg=name)
        self.assertAlmostEqual(r["Fs"], 506.3291139240506)
        self.assertAlmostEqual(r["As_req"], 1265.8227848101267)
        self.assertAlmostEqual(r["sigma_c_1_max"], 480000/(400*(150+20/math.tan(math.radians(26.6)))))
        self.assertEqual(r["status_tryck"], "Uppfyller")
        self.assertEqual(r["styrande_tvarkraft"], "F1")
        json.dumps(d, allow_nan=False)

    def test_jamvikt_utan_och_med_friktion(self):
        for mu in (0., .1, .3):
            for reactions in ((240., 90., 600.), (90., 240., 600.), (0., 0., 0.)):
                F1, F2, F3 = reactions
                # Direkt summering av krafternas moment kring överkantens mitt.
                Fh = F1-F2-mu*F3
                Fv = mu*F1-mu*F2+F3
                M = (-50*F1 + 450*F2 + mu*150*(F1+F2) + mu*500*F3)/1000
                r = values(Pelarholk(data(mu=mu, Fh=Fh, Fv=Fv, M=M)))
                for i, force in enumerate(reactions, 1):
                    self.assertAlmostEqual(r[f"F{i}"], force)
                self.assertAlmostEqual(r["F1"]-r["F2"]-mu*r["F3"], Fh)
                self.assertAlmostEqual(mu*r["F1"]-mu*r["F2"]+r["F3"], Fv)

    def test_f2_styr_fristaende_men_bojning_avser_f1(self):
        r = values(Pelarholk(data(M=173.4, Fh=-270, Fv=570)))
        self.assertAlmostEqual(r["F1"], 90)
        self.assertAlmostEqual(r["F2"], 240)
        self.assertAlmostEqual(r["V_Ed"], 240)
        self.assertEqual(r["styrande_tvarkraft"], "F2")
        self.assertAlmostEqual(r["M_holk"], 40.5)

    def test_plattansluten_ignorerar_bojindata(self):
        v = data(fristaende=False, c_nom=float("nan"), phi=-1, f_yd=None, bh="inaktiv")
        r = values(Pelarholk(v))
        self.assertAlmostEqual(r["V_Ed"], 90)
        self.assertEqual(r["status_bojarmering"], "Ej beräknad")
        for name in ("Fs", "As_req", "M_holk", "d", "z", "phi", "f_yd", "bh"):
            self.assertNotIn(name, r)
        for name in ("bh", "phi", "f_yd", "c_nom"):
            v.pop(name)
        self.assertEqual(r, values(Pelarholk(v)))
        self.assertNotIn("M_{holk}", str(Pelarholk(v)["ekvationer"]))

    def test_vagg_enmeter_och_enheter(self):
        col = values(Pelarholk(data(D=1000)))
        details = Pelarholk(data(typ="vagg", D=float("nan")))
        r = values(details)
        for name in ("F1", "F2", "F3", "As_req", "Fs", "sigma_ig_1_max"):
            self.assertEqual(col[name], r[name])
        for section in ("indata", "delresultat", "slutresultat"):
            for item in details[section]["items"]:
                if item["namn"] in ("F1", "F2", "F3", "Fs", "V_Ed", "Fv", "Fh"):
                    self.assertEqual(item["unit"], "kN/m")
                if item["namn"] == "As_req":
                    self.assertEqual(item["unit"], "mm²/m")
        v = data(typ="vagg")
        v.pop("D")
        self.assertEqual(values(Pelarholk(v)), r)

    def test_skissegenskaper_paverkar_inte_berakning(self):
        self.assertEqual(Pelarholk(data()), Pelarholk(data(H=-1, bv=float("nan"), t_p=None)))

    def test_gynnsam_lokal_friktion_ar_utelamnad(self):
        r = values(Pelarholk(data()))
        self.assertAlmostEqual(r["Fs"] * r["z"], r["F1"] * .9*500)
        self.assertEqual(r["d"], 300-20-35-8)

    def test_ogiltigt_kraftspel_klipps_inte(self):
        for changes in ({"M": 0, "Fh": 0}, {"M": -1000}, {"Fv": 0, "Fh": 30}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "negativ"):
                Pelarholk(data(**changes))

    def test_granser_och_icke_andliga_tal(self):
        for changes in ({"mu": -.1}, {"mu": .30001}, {"l": 359.9}, {"h": 0}, {"t_ig": 0},
                        {"D": -1}, {"f_cd_ig": 0}, {"f_cd_c": 0}, {"f_yd": 0},
                        {"bh": 40}, {"c_nom": -1}, {"phi": 0}, {"Fv": -1},
                        {"fristaende": "False"}, {"typ": "platta"}, {"M": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Pelarholk(data(**changes))
        Pelarholk(data(l=360, mu=.3))
        for name in ("M", "Fv", "Fh", "mu", "h", "l", "D", "t_ig", "bh", "c_nom", "phi", "f_yd", "f_cd_c", "f_cd_ig"):
            for invalid in (float("nan"), float("inf"), None):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    Pelarholk(data(**{name: invalid}))

    def test_tryckoverskridande_och_nollast(self):
        r = values(Pelarholk(data(f_cd_ig=4)))
        self.assertEqual(r["eta_ig_1"], 200)
        self.assertEqual(r["status_tryck"], "Överskriden")
        r = values(Pelarholk(data(Fv=0, Fh=0, M=0)))
        self.assertEqual(r["As_req"], 0)
        self.assertEqual(r["eta_tryck_max"], 0)

    def test_px_och_alias_och_unika_nycklar(self):
        self.assertIs(pelarholk, Pelarholk)
        v = data()
        self.assertEqual(Pelarholk(v), Pelarholk([v[k] for k in Pelarholk.panel_schema["px"]]))
        before = copy.deepcopy(v)
        details = Pelarholk(v)
        self.assertEqual(before, v)
        all_names = [i["namn"] for k in ("indata", "delresultat", "slutresultat") for i in details[k]["items"]]
        self.assertEqual(len(all_names), len(set(all_names)))
        with self.assertRaisesRegex(ValueError, "Okända"):
            Pelarholk(data(F_h=3))
        with self.assertRaises(ValueError):
            Pelarholk([1, 2])


if __name__ == "__main__":
    unittest.main()
