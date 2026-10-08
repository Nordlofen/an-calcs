"""Self-contained, offline HTML result view using the notebook's shared UI."""

import html
import json
from pathlib import Path


_ASSETS = Path(__file__).parent


def render_html(snapshot, *, pdf_mode=False):
    # JSON script elements are still HTML raw text: escape '<' so comments,
    # titles and labels cannot close the element or inject executable markup.
    data = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
    for character in ("<", ">", "&", "\u2028", "\u2029"):
        data = data.replace(character, f"\\u{ord(character):04x}")
    css = (_ASSETS / "grundplan.css").read_text(encoding="utf-8")
    script = (_ASSETS / "grundplan.js").read_text(encoding="utf-8")
    script += "\n" + (_ASSETS / "grundplan_html.js").read_text(encoding="utf-8")
    title = html.escape(str(snapshot["state"]["title"]))
    pdf_css = pdf_script = ""
    if pdf_mode:
        width, height = snapshot["pages"][0]["width"], snapshot["pages"][0]["height"]
        pdf_css = f'''
@page {{ size: {width}px {height}px; margin: 0; }}
html, body, #grundplan {{ margin: 0; padding: 0; width: {width}px; height: {height}px; min-height: 0; background: transparent; }}
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.an-grundplan.gp-pdf {{ width: {width}px; min-width: 0; min-height: 0; border: 0; border-radius: 0; overflow: hidden; background: transparent; }}
.gp-pdf .gp-workspace {{ width: {width}px !important; max-width: none; padding: 0; border: 0; }}
.gp-pdf .gp-workspace > :not(.gp-board), .gp-pdf .gp-table-section,
.gp-pdf .gp-board > :not(.gp-viewport) {{ display: none !important; }}
.gp-pdf .gp-board {{ width: {width}px; height: {height}px !important; border: 0; }}
.gp-pdf .gp-viewport, .gp-pdf .gp-sheet {{ background: transparent; box-shadow: none; }}
.gp-pdf .gp-picture {{ visibility: hidden; }}
'''
        # The same DOM handles wrapping, math indices and font metrics. Fit only
        # cards that cross the page boundary, without changing saved positions.
        pdf_script = '''
await document.fonts.ready;
await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
const sheet = document.querySelector(".gp-sheet"), pageBox = sheet.getBoundingClientRect();
function paintBox(element) {
  if (!element.classList.contains("gp-text-annotation")) return element.getBoundingClientRect();
  // A wide heading container does not make its short text wider or smaller.
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT), boxes = [];
  while (walker.nextNode()) {
    if (!walker.currentNode.textContent.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(walker.currentNode);
    boxes.push(...range.getClientRects());
  }
  if (!boxes.length) return element.getBoundingClientRect();
  const left = Math.min(...boxes.map(b => b.left)), top = Math.min(...boxes.map(b => b.top)),
    right = Math.max(...boxes.map(b => b.right)), bottom = Math.max(...boxes.map(b => b.bottom));
  return {left, top, right, bottom, width: right - left, height: bottom - top};
}
for (const element of sheet.querySelectorAll(".gp-tag, .gp-sliding-overlay")) {
  if (element.hidden) continue;
  const box = paintBox(element);
  const fit = Math.min(1, pageBox.width / box.width, pageBox.height / box.height);
  if (fit < 1) element.style.transform += " scale(" + fit + ")";
  const fitted = paintBox(element);
  const dx = Math.max(pageBox.left - fitted.left, Math.min(0, pageBox.right - fitted.right));
  const dy = Math.max(pageBox.top - fitted.top, Math.min(0, pageBox.bottom - fitted.bottom));
  element.style.left = parseFloat(element.style.left) + dx / pageBox.width * 100 + "%";
  element.style.top = parseFloat(element.style.top) + dy / pageBox.height * 100 + "%";
}
sheet.dispatchEvent(new Event("gp:layout"));
document.documentElement.dataset.pdfReady = "true";
'''
    return f'''<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{title} – resultat</title>
<style>
{css}
html, body {{ margin: 0; height: 100%; background: #eaf0f0; }}
body {{ padding: 12px; box-sizing: border-box; }}
#grundplan {{ min-height: 100%; }}
.an-grundplan.gp-readonly {{ min-height: 100%; display: flex; flex-direction: column; }}
.gp-readonly .gp-heading, .gp-readonly .gp-toolbar, .gp-readonly .gp-status,
.gp-readonly .gp-legend {{ flex-shrink: 0; }}
.gp-readonly .gp-board {{ flex: none; height: clamp(360px, 65vh, 860px); }}
.gp-readonly .gp-legend {{ padding-bottom: 10px; }}
@media (max-width: 650px) {{
  body {{ padding: 0; }}
  .an-grundplan.gp-readonly {{ border-radius: 0; }}
  .gp-readonly .gp-heading {{ padding: 12px 14px; }}
}}
{pdf_css}
</style>
</head>
<body>
<main id="grundplan" aria-label="Grundplan – resultat"></main>
<noscript>Aktivera JavaScript i webbläsaren för att visa ritningen och öppna etiketterna.</noscript>
<script id="grundplan-data" type="application/json">{data}</script>
<script type="module">
{script}
const snapshot = JSON.parse(document.getElementById("grundplan-data").textContent);
render({{ model: createResultModel(snapshot, validateCalibration, validateLayout), el: document.getElementById("grundplan"), readOnly: true, pdfMode: {str(pdf_mode).lower()} }});
{pdf_script}
</script>
</body>
</html>
'''.encode("utf-8")
