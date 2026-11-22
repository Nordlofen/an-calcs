"""Kompakt inmatning för Betongtvärsnittets Panel."""

PANEL_STYLE = """
<style>
.bt-panel { padding: 8px 18px; }
.bt-panel .anp-title h3 { margin-bottom: 4px; }
.bt-panel .anp-cases { padding: 3px 10px; margin-bottom: 6px; }
.bt-panel .anp-cases > .anp-section-summary { top: 7px; }
.bt-panel .anp-section { padding-block: 4px; }
.bt-panel .anp-section .p-Collapse-contents,
.bt-panel .anp-section .jupyter-widget-Collapse-contents { padding-top: 5px; }
.bt-panel .anp-grid { gap: 6px 12px; align-items: start; }
.bt-panel .anp-subsections { gap: 5px 16px; }
.bt-panel .anp-subsections:not(.anp-cols-1) > .anp-section-static + .anp-section-static { padding-left: 16px; }
.bt-panel .anp-section-heading h4 { font-weight: 600; margin-bottom: 3px; }
.bt-panel .anp-field { gap: 2px 6px; }
.bt-panel .anp-field-help { font-size: 11px; line-height: 1.35; }
.bt-panel .anp-illustrated-section { gap: 0; }
.bt-panel .anp-figure figcaption { margin-top: 4px; font-size: 11px; }
.bt-panel .anp-figure figcaption:empty { display: none; }
.bt-panel .anp-figure svg[aria-label^="Måttsatt tvärsnitt"] { max-height: 174px; }
.bt-panel .betongtvarsnitt-stadium-help summary { cursor: pointer; }
.bt-panel .betongtvarsnitt-stadium-help div + div { margin-top: .35em; }
.bt-panel .anp-table { margin: 0; }
.bt-panel .anp-table .anp-section-heading { display: none; }
.bt-panel .anp-table-row { padding: 3px 0; }
.bt-panel .anp-table-header .widget-html-content { line-height: 1.2; }
.bt-panel .anp-table-add { margin-top: 3px; }
.bt-panel .anp-footer { padding-top: 8px; }
@media (pointer: fine) {
    .bt-panel .anp-input :is(input, select) { height: 30px; padding-block: 2px; }
    .bt-panel .anp-table .widget-button { min-height: 28px; padding: 3px 8px; }
}
@container (min-width: 720px) {
    .bt-panel .anp-grid:has(> .anp-field .betongtvarsnitt-stadium-help) {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }
}
@container (min-width: 890px) {
    .bt-panel .anp-field:has(> :nth-child(2) .anp-field-meta:not(:empty)) {
        display: grid;
        grid-template-columns: max-content minmax(0, 1fr);
        align-items: baseline;
    }
    .bt-panel .anp-field:has(> :nth-child(2) .anp-field-meta:not(:empty)) > :nth-child(n+3) {
        grid-column: 1 / -1;
    }
}
@container (max-width: 560px) {
    .bt-panel .anp-subsections:not(.anp-cols-1) > .anp-section-static + .anp-section-static {
        padding-left: 0;
        border-left: 0;
    }
}
</style>
""".replace(".bt-panel", ".anp-panel:has(.betongtvarsnitt-stadium-help)")
