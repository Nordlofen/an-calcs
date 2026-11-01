"""Menu positioning inside transformed/virtualized notebook output containers."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HAS_BROWSER = all(importlib.util.find_spec(name) for name in ("anywidget", "PIL", "pypdfium2", "playwright"))
if HAS_BROWSER:
    from PIL import Image
    from an_calcs.notebook import Grundplan


@unittest.skipUnless(HAS_BROWSER, "Installera an-calcs[notebook].")
class TestNotebookMenus(unittest.TestCase):
    def test_menus_stay_at_their_buttons_in_notebook_containers(self):
        from playwright.sync_api import sync_playwright, Error
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "plan.png"
            Image.new("RGB", (800, 600), "white").save(image)
            plan = Grundplan(image)
            self.addCleanup(plan.close)
            plan.lagg_till(.3, .4, typ="pelarsula")
            assets = Path(__file__).resolve().parents[1] / "src/an_calcs/notebook"
            source = (assets / "grundplan.js").read_text().replace("export default { render };", "").replace("export function ", "function ")
            fixture = json.dumps({"state": plan.state, "schema": plan.schema, "background": plan.background}).replace("<", "\\u003c")
            html = ('<!doctype html><style>body{margin:8px}' + (assets / "grundplan.css").read_text()
                    + '</style><div id="notebook-output"><div id="host"></div></div><script id="fixture" type="application/json">'
                    + fixture + '</script><script type="module">' + source + '''
const data=JSON.parse(document.getElementById('fixture').textContent);window.commands=[];
render({model:{get:name=>data[name],on:()=>{},off:()=>{},send:request=>window.commands.push(request)},el:document.getElementById('host')});
</script>''')
            with sync_playwright() as runtime:
                browser = None
                for channel in ("chrome", "msedge", None):
                    try:
                        browser = runtime.chromium.launch(channel=channel, headless=True, chromium_sandbox=True)
                        break
                    except Error:
                        continue
                if browser is None:
                    self.skipTest("Ingen lokal Chromium, Chrome eller Edge.")
                try:
                    for width, top, left, scale, scroll in ((1450, 0, 0, 1, 0), (1450, 390, 70, 1, 0), (1450, 320, 100, .8, 0), (1450, 700, 70, 1, 300), (420, 100, 0, 1, 0)):
                        with self.subTest(width=width, top=top, left=left, scale=scale, scroll=scroll):
                            context = browser.new_context(viewport={"width": width, "height": 1100})
                            context.route("**/*", lambda route: route.abort())
                            page = context.new_page()
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            page.set_content(html)
                            page.locator(".gp-menubar").wait_for()
                            page.locator("#notebook-output").evaluate("(el,p)=>{el.style.margin=p.top+'px 0 0 '+p.left+'px';el.style.transform='translate(0px,0px) scale('+p.scale+')';el.style.transformOrigin='top left';}",
                                                                         {"top": top, "left": left, "scale": scale})
                            page.evaluate("y=>window.scrollTo(0,y)", scroll)
                            for caption in ("Projekt", "Skapa", "Visa", "Beräkning", "Ritning"):
                                trigger = page.locator(".gp-menubar .gp-menu-trigger").filter(has_text=caption)
                                trigger.click()
                                self.check_position(page, trigger, scale)
                                # Scrolling a long menu must not dismiss it.
                                panel = page.locator(".gp-menu-panel:visible")
                                panel.evaluate("el=>el.scrollTop=el.scrollHeight")
                                self.assertTrue(panel.is_visible())
                                page.keyboard.press("Escape")
                            page.get_by_role("button", name="Markera samtliga", exact=True).click()
                            for caption in ("Lås", "Ordna", "Skala…"):
                                trigger = page.locator(".gp-selection-actions .gp-menu-trigger").filter(has_text=caption)
                                trigger.click()
                                self.check_position(page, trigger, scale)
                                page.keyboard.press("Escape")
                            self.assertEqual(page.evaluate("window.commands"), [])
                            self.assertEqual(errors, [])
                            context.close()
                finally:
                    browser.close()

    def check_position(self, page, trigger, scale):
        panel = page.locator(".gp-menu-panel:visible")
        self.assertEqual(panel.count(), 1)
        a, b = trigger.bounding_box(), panel.bounding_box()
        root = page.locator(".an-grundplan").bounding_box()
        gap = 5 * scale
        left = max(8, root["x"] + 2 * scale)
        right = min(page.viewport_size["width"] - 8, root["x"] + root["width"] - 2 * scale)
        expected_x = max(left, min(a["x"], right - b["width"]))
        self.assertLess(abs(b["x"] - expected_x), 2, "Menu must align horizontally with the trigger or clamp to the visible edge.")
        below = abs(b["y"] - a["y"] - a["height"] - gap)
        above = abs(b["y"] + b["height"] - a["y"] + gap)
        self.assertLess(min(below, above), 2, "Menu must stay directly beside its trigger, even inside a transformed output.")
        self.assertGreaterEqual(b["x"], max(0, root["x"]) - 1)
        self.assertLessEqual(b["x"] + b["width"], min(page.viewport_size["width"], root["x"] + root["width"]) + 1)
        self.assertGreaterEqual(b["y"], max(0, root["y"]) - 1)
        self.assertLessEqual(b["y"] + b["height"], page.viewport_size["height"] + 1)
        # Bounds alone are insufficient: the panel must actually receive clicks.
        self.assertTrue(panel.evaluate("el=>{const r=el.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+12)?.closest('.gp-menu-panel')===el;}"))
