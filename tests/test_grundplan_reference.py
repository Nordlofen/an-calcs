import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_NOTEBOOK = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2"))
if HAS_NOTEBOOK:
    from PIL import Image
    from an_calcs.notebook import Grundplan
    from an_calcs.notebook.grundplan_colour import group_data as colour_groups, validate_settings
    from an_calcs.notebook.grundplan_types import footing_category


@unittest.skipUnless(HAS_NOTEBOOK, "Installera an-calcs[notebook].")
class TestReference(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        drawing = self.root / "drawing.png"
        Image.new("RGB", (1800, 2200), "white").save(drawing)
        self.plan = Grundplan(drawing)
        self.addCleanup(self.plan.close)

    def add(self, label="VS.1", typ="vaggsula", **values):
        return self.plan.lagg_till(.8, .8, littera=label, typ=typ,
            indata={"F_vy": 100, "F_vy_bruk": 60, "b": 1.4, "t": .25, **values})

    def test_group_picks_highest_u_and_documents_only_the_exception_without_editing_comments(self):
        a = self.add("VS.22", isolering=True, f_d_brott=300, f_d_bruk=60, kommentar="Egen kommentar")
        b = self.add("VS.28", isolering=False, F_vy=50)
        before = copy.deepcopy((self.plan.taggar, self.plan.resultat))
        data = self.plan.referensgrupper
        self.assertEqual(len(data["groups"]), 1)
        group = data["groups"][0]
        self.assertEqual(group["reference_id"], a)
        self.assertEqual(group["geometry"], {"t": .25, "b": 1.4})
        self.assertEqual(group["loads"], {"brott": 100, "bruk": 60})
        self.assertEqual(group["utilization_range"], {
            "min": self.plan._tag(b)["summary"]["utnyttjandegrad"],
            "max": self.plan._tag(a)["summary"]["utnyttjandegrad"]})
        self.assertIn("Utan isolering: VS.28", group["comments"])
        self.assertIn("Styrande för VS.22: " + self.plan._tag(a)["summary"]["styrande"], group["comments"])
        self.assertEqual([member["id"] for member in group["members"]], [a, b])
        self.plan.referens = {"enabled": True}
        self.assertEqual((self.plan.taggar, self.plan.resultat), before)
        self.assertEqual(self.plan._tag(a)["values"]["kommentar"], "Egen kommentar")
        self.assertEqual(self.plan.state["reference_data"], data)
        self.plan.uppdatera(a, indata={"isolering": False})
        self.assertIn("Utan isolering", self.plan.referensgrupper["groups"][0]["comments"])

    def test_reference_recomputes_after_inputs_and_membership_change_with_natural_ties(self):
        ten = self.add("VS.10")
        two = self.add("VS.2")
        self.assertEqual(self.plan.referensgrupper["groups"][0]["reference_id"], two)
        self.plan.uppdatera(ten, indata={"F_vy": 200})
        self.assertEqual(self.plan.referensgrupper["groups"][0]["reference_id"], ten)
        self.assertEqual(self.plan.referensgrupper["groups"][0]["utilization_range"]["min"],
                         self.plan._tag(two)["summary"]["utnyttjandegrad"])
        self.plan.uppdatera(ten, indata={"b": 2})
        self.assertEqual(len(self.plan.referensgrupper["groups"]), 2)
        self.plan.ta_bort(ten)
        self.assertEqual(self.plan.referensgrupper["groups"][0]["reference_id"], two)

    def test_geometry_and_soil_split_groups_but_loads_and_insulation_do_not(self):
        self.add("VS.1")
        self.add("VS.2", F_vy=150)
        for i, values in enumerate(({"t": .3}, {"b": 1.5}, {"phi_k": 33},
                                     {"l_override": True, "l": 2}, {"L_vagg_minst_1": False, "L_vagg": .7}), 3):
            self.add("VS." + str(i), **values)
        self.assertEqual(len(self.plan.referensgrupper["groups"]), 6)

    def test_equal_integer_and_float_parameters_share_groups_without_rounding(self):
        from an_calcs.notebook.grundplan_reference import CONDITIONS
        wall = self.add("VS.7", t=1, b=1)
        conditions = {name: float(self.plan._tag(wall)["values"][name]) for name in CONDITIONS}
        same_wall = self.add("VS.8", t=1.0, b=1.0, **conditions)
        modeled = self.add("VS.11", lang=0, lasttyp=1, t=1, b=1, l=1, L_vagg=1)
        same_modeled = self.add("VS.12", lang=0, lasttyp=1, t=1.0, b=1.0, l=1.0, L_vagg=1.0, **conditions)
        before = copy.deepcopy(self.plan.taggar)
        groups = self.plan.referensgrupper["groups"]
        self.assertEqual([{member["id"] for member in group["members"]} for group in groups],
                         [{wall, same_wall}, {modeled, same_modeled}])
        self.assertEqual(self.plan.taggar, before)
        self.add("VS.9", t=1.0, b=1.0000000001, **conditions)
        self.assertEqual(len(self.plan.referensgrupper["groups"]), 3)

    def test_three_physical_categories_and_converted_loads_are_distinct(self):
        wall = self.add()
        modeled = self.add("VS.11", lang=0, lasttyp=1, l=1.3, L_vagg=.5, F_vy=535.3, F_vy_bruk=438.6)
        pad = self.add("PS.1", typ="pelarsula", l=1.3)
        self.assertEqual([footing_category(self.plan._tag(id)) for id in (wall, modeled, pad)], ["wall", "wall_pad", "pad"])
        data = self.plan.referensgrupper["groups"]
        self.assertEqual([g["category"] for g in data], ["wall", "wall_pad", "pad"])
        self.assertEqual(data[1]["geometry"], {"t": .25, "b": 1.4, "l": 1.3, "L_vagg": .5})
        self.assertEqual(data[1]["resultants"], {"brott": 267.65, "bruk": 219.3})
        self.add("VS.12", lang=0, lasttyp=1, l=1.3, L_vagg=.6)
        self.add("PS.2", typ="pelarsula", l=1.4)
        self.assertEqual(len(self.plan.referensgrupper["groups"]), 5)
        settings = validate_settings({"categories": ["sultyp", "t", "b"]})
        groups = colour_groups(self.plan.taggar, settings)
        self.assertEqual(len({groups["assignments"][id]["key"] for id in (wall, modeled, pad)}), 3)
        self.assertTrue(all(g["pattern"] == "plain" for g in groups["groups"]))

    def test_pad_model_is_fixed_in_creation_updates_and_copies(self):
        with self.assertRaisesRegex(ValueError, "bara väljas"):
            self.add("PS.1", typ="pelarsula", lang=1)
        ident = self.add("PS.1", typ="pelarsula")
        before = self.plan.taggar
        with self.assertRaisesRegex(ValueError, "bara väljas"):
            self.plan.uppdatera(ident, indata={"lang": 1})
        self.assertEqual(self.plan.taggar, before)
        with self.assertRaises(ValueError):
            self.plan.kopiera(ident, .3, .3, indata={"lang": 1})
        wall = self.add("VS.11", lang=0, lasttyp=1, l=1.3, L_vagg=.5)
        duplicate = self.plan.kopiera(wall, .4, .4)
        self.assertEqual(self.plan._tag(duplicate)["footing_type"], "vaggsula")
        self.assertTrue(self.plan._tag(duplicate)["label"].startswith("VS"))
        self.plan.uppdatera(duplicate, indata={"lang": 1})
        self.assertEqual(self.plan._tag(duplicate)["values"]["lang"], 1)

    def test_inactive_h_only_invalid_and_stale_objects_never_become_references(self):
        active = self.add()
        self.add("VS.2", inaktiv=True, F_vy=None)
        self.add("H-GR.1", endast_h_stabilitet=True)
        self.add("VS.3", F_vy=None)
        stale = self.add("VS.4")
        self.plan.uppdatera_flera([stale], indata={"t": .3}, berakna=False)
        data = self.plan.referensgrupper
        self.assertEqual(data["groups"][0]["reference_id"], active)
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(len(data["excluded"]), 4)

    def test_roundtrip_and_legacy_migration_preserve_engine_inputs_and_results(self):
        self.add("VS.11", lang=0, lasttyp=1, l=1.3, L_vagg=.5)
        self.add("PS.1", typ="pelarsula")
        self.plan.referens = {"enabled": True, "x": .2, "size": 550}
        self.plan.farggruppering = {"enabled": True, "categories": ["sultyp", "t", "b", "V"]}
        path = self.plan.spara(self.root / "project.json")
        loaded = Grundplan.oppna(path); self.addCleanup(loaded.close)
        self.assertEqual(loaded.referens, self.plan.referens)
        self.assertEqual(loaded.referensgrupper, self.plan.referensgrupper)
        self.assertEqual(loaded.taggar, self.plan.taggar)
        legacy = self.plan._document(); legacy["version"] = 19
        legacy.pop("reference_widget")
        for tag in legacy["tags"]:
            tag.pop("footing_type")
        legacy["colour_grouping"] = {}
        loaded._load_document(json.dumps(legacy).encode())
        self.assertEqual(loaded.resultat, self.plan.resultat)
        self.assertEqual([tag["footing_type"] for tag in loaded.taggar], ["vaggsula", "pelarsula"])
        self.assertFalse(loaded.referens["enabled"])
        self.plan.farggruppering = {"categories": ["sultyp", "t", "b", "l", "V", "isolering"]}
        loaded = Grundplan.oppna(self.plan.spara(self.root / "all-categories.json"))
        self.addCleanup(loaded.close)
        self.assertEqual(loaded.farggruppering, self.plan.farggruppering)

    def test_ambiguous_legacy_origin_requires_confirmation_and_retains_numerics(self):
        ident = self.add("Objekt A", typ="pelarsula")
        original = self.plan.resultat
        document = self.plan._document(); document["version"] = 19
        document["tags"][0].pop("footing_type")
        self.plan._load_document(json.dumps(document).encode())
        self.assertTrue(self.plan._tag(ident)["footing_type_inferred"])
        self.assertEqual(self.plan.referensgrupper["groups"], [])
        self.plan.bekrafta_sultyp(ident, "vaggsula")
        self.assertEqual(self.plan.resultat, original)
        self.assertEqual(self.plan.referensgrupper["groups"][0]["category"], "wall_pad")
        with self.assertRaises(ValueError):
            self.plan.bekrafta_sultyp(ident, "pelarsula")

    def test_settings_and_type_metadata_validate_atomically(self):
        self.add()
        before = self.plan.referens
        for patch_value in ({"enabled": 1}, {"size": 204}, {"x": 1.1}, {"other": True}):
            with self.assertRaises(ValueError):
                self.plan.referens = patch_value
            self.assertEqual(self.plan.referens, before)
        before_tags = self.plan.taggar
        document = self.plan._document(); document["tags"][0]["footing_type"] = "unknown"
        with self.assertRaises(ValueError):
            self.plan._load_document(json.dumps(document).encode())
        self.assertEqual(self.plan.taggar, before_tags)

    def test_pdf_and_html_share_reference_data_and_keep_widgets_as_vectors(self):
        from pypdf import PdfReader
        from reportlab.pdfgen.canvas import Canvas
        source = io.BytesIO(); canvas = Canvas(source, pagesize=(1200, 1600))
        canvas.line(600, 300, 1000, 1300); canvas.showPage(); canvas.save()
        drawing = self.root / "drawing.pdf"; drawing.write_bytes(source.getvalue())
        self.plan.importera_ritning(drawing)
        self.add("VS.22", isolering=True, f_d_brott=300, f_d_bruk=60)
        self.add("VS.28", F_vy=50)
        self.plan.referens = {"enabled": True, "x": .04, "y": .08}
        self.plan.farggruppering = {"enabled": True, "categories": ["sultyp", "t", "b"]}
        pdf = self.plan._pdf_bytes()
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        self.assertEqual(list(page.images), [])
        text = page.extract_text()
        for caption in ("Referens", "VS.22", "Foundation", "Gäller för", "Linjelast", "(2 st)"):
            self.assertIn(caption, text)
        self.assertNotIn("Styrande för", text)
        self.assertNotIn("Utan isolering: VS.28", text)
        with patch.object(self.plan, "_pdf_bytes", return_value=pdf):
            html = self.plan._html_bytes().decode()
        self.assertIn('"reference_data"', html)
        self.assertIn('"footing_type": "vaggsula"', html)
        self.assertIn('"Utan isolering: VS.28"', html)
