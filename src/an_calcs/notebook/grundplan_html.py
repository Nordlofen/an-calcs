"""Self-contained, offline HTML result view using the notebook's shared UI."""

import html
import json
from pathlib import Path


_ASSETS = Path(__file__).parent


def render_html(snapshot):
    # JSON script elements are still HTML raw text: escape '<' so comments,
    # titles and labels cannot close the element or inject executable markup.
    data = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
    for character in ("<", ">", "&", "\u2028", "\u2029"):
        data = data.replace(character, f"\\u{ord(character):04x}")
    css = (_ASSETS / "grundplan.css").read_text(encoding="utf-8")
    script = (_ASSETS / "grundplan.js").read_text(encoding="utf-8")
    script += "\n" + (_ASSETS / "grundplan_html.js").read_text(encoding="utf-8")
    title = html.escape(str(snapshot["state"]["title"]))
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
</style>
</head>
<body>
<main id="grundplan" aria-label="Grundplan – resultat"></main>
<noscript>Aktivera JavaScript i webbläsaren för att visa ritningen och öppna etiketterna.</noscript>
<script id="grundplan-data" type="application/json">{data}</script>
<script type="module">
{script}
const snapshot = JSON.parse(document.getElementById("grundplan-data").textContent);
render({{ model: createResultModel(snapshot, validateCalibration), el: document.getElementById("grundplan"), readOnly: true }});
</script>
</body>
</html>
'''.encode("utf-8")
