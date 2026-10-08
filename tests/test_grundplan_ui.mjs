// Run with: node --test tests/test_grundplan_ui.mjs
// Exercise the actual widget event handlers; browser tests cover CSS/layout.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.style = { setProperty(name, value) { this[name] = value; } };
    this.className = this.textContent = this.value = "";
    this.hidden = false;
    this.checked = false;
    this.clientWidth = 848;
    this.clientHeight = 648;
    this.offsetWidth = 355;
    this.offsetHeight = 400;
    this.scrollLeft = this.scrollTop = 0;
    this.captures = new Set();
    const classes = () => new Set(this.className.split(/\s+/).filter(Boolean));
    this.classList = {
      toggle: (name, force) => {
        const value = classes();
        if (force ?? !value.has(name)) value.add(name); else value.delete(name);
        this.className = [...value].join(" ");
      },
      add: name => this.classList.toggle(name, true),
      remove: name => this.classList.toggle(name, false),
    };
  }
  set value(value) { this._value = String(value); }
  get value() { return this._value; }
  set type(value) {
    if (this.tag === "textarea") throw new TypeError("HTMLTextAreaElement.type is read-only");
    this._type = value;
  }
  get type() { return this.tag === "textarea" ? "textarea" : this._type; }
  append(...children) {
    for (const child of children) {
      if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child);
      child.parent = this; this.children.push(child);
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parent = null;
    this.children = [];
    this.append(...children);
  }
  remove() { this.parent?.replaceChildren(...this.parent.children.filter(child => child !== this)); }
  click() {
    if (this.tag === "a") document.downloads.push({ href: this.href, filename: this.download });
    this.dispatch("click");
  }
  setAttribute(name, value) { (this.attributes ??= {})[name] = String(value); }
  getAttribute(name) { return this.attributes?.[name] ?? null; }
  removeAttribute() {}
  setCustomValidity(value) { this.validityMessage = value; }
  get validity() {
    return { valid: this.disabled || (!this.validityMessage && (!this.required || this.value !== "")) };
  }
  reportValidity() { return this.validity.valid && this.children.every(child => child.reportValidity()); }
  focus() { document.activeElement = this; }
  closest(selector) {
    if (selector.startsWith(".") ? this.className.split(" ").includes(selector.slice(1)) : this.tag === selector) return this;
    return this.parent?.closest(selector) ?? null;
  }
  addEventListener(name, fn) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(fn);
  }
  removeEventListener(name, fn) {
    this.listeners.set(name, (this.listeners.get(name) ?? []).filter(listener => listener !== fn));
  }
  dispatch(name, options = {}) {
    const event = { target: this, button: 0, pointerId: 1, clientX: 0, clientY: 0,
      detail: 0, preventDefault() {}, stopPropagation() {}, ...options };
    for (const fn of this.listeners.get(name) ?? []) fn(event);
  }
  setPointerCapture(id) { this.captures.add(id); }
  hasPointerCapture(id) { return this.captures.has(id); }
  releasePointerCapture(id) {
    this.captures.delete(id);
    this.dispatch("lostpointercapture", { pointerId: id });
  }
  getBoundingClientRect() {
    if (this.className.split(" ").includes("gp-tag")) {
      const sheet = this.parent.parent;
      const picture = sheet.children.find(e => e.tag === "img").getBoundingClientRect();
      const scale = Number(this.closest(".an-grundplan").style["--gp-tag-scale"] || 1);
      return {left: picture.left + parseFloat(this.style.left) / 100 * picture.width - 10 * scale,
        top: picture.top + parseFloat(this.style.top) / 100 * picture.height - 10 * scale,
        width: 160 * scale, height: 60 * scale};
    }
    if (this.className.split(" ").includes("gp-sliding-legend")) {
      const scale = Number(this.style.transform?.match(/scale\(([^)]+)\)/)?.[1] ?? 1);
      return {left: 0, top: 0, width: 410 * scale, height: 180 * scale};
    }
    if (this.className.split(" ").includes("gp-colour-legend")) {
      const scale = Number(this.style.transform?.match(/scale\(([^)]+)\)/)?.[1] ?? 1);
      return {left: 0, top: 0, width: 300 * scale, height: 220 * scale};
    }
    if (this.tag === "img") return { left: parseFloat(this.parent.style.left) || 0, top: parseFloat(this.parent.style.top) || 0,
      width: parseFloat(this.parent.style.width), height: parseFloat(this.parent.style.height) };
    if (["gp-workspace", "gp-table-section"].some(name => this.className.split(" ").includes(name))) {
      const workspace = this.className.includes("gp-workspace");
      const content = this.children.find(child => child.className === (workspace ? "gp-board" : "gp-table-scroll"));
      return {left: 0, top: 0, width: Math.min(parseFloat(this.style.width) || this.clientWidth, this.closest(".an-grundplan").clientWidth),
        height: content.getBoundingClientRect().height + (this.panelChromeHeight ?? (workspace ? 200 : 120))};
    }
    return { left: 0, top: 0, width: parseFloat(this.style.width) || this.clientWidth, height: parseFloat(this.style.height) || this.clientHeight };
  }
}

const source = await readFile(new URL("../src/an_calcs/notebook/grundplan.js", import.meta.url), "utf8");
const { default: widget, validateCalibration, measuredDistance, colourGroups, validateLayout } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const resultSource = await readFile(new URL("../src/an_calcs/notebook/grundplan_html.js", import.meta.url), "utf8");
const { createResultModel } = await import("data:text/javascript;base64," + Buffer.from(resultSource).toString("base64"));
const names = ["lang", "b", "l", "t", "d", "e_b_plac", "e_l_plac", "F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b", "c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "delta_h", "beta", "alpha", "eta", "gamma_m", "gamma_m0", "gamma_Rd"];
names.push("isolering", "isolerprodukt", "f_d_brott", "f_d_bruk", "F_vy_bruk", "M_insp_l_bruk", "M_insp_b_bruk");
names.push("glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L");
names.push("L_vagg", "L_vagg_minst_1", "l_override", "endast_h_stabilitet", "kommentar", "lasttyp");
const elementText = element => element.textContent + element.children.map(elementText).join("");
const loadGroups = [{label: "Brott", fields: [["F_vy", "V", "kN"], ["F_hb", "Hₓ", "kN"], ["F_hl", "Hᵧ", "kN"], ["M_insp_b", "Mₓ", "kNm"], ["M_insp_l", "Mᵧ", "kNm"]]},
  {label: "Bruk", fields: [["F_vy_bruk", "V", "kN"], ["M_insp_b_bruk", "Mₓ", "kNm"], ["M_insp_l_bruk", "Mᵧ", "kNm"]]}]
  .map(group => ({...group, fields: group.fields.map(([name, symbol, unit]) => ({name, symbol, unit}))}));

function setup(t, { readOnly = false, standalone = false, page = 1, pdf, pdfMode = false } = {}) {
  globalThis.document = Object.assign(new Element("document"), {
    createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag), activeElement: null, downloads: [] });
  globalThis.window = { confirm: () => true };
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
  globalThis.requestAnimationFrame = fn => fn();
  const tag = { id: "tag1", label: "VS1", x: .3, y: .4, page,
    values: Object.fromEntries(names.map(name => [name, 1])), status: "calculated",
      summary: { utnyttjandegrad: .75, styrande: "Jord · brott", b: 1, last: 100, barformaga: 133, q_bd: 133, b_ef: 1, lastenhet: "kN/m" } };
  Object.assign(tag.values, {isolering: false, isolerprodukt: "", kommentar: "", f_d_brott: null, f_d_bruk: null, F_vy_bruk: null});
  Object.assign(tag.values, {glid_x: false, glid_y: false, V_Ed_EQU: null, glid_mu: null, glid_L: null});
  tag.values.L_vagg = null;
  tag.values.L_vagg_minst_1 = true;
  tag.values.l_override = false;
  tag.values.endast_h_stabilitet = false;
  tag.values.lasttyp = 0; // A wall model always uses line units; pads default to total inputs.
  const data = { state: { title: "Test", subtitle: "Projektets underrubrik", tags: [tag], label_size: 100 },
    background: { url: "data:test", width: 800, height: 600, page, page_count: page },
    schema: { load_groups: loadGroups, fields: names.map(name => ({ name, label: name, multiline: name === "kommentar",
      display_symbol: name === "L_vagg" ? {base: "L", subscript: "vägg"} : name === "glid_L" ? {base: "L", subscript: "su"} : undefined,
      type: ["isolerprodukt", "kommentar"].includes(name) ? "text" : ["isolering", "glid_x", "glid_y", "l_override", "L_vagg_minst_1", "endast_h_stabilitet"].includes(name) ? "bool" : ["lang", "lasttyp"].includes(name) ? "choice" : "number",
      unit: loadGroups.flatMap(group => group.fields).find(field => field.name === name)?.unit ?? (name === "V_Ed_EQU" ? "kN" : "m"),
      options: name === "lasttyp" ? [{value: 0, label: "Total last [kN]"}, {value: 1, label: "Linjelast [kN/m]"}] : [{ value: 0 }, { value: 1 }] })) } };
  const sent = [], transfers = [], handlers = new Map();
  const snapshot = { state: data.state, schema: data.schema, page, pages: [data.background], pdf };
  const model = standalone ? createResultModel(snapshot, validateCalibration, validateLayout) : { get: name => data[name], send: (payload, _, buffers) => {
    sent.push(payload); if (buffers?.length) transfers.push({request: payload.request, buffers});
  },
    on: (name, fn) => handlers.set(name, fn), off: name => handlers.delete(name) };
  const host = new Element("host");
  t.after(widget.render({ model, el: host, readOnly, pdfMode }));
  const walk = element => [element, ...element.children.flatMap(walk)];
  const find = predicate => {
    const element = walk(host).find(predicate);
    assert.ok(element, "Requested widget element exists");
    return element;
  };
  const byClass = name => find(element => element.className.split(" ").includes(name));
  const byText = text => find(element => element.textContent === text);
  const viewport = byClass("gp-viewport");
  const marker = () => byClass("gp-tag");
  const position = () => [parseFloat(marker().style.left) / 100, parseFloat(marker().style.top) / 100];
  const ack = (request, extra = {}, buffers = []) => handlers.get("msg:custom")({ ...request, ok: true, ...extra }, buffers);
  const changed = () => standalone ? model.send({action: "label_size", value: 100}) : handlers.get("change:state")();
  const start = (target = marker(), x = 300, y = 300, options = {}) => viewport.dispatch("pointerdown", { target, clientX: x, clientY: y, ...options });
  const move = (x, y) => viewport.dispatch("pointermove", { clientX: x, clientY: y });
  const finish = (x, y, options = {}) => viewport.dispatch("pointerup", { clientX: x, clientY: y, ...options });
  const drag = (dx, dy) => { start(); move(300 + dx, 300 + dy); finish(300 + dx, 300 + dy); };
  const place = (x = 400, y = 400) => { start(byClass("gp-picture"), x, y); finish(x, y); };
  return { tag, data, model, snapshot, elements: () => walk(host), sent, transfers, byClass, byText, find, viewport, marker, position, ack, changed,
    start, move, finish, drag, place, field: name => find(element => element.name === name),
    label: () => byClass("gp-label-row").children[0] };
}

function near(actual, expected) { assert.ok(Math.abs(actual - expected) < 1e-10, `${actual} is close to ${expected}`); }

test("PDF mode uses the shared readonly overlays at drawing coordinates and 100% zoom", t => {
  const ui = setup(t, {readOnly: true, pdfMode: true});
  assert.ok(ui.byClass("an-grundplan").className.includes("gp-pdf"));
  const sheet = ui.byClass("gp-sheet");
  assert.equal(sheet.style.width, "800px"); assert.equal(sheet.style.height, "600px");
  assert.equal(sheet.style.left, "0px"); assert.equal(sheet.style.top, "0px");
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 75 % · bₓ 1 m · t 1 m");
  assert.deepEqual(ui.position(), [.3, .4]);
  assert.equal(ui.sent.length, 0);
});
const inputSection = (ui, label) => ui.find(e => e.tag === "summary" && e.textContent === label && e.closest(".gp-form")).parent;

function measurePoint(ui, x, y) {
  const rect = ui.byClass("gp-picture").getBoundingClientRect();
  ui.place(rect.left + x * rect.width, rect.top + y * rect.height);
}

function saveReference(ui, text = "10,0") {
  const field = ui.find(e => e.getAttribute("aria-label") === "Känt referensmått i meter");
  field.value = text; field.dispatch("input");
  ui.byText("Spara kalibrering").click();
  if (ui.sent.length) {
    const request = ui.sent.at(-1);
    ui.data.state.calibration = request.calibration; ui.changed(); ui.ack(request);
  }
}

test("calibrated lengths use the drawing aspect ratio and survive render resolution changes", () => {
  const bg = {url: "data:test", width: 800, height: 600};
  const calibration = validateCalibration({start: {x: .1, y: .2}, end: {x: .6, y: .2}, length_m: 10}, bg);
  near(measuredDistance({x: .1, y: .1}, {x: .4, y: .5}, bg, calibration), Math.hypot(240, 240) / 40);
  near(measuredDistance({x: .1, y: .1}, {x: .4, y: .5}, {...bg, width: 1600, height: 1200}, calibration), Math.hypot(240, 240) / 40);
  for (const length of [0, -1, NaN, Infinity, "10", true]) {
    assert.throws(() => validateCalibration({...calibration, length_m: length}, bg));
  }
  assert.throws(() => validateCalibration({...calibration, end: calibration.start}, bg));
  assert.throws(() => validateCalibration({...calibration, end: {x: 2, y: .2}}, bg));
});

test("measurement calibrates from two clicks, accepts decimal comma and displays exactly one decimal", t => {
  const ui = setup(t), original = structuredClone(ui.tag);
  ui.byText("Mät").click();
  assert.equal(ui.byClass("gp-measurement-bar").hidden, false);
  assert.match(ui.byClass("gp-measurement-hint").textContent, /startpunkten/);
  measurePoint(ui, .1, .2); measurePoint(ui, .6, .2);
  assert.equal(ui.byClass("gp-calibration-fields").hidden, false);
  saveReference(ui);
  assert.deepEqual(ui.data.state.calibration, {start: {x: .1, y: .2}, end: {x: .6, y: .2}, length_m: 10});
  assert.equal(ui.sent.at(-1).action, "calibration");
  measurePoint(ui, .1, .2); measurePoint(ui, .35, .2);
  assert.equal(ui.byClass("gp-measurement-value").textContent, "5,0 m");
  const line = ui.byClass("gp-measurement-overlay").children[0].children.find(e => e.tag === "line");
  assert.equal(line.getAttribute("stroke-dasharray"), "none");
  measurePoint(ui, .1, .2);
  assert.equal(ui.byClass("gp-measurement-value").textContent, "", "Third click starts a new measurement");
  measurePoint(ui, .4, .5);
  assert.equal(ui.byClass("gp-measurement-value").textContent, "7,5 m");
  assert.deepEqual(ui.tag, original);
  assert.equal(ui.sent.length, 1, "Measurement does not send engineering updates");
});

test("measurement supports preview, zoom and both pan buttons without moving tags or adding false points", t => {
  const ui = setup(t);
  ui.data.state.calibration = {start: {x: .1, y: .2}, end: {x: .6, y: .2}, length_m: 10}; ui.changed();
  ui.byText("Mät").click(); measurePoint(ui, .1, .2);
  let rect = ui.byClass("gp-picture").getBoundingClientRect();
  ui.move(rect.left + .35 * rect.width, rect.top + .2 * rect.height);
  assert.equal(ui.byClass("gp-measurement-value").textContent, "5,0 m");
  for (const button of [0, 2]) {
    ui.start(ui.marker(), 200, 200, {button}); ui.move(240, 220); ui.finish(240, 220, {button});
    assert.match(ui.byClass("gp-measurement-hint").textContent, /slutpunkten/);
  }
  ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: -100, clientX: 400, clientY: 300});
  measurePoint(ui, .35, .2);
  assert.equal(ui.byClass("gp-measurement-value").textContent, "5,0 m");
  ui.byText("Anpassa").click();
  assert.equal(ui.byClass("gp-measurement-value").textContent, "5,0 m");
  assert.deepEqual(ui.position(), [.3, .4]);
  assert.equal(ui.sent.length, 0);
  ui.byText("Rensa mått").click();
  assert.equal(ui.byClass("gp-measurement-overlay").hidden, true);
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  assert.equal(ui.byClass("gp-measurement-bar").hidden, true);
  ui.byText("Mät").click();
  assert.match(ui.byClass("gp-measurement-hint").textContent, /^Mätning:/, "Escape retains calibration");
});

test("invalid reference, coincident points and failed calibration do not discard the old reference", t => {
  const ui = setup(t);
  const old = {start: {x: .1, y: .2}, end: {x: .6, y: .2}, length_m: 10};
  ui.data.state.calibration = old; ui.changed(); ui.byText("Mät").click(); ui.byText("Kalibrera om").click();
  ui.place(-100, -100);
  assert.equal(ui.byClass("gp-measurement-overlay").hidden, true);
  measurePoint(ui, .2, .3); measurePoint(ui, .2, .3);
  assert.equal(ui.byClass("gp-calibration-fields").hidden, true);
  measurePoint(ui, .5, .3);
  const field = ui.find(e => e.getAttribute("aria-label") === "Känt referensmått i meter");
  for (const text of ["", "0", "-10", "abc", "Infinity"]) {
    field.value = text; field.dispatch("input");
    assert.equal(ui.byText("Spara kalibrering").disabled, true);
  }
  field.value = "12"; field.dispatch("input"); ui.byText("Spara kalibrering").click();
  ui.ack(ui.sent.at(-1), {ok: false, error: "Kalibreringen kunde inte sparas"});
  assert.equal(ui.byClass("gp-status").textContent, "Kalibreringen kunde inte sparas");
  assert.deepEqual(ui.data.state.calibration, old);
  assert.equal(ui.byText("Spara kalibrering").disabled, false);
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  ui.marker().click();
  assert.equal(ui.byClass("gp-dialog").hidden, false, "Leaving measurement restores tag editing");
});

test("standalone calibration changes only local display state, with all footing values still read-only", t => {
  const ui = setup(t, {readOnly: true, standalone: true}), original = structuredClone(ui.snapshot);
  ui.byText("Mät").click(); measurePoint(ui, .1, .2); measurePoint(ui, .6, .2); saveReference(ui);
  assert.equal(ui.model.get("state").calibration.length_m, 10);
  measurePoint(ui, .1, .2); measurePoint(ui, .35, .2);
  assert.equal(ui.byClass("gp-measurement-value").textContent, "5,0 m");
  assert.deepEqual(ui.snapshot, original, "HTML file and embedded engineering snapshot remain unchanged");
});

test("standalone HTML downloads its embedded PDF without a kernel or external resources", async t => {
  const bytes = Buffer.from([37, 80, 68, 70, 45, 10, 0, 128, 255]);
  const ui = setup(t, {readOnly: true, standalone: true, pdf: {filename: "ritning_med_etiketter.pdf", data: bytes.toString("base64")}});
  const original = structuredClone(ui.snapshot), downloads = [];
  t.mock.method(URL, "createObjectURL", blob => { downloads.push(blob); return "blob:offline-pdf"; });
  t.mock.method(URL, "revokeObjectURL", () => {});
  t.mock.method(globalThis, "setTimeout", fn => {fn(); return 0;});
  for (let i = 0; i < 2; i++) ui.byText("Exportera PDF").click();
  assert.equal(downloads.length, 2);
  assert.equal(downloads[0].type, "application/pdf");
  assert.deepEqual(Buffer.from(await downloads[0].arrayBuffer()), bytes);
  assert.equal(document.downloads[0].filename, "ritning_med_etiketter.pdf");
  assert.equal(ui.byText("Exportera PDF").disabled, false);
  assert.deepEqual(ui.snapshot, original);
  ui.snapshot.pdf.data = "%%%";
  ui.byText("Exportera PDF").click();
  assert.equal(downloads.length, 2, "Invalid embedded data reports an error instead of a broken download");
  assert.match(ui.byClass("gp-status").textContent, /PDF-filen kunde inte läsas/);
  assert.equal(ui.byText("Exportera PDF").disabled, false);
});

function importFixture(ui) {
  const items = [
    {label: "W1", kind: "vaggsula", values: {F_vy: 80, F_vy_bruk: 25, V_Ed_EQU: 30, glid_L: 6.2}},
    {label: "P1", kind: "pelarsula", values: {F_vy: 120, F_vy_bruk: 50, V_Ed_EQU: 60}},
  ];
  const queue = {token: "import-test", filename: "loads.json", total: 2, index: 0, paused: false, next: items[0]};
  ui.data.state.load_import = queue; ui.changed();
  return {queue, items, added: (index, request) => {
    const item = items[index];
    ui.data.state.tags.push({...structuredClone(ui.tag), id: item.label, label: item.label,
      x: request.x, y: request.y, page: request.page, status: "new", summary: null,
      values: {...ui.tag.values, ...item.values, lang: item.kind === "vaggsula" ? 1 : 0}});
    ui.data.state.load_import = index === 0 ? {...queue, index: 1, next: items[1]} : null;
    ui.changed(); ui.ack(request, {id: item.label, finished: index === 1, total: 2});
  }};
}

test("drawing update keeps selection, unfinished input text, dialog sections and tag positions", async t => {
  const ui = setup(t);
  ui.marker().click(); ui.field("b").value = "0,"; ui.field("b").dispatch("input");
  const section = ui.byClass("gp-group"); section.open = false; section.dispatch("toggle");
  ui.byText("Minimera").click(); ui.marker().dispatch("click", {shiftKey: true});
  const button = ui.byText("Importera/Uppdatera ritning"), original = structuredClone(ui.tag), point = ui.position();
  assert.equal(button.disabled, false, "Existing footings allow replacing the drawing");
  const input = ui.find(e => e.getAttribute("aria-label") === "Ritningsfil"), buffer = new ArrayBuffer(4);
  input.files = [{name: "revision_b.png", size: 4, arrayBuffer: async () => buffer}];
  await input.listeners.get("change")[0]();
  const request = ui.sent.at(-1);
  assert.equal(request.action, "drawing");
  assert.equal(button.disabled, true);
  assert.equal(ui.transfers.at(-1).buffers[0], buffer);
  ui.data.background = {...ui.data.background, url: "data:revision-b", width: 1200, height: 500};
  ui.changed(); ui.ack(request, {updated: true, page: 1});
  assert.equal(button.disabled, false);
  assert.deepEqual(ui.tag, original);
  assert.deepEqual(ui.position(), point);
  assert.equal(ui.marker().getAttribute("aria-pressed"), "true");
  ui.marker().click();
  assert.equal(ui.field("b").value, "0,");
  assert.equal(ui.byClass("gp-group").open, false);
  assert.match(ui.byClass("gp-status").textContent, /uppdaterad/);
});

test("failed drawing update leaves draft and selection editable and allows another file", async t => {
  const ui = setup(t);
  ui.marker().click(); ui.field("b").value = "0,"; ui.field("b").dispatch("input");
  const input = ui.find(e => e.getAttribute("aria-label") === "Ritningsfil");
  input.files = [{name: "bad.png", size: 4, arrayBuffer: async () => new ArrayBuffer(4)}];
  await input.listeners.get("change")[0]();
  ui.ack(ui.sent.at(-1), {ok: false, error: "Ogiltig ritning"});
  assert.equal(ui.byText("Importera/Uppdatera ritning").disabled, false);
  assert.equal(ui.field("b").value, "0,");
  assert.equal(ui.byClass("gp-status").textContent, "Ogiltig ritning");
  assert.equal(ui.byClass("gp-dialog").hidden, false);
});

test("load import uploads JSON bytes without replacing existing footing drafts", async t => {
  const ui = setup(t);
  ui.marker().click(); ui.field("b").value = "0,8"; ui.field("b").dispatch("input");
  const input = ui.find(e => e.getAttribute("aria-label") === "Lasteffektfil");
  const buffer = new TextEncoder().encode('{"schemaVersion":1}').buffer;
  input.files = [{name: "loads.json", size: buffer.byteLength, arrayBuffer: async () => buffer}];
  await input.listeners.get("change")[0]();
  const request = ui.sent.at(-1);
  assert.equal(request.action, "import_loads");
  assert.equal(ui.byClass("gp-dialog").hidden, true, "Older dialog loads cannot be submitted during import");
  assert.equal(ui.transfers.at(-1).buffers[0], buffer);
  importFixture(ui); ui.ack(request);
  ui.byText("Placera W1 – väggsula (1 av 2)");
  assert.equal(ui.data.state.tags.length, 1, "Import does not create unplaced objects");
  assert.equal(ui.byText("Importera/Uppdatera lasteffekt").disabled, true);
  ui.byText("Pausa placering").click();
  ui.data.state.load_import.paused = true; ui.changed(); ui.ack(ui.sent.at(-1));
  ui.marker().click();
  assert.equal(ui.field("b").value, "0,8", "Imported queue does not erase an existing draft");
});

test("placement advances once per acknowledged click, shows types and creates no dialog", t => {
  const ui = setup(t), imported = importFixture(ui);
  assert.equal(ui.byClass("gp-import-bar").hidden, false);
  ui.byText("Brott V 80 kN/m · Bruk V 25 kN/m · EQU V 30 kN/m · Lvägg 6,2 m");
  ui.place();
  const first = ui.sent.at(-1);
  assert.equal(first.action, "place_import");
  assert.equal(first.token, "import-test"); assert.equal(first.index, 0); assert.equal(first.page, 1);
  assert.equal(first.values, undefined, "Only the kernel owns the queue's loads");
  const before = ui.sent.length; ui.place(500, 400);
  assert.equal(ui.sent.length, before, "Fast second clicks cannot place the same support twice");
  imported.added(0, first);
  ui.byText("Placera P1 – pelarsula (2 av 2)");
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  ui.place(500, 400); imported.added(1, ui.sent.at(-1));
  assert.equal(ui.byClass("gp-import-bar").hidden, true);
  assert.equal(ui.byText("Importera/Uppdatera lasteffekt").disabled, false);
  assert.equal(ui.byClass("gp-status").textContent, "Alla 2 importerade sulor är placerade. Anpassa övriga indata; resultaten uppdateras automatiskt.");
  const after = ui.sent.length; ui.place(); assert.equal(ui.sent.length, after, "Finished queue returns to panning");
});

test("failed placement, panning and outside clicks do not discard or advance the queue", t => {
  const ui = setup(t); importFixture(ui);
  const sheet = ui.byClass("gp-sheet"), left = parseFloat(sheet.style.left), top = parseFloat(sheet.style.top);
  ui.start(ui.byClass("gp-picture"), 300, 300); ui.move(500, 500); ui.finish(500, 500);
  near(parseFloat(sheet.style.left), left + 200); near(parseFloat(sheet.style.top), top + 200);
  assert.equal(ui.sent.length, 0, "Dragging the background pans instead of placing");
  assert.equal(ui.data.state.load_import.index, 0);
  ui.place(-100, -100); assert.equal(ui.sent.length, 0);
  ui.place(); const request = ui.sent.at(-1);
  ui.ack(request, {ok: false, error: "Littera finns redan"});
  assert.equal(ui.data.state.load_import.index, 0);
  assert.equal(ui.byClass("gp-status").textContent, "Littera finns redan");
  assert.equal(ui.byText("Pausa placering").disabled, false);
  ui.place(); assert.equal(ui.sent.at(-1).index, 0, "Failed support remains available for retry");
});

test("drawing can pan while placement is awaiting the kernel and pending clicks cannot place another support", t => {
  const ui = setup(t), imported = importFixture(ui);
  ui.place(); const request = ui.sent.at(-1), count = ui.sent.length;
  const sheet = ui.byClass("gp-sheet"), left = parseFloat(sheet.style.left), top = parseFloat(sheet.style.top);
  ui.start(ui.byClass("gp-picture"), 450, 450, {button: 2}); ui.move(490, 500);
  near(parseFloat(sheet.style.left), left + 40); near(parseFloat(sheet.style.top), top + 50);
  imported.added(0, request); ui.finish(490, 500, {button: 2});
  assert.equal(ui.sent.length, count);
  assert.equal(ui.data.state.load_import.index, 1, "Pan never consumes the next support");
  ui.place(600, 450); const second = ui.sent.at(-1);
  ui.start(ui.byClass("gp-picture"), 450, 450);
  ui.ack(second, {ok: false, error: "Försök igen"}); ui.finish(450, 450);
  assert.equal(ui.sent.length, count + 1, "Gesture begun during a pending request is not a new placement");
});

test("pause, resume and Escape preserve the pending support on the chosen page", t => {
  const ui = setup(t), imported = importFixture(ui);
  ui.byText("Pausa placering").click();
  const pause = ui.sent.at(-1);
  assert.equal(pause.operation, "pause");
  imported.queue.paused = true; ui.changed(); ui.ack(pause);
  ui.byText("Placering pausad · Placera W1 – väggsula (1 av 2)");
  const before = ui.sent.length; ui.place(); assert.equal(ui.sent.length, before);
  ui.byText("Fortsätt placera").click();
  const resume = ui.sent.at(-1); imported.queue.paused = false; ui.changed(); ui.ack(resume);
  ui.place(); const placed = ui.sent.at(-1); assert.equal(placed.page, 1); assert.equal(placed.index, 0);
  ui.ack(placed, {ok: false, error: "Test"});
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  assert.equal(ui.sent.at(-1).operation, "pause");
  assert.equal(ui.data.state.load_import.next.label, "W1");
});

test("cancelling import leaves placed tags, and other tools pause instead of losing the queue", t => {
  const ui = setup(t), imported = importFixture(ui);
  ui.place(); imported.added(0, ui.sent.at(-1));
  ui.byText("+ Pelarsula").click();
  assert.equal(ui.sent.at(-1).operation, "pause");
  ui.data.state.load_import.paused = true; ui.changed(); ui.ack(ui.sent.at(-1));
  ui.byText("Avbryt import").click();
  const cancel = ui.sent.at(-1); assert.equal(cancel.operation, "cancel");
  ui.data.state.load_import = null; ui.changed(); ui.ack(cancel);
  assert.equal(ui.data.state.tags.length, 2);
  assert.equal(ui.byClass("gp-import-bar").hidden, true);
});

test("imported footing inputs remain editable including unused Bruk and EQU loads", t => {
  const ui = setup(t), original = structuredClone(ui.tag), imported = importFixture(ui);
  ui.place(); imported.added(0, ui.sent.at(-1));
  ui.place(500, 400); imported.added(1, ui.sent.at(-1));
  ui.data.state.sliding = {enabled: true, check_x: false, check_y: false}; ui.changed();
  const wall = ui.data.state.tags.find(tag => tag.id === "W1");
  const pad = structuredClone(ui.data.state.tags.find(tag => tag.id === "P1"));
  const marker = () => ui.find(e => e.dataset.tagId === "W1");
  marker().click();
  for (const [name, text, value] of [["F_vy", "150", 150], ["F_vy_bruk", "60", 60],
      ["V_Ed_EQU", "70", 70], ["glid_L", "7,5", 7.5], ["b", "0,9", .9]]) {
    const field = ui.field(name);
    assert.equal(field.disabled, false, name + " is editable");
    assert.equal(field.parent.hidden, false, name + " is visible");
    field.value = text; field.dispatch("input");
    const request = ui.sent.at(-1);
    assert.equal(request.action, "update"); assert.equal(request.id, "W1"); assert.equal(request.values[name], value);
    Object.assign(wall.values, request.values); wall.status = "stale";
    ui.changed(); ui.ack(request);
  }
  assert.deepEqual(ui.tag, original);
  assert.deepEqual(ui.data.state.tags.find(tag => tag.id === "P1"), pad);
  ui.byText("Minimera").click(); marker().click();
  assert.equal(ui.field("glid_L").value, "7,5");
  assert.equal(ui.field("V_Ed_EQU").value, "70");
  assert.equal(ui.field("F_vy_bruk").value, "60");
  assert.equal(wall.values.glid_x, false); assert.equal(wall.values.isolering, false);
});

test("update-only import replaces old load drafts, preserves geometry drafts and remains repeatable", async t => {
  const ui = setup(t);
  ui.data.state.sliding = {enabled: true}; ui.changed(); ui.marker().click();
  for (const [name, text] of [["F_vy", "99"], ["F_vy_bruk", "40"], ["V_Ed_EQU", "50"], ["glid_L", "3"], ["b", "0,8"]]) {
    ui.field(name).value = text; ui.field(name).dispatch("input");
    Object.assign(ui.tag.values, ui.sent.at(-1).values); ui.ack(ui.sent.at(-1));
  }
  const beforePosition = [ui.tag.id, ui.tag.x, ui.tag.y, ui.tag.page];
  const input = ui.find(e => e.getAttribute("aria-label") === "Lasteffektfil");
  const buffer = new TextEncoder().encode('{"schemaVersion":1}').buffer;
  input.files = [{name: "updated.json", size: buffer.byteLength, arrayBuffer: async () => buffer}];
  await input.listeners.get("change")[0]();
  const request = ui.sent.at(-1);
  Object.assign(ui.tag.values, {F_vy: 160, F_vy_bruk: 0, V_Ed_EQU: 70, glid_L: 7.5});
  ui.tag.status = "stale"; ui.tag.summary = null; ui.changed();
  ui.ack(request, {report: {updated: 1, new: 0, updated_ids: [ui.tag.id]}});
  assert.equal(ui.byClass("gp-import-bar").hidden, true);
  assert.equal(ui.byClass("gp-status").textContent, "1 befintliga sulor uppdaterade. Inga nya sulor att placera.");
  assert.equal(ui.byText("Importera/Uppdatera lasteffekt").disabled, false);
  ui.marker().click();
  for (const [name, text] of [["F_vy", "160"], ["F_vy_bruk", "0"], ["V_Ed_EQU", "70"], ["glid_L", "7,5"], ["b", "0,8"]]) {
    assert.equal(ui.field(name).value, text, name + " reflects the import and preserves unrelated drafts");
    assert.equal(ui.field(name).disabled, false);
  }
  assert.deepEqual([ui.tag.id, ui.tag.x, ui.tag.y, ui.tag.page], beforePosition);
  ui.field("F_vy").value = "170"; ui.field("F_vy").dispatch("input");
  assert.equal(ui.sent.at(-1).values.F_vy, 170, "Imported loads remain editable");
  const count = ui.sent.length; ui.place(700, 500);
  assert.equal(ui.sent.length, count, "An update-only import returns to panning");
});

test("mixed import reports updated footings and places only its new queue", async t => {
  const ui = setup(t), input = ui.find(e => e.getAttribute("aria-label") === "Lasteffektfil");
  const buffer = new TextEncoder().encode('{}').buffer;
  input.files = [{name: "mixed.json", size: buffer.byteLength, arrayBuffer: async () => buffer}];
  await input.listeners.get("change")[0]();
  const request = ui.sent.at(-1), imported = importFixture(ui);
  ui.tag.values.F_vy = 250; ui.changed();
  ui.ack(request, {report: {updated: 1, new: 2, updated_ids: [ui.tag.id]}});
  assert.equal(ui.byClass("gp-status").textContent, "1 befintliga sulor uppdaterade. 2 nya sulor att placera. Placera W1 – väggsula (1 av 2)");
  assert.equal(ui.data.state.tags.length, 1);
  ui.place(); imported.added(0, ui.sent.at(-1));
  assert.equal(ui.data.state.tags.length, 2);
  assert.equal(ui.tag.values.F_vy, 250);
  ui.byText("Placera P1 – pelarsula (2 av 2)");
});

test("failed import preserves existing drafts and allows retry", async t => {
  const ui = setup(t); ui.marker().click();
  ui.field("F_vy").value = "99"; ui.field("F_vy").dispatch("input");
  const input = ui.find(e => e.getAttribute("aria-label") === "Lasteffektfil");
  input.files = [{name: "bad.json", size: 2, arrayBuffer: async () => new ArrayBuffer(2)}];
  await input.listeners.get("change")[0]();
  ui.ack(ui.sent.at(-1), {ok: false, error: "Littera matchar flera sulor"});
  assert.equal(ui.field("F_vy").value, "99");
  assert.equal(ui.byClass("gp-status").textContent, "Littera matchar flera sulor");
  assert.equal(ui.byText("Importera/Uppdatera lasteffekt").disabled, false);
});

test("delete all requires confirmation and cancellation keeps selection and inputs", t => {
  const ui = setup(t); ui.start(ui.marker(), 300, 300, {shiftKey: true}); ui.finish(300, 300);
  const before = structuredClone(ui.data.state), count = ui.sent.length;
  let prompt;
  window.confirm = text => {prompt = text; return false;};
  ui.byText("Radera samtliga sulor").click();
  assert.match(prompt, /samtliga 1 sulor\?/);
  assert.deepEqual(ui.data.state, before); assert.equal(ui.sent.length, count);
  assert.deepEqual(selectedIds(ui), ["tag1"]);
});

test("delete all clears footings, drafts and placement and blocks repeat requests while pending", t => {
  const ui = setup(t); ui.marker().click(); ui.field("b").value = "0,9"; ui.field("b").dispatch("input");
  importFixture(ui);
  let prompt;
  window.confirm = text => {prompt = text; return true;};
  ui.byText("Radera samtliga sulor").click();
  const request = ui.sent.at(-1), count = ui.sent.length;
  assert.equal(request.action, "delete_all"); assert.match(prompt, /återstående placeringar avbryts/);
  assert.equal(ui.byText("Radera samtliga sulor").disabled, true);
  assert.equal(ui.byText("Importera/Uppdatera lasteffekt").disabled, true);
  ui.byText("Radera samtliga sulor").click(); ui.place();
  assert.equal(ui.sent.length, count);
  const bg = structuredClone(ui.data.background);
  ui.data.state.tags = []; ui.data.state.load_import = null; ui.changed(); ui.ack(request, {deleted: 1});
  assert.deepEqual(ui.data.background, bg); assert.deepEqual(selectedIds(ui), []);
  assert.equal(ui.byClass("gp-dialog").hidden, true); assert.equal(ui.byClass("gp-bulk-dialog").hidden, true);
  assert.equal(ui.byClass("gp-import-bar").hidden, true);
  assert.equal(ui.byText("Radera samtliga sulor").disabled, true);
  assert.equal(ui.byText("Importera/Uppdatera lasteffekt").disabled, false);
  assert.equal(ui.byClass("gp-status").textContent, "Samtliga 1 sulor har raderats.");
  const n = ui.sent.length; ui.place(); assert.equal(ui.sent.length, n, "No old import/copy gesture survives deletion");
  ui.data.state.tags = [ui.tag]; ui.changed(); ui.marker().click();
  assert.equal(ui.field("b").value, "1", "Deleted drafts cannot leak into another footing");
});

test("delete-all failure leaves the drawing and footing editable", t => {
  const ui = setup(t), before = structuredClone(ui.data.state);
  ui.byText("Radera samtliga sulor").click();
  ui.ack(ui.sent.at(-1), {ok: false, error: "Kunde inte radera"});
  assert.deepEqual(ui.data.state, before);
  assert.equal(ui.byText("Radera samtliga sulor").disabled, false);
  assert.equal(ui.byClass("gp-status").textContent, "Kunde inte radera");
  ui.marker().click(); assert.equal(ui.byClass("gp-dialog").hidden, false);
});

test("result HTML exposes neither load import nor delete-all controls", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  assert.ok(!ui.elements().some(e => ["Radera samtliga sulor", "Importera/Uppdatera lasteffekt"].includes(e.textContent)));
});

function slidingFixture(ui, enabled = true) {
  Object.assign(ui.tag.values, {glid_x: true, glid_y: true, V_Ed_EQU: 120, glid_mu: .4, glid_L: 3});
  ui.tag.sliding = {x: 144, y: 144, status: "ready"};
  ui.data.state.sliding = {enabled, check_x: true, check_y: true, H_x_Ed: 100, H_y_Ed: 180, placements: {}};
  ui.data.state.sliding_result = {
    x: {H_Ed: 100, H_Rd: 144, count: 1, contributors: [{label: "VS1"}], missing: [], status: "ok", utilization: 100 / 144},
    y: {H_Ed: 180, H_Rd: 144, count: 1, contributors: [{label: "VS1"}], missing: [], status: "over", utilization: 1.25},
  };
  Object.assign(ui.model.get("state"), {sliding: ui.data.state.sliding, sliding_result: ui.data.state.sliding_result});
  if (ui.model.get("state").tags[0] !== ui.tag) Object.assign(ui.model.get("state").tags[0], ui.tag);
  ui.changed();
}

function bulkFixture(ui, pad = false) {
  const second = structuredClone(ui.tag);
  Object.assign(second, {id: "tag2", label: pad ? "PS2" : "VS2", x: .6, y: .6});
  Object.assign(second.values, {lang: pad ? 0 : 1, b: 2, l: 3, F_vy: 200});
  ui.data.state.tags.push(second); ui.changed();
  const marker = id => ui.find(e => e.dataset.tagId === id);
  const field = name => ui.find(e => e.name === "bulk_" + name);
  const choose = name => ui.find(e => e.getAttribute("aria-label") === "Ändra " + name);
  const select = () => {
    ui.byText("Minimera").click();
    marker("tag1").dispatch("click", {shiftKey: true}); marker("tag2").dispatch("click", {shiftKey: true});
    ui.byText("Ändra markerade").click();
  };
  return {second, marker, field, choose, select};
}

function marquee(ui, from, to, options = {}) {
  ui.start(ui.byClass("gp-picture"), ...from, {shiftKey: true, ...options});
  ui.move(...to);
  ui.finish(...to);
}

const selectedIds = ui => ui.elements().filter(e => e.dataset.tagId && e.className.includes("gp-multi-selected"))
  .map(e => e.dataset.tagId).sort();

const tableField = (ui, id, name) => ui.find(e => e.name === "table_" + name && e.dataset.tagId === id);
const tableOrder = ui => ui.byClass("gp-input-table").children[1].children.map(row => row.dataset.tagId);
const tableSortButton = (ui, key) => ui.find(e => e.getAttribute("aria-label") ===
  "Sortera efter " + (key === "label" ? "littera" : key === "status" ? "status och utnyttjandegrad" : key));
const selectTableRow = (ui, label, checked = true, options = {}) => {
  const control = ui.find(e => e.getAttribute("aria-label") === "Markera " + label + " i tabellen");
  control.checked = checked; control.dispatch("click", options); control.dispatch("change"); return control;
};

test("table contains every input without page information or navigation, with type-dependent fields and result status", t => {
  const ui = setup(t), second = {...structuredClone(ui.tag), id: "tag2", label: "PS2"};
  ui.data.background.page_count = 2;
  second.values.lang = 0; second.status = "new"; second.summary = null;
  ui.data.state.tags.push(second); ui.changed();
  assert.equal(ui.elements().filter(e => e.tag === "tr" && e.dataset.tagId).length, 2);
  assert.equal(ui.elements().some(e => e.className.includes("gp-table-page") || e.className.includes("gp-page-label") || e.getAttribute("aria-label") === "PDF-sida"), false);
  assert.equal(ui.elements().some(e => e.tag === "th" && e.textContent === "Sida"), false);
  for (const tag of ui.data.state.tags) {
    for (const name of names) assert.ok(tableField(ui, tag.id, name));
    assert.ok(tableField(ui, tag.id, "label"));
  }
  assert.equal(tableField(ui, "tag1", "l").disabled, true);
  assert.equal(tableField(ui, "tag2", "l").disabled, false);
  assert.equal(tableField(ui, "tag2", "glid_L").disabled, true);
  assert.equal(tableField(ui, "tag1", "V_Ed_EQU").disabled, false, "Gliding can be preconfigured before enabling the global check");
  ui.byText("2 sulor"); ui.byText("U 75%");
  assert.equal(ui.elements().some(e => e.tag === "button" && /beräkna/i.test(e.textContent)), false);
});

for (const readOnly of [false, true]) test(`soil and coefficients share one input and table category (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly}), original = structuredClone(ui.tag);
  ui.marker().click();
  const label = "Jord - Allm. Bärighets.", section = inputSection(ui, label);
  const fields = ["c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "d", "delta_h", "beta", "alpha", "eta", "gamma_m", "gamma_m0", "gamma_Rd"];
  for (const name of fields) {
    const caption = ui.find(e => e.className === "gp-field-caption" && e.textContent === name);
    assert.equal(caption.closest("details"), section);
    assert.ok(ui.elements().some(e => e.tag === "th" && e.getAttribute("aria-label") === label + ": " + name));
  }
  const header = ui.find(e => e.className === "gp-table-group" && e.children[0]?.textContent === "▾ " + label);
  assert.equal(header.getAttribute("colspan"), "13");
  assert.equal(ui.elements().some(e => ["Jord och grundvatten", "Koefficienter"].includes(e.textContent)), false);
  assert.deepEqual(ui.tag, original);
  if (!readOnly) {
    const bulk = bulkFixture(ui); bulk.select();
    assert.equal(bulk.field("phi_k").closest("details"), bulk.field("gamma_m").closest("details"));
    assert.equal(bulk.field("phi_k").closest("details").children[0].textContent, label);
  }
});

test("wall by is editable in table and dialog and can be overridden for selected walls", t => {
  const ui = setup(t);
  const length = tableField(ui, ui.tag.id, "l");
  assert.equal(length.value, "1"); assert.equal(length.disabled, true);
  assert.match(length.title, /Aktivera Egen längd/);
  ui.marker().click();
  assert.equal(ui.field("l").parent.parent.hidden, false);
  assert.equal(ui.field("l").disabled, true);
  assert.equal(ui.field("l_override").parent.className, "gp-length-override");
  const second = {...structuredClone(ui.tag), id: "tag2", label: "VS2"};
  ui.data.state.tags.push(second); ui.changed();
  selectTableRow(ui, "VS1"); selectTableRow(ui, "VS2");
  const ownLength = tableField(ui, ui.tag.id, "l_override");
  ownLength.checked = true; ownLength.dispatch("change");
  assert.deepEqual(ui.sent.at(-1).values, {l_override: true});
  ui.tag.values.l_override = second.values.l_override = true; ui.changed(); ui.ack(ui.sent.at(-1));
  assert.equal(length.disabled, false);
  length.value = "2,4"; length.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"]);
  assert.deepEqual(ui.sent.at(-1).values, {l: 2.4});
  ui.tag.values.l = second.values.l = 2.4; ui.changed(); ui.ack(ui.sent.at(-1));
  assert.equal(length.value, "2,4"); assert.equal(length.disabled, false);
  assert.match(ui.byClass("gp-tag-result").textContent, /bₓ 1 m · bᵧ 2,4 m · t 1 m/);
  assert.match(ui.marker().getAttribute("aria-label"), /bₓ × bᵧ/);
  ui.byText("Ändra markerade").click();
  assert.ok(ui.find(e => e.name === "bulk_l"), "Bulk dialog also includes wall by");
  const bulkOwn = ui.find(e => e.name === "bulk_l_override");
  bulkOwn.value = "false"; bulkOwn.dispatch("change");
  assert.equal(ui.find(e => e.name === "bulk_l").disabled, true);
  ui.byText("Tillämpa").click();
  assert.deepEqual(ui.sent.at(-1).values, {l_override: false});
});

test("compact dialog checkbox enables wall by and restores one metre when unchecked", t => {
  const ui = setup(t);
  ui.marker().click();
  const own = ui.field("l_override"), length = ui.field("l");
  assert.equal(own.checked, false); assert.equal(length.disabled, true); assert.equal(length.value, "1");
  own.checked = true; own.dispatch("input");
  assert.equal(length.disabled, false);
  length.value = "2,5"; length.dispatch("input");
  assert.equal(ui.sent.at(-1).values.l, 2.5); assert.equal(ui.sent.at(-1).values.l_override, true);
  own.checked = false; own.dispatch("input");
  assert.equal(length.value, "1"); assert.equal(length.disabled, true);
  assert.equal(ui.sent.at(-1).values.l, 1); assert.equal(ui.sent.at(-1).values.l_override, false);
  ui.field("lang").value = "0"; ui.field("lang").dispatch("input");
  assert.equal(length.disabled, false); assert.equal(own.parent.hidden, true);
});

test("bulk wall length requires enabling own length and can be reset for all selected walls", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  bulk.select(); ui.byText("Ändra markerade").click();
  const length = ui.find(e => e.name === "bulk_l"), own = ui.find(e => e.name === "bulk_l_override");
  assert.equal(length.disabled, true);
  own.value = "true"; own.dispatch("change");
  assert.equal(length.disabled, false);
  length.value = "2,4"; length.dispatch("input");
  ui.byText("Tillämpa").click();
  assert.deepEqual(ui.sent.at(-1).values, {l: 2.4, l_override: true});
});

test("table littera sorting is natural, reversible and preserves selected objects and input controls", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  ui.tag.label = "S.10"; bulk.second.label = "S.2";
  const third = {...structuredClone(ui.tag), id: "tag3", label: "S.1"};
  ui.data.state.tags.push(third); ui.changed();
  selectTableRow(ui, "S.10"); selectTableRow(ui, "S.2");
  const control = tableField(ui, "tag1", "b"), original = structuredClone(ui.data.state.tags);
  assert.deepEqual(tableOrder(ui), ["tag1", "tag2", "tag3"]);
  const sort = tableSortButton(ui, "label"); sort.click();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1", "tag3"]);
  assert.equal(sort.parent.getAttribute("aria-sort"), "ascending");
  sort.click();
  assert.deepEqual(tableOrder(ui), ["tag1", "tag2", "tag3"]);
  assert.equal(sort.parent.getAttribute("aria-sort"), "descending");
  assert.deepEqual(ui.data.state.tags, original, "Sorting never changes model order or calculation inputs");
  assert.equal(tableField(ui, "tag1", "b"), control);
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  control.value = "0,8"; control.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"], "Bulk editing still targets object ids after sorting");
});

function selectedSortFixture(ui) {
  const labels = ["S.4", "S.10", "S.2", "S.8", "S.1", "S.3"], widths = [1.4, .8, .8, 1.2, .6, 1.8];
  ui.data.state.tags.splice(0, ui.data.state.tags.length, ...labels.map((label, i) => ({...structuredClone(ui.tag), id: "tag" + (i + 1), label,
    values: {...ui.tag.values, b: widths[i]}})));
  ui.changed();
  tableSortButton(ui, "label").click();
  assert.deepEqual(tableOrder(ui), ["tag5", "tag3", "tag6", "tag1", "tag4", "tag2"]);
}

for (const readOnly of [false, true]) test(`selected rows sort at the top with littera ties and preserve the remaining display order (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly, standalone: readOnly}); selectedSortFixture(ui);
  selectTableRow(ui, "S.10"); selectTableRow(ui, "S.2"); selectTableRow(ui, "S.8");
  const original = structuredClone(ui.data.state.tags);
  const cells = ui.elements().filter(e => e.dataset.field && e.dataset.tagId);
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag4", "tag5", "tag6", "tag1"]);
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag4", "tag3", "tag2", "tag5", "tag6", "tag1"]);
  assert.deepEqual(selectedIds(ui), ["tag2", "tag3", "tag4"]);
  assert.deepEqual(ui.data.state.tags, original, "Sorting keeps model order, inputs, results and coordinates");
  assert.ok(cells.every(cell => ui.elements().includes(cell)), "Sorting reuses the existing cells");
  ui.data.state.tags[4].values.b = 4; ui.data.state.tags[5].values.b = .1; ui.changed();
  assert.deepEqual(tableOrder(ui), ["tag4", "tag3", "tag2", "tag5", "tag6", "tag1"], "Unselected data updates do not reorder the remaining rows");
  ui.data.state.tags.push({...structuredClone(ui.tag), id: "tag7", label: "S.0", values: {...ui.tag.values, b: .2}});
  ui.changed();
  assert.deepEqual(tableOrder(ui), ["tag4", "tag3", "tag2", "tag5", "tag6", "tag1", "tag7"], "New objects join the unchanged rows at the end");
  ui.data.state.tags.splice(ui.data.state.tags.findIndex(tag => tag.id === "tag3"), 1); ui.changed();
  assert.deepEqual(tableOrder(ui), ["tag4", "tag2", "tag5", "tag6", "tag1", "tag7"], "Deleted objects cannot leave stale table rows");
});

for (const readOnly of [false, true]) test(`selection changes wait for a header click before regrouping or returning to global sorting (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly, standalone: readOnly}); selectedSortFixture(ui);
  const order = tableOrder(ui);
  selectTableRow(ui, "S.10"); selectTableRow(ui, "S.8");
  ui.changed(); ui.byClass("gp-table-scroll").dispatch("focusout");
  tableFold(ui, "Laster – Bruk").click();
  assert.deepEqual(tableOrder(ui), order, "Selection and ordinary redraws cannot move rows before sorting");
  tableSortButton(ui, "b").click();
  const sorted = ["tag2", "tag4", "tag5", "tag3", "tag6", "tag1"];
  assert.deepEqual(tableOrder(ui), sorted);
  selectTableRow(ui, "S.10", false); selectTableRow(ui, "S.4");
  ui.changed(); ui.byClass("gp-table-scroll").dispatch("focusout");
  tableFold(ui, "Laster – Brott").click();
  assert.deepEqual(tableOrder(ui), sorted, "A changed selection retains the last displayed order until the next sort click");
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag1", "tag4", "tag2", "tag5", "tag3", "tag6"], "The next click captures the current selection");
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"}); ui.changed();
  assert.deepEqual(selectedIds(ui), []);
  assert.deepEqual(tableOrder(ui), ["tag1", "tag4", "tag2", "tag5", "tag3", "tag6"], "Clearing the selection does not move rows");
  tableSortButton(ui, "label").click();
  assert.deepEqual(tableOrder(ui), order, "A header click without selection sorts the entire table");
});

test("drawing selection scopes table sorting and selected edits retain focus until editing ends", t => {
  const ui = setup(t); selectedSortFixture(ui);
  for (const id of ["tag1", "tag2"]) ui.find(e => e.dataset.tagId === id && e.className.includes("gp-tag"))
    .dispatch("click", {shiftKey: true});
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1", "tag5", "tag3", "tag6", "tag4"]);
  const label = tableField(ui, "tag2", "label"); label.focus(); label.value = "S.20"; label.dispatch("input");
  const request = ui.sent.at(-1);
  ui.data.state.tags[1].label = "S.20"; ui.changed(); ui.ack(request);
  assert.equal(document.activeElement, label); assert.equal(label.value, "S.20");
  const width = tableField(ui, "tag2", "b"); width.focus(); width.value = "1,6"; width.dispatch("input");
  const bulkRequest = ui.sent.at(-1);
  assert.deepEqual(bulkRequest.ids, ["tag1", "tag2"]);
  for (const tag of ui.data.state.tags.slice(0, 2)) tag.values.b = 1.6;
  ui.changed(); ui.ack(bulkRequest, {report: {updated: 2, calculated: 2, errors: []}});
  assert.equal(document.activeElement, width); assert.equal(tableField(ui, "tag2", "b"), width);
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1", "tag5", "tag3", "tag6", "tag4"]);
  document.activeElement = null; ui.byClass("gp-table-scroll").dispatch("focusout");
  assert.deepEqual(tableOrder(ui), ["tag1", "tag2", "tag5", "tag3", "tag6", "tag4"]);
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
});

test("table status sorting uses numeric utilization and prioritizes errors", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  ui.tag.summary.utnyttjandegrad = .09; bulk.second.summary.utnyttjandegrad = 1.2;
  const third = {...structuredClone(ui.tag), id: "tag3", label: "VS3", status: "error", summary: null};
  ui.data.state.tags.push(third); ui.changed();
  const sort = tableSortButton(ui, "status"); sort.click();
  assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag1"]);
  assert.equal(sort.parent.getAttribute("aria-sort"), "descending");
  sort.click();
  assert.deepEqual(tableOrder(ui), ["tag1", "tag2", "tag3"]);
  bulk.second.summary.utnyttjandegrad = .05; ui.changed();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1", "tag3"], "Updated results keep the chosen numeric order");
});

test("sorted table defers row movement while typing and Enter follows the visible order", t => {
  const ui = setup(t); bulkFixture(ui);
  tableSortButton(ui, "label").click();
  const label = tableField(ui, "tag1", "label"); label.focus(); label.value = "VS10"; label.dispatch("input");
  const request = ui.sent.at(-1); ui.tag.label = "VS10"; ui.changed(); ui.ack(request);
  assert.equal(document.activeElement, label); assert.equal(label.value, "VS10");
  assert.deepEqual(tableOrder(ui), ["tag1", "tag2"], "Typing does not detach a focused row");
  document.activeElement = null; ui.byClass("gp-table-scroll").dispatch("focusout");
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1"]);
  const first = tableField(ui, "tag2", "b"), second = tableField(ui, "tag1", "b");
  first.dispatch("keydown", {key: "Enter"}); assert.equal(document.activeElement, second);
  second.dispatch("keydown", {key: "Enter", shiftKey: true}); assert.equal(document.activeElement, first);
});

test("table edits only the chosen field, retains focus and coordinates, and shares drafts with the dialog", t => {
  const ui = setup(t), before = structuredClone(ui.tag);
  const control = tableField(ui, ui.tag.id, "b"); control.focus();
  control.value = "0,9"; control.dispatch("input");
  const request = ui.sent.at(-1);
  assert.equal(request.action, "update"); assert.equal(request.id, ui.tag.id);
  assert.deepEqual(request.values, {b: .9});
  ui.tag.values.b = .9; ui.tag.status = "stale"; ui.tag.summary = null;
  ui.changed(); ui.ack(request);
  assert.equal(tableField(ui, ui.tag.id, "b"), control, "Model updates cannot rebuild the focused cell");
  assert.equal(document.activeElement, control); assert.equal(control.value, "0,9");
  assert.deepEqual([ui.tag.x, ui.tag.y, ui.tag.page], [before.x, before.y, before.page]);
  ui.marker().click(); assert.equal(ui.field("b").value, "0,9");
  ui.field("b").value = "1,1"; ui.field("b").dispatch("input");
  const dialogRequest = ui.sent.at(-1); ui.tag.values.b = 1.1; ui.changed(); ui.ack(dialogRequest);
  assert.equal(control.value, "1,1", "Dialog edits are reflected in the table");
});

test("table supports insulation, comments, labels, signed loads and changing foundation type", t => {
  const ui = setup(t);
  for (const [name, value, expected] of [["F_vy", "-25,5", -25.5], ["F_vy_bruk", "0", 0],
      ["isolerprodukt", "EPS S200", "EPS S200"], ["lang", "0", 0]]) {
    const control = tableField(ui, ui.tag.id, name); control.value = value;
    control.dispatch(name === "lang" ? "change" : "input");
    assert.deepEqual(ui.sent.at(-1).values, {[name]: expected});
    ui.tag.values[name] = expected; ui.changed(); ui.ack(ui.sent.at(-1));
  }
  assert.equal(tableField(ui, ui.tag.id, "l").disabled, false);
  const insulated = tableField(ui, ui.tag.id, "isolering"); insulated.checked = true; insulated.dispatch("change");
  assert.deepEqual(ui.sent.at(-1).values, {isolering: true});
  const label = tableField(ui, ui.tag.id, "label"); label.value = "PS12"; label.dispatch("input");
  assert.equal(ui.sent.at(-1).label, "PS12"); assert.equal(ui.sent.at(-1).values, undefined);
});

test("invalid numeric table text cannot calculate with an old numeric value", t => {
  const ui = setup(t), control = tableField(ui, ui.tag.id, "b");
  control.value = "abc"; control.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).values, {b: null});
  assert.equal(control.validityMessage, "Ange ett tal.");
  control.value = "1,2"; control.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).values, {b: 1.2}); assert.equal(control.validityMessage, "");
});

test("table selection and drawing selection stay synchronized through marquee, checkbox and Escape", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  marquee(ui, [200, 200], [420, 320]);
  const first = ui.find(e => e.getAttribute("aria-label") === "Markera VS1 i tabellen");
  assert.equal(first.checked, true);
  assert.equal(first.parent.parent.className.includes("gp-table-row-selected"), true);
  selectTableRow(ui, "VS2"); assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  const all = ui.find(e => e.getAttribute("aria-label") === "Markera samtliga tabellrader");
  assert.equal(all.checked, true);
  bulk.marker("tag1").dispatch("click", {shiftKey: true});
  assert.equal(first.checked, false); assert.equal(all.indeterminate, true);
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  assert.deepEqual(selectedIds(ui), []); assert.equal(all.checked, false); assert.equal(all.indeterminate, false);
  assert.equal(ui.byClass("gp-table-selection-info").hidden, true);
});

test("Shift-click checkboxes include or exclude a range from the first click and keep other rows", t => {
  const ui = setup(t); bulkFixture(ui);
  for (let n = 3; n <= 5; n++) ui.data.state.tags.push({...structuredClone(ui.tag), id: "tag" + n, label: "VS" + n});
  ui.changed();
  selectTableRow(ui, "VS1"); selectTableRow(ui, "VS4", true, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2", "tag3", "tag4"]);
  selectTableRow(ui, "VS3", false, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag4"], "A checked endpoint removes the interval and preserves rows outside it");
  selectTableRow(ui, "VS5", true, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2", "tag3", "tag4", "tag5"], "Repeated Shift clicks retain the first anchor");
  selectTableRow(ui, "VS2", false); selectTableRow(ui, "VS4", false, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1", "tag5"], "An ordinary click sets a new anchor");
  const cell = tableField(ui, "tag5", "b"); cell.value = "0,8"; cell.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag5"]);
});

test("Shift-click ranges follow sorted rows in both directions and Escape clears the anchor", t => {
  const ui = setup(t); bulkFixture(ui);
  ui.tag.label = "VS10";
  const third = {...structuredClone(ui.tag), id: "tag3", label: "VS3"};
  ui.data.state.tags.push(third); ui.changed(); tableSortButton(ui, "label").click();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag3", "tag1"]);
  selectTableRow(ui, "VS10"); selectTableRow(ui, "VS2", true, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2", "tag3"]);
  selectTableRow(ui, "VS3", false, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag2"], "Reverse ranges use visible order rather than model order");
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  selectTableRow(ui, "VS2", true, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag2"], "Escape prevents the earlier endpoint from selecting an old range");
});

test("selected table rows edit directly without a popup, preserving other values and keyboard focus", t => {
  const ui = setup(t); bulkFixture(ui);
  const beforeLoads = ui.data.state.tags.map(tag => tag.values.F_vy);
  selectTableRow(ui, "VS1"); selectTableRow(ui, "VS2");
  const control = tableField(ui, "tag1", "b"); control.focus();
  control.value = "0,8"; control.dispatch("input"); const request = ui.sent.at(-1);
  assert.equal(request.action, "bulk_update");
  assert.deepEqual(request.ids, ["tag1", "tag2"]); assert.deepEqual(request.values, {b: .8});
  assert.equal(ui.byClass("gp-bulk-dialog").hidden, true);
  assert.equal(tableField(ui, "tag2", "b").value, "0,8");
  assert.equal(document.activeElement, control);
  for (const tag of ui.data.state.tags) {tag.values.b = .8; tag.status = "calculated";}
  ui.changed(); ui.ack(request, {report: {updated: 2, calculated: 2, errors: []}});
  assert.equal(tableField(ui, "tag1", "b"), control);
  assert.ok(!ui.marker().className.includes("gp-tag-stale"), "The automatically calculated result becomes current on acknowledgment");
  assert.deepEqual(ui.data.state.tags.map(tag => tag.values.F_vy), beforeLoads);
});

test("select-all table rows survives ordinary state updates", t => {
  const ui = setup(t); bulkFixture(ui);
  const all = ui.find(e => e.getAttribute("aria-label") === "Markera samtliga tabellrader");
  all.checked = true; all.dispatch("change"); ui.changed();
  assert.equal(all.checked, true); ui.byText("2 markerade");
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  const control = tableField(ui, "tag1", "b"); control.value = "0,8"; control.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"]);
});

test("mixed table selection blocks load units and length fields but allows geometry and insulation", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  bulk.second.values.lang = 0; ui.changed();
  selectTableRow(ui, "VS1"); selectTableRow(ui, "VS2");
  assert.equal(tableField(ui, "tag1", "F_vy").disabled, true);
  assert.equal(tableField(ui, "tag2", "l").disabled, true);
  assert.equal(tableField(ui, "tag1", "b").disabled, false);
  const insulation = tableField(ui, "tag1", "isolering");
  insulation.checked = true; insulation.dispatch("change");
  assert.deepEqual(ui.sent.at(-1).values, {isolering: true});
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"]);
  selectTableRow(ui, "VS1", false);
  assert.equal(tableField(ui, "tag2", "F_vy").disabled, false);
  assert.equal(tableField(ui, "tag2", "l").disabled, false);
});

test("table changes on unselected rows, labels and foundation type remain individual", t => {
  const ui = setup(t); bulkFixture(ui); selectTableRow(ui, "VS1");
  let cell = tableField(ui, "tag2", "b"); cell.value = "1,2"; cell.dispatch("input");
  assert.equal(ui.sent.at(-1).action, "update"); assert.equal(ui.sent.at(-1).id, "tag2");
  selectTableRow(ui, "VS2");
  for (const [name, value, event] of [["label", "VS3", "input"], ["lang", "0", "change"]]) {
    cell = tableField(ui, "tag1", name); cell.value = value; cell.dispatch(event);
    assert.equal(ui.sent.at(-1).action, "update"); assert.equal(ui.sent.at(-1).id, "tag1");
  }
});

test("an automatic table calculation error stays on its row and correction restores the current result", t => {
  const ui = setup(t); bulkFixture(ui);
  const cell = tableField(ui, "tag1", "b"); cell.value = "abc"; cell.dispatch("input");
  let request = ui.sent.at(-1);
  Object.assign(ui.tag, {status: "error", error: "Ange giltig bredd", summary: null});
  ui.tag.values.b = null; ui.changed(); ui.ack(request);
  ui.byText("2 sulor · 1 med fel i indata");
  const row = ui.find(e => e.tag === "tr" && e.dataset.tagId === "tag1");
  assert.equal(row.children[2].textContent, "Fel i indata");
  assert.ok(ui.data.state.tags[1].summary, "The other footing retains its own result");
  cell.value = "1,1"; cell.dispatch("input"); request = ui.sent.at(-1);
  ui.tag.values.b = 1.1;
  Object.assign(ui.tag, {status: "calculated", error: "", summary: structuredClone(ui.data.state.tags[1].summary)});
  ui.changed(); ui.ack(request);
  assert.equal(row.children[2].textContent, "U 75%"); assert.equal(cell.value, "1,1");
  assert.equal(ui.elements().some(e => e.tag === "button" && /beräkna/i.test(e.textContent)), false);
});

test("Enter moves through table rows without replacing controls or running notebook cells", t => {
  const ui = setup(t); bulkFixture(ui);
  const first = tableField(ui, "tag1", "b"), second = tableField(ui, "tag2", "b");
  let prevented = false; first.dispatch("keydown", {key: "Enter", preventDefault() {prevented = true;}});
  assert.equal(prevented, true); assert.equal(document.activeElement, second);
  second.dispatch("keydown", {key: "Enter", shiftKey: true}); assert.equal(document.activeElement, first);
});

test("Shift-left marquee previews two labels without moving the canvas and opens the existing bulk editor", t => {
  const ui = setup(t), bulk = bulkFixture(ui), picture = ui.byClass("gp-picture");
  const initial = picture.getBoundingClientRect(), original = structuredClone(ui.data.state);
  ui.start(picture, 200, 200, {shiftKey: true}); ui.move(700, 500);
  const box = ui.byClass("gp-selection-box");
  assert.equal(box.hidden, false);
  assert.equal(box.style.width, "500px"); assert.equal(box.style.height, "300px");
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  assert.equal(ui.byClass("gp-selection-bar").hidden, true, "Preview does not shift the canvas by inserting a toolbar");
  assert.deepEqual(picture.getBoundingClientRect(), initial);
  ui.finish(700, 500);
  assert.equal(box.hidden, true);
  assert.equal(ui.byClass("gp-selection-count").textContent, "2 markerade");
  assert.deepEqual(ui.data.state, original);
  assert.equal(ui.sent.length, 0, "Selection is local until an edit is applied");
  ui.byText("Ändra markerade").click();
  bulk.field("b").value = "0,9"; bulk.field("b").dispatch("input");
  ui.byText("Tillämpa").click();
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"]);
  assert.deepEqual(ui.sent.at(-1).values, {b: .9}, "Different loads and other inputs are retained");
});

test("Shift marquee toggles overlapping labels once, adds new labels and preserves labels outside the rectangle", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  const third = {...structuredClone(ui.tag), id: "tag3", label: "PS3", x: .05, y: .8};
  ui.data.state.tags.push(third); ui.changed();
  marquee(ui, [150, 450], [40, 560]);
  assert.deepEqual(selectedIds(ui), ["tag3"], "Reverse drag selects a partially intersecting label");
  marquee(ui, [200, 200], [420, 320], {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1", "tag3"]);
  ui.start(ui.byClass("gp-picture"), 200, 200, {shiftKey: true});
  ui.move(700, 480);
  assert.deepEqual(selectedIds(ui), ["tag2", "tag3"], "Overlap removes tag1, adds tag2 and preserves tag3");
  ui.move(701, 481); ui.move(700, 480); ui.finish(700, 480);
  assert.deepEqual(selectedIds(ui), ["tag2", "tag3"], "Preview and release do not toggle a second time");
  bulk.marker("tag2").dispatch("click", {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag3"], "Shift-click uses the same toggle rule");
  ui.byText("Avmarkera").click();
  marquee(ui, [420, 320], [200, 200]);
  assert.deepEqual(selectedIds(ui), ["tag1"]);
  marquee(ui, [30, 30], [130, 130], {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1"], "An empty Shift rectangle retains the selection");
  marquee(ui, [200, 200], [420, 320]);
  assert.deepEqual(selectedIds(ui), []);
  assert.equal(ui.byClass("gp-selection-bar").hidden, true);
});

for (const cancel of ["pointercancel", "lostpointercapture"]) {
  test(cancel + " restores the selection that existed before a marquee", t => {
    const ui = setup(t); bulkFixture(ui);
    marquee(ui, [200, 200], [420, 320]);
    ui.start(ui.byClass("gp-picture"), 480, 360, {shiftKey: true}); ui.move(700, 450);
    assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
    ui.viewport.dispatch(cancel);
    assert.deepEqual(selectedIds(ui), ["tag1"]);
    assert.equal(ui.byClass("gp-selection-box").hidden, true);
    assert.equal(ui.byClass("gp-selection-count").textContent, "1 markerade");
    ui.finish(700, 450);
    assert.deepEqual(selectedIds(ui), ["tag1"]);
    assert.equal(ui.sent.length, 0);
  });
}

for (const entry of ["Shift-click", "marquee", "unfinished marquee"]) {
  test("Escape ends selection and clears all highlights after " + entry, t => {
    const ui = setup(t), bulk = bulkFixture(ui), original = structuredClone(ui.data.state);
    const notebookEditor = document.createElement("input"); notebookEditor.focus();
    if (entry === "Shift-click") {
      ui.start(bulk.marker("tag1"), 300, 300, {shiftKey: true}); ui.finish(300, 300);
    } else {
      marquee(ui, [200, 200], [420, 320]);
      if (entry === "unfinished marquee") {
        ui.start(ui.byClass("gp-picture"), 480, 360, {shiftKey: true}); ui.move(700, 450);
        assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
      }
    }
    assert.equal(document.activeElement, ui.viewport, "Selection must focus the widget so Jupyter cannot consume Escape");
    let prevented = false;
    ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape", target: document.activeElement,
      preventDefault() {prevented = true;}});
    assert.equal(prevented, true);
    assert.deepEqual(selectedIds(ui), []);
    assert.equal(ui.byClass("gp-selection-box").hidden, true);
    assert.equal(ui.byClass("gp-selection-bar").hidden, true);
    assert.equal(ui.elements().some(e => e.tag === "button" && e.textContent === "Markera flera"), false);
    assert.equal(ui.viewport.style.cursor, "grab");
    assert.ok(!ui.viewport.className.includes("gp-selecting"));
    assert.equal(ui.viewport.captures.size, 0);
    ui.move(750, 500); ui.finish(750, 500);
    assert.deepEqual(selectedIds(ui), [], "Releasing the mouse after Escape cannot restore the selection");
    assert.equal(ui.sent.length, 0); assert.deepEqual(ui.data.state, original);
    ui.byText("Markeringen avbröts.");
    marquee(ui, [480, 360], [700, 450]);
    assert.deepEqual(selectedIds(ui), ["tag2"], "The next selection starts with an empty group");
  });
}

test("Escape closes bulk editing and discards the old selection without applying its draft", t => {
  const ui = setup(t), bulk = bulkFixture(ui), original = structuredClone(ui.data.state);
  bulk.select();
  bulk.field("b").value = "0,9"; bulk.field("b").dispatch("input");
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  assert.equal(ui.byClass("gp-bulk-dialog").hidden, true);
  assert.deepEqual(selectedIds(ui), []); assert.deepEqual(ui.data.state, original);
  assert.equal(ui.sent.length, 0);
  marquee(ui, [480, 360], [700, 450]); ui.byText("Ändra markerade").click();
  assert.equal(bulk.field("b").value, "2");
  assert.equal(bulk.choose("b").checked, false, "Canceled bulk changes cannot carry into a new group");
});

test("marquee hit testing follows displayed label rectangles after zoom, label sizing and panning", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  const old = bulk.marker("tag2").getBoundingClientRect();
  ui.byText("+").click();
  const slider = ui.find(e => e.getAttribute("aria-label") === "Etikettstorlek i procent");
  slider.value = 160; slider.dispatch("input");
  ui.start(ui.byClass("gp-picture"), 100, 100, {button: 2}); ui.move(100, 250); ui.finish(100, 250, {button: 2});
  marquee(ui, [old.left + old.width - 10, old.top], [old.left + old.width, old.top + 10]);
  assert.deepEqual(selectedIds(ui), [], "The former screen location is no longer a hit");
  const current = bulk.marker("tag2").getBoundingClientRect();
  marquee(ui, [current.left + current.width - 8, current.top + 8], [current.left + current.width - 2, current.top + 20]);
  assert.deepEqual(selectedIds(ui), ["tag2"], "A rectangle intersecting only the scaled label edge selects it");
});

for (const target of ["gp-picture", "gp-tag", "gp-global-axes", "gp-sliding-legend"]) {
  test("right drag pans from " + target + " without moving or selecting objects", t => {
    const ui = setup(t); slidingFixture(ui);
    const before = structuredClone(ui.data.state), sheet = ui.byClass("gp-sheet");
    const initial = [parseFloat(sheet.style.left), parseFloat(sheet.style.top)];
    ui.start(ui.byClass(target), 300, 300, {button: 2}); ui.move(400, 360); ui.finish(400, 360, {button: 2});
    near(parseFloat(sheet.style.left), initial[0] + 100); near(parseFloat(sheet.style.top), initial[1] + 60);
    assert.deepEqual(ui.data.state, before);
    assert.deepEqual(selectedIds(ui), []);
    assert.equal(ui.byClass("gp-dialog").hidden, true);
    assert.equal(ui.sent.length, 0);
    let suppressed = false;
    ui.viewport.dispatch("contextmenu", {preventDefault() { suppressed = true; }});
    assert.equal(suppressed, true, "The browser menu cannot interrupt a right drag");
  });
}

test("marquee during import pauses placement without consuming a support; right pan preserves placement mode", t => {
  const ui = setup(t); bulkFixture(ui); importFixture(ui);
  ui.start(ui.marker(), 300, 300, {button: 2}); ui.move(350, 350); ui.finish(350, 350, {button: 2});
  assert.equal(ui.sent.length, 0);
  ui.byText("Placera W1 – väggsula (1 av 2)");
  marquee(ui, [200, 200], [750, 550]);
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  assert.equal(ui.sent.at(-1).action, "import_control"); assert.equal(ui.sent.at(-1).operation, "pause");
  assert.equal(ui.data.state.load_import.index, 0);
  assert.equal(ui.sent.some(request => request.action === "place_import"), false);
});

test("ordinary left drag pans while preserving an existing multi-selection", t => {
  const ui = setup(t); bulkFixture(ui);
  marquee(ui, [200, 200], [700, 500]);
  const before = ui.byClass("gp-picture").getBoundingClientRect();
  ui.start(ui.byClass("gp-picture"), 50, 50); ui.move(100, 140); ui.finish(100, 140);
  const after = ui.byClass("gp-picture").getBoundingClientRect();
  near(after.left, before.left + 50); near(after.top, before.top + 90);
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  assert.equal(ui.byClass("gp-selection-box").hidden, true);
  assert.equal(ui.sent.length, 0);
});

test("Shift click or a jittering selection gesture on the drawing cannot place an imported support", t => {
  const ui = setup(t); importFixture(ui);
  ui.start(ui.byClass("gp-picture"), 400, 400, {shiftKey: true}); ui.finish(400, 400);
  ui.start(ui.byClass("gp-picture"), 400, 400, {shiftKey: true}); ui.move(402, 401); ui.finish(402, 401);
  assert.equal(ui.sent.length, 0);
  assert.equal(ui.data.state.load_import.index, 0);
  assert.equal(ui.byClass("gp-selection-box").hidden, true);
  ui.place(); assert.equal(ui.sent.at(-1).action, "place_import", "Normal clicks still place the next support");
});

test("multi-selection only sends chosen fields and retains different loads", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  bulk.select();
  ui.place();
  assert.equal(ui.sent.length, 0, "Background clicks in selection mode do not add a footing");
  assert.equal(ui.byClass("gp-selection-count").textContent, "2 markerade");
  assert.match(bulk.marker("tag1").className, /gp-multi-selected/);
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  assert.equal(ui.byClass("gp-bulk-dialog").hidden, false);
  assert.equal(bulk.field("b").placeholder, "Olika värden");
  assert.equal(bulk.field("b").value, "");
  assert.equal(bulk.choose("b").checked, false);
  const before = structuredClone(ui.data.state);
  bulk.field("b").value = "0,9"; bulk.field("b").dispatch("input");
  assert.equal(bulk.choose("b").checked, true);
  assert.deepEqual(ui.data.state, before, "Typing stays local until Apply");
  assert.equal(ui.sent.length, 0);
  ui.byText("Tillämpa").click();
  const request = ui.sent.at(-1);
  assert.deepEqual(request.ids, ["tag1", "tag2"]);
  assert.deepEqual(request.values, {b: .9});
  assert.equal(request.calculate, undefined, "The kernel always calculates widget edits automatically");
  assert.equal(ui.byText("Ändra markerade").disabled, true);
  assert.equal(bulk.field("b").disabled, true);
  for (const tag of ui.data.state.tags) tag.values.b = .9;
  ui.changed(); ui.ack(request, {report: {updated: 2, calculated: 2, errors: []}});
  assert.deepEqual(ui.data.state.tags.map(tag => tag.values.F_vy), [1, 200]);
  assert.equal(ui.byText("Ändra markerade").disabled, false);
  assert.equal(bulk.field("b").value, "0.9");
  assert.equal(bulk.choose("b").checked, false);
  ui.byText("2 av 2 sulor beräknade automatiskt.");
});

for (const entry of ["Shift-click", "marquee"]) {
  test("ordinary left drag moves only the dragged footing after selection entered via " + entry, t => {
    const ui = setup(t), bulk = bulkFixture(ui);
    if (entry === "Shift-click") bulk.marker("tag1").dispatch("click", {shiftKey: true});
    else marquee(ui, [200, 200], [700, 500]);
    const original = structuredClone(ui.data.state), selected = selectedIds(ui);
    ui.start(bulk.marker("tag2"), 520, 390); ui.move(640, 450); ui.finish(640, 450);
    const request = ui.sent.at(-1);
    assert.equal(ui.sent.length, 1);
    assert.equal(request.action, "update"); assert.equal(request.id, "tag2");
    near(request.x, bulk.second.x + 120 / 800); near(request.y, bulk.second.y + 60 / 600);
    assert.equal(request.values, undefined, "A position update never replaces loads or geometry");
    assert.deepEqual(ui.data.state, original, "The project waits for the kernel acknowledgment");
    assert.deepEqual(selectedIds(ui), selected, "Moving one label does not toggle the group selection");
    assert.equal(ui.byClass("gp-dialog").hidden, true, "A drag does not open the single-footing form");
    Object.assign(bulk.second, {x: request.x, y: request.y}); ui.changed(); ui.ack(request);
    assert.deepEqual(ui.tag, original.tags[0], "The other footing remains unchanged");
    assert.deepEqual(bulk.second.values, original.tags[1].values);
    near(parseFloat(bulk.marker("tag2").style.left) / 100, request.x);
    near(parseFloat(bulk.marker("tag2").style.top) / 100, request.y);
  });

  for (const activation of ["pointer", "keyboard"]) {
    test("ordinary " + activation + " click edits a footing after selection entered via " + entry, t => {
      const ui = setup(t), bulk = bulkFixture(ui);
      if (entry === "Shift-click") bulk.marker("tag1").dispatch("click", {shiftKey: true});
      else marquee(ui, [200, 200], [700, 500]);
      const original = structuredClone(ui.data.state);
      if (activation === "pointer") {
        ui.start(bulk.marker("tag2"), 520, 390); ui.finish(520, 390);
      } else bulk.marker("tag2").click();
      assert.equal(ui.byClass("gp-dialog").hidden, false);
      assert.equal(ui.byClass("gp-bulk-dialog").hidden, true);
      assert.equal(ui.label().value, "VS2");
      assert.equal(ui.field("b").value, "2");
      assert.equal(ui.field("F_vy").value, "200");
      assert.deepEqual(selectedIds(ui), [], "Ordinary editing never toggles a multi-selection");
      assert.equal(ui.byClass("gp-selection-bar").hidden, true);
      assert.equal(bulk.marker("tag2").getAttribute("aria-pressed"), "false");
      assert.deepEqual(ui.data.state, original); assert.equal(ui.sent.length, 0);
      ui.field("b").value = "1,8"; ui.field("b").dispatch("input");
      assert.equal(ui.sent.at(-1).id, "tag2", "The opened form edits this footing only");
      assert.equal(ui.sent.at(-1).values.b, 1.8);
    });
  }
}

test("Shift pointer clicks toggle selection without dragging or opening single forms", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  ui.marker().click();
  ui.viewport.dispatch("pointerdown", {target: bulk.marker("tag2"), shiftKey: true, clientX: 300, clientY: 300});
  ui.finish(300, 300);
  assert.equal(ui.byClass("gp-selection-count").textContent, "2 markerade", "Active single footing joins shift-selection");
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  ui.viewport.dispatch("pointerdown", {target: bulk.marker("tag2"), shiftKey: true, clientX: 300, clientY: 300});
  ui.move(500, 500); ui.finish(500, 500);
  assert.equal(ui.sent.length, 0, "Dragging with a selection modifier cannot move a footing");
  assert.equal(ui.byClass("gp-selection-count").textContent, "2 markerade");
  bulk.marker("tag1").dispatch("click", {shiftKey: true});
  assert.equal(ui.byClass("gp-selection-count").textContent, "1 markerade");
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  assert.equal(ui.byClass("gp-selection-bar").hidden, true);
  assert.ok(ui.elements().filter(e => e.dataset.tagId).every(e => !e.className.includes("gp-multi-selected")));
});

test("mixed types allow insulation while blocking differently defined loads and lengths", t => {
  const ui = setup(t), bulk = bulkFixture(ui, true);
  bulk.second.values.isolering = true;
  bulk.select();
  assert.equal(bulk.field("isolering").value, "");
  assert.equal(bulk.field("F_vy").disabled, true);
  assert.equal(bulk.choose("F_vy").disabled, true);
  assert.equal(bulk.field("l").disabled, true);
  assert.equal(bulk.field("b").disabled, false);
  bulk.field("isolering").value = "false"; bulk.field("isolering").dispatch("change");
  ui.byText("Tillämpa").click();
  const request = ui.sent.at(-1);
  assert.deepEqual(request.values, {isolering: false});
  assert.equal(request.calculate, undefined, "The kernel calculates this patch automatically");
  ui.ack(request, {ok: false, error: "Testfel"});
  assert.equal(bulk.field("isolering").value, "false", "Rejected request preserves the patch for correction");
  assert.equal(bulk.choose("isolering").checked, true);
  assert.equal(bulk.field("F_vy").disabled, true);
});

test("pad dimensions, validation and minimized bulk drafts work independently", t => {
  const ui = setup(t); ui.tag.values.lang = 0;
  const bulk = bulkFixture(ui, true); bulk.select();
  bulk.field("b").value = "invalid"; bulk.field("b").dispatch("input");
  ui.byText("Tillämpa").click();
  assert.equal(ui.sent.length, 0);
  assert.equal(bulk.field("b").validityMessage, "Ange ett tal.");
  bulk.field("b").value = "1,8"; bulk.field("b").dispatch("input");
  bulk.field("l").value = "2,4"; bulk.field("l").dispatch("input");
  ui.byClass("gp-bulk-dialog").children[0].children[1].click();
  assert.equal(ui.byClass("gp-bulk-dialog").hidden, true);
  ui.byText("Ändra markerade").click();
  assert.equal(bulk.field("l").value, "2,4");
  bulk.choose("b").checked = false; bulk.choose("b").dispatch("change");
  ui.byText("Tillämpa").click();
  assert.deepEqual(ui.sent.at(-1).values, {l: 2.4}, "Unchecked fields retain their individual values");
});

test("batch calculation reports failed footing labels and clears older individual drafts", t => {
  const ui = setup(t), bulk = bulkFixture(ui);
  ui.marker().click(); ui.field("b").value = "1,4"; ui.field("b").dispatch("input");
  ui.tag.values.b = 1.4; ui.changed(); ui.ack(ui.sent.at(-1));
  bulk.select();
  bulk.field("b").value = "0,7"; bulk.field("b").dispatch("input");
  ui.byText("Tillämpa").click();
  const request = ui.sent.at(-1);
  Object.assign(ui.tag, {values: {...ui.tag.values, b: .7}, status: "calculated"});
  Object.assign(bulk.second, {values: {...bulk.second.values, b: .7}, status: "error", summary: null, error: "Saknad last"});
  ui.changed(); ui.ack(request, {report: {updated: 2, calculated: 1,
    errors: [{id: "tag2", label: "VS2", error: "Saknad last"}]}});
  ui.byText("VS2: Saknad last");
  bulk.marker("tag1").click();
  assert.equal(ui.field("b").value, "0.7", "Successful batch supersedes the old single-footing draft");
  assert.match(bulk.marker("tag2").className, /gp-tag-error/);
});

test("standalone HTML allows local selection without exposing editing controls", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  const original = structuredClone(ui.snapshot), replies = [];
  ui.model.on("msg:custom", reply => replies.push(reply));
  assert.ok(!ui.elements().some(e => ["Markera flera", "Ändra markerade", "Tillämpa"].includes(e.textContent)));
  ui.marker().dispatch("click", {shiftKey: true});
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  assert.deepEqual(selectedIds(ui), ["tag1"]);
  assert.equal(ui.marker().getAttribute("aria-pressed"), "true");
  assert.equal(ui.byClass("gp-selection-bar").hidden, false);
  assert.equal(ui.find(e => e.tag === "tr" && e.dataset.tagId === "tag1").className, "gp-table-row-selected");
  ui.marker().click();
  assert.equal(ui.byClass("gp-dialog").hidden, false, "Ordinary click still opens the read-only details");
  assert.deepEqual(selectedIds(ui), ["tag1"], "Opening details preserves the highlighted rows");
  assert.ok(!ui.elements().some(e => e.className.includes("gp-bulk-dialog")));
  ui.byText("Avmarkera").click();
  assert.deepEqual(selectedIds(ui), []);
  assert.equal(ui.byClass("gp-selection-bar").hidden, true);
  assert.deepEqual(ui.snapshot, original);
  assert.equal(replies.length, 0, "Selecting never sends a calculation or mutation command");
});

const resultTableValue = (ui, id, name) => ui.find(e => e.className === "gp-table-value" && e.dataset.tagId === id && e.dataset.field === name);

test("standalone table includes all fields and formats read-only numbers, booleans, types and literal comments", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  Object.assign(ui.tag.values, {b: .95, l: 2.4, l_override: true, isolering: true, F_vy: -150.5, F_vy_bruk: 0,
    isolerprodukt: '<img src=x onerror=alert(1)> EPS ÅÄÖ', glid_x: false});
  const pad = {...structuredClone(ui.tag), id: "pad", label: "PS2", values: {...ui.tag.values, lang: 0, isolering: false},
    status: "error", summary: null, error: "Ange giltig last"};
  ui.data.state.tags.push(pad); ui.changed();
  const original = structuredClone(ui.snapshot);
  assert.equal(ui.byClass("gp-table-section").hidden, false);
  ui.byText("Sulor – indata och resultat");
  for (const tag of ui.data.state.tags) for (const name of ["label", ...names]) {
    const value = resultTableValue(ui, tag.id, name);
    assert.equal(value.tag, "span");
    assert.ok(!value.listeners.has("input") && !value.listeners.has("change"));
  }
  assert.equal(resultTableValue(ui, "tag1", "b").textContent, "0,95");
  assert.equal(resultTableValue(ui, "tag1", "l").textContent, "2,4");
  assert.equal(resultTableValue(ui, "tag1", "l_override").textContent, "Ja");
  assert.equal(resultTableValue(ui, "pad", "l_override").textContent, "—");
  assert.equal(resultTableValue(ui, "pad", "l").textContent, "2,4");
  assert.equal(resultTableValue(ui, "tag1", "lang").textContent, "Väggsula");
  assert.equal(resultTableValue(ui, "pad", "lang").textContent, "Pelarsula");
  assert.equal(resultTableValue(ui, "tag1", "isolering").textContent, "Ja");
  assert.equal(resultTableValue(ui, "pad", "isolering").textContent, "Nej");
  assert.equal(resultTableValue(ui, "tag1", "F_vy").textContent, "-150,5");
  assert.equal(resultTableValue(ui, "tag1", "F_vy_bruk").textContent, "0");
  assert.equal(resultTableValue(ui, "tag1", "V_Ed_EQU").textContent, "—");
  assert.equal(resultTableValue(ui, "pad", "glid_L").textContent, "—");
  assert.equal(resultTableValue(ui, "tag1", "isolerprodukt").textContent, ui.tag.values.isolerprodukt);
  assert.equal(resultTableValue(ui, "tag1", "isolerprodukt").children.length, 0, "Comment is text, never parsed as HTML");
  const row = ui.find(e => e.tag === "tr" && e.dataset.tagId === "pad");
  assert.equal(row.children[2].textContent, "Fel i indata"); assert.equal(row.children[2].title, pad.error);
  const tableElements = ui.elements().filter(e => e.closest("table"));
  assert.ok(tableElements.every(e => !["select", "textarea"].includes(e.tag) && (e.tag !== "input" || e.type === "checkbox")));
  assert.equal(tableElements.filter(e => e.tag === "input").length, 3, "Only row-selection checkboxes are present");
  assert.deepEqual(ui.snapshot, original);
});

test("standalone marquee and pointer Shift clicks toggle multiple table highlights without changing data or positions", t => {
  const ui = setup(t, {readOnly: true, standalone: true}), bulk = bulkFixture(ui);
  const original = structuredClone(ui.snapshot), before = ui.byClass("gp-picture").getBoundingClientRect(), replies = [];
  ui.model.on("msg:custom", reply => replies.push(reply));
  marquee(ui, [200, 200], [700, 500]);
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2"]);
  assert.deepEqual(ui.byClass("gp-picture").getBoundingClientRect(), before);
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  for (const id of selectedIds(ui)) {
    const row = ui.find(e => e.tag === "tr" && e.dataset.tagId === id);
    assert.equal(row.children[0].children[0].checked, true);
    assert.ok(row.className.includes("gp-table-row-selected"));
  }
  ui.start(bulk.marker("tag2"), 300, 300, {shiftKey: true}); ui.finish(300, 300);
  assert.deepEqual(selectedIds(ui), ["tag1"]);
  marquee(ui, [200, 200], [700, 500]);
  assert.deepEqual(selectedIds(ui), ["tag2"], "A second rectangle toggles overlap using the existing convention");
  ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
  assert.deepEqual(selectedIds(ui), []);
  assert.equal(ui.byClass("gp-table-selection-info").hidden, true);
  assert.deepEqual(ui.snapshot, original);
  assert.equal(replies.length, 0);
});

test("standalone sorted checkbox ranges synchronize with labels and never edit objects", t => {
  const ui = setup(t, {readOnly: true, standalone: true}); bulkFixture(ui);
  ui.tag.label = "S.10"; ui.data.state.tags[1].label = "S.2";
  ui.data.state.tags.push({...structuredClone(ui.tag), id: "tag3", label: "S.1", summary: {...ui.tag.summary, utnyttjandegrad: 1.2}});
  ui.changed(); const original = structuredClone(ui.snapshot);
  tableSortButton(ui, "label").click(); assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag1"]);
  selectTableRow(ui, "S.1"); selectTableRow(ui, "S.10", true, {shiftKey: true});
  assert.deepEqual(selectedIds(ui), ["tag1", "tag2", "tag3"]);
  selectTableRow(ui, "S.2", false, {shiftKey: true}); assert.deepEqual(selectedIds(ui), ["tag1"]);
  tableSortButton(ui, "status").click(); assert.deepEqual(tableOrder(ui), ["tag1", "tag3", "tag2"]);
  assert.deepEqual(selectedIds(ui), ["tag1"]);
  const all = ui.find(e => e.getAttribute("aria-label") === "Markera samtliga tabellrader");
  all.checked = true; all.dispatch("change"); assert.deepEqual(selectedIds(ui), ["tag1", "tag2", "tag3"]);
  all.checked = false; all.dispatch("change"); assert.deepEqual(selectedIds(ui), []);
  assert.deepEqual(ui.snapshot, original);
});

test("sliding toggle and directional demands preserve settings while hidden", t => {
  const ui = setup(t);
  slidingFixture(ui, false);
  const toggle = ui.byText("Glidningskontroll");
  assert.equal(toggle.getAttribute("aria-pressed"), "false");
  assert.equal(ui.byClass("gp-global-axes").hidden, true);
  toggle.click();
  assert.equal(ui.sent.at(-1).action, "sliding");
  assert.deepEqual(ui.sent.at(-1).settings, {enabled: true});
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.equal(ui.byClass("gp-sliding-legend").hidden, false);
  ui.data.state.sliding.enabled = true; ui.changed(); ui.ack(ui.sent.at(-1));
  ui.byText("Godkänd"); ui.byText("Överskriden");
  const yCheck = ui.find(e => e.getAttribute("aria-label") === "Kontroll Y_g");
  const yDemand = ui.find(e => e.getAttribute("aria-label") === "Global H_y,Ed i kN, EQU");
  yCheck.checked = false; yCheck.dispatch("change");
  assert.equal(yDemand.parent.hidden, true);
  ui.data.state.sliding.check_y = false; ui.changed(); ui.ack(ui.sent.at(-1));
  yCheck.checked = true; yCheck.dispatch("change");
  assert.equal(yDemand.parent.hidden, false);
  assert.equal(yDemand.value, "180");
  ui.data.state.sliding.check_y = true; ui.changed(); ui.ack(ui.sent.at(-1));
  yDemand.focus(); yDemand.value = "-190,5"; yDemand.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).settings, {H_y_Ed: -190.5});
  assert.ok(ui.elements().some(e => e.textContent === "Ofullständig"), "Pending demand cannot show a pass");
  yDemand.value = ""; yDemand.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).settings, {H_y_Ed: null}, "Empty demand is not zero");
});

for (const readOnly of [false, true]) test(`compact sliding labels exclude insulation and pad length (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  slidingFixture(ui);
  colourFixture(ui, {category: "isolering"});
  assert.equal(ui.byClass("gp-tag-sliding-inputs").children.length, 4, "Strip has V and L");
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children.length, 4, "Both selected capacities");
  ui.byText("120 kN/m"); ui.byText("144 kN");
  ui.tag.values.lang = 0; ui.tag.values.glid_y = false; ui.changed();
  assert.equal(ui.byClass("gp-tag-sliding-inputs").children.length, 2);
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children.length, 2);
  ui.byText("120 kN");
  ui.tag.values.isolering = true; ui.changed();
  assert.ok(!ui.elements().some(e => e.className === "gp-tag-sliding"));
  ui.tag.values.isolering = false; ui.data.state.sliding.enabled = false; ui.changed();
  assert.ok(!ui.elements().some(e => e.className === "gp-tag-sliding"));
});

test("gliding inputs follow load basis and edits hide old resistance without invalidating bearing", t => {
  const ui = setup(t);
  slidingFixture(ui);
  ui.marker().click();
  assert.equal(ui.field("V_Ed_EQU").disabled, false);
  assert.equal(ui.field("V_Ed_EQU").parent.children.at(-1).textContent, "kN/m");
  ui.field("V_Ed_EQU").value = "160"; ui.field("V_Ed_EQU").dispatch("input");
  assert.match(ui.marker().className, /gp-tag-ok/);
  assert.ok(ui.elements().some(e => e.textContent === "Ofullständig"));
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children[1].textContent, "—");
  const edit = ui.sent.at(-1);
  Object.assign(ui.tag.values, edit.values);
  ui.tag.sliding = {x: 192, y: 192, status: "ready"};
  ui.data.state.sliding_result.x.H_Rd = 192;
  ui.changed(); ui.ack(edit);
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children[1].textContent, "192 kN");
  ui.field("lang").value = 0; ui.field("lang").dispatch("input");
  assert.equal(ui.field("glid_L").parent.hidden, true);
  assert.equal(ui.field("glid_L").disabled, true);
  assert.equal(ui.field("V_Ed_EQU").parent.children.at(-1).textContent, "kN/m");
  ui.field("lasttyp").value = 0; ui.field("lasttyp").dispatch("input");
  assert.equal(ui.field("V_Ed_EQU").parent.children.at(-1).textContent, "kN");
  ui.field("isolering").checked = true; ui.field("isolering").dispatch("input");
  assert.equal(ui.field("glid_x").disabled, true);
  assert.equal(ui.field("V_Ed_EQU").parent.hidden, true);
});

for (const readOnly of [false, true]) test(`H_Rd displays at most one decimal without rounding stored capacities (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly, standalone: readOnly});
  slidingFixture(ui);
  ui.model.get("state").tags = ui.data.state.tags;
  Object.assign(ui.tag.sliding, {x: 1240.704, y: 149.949});
  Object.assign(ui.data.state.sliding_result.x, {H_Rd: 1240.704, H_Ed: 100.123});
  ui.data.state.sliding_result.y.H_Rd = 149.949;
  ui.changed();
  const before = structuredClone(ui.model.get("state"));
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children[1].textContent, "1\u00a0240,7 kN");
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children[3].textContent, "149,9 kN");
  assert.deepEqual(ui.elements().filter(e => e.className === "gp-sliding-value").map(e => e.textContent),
    ["100,12 kN", "1\u00a0240,7 kN", "180 kN", "149,9 kN"]);
  assert.deepEqual(ui.model.get("state"), before);
  ui.tag.values.endast_h_stabilitet = true;
  ui.tag.summary = structuredClone(onlyHSummary);
  ui.changed(); ui.marker().click();
  assert.ok(ui.elements().some(e => e.tag === "dd" && e.textContent === "1\u00a0240,7 kN"));
  assert.equal(ui.tag.sliding.x, 1240.704);
});

for (const readOnly of [false, true]) test(`wall length is editable but hidden on labels without sliding directions (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  slidingFixture(ui);
  ui.tag.values.glid_x = ui.tag.values.glid_y = false; ui.changed();
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 75 % · bₓ 1 m · t 1 m");
  assert.ok(!ui.elements().some(e => e.className === "gp-tag-sliding"));
  ui.marker().click();
  const row = readOnly ? ui.find(e => e.getAttribute("aria-label")?.startsWith("glid_L")) : ui.field("glid_L").parent;
  assert.equal(row.hidden, false);
  assert.equal(row.parent.hidden, false);
  if (!readOnly) {
    assert.equal(ui.field("glid_L").disabled, false);
    assert.equal(ui.field("glid_L").required, false);
    ui.field("glid_L").value = "6,2"; ui.field("glid_L").dispatch("input");
    assert.equal(ui.sent.at(-1).values.glid_L, 6.2);
    assert.ok(!ui.byClass("gp-tag-result").textContent.includes(" · L "));
    assert.match(ui.marker().className, /gp-tag-ok/, "Length alone does not invalidate bearing");
    ui.field("glid_L").value = ""; ui.field("glid_L").dispatch("input");
    assert.equal(ui.field("glid_L").validity.valid, true, "Unused length may be left empty");
    assert.ok(!ui.byClass("gp-tag-result").textContent.includes(" · L "));
    ui.field("isolering").checked = true; ui.field("isolering").dispatch("input");
    assert.equal(ui.field("glid_L").parent.hidden, false);
    assert.equal(ui.field("glid_L").disabled, false, "Insulation does not remove wall geometry");
  }
});

for (const readOnly of [false, true]) test(`length stays on inactive/new wall labels and is not repeated or applied to pads (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  slidingFixture(ui, false);
  assert.match(elementText(ui.byClass("gp-tag-result")), /Lsu 3 m$/);
  ui.tag.status = "new"; ui.tag.summary = null; ui.changed();
  assert.equal(elementText(ui.byClass("gp-tag-result")), "Kontrollera indata · Lsu 3 m");
  ui.data.state.sliding.enabled = true; ui.changed();
  assert.equal(ui.byClass("gp-tag-result").textContent, "Kontrollera indata");
  assert.equal(ui.byClass("gp-tag-sliding-inputs").children[3].textContent, "3 m");
  ui.tag.values.isolering = true; ui.changed();
  assert.equal(ui.byClass("gp-tag-result").textContent, "Kontrollera indata");
  ui.tag.values.lang = 0; ui.changed();
  assert.equal(ui.byClass("gp-tag-result").textContent, "Kontrollera indata");
  ui.tag.values.lang = 1;
  for (const length of [null, "", "saknas", 0, -1]) {
    ui.tag.values.glid_L = length; ui.changed();
    assert.equal(ui.byClass("gp-tag-result").textContent, "Kontrollera indata");
  }
});

test("global symbol drag and proportional corner resize use drawing zoom and survive delayed replies", t => {
  const ui = setup(t);
  slidingFixture(ui);
  ui.byText("+").click();
  const symbol = ui.byClass("gp-global-axes"), handle = ui.byClass("gp-axis-resize");
  assert.equal(symbol.style.width, "200px");
  assert.equal(handle.hidden, true);
  ui.start(ui.byClass("gp-axis-symbol")); ui.move(400, 375); ui.finish(400, 375);
  const first = ui.sent.at(-1);
  assert.equal(first.action, "sliding_placement");
  assert.equal(first.kind, "symbol");
  near(first.position.x, .16); near(first.position.y, .65);
  assert.equal(handle.hidden, false);
  ui.start(handle); ui.move(350, 350); ui.finish(350, 350);
  const second = ui.sent.at(-1);
  assert.equal(second.position.size, 200);
  assert.equal(symbol.style.width, "250px");
  ui.data.state.sliding.placements = {"1": {symbol: first.position}};
  ui.changed(); ui.ack(first);
  assert.equal(symbol.style.width, "250px", "Older move cannot undo pending resize");
  ui.data.state.sliding.placements["1"].symbol = second.position;
  ui.changed(); ui.ack(second);
  assert.equal(symbol.style.width, "250px");
  const before = ui.sent.length;
  ui.start(handle); ui.move(600, 600); ui.viewport.dispatch("pointercancel");
  assert.equal(symbol.style.width, "250px");
  assert.equal(ui.sent.length, before);
  ui.byText("Anpassa").click();
  assert.equal(symbol.style.width, "200px", "Saved base size follows drawing zoom");
});

test("legend moves by its header while result cells cannot move it", t => {
  const ui = setup(t);
  slidingFixture(ui);
  ui.start(ui.byClass("gp-sliding-header")); ui.move(220, 360); ui.finish(220, 360);
  const request = ui.sent.at(-1);
  assert.equal(request.kind, "legend");
  near(request.position.x, .4); near(request.position.y, .14);
  const before = ui.sent.length;
  ui.start(ui.byClass("gp-sliding-value")); ui.move(400, 400); ui.finish(400, 400);
  assert.equal(ui.sent.length, before);
});

test("legend corner scales text and box together, follows zoom and retains newer pending resize", t => {
  const ui = setup(t);
  slidingFixture(ui);
  const legend = ui.byClass("gp-sliding-legend"), handle = ui.byClass("gp-legend-resize");
  assert.equal(handle.hidden, true);
  ui.byClass("gp-sliding-header").click();
  assert.equal(handle.hidden, false);
  ui.byText("+").click();
  assert.equal(legend.style.transform, "scale(1.25)");
  ui.start(handle); ui.move(300 + 512.5 / 2, 300 + 225 / 2); ui.finish();
  const first = ui.sent.at(-1);
  assert.equal(first.action, "sliding_placement");
  assert.equal(first.kind, "legend");
  near(first.position.size, 615);
  assert.equal(legend.style.transform, "scale(1.875)");
  near(Number(handle.style.transform.match(/scale\(([^)]+)\)/)[1]) * 1.875, 1, "Handle stays usable");
  assert.equal(first.position.x, .5); assert.equal(first.position.y, .04);
  ui.start(handle); ui.move(300 - 768.75 / 3, 300 - 337.5 / 3); ui.finish();
  const second = ui.sent.at(-1);
  near(second.position.size, 410);
  ui.data.state.sliding.placements = {"1": {legend: first.position}};
  ui.changed(); ui.ack(first);
  assert.equal(legend.style.transform, "scale(1.25)");
  ui.data.state.sliding.placements["1"].legend = second.position;
  ui.changed(); ui.ack(second);
  const before = ui.sent.length;
  ui.start(handle); ui.move(800, 600); ui.viewport.dispatch("pointercancel");
  assert.equal(ui.sent.length, before);
  assert.equal(legend.style.transform, "scale(1.25)");
  ui.byText("Anpassa").click();
  assert.equal(legend.style.transform, "scale(1)");
  handle.dispatch("keydown", {key: "+", shiftKey: true});
  assert.equal(ui.sent.at(-1).position.size, 430);
});

test("standalone sliding overlays and contributions remain visible but cannot be edited", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  slidingFixture(ui);
  ui.data.state.sliding.placements = {"1": {legend: {x: .5, y: .04, size: 615}}};
  ui.changed();
  assert.equal(ui.byClass("gp-global-axes").hidden, false);
  assert.equal(ui.byClass("gp-sliding-legend").hidden, false);
  ui.byText("144 kN"); ui.byText("Godkänd");
  assert.equal(ui.byClass("gp-axis-resize").hidden, true);
  assert.equal(ui.byClass("gp-legend-resize").hidden, true);
  const symbol = ui.byClass("gp-global-axes"), legend = ui.byClass("gp-sliding-legend");
  assert.equal(legend.style.transform, "scale(1.5)");
  const before = structuredClone(ui.model.get("state"));
  ui.start(ui.byClass("gp-axis-symbol")); ui.move(450, 420); ui.finish(450, 420);
  assert.equal(symbol.style.left, "6%");
  ui.start(ui.byClass("gp-sliding-header")); ui.move(450, 420); ui.finish(450, 420);
  assert.equal(legend.style.left, "50%");
  assert.deepEqual(ui.model.get("state"), before);
});

for (const readOnly of [false, true]) test(`outside click minimizes without losing drafts or section state (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  ui.marker().click();
  const soil = inputSection(ui, "Jord - Allm. Bärighets.");
  soil.open = true;
  if (!readOnly) {
    ui.field("b").value = "2,";
    ui.field("b").dispatch("input");
  }
  const before = ui.sent.length;
  const click = target => {
    document.dispatch("pointerdown", {target, clientX: 500, clientY: 500});
    document.dispatch("pointerup", {target, clientX: 500, clientY: 500});
  };
  click(ui.byClass("gp-form"));
  assert.equal(ui.byClass("gp-dialog").hidden, false, "Inside clicks keep the form open");
  ui.byText("Visa definitionsskiss").click();
  click(ui.byClass("gp-sketch-panel"));
  assert.equal(ui.byClass("gp-dialog").hidden, false, "The associated sketch remains usable");
  document.dispatch("pointerdown", {target: ui.viewport, clientX: 500, clientY: 500});
  document.dispatch("pointermove", {target: ui.viewport, clientX: 510, clientY: 500});
  document.dispatch("pointerup", {target: ui.viewport, clientX: 500, clientY: 500});
  assert.equal(ui.byClass("gp-dialog").hidden, false, "A drag returning to its start is still a drag");
  click(new Element("outside-notebook-cell"));
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  assert.equal(ui.byClass("gp-sketch-panel").hidden, true);
  assert.equal(ui.sent.length, before, "Minimization does not change stored inputs or request calculation");
  ui.marker().click();
  assert.equal(inputSection(ui, "Jord - Allm. Bärighets.").open, true);
  assert.equal(ui.byClass("gp-sketch-panel").hidden, false);
  if (!readOnly) assert.equal(ui.field("b").value, "2,", "Unfinished raw input survives minimization");
  click(ui.marker());
  assert.equal(ui.byClass("gp-dialog").hidden, false, "A tag click is handled by the tag itself");
});

for (const readOnly of [false, true]) test(`nonzero external loads and definitions work in ${readOnly ? "HTML" : "notebook"}`, t => {
  const ui = setup(t, {readOnly});
  Object.assign(ui.tag.values, {F_vy: 150, F_hb: 0, F_hl: null, M_insp_b: -.25, M_insp_l: 1e-8,
    F_vy_bruk: 90, M_insp_b_bruk: 0, M_insp_l_bruk: 0});
  ui.changed();
  ui.byText("V 150 kN/m"); ui.byText("Mₓ −0,25 kNm/m"); ui.byText("Mᵧ 1,00e-8 kNm/m");
  assert.ok(!ui.elements().some(element => element.textContent === "Bruk" && element.closest(".gp-tag-load-row")));
  ui.marker().click();
  const before = ui.sent.length;
  ui.byText("Visa definitionsskiss").click();
  assert.equal(ui.byClass("gp-sketch-panel").hidden, false);
  ui.byText("Planvy – väggsula");
  ui.byText("Minimera").click();
  assert.equal(ui.byClass("gp-sketch-panel").hidden, true);
  ui.marker().click();
  assert.equal(ui.byClass("gp-sketch-panel").hidden, false);
  assert.equal(ui.sent.length, before, "Viewing sketches never edits data");
  ui.byText("Stäng").click();
  ui.byText("Minimera").click(); ui.marker().click();
  assert.equal(ui.byClass("gp-sketch-panel").hidden, true);
  ui.byText("Minimera").click();
  Object.assign(ui.tag.values, {lang: 0, isolering: true, F_hl: NaN});
  ui.changed(); ui.marker().click();
  ui.byText("V 150 kN"); ui.byText("V 90 kN");
  ui.byClass("gp-board").clientWidth = 600;
  ui.byText("Visa definitionsskiss").click();
  assert.equal(ui.byClass("gp-sketch-panel").parent, ui.byClass("gp-sketch-slot"));
  ui.byText("Planvy – pelarsula");
  if (!readOnly) {
    ui.field("lang").value = "1"; ui.field("lang").dispatch("input");
    ui.byText("Planvy – väggsula");
    ui.field("F_vy").value = ""; ui.field("F_vy").dispatch("input");
    assert.ok(!ui.elements().some(element => element.textContent === "V 150 kN/m"));
    ui.byText("Minimera").click(); ui.marker().click();
    ui.byText("Planvy – väggsula");
  }
});

for (const readOnly of [false, true]) test(`effective-area plot preserves signed coordinates and phase selection (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  const a = {bx: 2, by: 3, bx_eff: 1.6, by_eff: 2.4, area: 3.84, V: 300,
    Mx: -60, My: 30, ex_placement: .1, ey_placement: -.1,
    ex_moment: .1, ey_moment: -.2, ex: .2, ey: -.3};
  ui.tag.summary.effective_area = {brott: a, bruk: {...a, ex: -.2, ey: .3}};
  ui.marker().click();
  const rectangle = () => ui.find(element => element.getAttribute("class") === "gp-effective-rectangle");
  const outline = () => ui.find(element => element.getAttribute("class") === "gp-footing-outline");
  const get = (element, name) => Number(element.getAttribute(name));
  // Positive x goes right and negative y goes down. Dimensions share one scale.
  assert.ok(get(rectangle(), "x") > get(outline(), "x"));
  assert.ok(get(rectangle(), "y") > get(outline(), "y"));
  near(get(rectangle(), "width") / get(outline(), "width"), .8);
  near(get(rectangle(), "height") / get(outline(), "height"), .8);
  const before = ui.sent.length;
  ui.byClass("gp-area-phase").value = "bruk"; ui.byClass("gp-area-phase").dispatch("change");
  near(get(rectangle(), "x"), get(outline(), "x"));
  near(get(rectangle(), "y"), get(outline(), "y"));
  ui.byText("Minimera").click(); ui.marker().click();
  assert.equal(ui.byClass("gp-area-phase").value, "bruk");
  assert.equal(ui.sent.length, before);
  if (readOnly) {
    ui.tag.status = "stale"; ui.changed();
  } else {
    ui.field("M_insp_l").value = "50"; ui.field("M_insp_l").dispatch("input");
  }
  assert.ok(!ui.elements().some(element => element.getAttribute("class") === "gp-effective-rectangle"));
});

test("heading edits persist before export and pending typing survives older model updates", t => {
  const ui = setup(t);
  const title = ui.byClass("gp-title"), subtitle = ui.byClass("gp-subtitle");
  const original = structuredClone(ui.tag);
  assert.equal(title.value, "Test");
  assert.equal(subtitle.value, "Projektets underrubrik");
  assert.equal(subtitle.tag, "textarea");
  assert.equal(subtitle.rows, 1);
  assert.equal(title.maxLength, 200);
  assert.ok(subtitle.maxLength == null || subtitle.maxLength === -1, "Subtitle must not limit typing to 200 characters");
  title.value = "Hus B"; title.dispatch("input");
  const first = ui.sent.at(-1);
  subtitle.value = "Revision A – ÅÄÖ\nHus B"; subtitle.dispatch("input");
  const latest = ui.sent.at(-1);
  assert.equal(latest.action, "heading");
  assert.equal(latest.title, "Hus B");
  assert.equal(latest.subtitle, "Revision A – ÅÄÖ\nHus B");
  Object.assign(ui.data.state, {title: first.title, subtitle: first.subtitle});
  ui.changed(); ui.ack(first);
  assert.equal(subtitle.value, "Revision A – ÅÄÖ\nHus B", "Earlier response must not discard the newest text");
  ui.byText("Exportera HTML").click();
  assert.equal(ui.sent.at(-1).action, "export_html", "Heading update is sent before the export request");
  Object.assign(ui.data.state, {title: latest.title, subtitle: latest.subtitle});
  ui.changed(); ui.ack(latest);
  assert.equal(title.value, "Hus B");
  assert.equal(subtitle.value, "Revision A – ÅÄÖ\nHus B");
  assert.deepEqual(ui.tag, original);
  const longSubtitle = "Kontroll av bärighet, isolering och H-stabilitet. ".repeat(10) + "\nRevision B";
  subtitle.value = longSubtitle; subtitle.dispatch("input");
  const longEdit = ui.sent.at(-1);
  assert.equal(longEdit.subtitle, longSubtitle);
  Object.assign(ui.data.state, {title: longEdit.title, subtitle: longEdit.subtitle});
  ui.changed(); ui.ack(longEdit);
  assert.equal(subtitle.value, longSubtitle);
});

test("key saves to the kernel file while JSON export downloads a portable copy", async t => {
  const ui = setup(t);
  const save = ui.byText("Spara projekt"), exportJson = ui.byText("Exportera JSON");
  assert.equal(exportJson.hidden, false, "Portable export is available independently of local saving");
  const path = "/notebooks/.an_calcs_grundplan_state.json";
  ui.data.state.storage = {key: "Hus A", path, state_file: ".an_calcs_grundplan_state.json", name: ".an_calcs_grundplan_state.json",
    arguments: "state_file='.an_calcs_grundplan_state.json', key='Hus A'"};
  ui.changed();
  assert.equal(exportJson.hidden, false);
  assert.ok(ui.byClass("gp-project-file").textContent.includes("Hus A"));
  let downloaded;
  t.mock.method(URL, "createObjectURL", blob => { downloaded = blob; return "blob:project-json"; });
  t.mock.method(URL, "revokeObjectURL", () => {});
  t.mock.method(globalThis, "setTimeout", fn => { fn(); return 0; });
  save.click();
  assert.equal(ui.sent.at(-1).action, "save_choices");
  ui.ack(ui.sent.at(-1), {choices: []});
  ui.byText("Spara").click();
  assert.equal(ui.sent.at(-1).action, "save");
  assert.equal(ui.sent.at(-1).state_file, ".an_calcs_grundplan_state.json");
  assert.equal(ui.sent.at(-1).key, "Hus A");
  ui.ack(ui.sent.at(-1), {saved_file: path});
  assert.equal(downloaded, undefined);
  assert.deepEqual(document.downloads, []);
  assert.equal(ui.byClass("gp-status").textContent, "Projektet sparat i " + path);
  const portable = '{"format":"an-calcs-grundplan","version":3}';
  exportJson.click();
  assert.equal(ui.sent.at(-1).action, "export_json");
  ui.ack(ui.sent.at(-1), {download: portable});
  assert.equal(await downloaded.text(), portable);
  assert.equal(downloaded.type, "application/json");
  assert.deepEqual(document.downloads, [{href: "blob:project-json", filename: "grundplan.json"}]);
  ui.data.background = {}; ui.data.state.tags = []; ui.changed();
  assert.equal(save.disabled, false, "An empty named project can be saved");
});

test("save dialog requires project and key, offers existing files and retains failed-save drafts", t => {
  const ui = setup(t);
  ui.byText("Spara projekt").click();
  const panel = ui.byClass("gp-save-panel");
  const project = ui.find(el => el.getAttribute("aria-label") === "Projektfil");
  const key = ui.find(el => el.getAttribute("aria-label") === "key");
  ui.ack(ui.sent.at(-1), {choices: [{name: "hus_a.json", state_file: "hus_a.json", keys: ["Fall 1", "Fall 2"]}]});
  const before = ui.sent.length;
  ui.byText("Spara").click();
  assert.equal(ui.sent.length, before, "Missing fields cannot send a save command");
  assert.ok(ui.byClass("gp-save-error").textContent.includes("projektfil och key"));
  const chooser = ui.find(el => el.getAttribute("aria-label") === "Välj projekt");
  chooser.value = "hus_a.json"; chooser.dispatch("change");
  assert.equal(project.value, "hus_a.json");
  assert.equal(project.hidden, true);
  assert.equal(key.value, "Fall 1");
  const keyChooser = ui.find(el => el.getAttribute("aria-label") === "Välj sparat fall");
  keyChooser.value = "Fall 2"; keyChooser.dispatch("change");
  ui.byText("Spara").click();
  const request = ui.sent.at(-1);
  assert.equal(request.key, "Fall 2");
  ui.ack(request, {ok: false, error: "Skrivfel"});
  assert.equal(panel.hidden, false);
  assert.equal(key.value, "Fall 2");
  assert.equal(ui.byClass("gp-save-error").textContent, "Skrivfel");
  chooser.value = ""; chooser.dispatch("change");
  assert.equal(project.hidden, false);
  project.value = "hus_b.json"; key.value = "Ny";
  ui.byText("Spara").click();
  assert.equal(ui.sent.at(-1).state_file, "hus_b.json");
  ui.ack(ui.sent.at(-1), {saved_file: "/notebooks/hus_b.json", storage: {state_file: "hus_b.json", key: "Ny", name: "hus_b.json", path: "/notebooks/hus_b.json", arguments: "state_file='hus_b.json', key='Ny'"}});
  assert.equal(panel.hidden, true);
  assert.equal(ui.byText("Kopiera projekt + key").disabled, false);
});

test("save destination collisions require confirmation and copying has a selectable fallback", async t => {
  const ui = setup(t);
  ui.byText("Spara projekt").click();
  ui.ack(ui.sent.at(-1), {choices: []});
  ui.find(el => el.getAttribute("aria-label") === "Projektfil").value = "projekt.json";
  ui.find(el => el.getAttribute("aria-label") === "key").value = "A";
  ui.byText("Spara").click();
  const request = ui.sent.at(-1);
  window.confirm = () => false;
  ui.ack(request, {ok: false, conflict: true, error: "Ersätt?"});
  assert.equal(ui.sent.at(-1), request, "Cancel never retries with overwrite permission");
  window.confirm = () => true;
  ui.byText("Spara").click();
  ui.ack(ui.sent.at(-1), {ok: false, conflict: true, error: "Ersätt?"});
  assert.equal(ui.sent.at(-1).overwrite, true);
  const argumentsText = 'state_file="Projekt \'A\'.json", key="Fall \'1\'"';
  const storage = {state_file: "Projekt 'A'.json", key: "Fall '1'", path: "/notebooks/Projekt 'A'.json", name: "Projekt 'A'.json", arguments: argumentsText};
  ui.data.state.storage = storage; ui.changed();
  ui.ack(ui.sent.at(-1), {saved_file: storage.path, storage});
  const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  let copied;
  Object.defineProperty(globalThis, "navigator", {configurable: true, value: {clipboard: {writeText: async text => {copied = text;}}}});
  t.after(() => { if (oldNavigator) Object.defineProperty(globalThis, "navigator", oldNavigator); else delete globalThis.navigator; });
  ui.byText("Kopiera projekt + key").click();
  await Promise.resolve();
  assert.equal(copied, argumentsText);
  assert.ok(ui.byClass("gp-status").textContent.includes("kopierade"));
  navigator.clipboard.writeText = async () => { throw new Error("Clipboard denied"); };
  ui.byText("Kopiera projekt + key").click();
  await Promise.resolve();
  assert.equal(ui.byClass("gp-copy-arguments").hidden, false);
  assert.equal(ui.byClass("gp-copy-arguments").value, argumentsText);
});

for (const [format, mime, content, filename] of [
  ["PDF", "application/pdf", "%PDF-1.4\nTest PDF\n", "plan_med_etiketter.pdf"],
  ["HTML", "text/html;charset=utf-8", "<!doctype html><p>ÅÄÖ · resultat</p>", "plan_resultat.html"],
]) test(format + " export downloads binary data and restores the button after success or failure", async t => {
  const ui = setup(t);
  const button = ui.byText("Exportera " + format);
  let downloaded;
  t.mock.method(URL, "createObjectURL", blob => { downloaded = blob; return "blob:test-pdf"; });
  t.mock.method(URL, "revokeObjectURL", () => {});
  t.mock.method(globalThis, "setTimeout", fn => { fn(); return 0; });
  const original = structuredClone(ui.tag);
  button.dispatch("click");
  const request = ui.sent.at(-1);
  assert.equal(request.action, "export_" + format.toLowerCase());
  assert.equal(button.disabled, true);
  ui.changed();
  assert.equal(button.disabled, true, "A model refresh cannot permit a duplicate export");
  const bytes = new TextEncoder().encode(content);
  ui.ack(request, {filename}, [new DataView(bytes.buffer)]);
  assert.equal(button.disabled, false);
  assert.equal(downloaded.type, mime);
  assert.equal(await downloaded.text(), content);
  assert.deepEqual(document.downloads, [{href: "blob:test-pdf", filename}]);
  assert.deepEqual(ui.tag, original, "Export never changes data or results");
  button.dispatch("click");
  ui.ack(ui.sent.at(-1), {ok: false, error: "PDF-export misslyckades"});
  assert.equal(button.disabled, false);
  assert.equal(document.downloads.length, 1);
  assert.equal(ui.byClass("gp-status").textContent, "PDF-export misslyckades");
  ui.data.background = {}; ui.changed();
  assert.equal(button.disabled, true, "A drawing is required for export");
});

test("standalone result labels open read-only values and remember expanded sections", t => {
  const ui = setup(t, { readOnly: true, standalone: true });
  assert.equal(ui.byClass("gp-title").tag, "h3");
  assert.equal(ui.byClass("gp-title").textContent, "Test");
  assert.equal(ui.byClass("gp-subtitle").tag, "p");
  assert.equal(ui.byClass("gp-subtitle").textContent, "Projektets underrubrik");
  ui.tag.values.lang = 0;
  ui.tag.values.l = 2.4;
  ui.tag.summary.b = 1.8;
  const original = structuredClone(ui.snapshot);
  ui.tag.values.isolerprodukt = "EPS ÅÄÖ <script>literal</script>";
  const forbidden = ["Beräkna", "Kopiera sula", "Ta bort", "Importera/Uppdatera ritning", "Öppna projekt", "Spara projekt", "Kopiera projekt + key", "Exportera JSON", "+ Väggsula", "+ Pelarsula", "Exportera PDF", "Exportera HTML"];
  assert.ok(ui.elements().every(element => !forbidden.includes(element.textContent)));
  ui.marker().click();
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 75 % · bₓ 1,8 m · bᵧ 2,4 m · t 1 m");
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Utan isolering");
  assert.match(ui.marker().getAttribute("aria-label"), /bₓ × bᵧ/);
  assert.equal(ui.byClass("gp-dialog").hidden, false);
  assert.equal(ui.byClass("gp-result-main").children[1].textContent, "75%");
  assert.equal(ui.byText("EPS ÅÄÖ <script>literal</script>").tag, "span");
  const formElements = ui.elements().filter(element => element.closest("form"));
  assert.ok(formElements.every(element => !["input", "select", "textarea"].includes(element.tag)));
  const geometry = () => ui.byText("Geometri").parent;
  assert.equal(geometry().open, false);
  geometry().open = true;
  ui.byText("Minimera").click();
  ui.marker().click();
  assert.equal(geometry().open, true);
  ui.byText("Minimera").click();
  const position = ui.position();
  ui.drag(70, 30);
  assert.deepEqual(ui.position(), position, "Dragging cannot edit exported tag positions");
  const before = ui.byClass("gp-sheet").style.left;
  ui.start(ui.byClass("gp-picture"), 100, 100); ui.move(160, 140); ui.finish(160, 140);
  assert.notEqual(ui.byClass("gp-sheet").style.left, before, "Background still pans");
  ui.byText("Anpassa").click();
  assert.equal(ui.byClass("gp-sheet").style.left, before);
  assert.deepEqual(ui.tag.summary, original.state.tags[0].summary);
});

test("standalone keeps the exported label size without a slider and rejects page and calculation commands", t => {
  const ui = setup(t, { readOnly: true, standalone: true, page: 2 });
  const original = structuredClone(ui.snapshot);
  const replies = [];
  ui.model.on("msg:custom", reply => replies.push(reply));
  assert.equal(ui.elements().some(e => e.className.includes("gp-page-label")), false);
  assert.equal(ui.model.get("background").page, 2);
  assert.equal(ui.byClass("gp-markers").children.length, 1);
  ui.marker().click();
  assert.equal(ui.elements().some(e => e.className.includes("gp-size-label") || e.tag === "input" && e.type === "range"), false);
  assert.equal(ui.model.get("state").label_size, original.state.label_size);
  assert.equal(ui.byClass("gp-dialog").hidden, false);
  for (const action of ["calculate", "update", "delete", "copy", "add", "save", "export_pdf", "sliding", "sliding_placement"]) {
    ui.model.send({ action, id: ui.tag.id, values: { b: 55 }, view: "test", request: 1 });
    assert.equal(replies.at(-1).ok, false);
  }
  ui.model.send({ action: "page", page: 500 });
  assert.equal(replies.at(-1).ok, false);
  ui.model.send({ action: "page", page: 1 });
  assert.equal(replies.at(-1).ok, false);
  assert.equal(ui.model.get("background").page, 2);
  ui.model.send({ action: "label_size", value: NaN });
  assert.equal(replies.at(-1).ok, false);
  assert.deepEqual(ui.snapshot, original, "Display choices do not modify the embedded snapshot");
});

test("tag dragging uses displayed drawing size and sends only position; clicks still open the dialog", t => {
  const ui = setup(t);
  ui.byText("+").dispatch("click"); // Drawing is now 1000 by 750 CSS pixels.
  const original = structuredClone(ui.tag);
  ui.drag(100, 75);
  const request = ui.sent.at(-1);
  assert.deepEqual(Object.keys(request).sort(), ["action", "id", "request", "view", "x", "y"]);
  assert.equal(request.action, "update");
  near(request.x, .4); near(request.y, .5);
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  assert.deepEqual(ui.tag, original, "Moving cannot replace input, label, status or results");
  ui.marker().dispatch("click", { detail: 1 });
  assert.equal(ui.byClass("gp-dialog").hidden, true, "Synthetic click after drag does not open form");
  Object.assign(ui.tag, { x: request.x, y: request.y }); ui.changed(); ui.ack(request);
  ui.start(); ui.finish(300, 300);
  assert.equal(ui.byClass("gp-dialog").hidden, false, "Pointer click opens form");
  ui.byText("Minimera").dispatch("click");
  ui.marker().dispatch("click");
  assert.equal(ui.byClass("gp-dialog").hidden, false, "Keyboard activation opens form");
});

test("older drag acknowledgments cannot undo the newer pending position", t => {
  const ui = setup(t);
  ui.drag(80, 60);
  const first = ui.sent.at(-1);
  ui.drag(80, 60);
  const second = ui.sent.at(-1);
  near(second.x, .5); near(second.y, .6);
  Object.assign(ui.tag, { x: first.x, y: first.y }); ui.changed(); ui.ack(first);
  near(ui.position()[0], second.x); near(ui.position()[1], second.y);
  Object.assign(ui.tag, { x: second.x, y: second.y }); ui.changed(); ui.ack(second);
  near(ui.position()[0], second.x); near(ui.position()[1], second.y);
});

test("pointer cancellation abandons an unfinished drag without sending an update", t => {
  const ui = setup(t);
  ui.start(); ui.move(460, 420);
  near(ui.position()[0], .5);
  ui.viewport.dispatch("pointercancel");
  assert.deepEqual(ui.position(), [.3, .4]);
  assert.equal(ui.sent.length, 0);
  assert.equal(ui.viewport.hasPointerCapture(1), false);
});

test("canceling a second drag preserves the first drag while its kernel update is pending", t => {
  const ui = setup(t);
  ui.drag(80, 60);
  const first = ui.sent.at(-1);
  ui.start(); ui.move(460, 420);
  ui.viewport.dispatch("pointercancel");
  near(ui.position()[0], first.x); near(ui.position()[1], first.y);
  assert.equal(ui.sent.length, 1);
});

test("copy places one independent snapshot with unsynchronized inputs; Escape cancels placement", t => {
  const ui = setup(t);
  ui.marker().dispatch("click");
  ui.field("isolerprodukt").value = "EPS S200, 100 mm – entré"; ui.field("isolerprodukt").dispatch("input");
  assert.match(ui.marker().className, /gp-tag-ok/, "Comments do not make the current calculation stale");
  assert.equal(ui.field("isolerprodukt").required, false);
  assert.equal(ui.sent.at(-1).values.isolerprodukt, "EPS S200, 100 mm – entré");
  ui.field("b").value = "1,20"; ui.field("b").dispatch("input");
  ui.field("F_vy").value = "168"; ui.field("F_vy").dispatch("input");
  ui.byText("Kopiera sula").dispatch("click");
  assert.equal(ui.byClass("gp-dialog").hidden, true);
  assert.equal(ui.byText("Avbryt kopiering").hidden, false);
  assert.equal(ui.tag.values.b, 1, "Kernel has not yet accepted the local edits");
  const pictureRect = ui.byClass("gp-picture").getBoundingClientRect();
  ui.place(); ui.place();
  const copies = ui.sent.filter(request => request.action === "copy");
  assert.equal(copies.length, 1, "Slow kernel response cannot allow duplicate placement");
  assert.equal(copies[0].id, "tag1");
  assert.equal(copies[0].values.b, 1.2);
  assert.equal(copies[0].values.F_vy, 168);
  assert.equal(copies[0].values.phi_k, 1);
  assert.equal(copies[0].values.isolerprodukt, "EPS S200, 100 mm – entré");
  assert.equal(copies[0].page, 1);
  near(copies[0].x, (400 - pictureRect.left) / pictureRect.width);
  near(copies[0].y, (400 - pictureRect.top) / pictureRect.height);
  assert.equal(ui.byText("Avbryt kopiering").hidden, true);
  ui.marker().dispatch("click");
  ui.byText("Kopiera sula").dispatch("click");
  ui.byClass("an-grundplan").dispatch("keydown", { key: "Escape" });
  ui.place();
  assert.equal(ui.sent.filter(request => request.action === "copy").length, 1);
  assert.equal(ui.byText("Avbryt kopiering").hidden, true);
});

test("labels follow drawing zoom while the size control persists their base size", t => {
  const ui = setup(t);
  const slider = ui.find(element => element.type === "range");
  const root = ui.byClass("an-grundplan");
  const sheet = ui.byClass("gp-sheet");
  const initialWidth = sheet.style.width;
  slider.value = 140; slider.dispatch("input");
  assert.equal(root.style["--gp-tag-scale"], "1.4");
  assert.equal(sheet.style.width, initialWidth);
  ui.byText("+").dispatch("click");
  near(parseFloat(sheet.style.width) / parseFloat(initialWidth), 1.25);
  assert.equal(root.style["--gp-tag-scale"], "1.75");
  assert.equal(slider.value, "140", "Zoom changes rendered size, not the saved base size");
  assert.equal(ui.sent.length, 0, "Zoom does not overwrite the project setting");
  slider.dispatch("change");
  const first = ui.sent.at(-1);
  assert.equal(first.action, "label_size"); assert.equal(first.value, 140);
  slider.value = 160; slider.dispatch("input"); slider.dispatch("change");
  const second = ui.sent.at(-1);
  ui.data.state.label_size = 140; ui.changed(); ui.ack(first);
  assert.equal(root.style["--gp-tag-scale"], "2", "Older acknowledgment preserves the current size and zoom");
  ui.data.state.label_size = 160; ui.changed(); ui.ack(second);
  ui.byText("−").dispatch("click");
  assert.equal(root.style["--gp-tag-scale"], "1.6");
  ui.byText("−").dispatch("click");
  near(Number(root.style["--gp-tag-scale"]), 1.28);
  ui.byText("Anpassa").dispatch("click");
  assert.equal(root.style["--gp-tag-scale"], "1.6");
  assert.equal(slider.value, "160");
});

for (const [label, kind] of [["+ Väggsula", "vaggsula"], ["+ Pelarsula", "pelarsula"]]) {
  test(label + " toggles placement and returns to default panning after one tag", t => {
    const ui = setup(t);
    const button = ui.byText(label);
    assert.equal(ui.viewport.style.cursor, "grab");
    button.click();
    assert.equal(button.getAttribute("aria-pressed"), "true");
    assert.equal(ui.viewport.style.cursor, "crosshair");
    button.click();
    assert.equal(button.getAttribute("aria-pressed"), "false");
    assert.equal(ui.viewport.style.cursor, "grab");
    ui.place();
    assert.equal(ui.sent.length, 0, "Canceling the tool cannot place a footing on the next click");
    button.click();
    ui.byClass("an-grundplan").dispatch("keydown", {key: "Escape"});
    ui.place();
    assert.equal(ui.sent.length, 0);
    button.click();
    ui.place();
    assert.equal(ui.sent.at(-1).action, "add");
    assert.equal(ui.sent.at(-1).kind, kind);
    assert.equal(button.getAttribute("aria-pressed"), "false");
    assert.equal(ui.viewport.style.cursor, "grab");
    ui.place();
    assert.equal(ui.sent.filter(request => request.action === "add").length, 1);
  });
}

test("pan moves a fitted drawing freely and Fit restores the centered full drawing", t => {
  const ui = setup(t);
  const sheet = ui.byClass("gp-sheet");
  const picture = ui.byClass("gp-picture");
  const initial = { ...picture.getBoundingClientRect() };
  near(initial.left, (ui.viewport.clientWidth - initial.width) / 2);
  near(initial.top, (ui.viewport.clientHeight - initial.height) / 2);
  assert.ok(initial.left >= 24 && initial.top >= 24, "Fit leaves a margin around the full drawing");
  const originalTag = structuredClone(ui.tag);
  ui.start(picture, 100, 100); ui.move(225, 185); ui.finish(225, 185);
  near(parseFloat(sheet.style.left), initial.left + 125);
  near(parseFloat(sheet.style.top), initial.top + 85);
  assert.deepEqual(ui.tag, originalTag);
  assert.equal(ui.sent.length, 0, "Camera movement does not modify project coordinates");
  ui.byText("+").dispatch("click");
  assert.notEqual(parseFloat(sheet.style.width), initial.width);
  ui.byText("Anpassa").dispatch("click");
  const fitted = picture.getBoundingClientRect();
  near(fitted.left, initial.left); near(fitted.top, initial.top);
  near(fitted.width, initial.width); near(fitted.height, initial.height);
});

for (const readOnly of [false, true]) {
  test("scroll without Shift leaves notebook scrolling enabled and never zooms (readOnly=" + readOnly + ")", t => {
    const ui = setup(t, {readOnly}), picture = ui.byClass("gp-picture");
    const before = picture.getBoundingClientRect();
    let prevented = false;
    for (const modifiers of [{}, {ctrlKey: true}, {metaKey: true}]) {
      ui.viewport.dispatch("wheel", {deltaY: -100, clientX: 200, clientY: 150,
        ...modifiers, preventDefault() {prevented = true;}});
    }
    assert.equal(prevented, false);
    assert.deepEqual(picture.getBoundingClientRect(), before);
    assert.equal(ui.sent.length, 0);
  });

  test("Shift-scroll zoom stays anchored to the pointer and preserves project data (readOnly=" + readOnly + ")", t => {
    const ui = setup(t, {readOnly}), picture = ui.byClass("gp-picture");
    const before = picture.getBoundingClientRect(), state = structuredClone(ui.data.state);
    const pointer = {clientX: 200, clientY: 150};
    let prevented = false;
    ui.viewport.dispatch("wheel", {shiftKey: true, ...pointer, deltaY: -100, deltaMode: 0, preventDefault() {prevented = true;}});
    const after = picture.getBoundingClientRect();
    assert.equal(prevented, true, "Zoom does not scroll the surrounding notebook");
    assert.ok(after.width > before.width);
    near((pointer.clientX - before.left) / before.width, (pointer.clientX - after.left) / after.width);
    near((pointer.clientY - before.top) / before.height, (pointer.clientY - after.top) / after.height);
    near(Number(ui.byClass("an-grundplan").style["--gp-tag-scale"]), after.width / 800);
    ui.viewport.dispatch("wheel", {shiftKey: true, ...pointer, deltaY: 100, deltaMode: 0});
    const restored = picture.getBoundingClientRect();
    near(restored.width, before.width); near(restored.left, before.left); near(restored.top, before.top);
    assert.deepEqual(ui.data.state, state); assert.equal(ui.sent.length, 0);
  });
}

test("wheel units, zoom limits and drag protection work while import placement remains active", t => {
  const ui = setup(t); importFixture(ui);
  const picture = ui.byClass("gp-picture"), before = picture.getBoundingClientRect();
  ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: -3, deltaMode: 1, clientX: 400, clientY: 300});
  near(picture.getBoundingClientRect().width, before.width * Math.exp(48 * .002));
  ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: -1, deltaMode: 2, clientX: 400, clientY: 300});
  const pageWidth = picture.getBoundingClientRect().width;
  for (let n = 0; n < 30; n++) ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: -500, deltaMode: 0, clientX: 400, clientY: 300});
  near(picture.getBoundingClientRect().width, 800 * 4);
  ui.start(picture, 50, 50, {shiftKey: true}); ui.move(80, 80);
  let suppressed = false;
  ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: 200, preventDefault() {suppressed = true;}});
  assert.equal(suppressed, true); near(picture.getBoundingClientRect().width, 800 * 4);
  ui.viewport.dispatch("pointercancel");
  ui.byText("Placera W1 – väggsula (1 av 2)");
  assert.equal(ui.sent.length, 0, "Wheel zoom and canceled selection never pause or advance placement");
  for (let n = 0; n < 30; n++) ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: 500, clientX: 400, clientY: 300});
  near(picture.getBoundingClientRect().width, 800 * .02);
  assert.ok(pageWidth > before.width);
  ui.byText("Anpassa").click();
  near(picture.getBoundingClientRect().width, before.width);
});

test("Shift-scroll zoom accepts a wheel reported as horizontal movement", t => {
  const ui = setup(t), picture = ui.byClass("gp-picture");
  const before = picture.getBoundingClientRect();
  let prevented = false;
  ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: 0, deltaX: -100, deltaMode: 0,
    clientX: 200, clientY: 150, preventDefault() {prevented = true;}});
  assert.equal(prevented, true);
  assert.ok(picture.getBoundingClientRect().width > before.width);
  ui.viewport.dispatch("wheel", {shiftKey: true, deltaY: 0, deltaX: 100, deltaMode: 0, clientX: 200, clientY: 150});
  near(picture.getBoundingClientRect().width, before.width);
});

test("raw input drafts survive minimize and stale calculation acknowledgments", t => {
  const ui = setup(t);
  const reopen = () => { ui.byText("Minimera").dispatch("click"); ui.marker().dispatch("click"); };
  ui.marker().dispatch("click");
  ui.byText("Geometri").parent.open = false;
  ui.byText("Laster – Brott").parent.open = false;
  inputSection(ui, "Isolering").open = true;
  ui.field("b").value = "1,20"; ui.field("b").dispatch("input");
  ui.label().value = "VS2"; ui.label().dispatch("input");
  reopen();
  assert.equal(ui.field("b").value, "1,20");
  assert.equal(ui.label().value, "VS2");
  assert.equal(ui.byText("Geometri").parent.open, false);
  assert.equal(ui.byText("Laster – Brott").parent.open, false);
  assert.equal(inputSection(ui, "Isolering").open, true);
  const other = { ...structuredClone(ui.tag), id: "tag2", label: "VS4" };
  ui.data.state.tags.push(other); ui.changed();
  const open = id => ui.find(element => element.dataset.tagId === id).dispatch("click");
  open(other.id);
  assert.equal(ui.byText("Geometri").parent.open, true, "A new tag starts with its own section settings");
  assert.equal(inputSection(ui, "Isolering").open, false);
  ui.byText("Laster – Bruk").parent.open = true;
  open(ui.tag.id);
  assert.equal(ui.byText("Geometri").parent.open, false);
  assert.equal(inputSection(ui, "Isolering").open, true);
  assert.equal(ui.byText("Laster – Bruk").parent.open, false);
  open(other.id);
  assert.equal(ui.byText("Laster – Bruk").parent.open, true, "Switching tags preserves their independent settings");
  open(ui.tag.id);
  ui.byClass("gp-form").dispatch("submit");
  const first = ui.sent.at(-1);
  ui.label().value = "VS3"; ui.label().dispatch("input");
  ui.ack(first); reopen();
  assert.equal(ui.label().value, "VS3");
  assert.equal(ui.field("b").value, "1,20");
  ui.byClass("gp-form").dispatch("submit");
  const second = ui.sent.at(-1);
  Object.assign(ui.tag, { label: second.label, values: { ...second.values }, status: "calculated" });
  ui.changed(); ui.ack(second); reopen();
  assert.equal(ui.field("b").value, "1,20", "Automatic updates preserve the user’s raw text");
  assert.equal(ui.label().value, "VS3");
});

test("insulation toggles required capacities and service load requirements, retaining editable drafts", t => {
  const ui = setup(t);
  ui.marker().dispatch("click");
  ui.byText("Laster – Brott"); ui.byText("Laster – Bruk"); ui.byText("Isolering");
  const enabled = ui.field("isolering");
  assert.equal(enabled.type, "checkbox");
  assert.equal(enabled.checked, false);
  assert.equal(ui.field("f_d_bruk").parent.hidden, true);
  assert.equal(ui.field("F_vy_bruk").disabled, false);
  assert.equal(ui.field("F_vy_bruk").required, false);
  ui.field("b").value = "1,1"; ui.field("b").dispatch("input");
  const soil = ui.sent.at(-1);
  assert.equal(soil.action, "update", "An edit automatically sends inputs without a calculation button");
  assert.equal(soil.values.isolering, false);
  for (const name of ["l_h", "l_h_bruk", "F_hb_bruk", "F_hl_bruk"]) {
    assert.equal(name in soil.values, false, "Removed lever-arm inputs are not sent for calculation");
  }
  ui.ack(soil);
  enabled.checked = true; enabled.dispatch("input");
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Med isolering", "The draft is shown before the kernel replies");
  assert.equal(ui.byClass("gp-tag-result").textContent, "Uppdaterar…");
  assert.equal(ui.field("f_d_brott").parent.hidden, false);
  assert.equal(ui.field("F_vy_bruk").disabled, false);
  assert.equal(ui.field("F_vy_bruk").required, true);
  const before = ui.sent.length;
  ui.byClass("gp-form").dispatch("submit");
  assert.equal(ui.sent.length, before, "Active insulation requires strengths and an explicit long-term load");
  assert.equal(ui.sent.at(-1).values.isolering, true, "Incomplete insulation inputs are sent so the kernel can display the calculation error");
  for (const [name, value] of [["F_vy_bruk", "70,5"], ["f_d_brott", "200"], ["f_d_bruk", "80"]]) {
    ui.field(name).value = value; ui.field(name).dispatch("input");
  }
  ui.byText("Minimera").dispatch("click"); ui.marker().dispatch("click");
  assert.equal(ui.field("isolering").checked, true);
  assert.equal(ui.field("F_vy_bruk").value, "70,5");
  ui.byClass("gp-form").dispatch("submit");
  const request = ui.sent.at(-1);
  assert.equal(request.action, "update");
  assert.equal(request.values.isolering, true);
  assert.equal(request.values.F_vy_bruk, 70.5);
  assert.equal(request.values.f_d_brott, 200);
  assert.equal(request.values.f_d_bruk, 80);
  ui.field("isolering").checked = false; ui.field("isolering").dispatch("input");
  assert.equal(ui.field("f_d_bruk").value, "80", "Deactivation retains values for reuse");
  ui.ack(request);
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Utan isolering", "An old calculation reply cannot revert the current insulation marker");
  assert.equal(ui.field("isolering").checked, false, "A stale calculation cannot reactivate insulation");
  ui.byText("Kopiera sula").dispatch("click"); ui.place();
  const copy = ui.sent.at(-1);
  assert.equal(copy.action, "copy");
  assert.equal(copy.values.isolering, false);
  assert.equal(copy.values.F_vy_bruk, 70.5);
  assert.equal(copy.values.f_d_bruk, 80);
});

test("labels retain the governing check below insulation, utilization and geometry", t => {
  const ui = setup(t);
  assert.equal(ui.byClass("gp-governing").textContent, "Styrande: Jord · brott");
  assert.match(ui.marker().getAttribute("aria-label"), /styrande: Jord · brott/);
  Object.assign(ui.tag.values, { isolering: true, F_vy_bruk: 70, f_d_brott: 200, f_d_bruk: 50 });
  Object.assign(ui.tag.summary, {
    utnyttjandegrad: 1.6, styrande: "Isolering · bruk",
    kontroller: [
      {label: "Jord · brott", utnyttjandegrad: .75},
      {label: "Isolering · brott", utnyttjandegrad: .575},
      {label: "Isolering · bruk", utnyttjandegrad: 1.6},
    ],
    isolering: Object.fromEntries(["brott", "bruk"].flatMap(phase =>
      ["N", "b_eff", "l_eff", "A_eff", "q_Ed", "f_d"].map(name => ["isolering_" + name + "_" + phase, 1]))),
  });
  ui.changed();
  assert.match(ui.marker().className, /gp-tag-over/);
  assert.equal(ui.marker().children.length, 4);
  assert.equal(ui.byClass("gp-governing").textContent, "Styrande: Isolering · bruk");
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Med isolering");
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 160 % · bₓ 1 m · t 1 m");
  assert.match(ui.marker().title, /styrande: Isolering · bruk/);
  ui.marker().dispatch("click");
  ui.byText("Styrande: Isolering · bruk");
  const checks = ui.byClass("gp-checks").children;
  assert.deepEqual(checks.map(child => child.textContent), [
    "Jord · brott", "75%", "Isolering · brott", "57,5%", "Isolering · bruk", "160%",
  ]);
  assert.match(checks[5].className, /gp-fail/);
  assert.match(checks[1].className, /gp-pass/);
  ui.byText("Isolering – Brott"); ui.byText("Isolering – Bruk · långtidslast");
  const service = () => ui.byText("Isolering – Bruk · långtidslast").parent;
  service().open = true;
  ui.byText("Minimera").dispatch("click"); ui.marker().dispatch("click");
  assert.equal(service().open, true, "Result sections survive minimizing and reopening");
  ui.changed();
  assert.equal(service().open, true, "Kernel refreshes preserve expanded result sections");
  ui.field("b").value = "2"; ui.field("b").dispatch("input");
  assert.ok(ui.marker().children.every(child => child.className !== "gp-governing"), "An outdated governing check must not be shown as current");
  ui.byClass("gp-form").dispatch("submit");
  const request = ui.sent.at(-1);
  Object.assign(ui.tag, { values: { ...request.values }, status: "calculated" });
  ui.changed(); ui.ack(request);
  assert.equal(service().open, true, "Expanded results return after recalculation");
  service().open = false;
  ui.byClass("an-grundplan").dispatch("keydown", { key: "Escape" });
  ui.marker().dispatch("click");
  assert.equal(service().open, false, "Collapsed result sections also survive closing with Escape");
});

const onlyHSummary = {endast_h_stabilitet: true, utnyttjandegrad: null, b: 1, kontroller: []};

test("H-only checkbox hides bearing inputs, keeps stored values and restores them when unchecked", t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {b: .95, l: 2.4, l_override: true, isolering: true,
    glid_x: true, V_Ed_EQU: 120, glid_mu: .4, glid_L: 3});
  ui.tag.sliding = {x: 144, y: 0, status: "ready"}; ui.changed();
  ui.marker().click();
  const toggle = ui.field("endast_h_stabilitet");
  toggle.checked = true; toggle.dispatch("input");
  assert.equal(ui.sent.at(-1).values.endast_h_stabilitet, true);
  assert.equal(ui.sent.at(-1).values.isolering, false);
  assert.equal(ui.field("isolering").checked, false);
  assert.equal(ui.field("isolering").parent.parent.hidden, true);
  assert.equal(ui.sent.at(-1).values.F_vy, 1, "Unused bearing values are preserved");
  assert.equal(ui.field("F_vy").parent.parent.hidden, true);
  assert.equal(ui.field("phi_k").disabled, true);
  assert.equal(ui.field("t").parent.hidden, true);
  for (const name of ["b", "l", "l_override"]) {
    assert.equal(ui.field(name).parent.hidden, true);
    assert.equal(ui.field(name).disabled, true);
  }
  assert.equal(ui.sent.at(-1).values.b, .95);
  assert.equal(ui.sent.at(-1).values.l, 2.4, "A hidden overridden wall dimension is preserved");
  assert.equal(ui.sent.at(-1).values.l_override, true);
  assert.equal(ui.field("glid_L").disabled, false);
  assert.equal(ui.field("V_Ed_EQU").parent.parent.hidden, false, "Gliding data can be configured without global control");
  Object.assign(ui.tag.values, ui.sent.at(-1).values);
  ui.tag.summary = structuredClone(onlyHSummary); ui.changed(); ui.ack(ui.sent.at(-1));
  assert.ok(ui.marker().className.includes("gp-tag-horizontal"));
  assert.ok(ui.byClass("gp-tag-result").textContent.startsWith("Endast H-stabilitet"));
  assert.equal(ui.marker().getAttribute("aria-label").includes("bₓ"), false);
  assert.equal(ui.byClass("gp-tag-sliding-capacities").children[1].textContent, "144 kN");
  assert.equal(ui.elements().some(e => e.className.includes("gp-tag-load-row")), false);
  assert.equal(ui.elements().some(e => e.className === "gp-governing"), false);
  assert.equal(ui.elements().some(e => e.className.includes("gp-result-main")), false);
  assert.equal(tableField(ui, "tag1", "F_vy").disabled, true);
  assert.equal(tableField(ui, "tag1", "isolering").disabled, true);
  assert.equal(tableField(ui, "tag1", "isolering").checked, false);
  assert.ok(ui.marker().getAttribute("aria-label").includes("Utan isolering"));
  assert.equal(ui.byClass("gp-sketch-toggle").hidden, true);
  toggle.checked = false; toggle.dispatch("input");
  assert.equal(ui.field("F_vy").parent.parent.hidden, false);
  assert.equal(ui.field("F_vy").value, "1");
  assert.equal(ui.field("phi_k").disabled, false);
  assert.equal(ui.field("b").parent.hidden, false);
  assert.equal(ui.field("l").parent.hidden, false);
  assert.equal(ui.field("l").disabled, false);
  assert.equal(ui.field("l").value, "2.4");
  assert.equal(ui.field("l_override").checked, true);
  assert.equal(ui.field("isolering").parent.parent.hidden, false);
  assert.equal(ui.field("isolering").checked, false);
  assert.equal(ui.byClass("gp-sketch-toggle").hidden, false);
});

test("H-only table checkbox changes selected walls and pads together", t => {
  const ui = setup(t), pad = {...structuredClone(ui.tag), id: "pad", label: "PS1"};
  ui.tag.values.isolering = pad.values.isolering = true;
  pad.values.lang = 0; ui.data.state.tags.push(pad); ui.changed();
  selectTableRow(ui, "VS1"); selectTableRow(ui, "PS1");
  const toggle = tableField(ui, "tag1", "endast_h_stabilitet");
  assert.equal(toggle.disabled, false);
  toggle.checked = true; toggle.dispatch("change");
  assert.equal(ui.sent.at(-1).action, "bulk_update");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "pad"]);
  assert.deepEqual(ui.sent.at(-1).values, {endast_h_stabilitet: true});
  assert.ok(ui.elements().filter(e => e.name === "table_isolering").every(e => !e.checked && e.disabled));
  for (const tag of ui.data.state.tags) {
    tag.values.endast_h_stabilitet = true; tag.values.isolering = false; tag.summary = structuredClone(onlyHSummary);
  }
  ui.changed(); ui.ack(ui.sent.at(-1));
  for (const id of ["tag1", "pad"]) {
    assert.equal(tableField(ui, id, "F_vy").disabled, true);
    for (const name of ["b", "l", "l_override"]) assert.equal(tableField(ui, id, name).disabled, true);
  }
  assert.equal(ui.elements().filter(e => e.textContent === "Endast H").length, 3);
  ui.byText("Ändra markerade").click();
  assert.equal(ui.elements().some(e => e.name === "bulk_isolering"), false);
  for (const name of ["b", "l", "l_override"]) assert.equal(ui.elements().some(e => e.name === "bulk_" + name), false);
});

test("read-only H-only labels and results have no bearing utilization or inactive loads", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  Object.assign(ui.tag.values, {endast_h_stabilitet: true, glid_x: true, V_Ed_EQU: 120, glid_mu: .4, glid_L: 3});
  ui.tag.summary = structuredClone(onlyHSummary); ui.tag.sliding = {x: 144, y: 0, status: "ready"}; ui.changed();
  assert.ok(ui.marker().className.includes("gp-tag-horizontal"));
  assert.equal(resultTableValue(ui, "tag1", "endast_h_stabilitet").textContent, "Ja");
  assert.equal(resultTableValue(ui, "tag1", "F_vy").textContent, "—");
  for (const name of ["b", "l", "l_override"]) assert.equal(resultTableValue(ui, "tag1", name).textContent, "—");
  ui.marker().click();
  const insulationRow = ui.elements().find(e => e.className.includes("gp-field") && e.children.some(child => child.textContent === "isolering"));
  assert.ok(insulationRow?.parent.hidden);
  for (const name of ["b", "l"]) {
    const row = ui.elements().find(e => e.className.split(" ").includes("gp-field") && e.children.some(child => child.textContent === name));
    assert.equal(row?.hidden, true);
  }
  assert.equal(ui.elements().some(e => e.className.includes("gp-result-main")), false);
  assert.ok(ui.elements().some(e => e.tag === "dd" && e.textContent === "144 kN"));
  assert.equal(ui.elements().some(e => e.className.includes("gp-tag-load-row")), false);
  assert.equal(ui.sent.length, 0);
});

const defaultColour = {enabled: false, category: "t", secondary: null, phase: "brott", edit_type: "pad", show_legend: true,
  bounds: {pad: [100, 200, 400], wall: [100, 200, 400]}, colors: {}, legend: {x: .65, y: .08, size: 300}};
function colourFixture(ui, changes = {}) {
  ui.data.state.colour_grouping = {...structuredClone(defaultColour), enabled: true, ...changes};
  ui.model.get("state").colour_grouping = ui.data.state.colour_grouping;
  ui.changed();
  const accept = request => {
    const settings = ui.data.state.colour_grouping;
    if (request.action === "colour_grouping") {
      const patch = request.settings;
      const next = {...settings, ...patch};
      for (const name of ["bounds", "colors", "legend"]) if (patch[name]) next[name] = {...settings[name], ...patch[name]};
      ui.data.state.colour_grouping = next;
    } else if (request.action === "colour_placement") ui.data.state.colour_grouping.legend = request.position;
    ui.changed(); ui.ack(request);
  };
  return accept;
}

test("colour grouping toggles without losing categories, colours, bounds or legend size", t => {
  const ui = setup(t);
  const accept = colourFixture(ui, {category: "V", phase: "EQU", edit_type: "wall", bounds: {pad: [100, 300], wall: [10, 20]},
    colors: {na: "#123456"}, legend: {x: .2, y: .4, size: 420}});
  const original = structuredClone(ui.data.state), toggle = ui.byClass("gp-colour-controls");
  const feature = ui.elements().find(e => e.tag === "button" && e.textContent === "Färggruppering" && e.closest(".gp-toolbar"));
  assert.equal(feature.getAttribute("aria-pressed"), "true");
  feature.click();
  assert.equal(toggle.hidden, true);
  assert.equal(ui.byClass("gp-colour-legend").hidden, true);
  assert.equal(ui.marker().style["--gp-tag-bg"], undefined);
  assert.deepEqual(ui.sent.at(-1).settings, {enabled: false}); accept(ui.sent.at(-1));
  feature.click(); accept(ui.sent.at(-1));
  assert.deepEqual(ui.data.state, original);
  assert.equal(ui.byClass("gp-colour-legend").style.transform, "scale(1.4)");
  assert.equal(feature.getAttribute("aria-pressed"), "true");
});

test("group category and phase buttons recolour labels without changing footing values or status", t => {
  const ui = setup(t), accept = colourFixture(ui);
  Object.assign(ui.tag.values, {t: .3, b: .6, l: 1, F_vy: 150, F_vy_bruk: 99.9999, V_Ed_EQU: 400}); ui.changed();
  const before = structuredClone(ui.tag);
  for (const [caption, category] of [["Bredd bₓ", "b"], ["Längd bᵧ", "l"], ["Vertikallast V", "V"]]) {
    const choice = ui.byText(caption); choice.click();
    assert.equal(ui.sent.at(-1).action, "colour_grouping");
    assert.deepEqual(ui.sent.at(-1).settings, {secondary: category});
    const previous = ui.data.state.colour_grouping.category; accept(ui.sent.at(-1));
    ui.byText({t: "Tjocklek t", b: "Bredd bₓ", l: "Längd bᵧ"}[previous]).click();
    assert.deepEqual(ui.sent.at(-1).settings, {category, secondary: null});
    assert.equal(choice.getAttribute("aria-pressed"), "true"); accept(ui.sent.at(-1));
    assert.ok(ui.marker().style["--gp-tag-bg"].startsWith("#"));
    assert.ok(ui.marker().className.includes("gp-tag-ok"));
  }
  ui.find(e => e.tag === "button" && e.textContent === "Bruk").click(); accept(ui.sent.at(-1));
  assert.ok(ui.marker().title.includes("V < 100"));
  ui.find(e => e.tag === "button" && e.textContent === "EQU").click(); accept(ui.sent.at(-1));
  assert.ok(ui.marker().title.includes("V ≥ 400"));
  assert.deepEqual(ui.tag, before);
  assert.equal(ui.byClass("gp-colour-bounds").parent.hidden, false);
});

test("custom intervals accept decimal comma with semicolons, validate boundaries and keep separate wall bounds", t => {
  const ui = setup(t), accept = colourFixture(ui, {category: "V"});
  const field = ui.find(e => e.getAttribute("aria-label") === "Intervallgränser för färggruppering");
  field.value = "100,5; 200,5; 399,5"; field.dispatch("change");
  assert.deepEqual(ui.sent.at(-1).settings, {bounds: {pad: [100.5, 200.5, 399.5]}}); accept(ui.sent.at(-1));
  ui.byText("Linjelaster [kN/m]").click(); accept(ui.sent.at(-1));
  assert.equal(field.value, "100; 200; 400");
  field.value = "100, 300, 600"; field.dispatch("change"); accept(ui.sent.at(-1));
  assert.deepEqual(ui.data.state.colour_grouping.bounds, {pad: [100.5, 200.5, 399.5], wall: [100, 300, 600]});
  for (const value of ["", "100; 100", "200; 100", "100; NaN", "100;"]) {
    const before = ui.sent.length; field.value = value; field.dispatch("change");
    assert.equal(ui.sent.length, before); assert.ok(field.validityMessage);
  }
  ui.byText("Totala laster [kN]").click(); accept(ui.sent.at(-1));
  assert.equal(field.value, "100,5; 200,5; 399,5");
  assert.equal(field.validityMessage, "", "Changing footing type restores its valid saved intervals");
  assert.equal(ui.byClass("gp-colour-error").textContent, "");
  field.value = "50; 150"; field.dispatch("change"); accept(ui.sent.at(-1));
  assert.equal(field.validityMessage, "");
});

test("custom colours and legend checkbox persist while status remains unchanged", t => {
  const ui = setup(t), accept = colourFixture(ui);
  const input = ui.find(e => e.type === "color" && e.closest(".gp-colour-swatches"));
  const before = structuredClone(ui.tag);
  input.value = "#0000ff"; input.dispatch("change"); accept(ui.sent.at(-1));
  const key = ui.marker().dataset.colourGroup;
  assert.equal(ui.data.state.colour_grouping.colors[key], "#0000ff");
  assert.equal(ui.marker().style["--gp-tag-bg"], "#b3b3ff");
  const check = ui.find(e => e.getAttribute("aria-label") === "Visa färglegend");
  check.checked = false; check.dispatch("change"); accept(ui.sent.at(-1));
  assert.equal(ui.byClass("gp-colour-legend").hidden, true);
  assert.equal(ui.marker().style["--gp-tag-bg"], "#b3b3ff");
  check.checked = true; check.dispatch("change"); accept(ui.sent.at(-1));
  assert.equal(ui.byClass("gp-colour-legend").hidden, false);
  assert.deepEqual(ui.tag, before);
});

for (const readOnly of [false, true]) test(`five insulation colours follow selected global directions including H-only (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly, standalone: readOnly});
  Object.assign(ui.tag.values, {isolering: true, glid_x: true, glid_y: true});
  const footings = [
    ["pad", {lang: 0, isolering: false, glid_x: false, glid_y: false}],
    ["x", {isolering: false, glid_x: true, glid_y: false, glid_mu: null}],
    ["y", {lang: 0, isolering: false, glid_x: false, glid_y: true, V_Ed_EQU: 0}],
    ["xy", {isolering: false}],
    ["horizontal", {endast_h_stabilitet: true, glid_x: false}],
  ].map(([id, values]) => ({...structuredClone(ui.tag), id, label: id, values: {...ui.tag.values, ...values}}));
  ui.data.state.tags.push(...footings); ui.model.get("state").tags = ui.data.state.tags;
  const before = structuredClone(ui.data.state.tags);
  const accept = colourFixture(ui, {category: readOnly ? "isolering" : "t"});
  if (!readOnly) {
    ui.find(e => e.tag === "button" && e.textContent === "Isolering" && e.closest(".gp-colour-controls")).click();
    assert.deepEqual(ui.sent.at(-1).settings, {secondary: "isolering"}); accept(ui.sent.at(-1));
    ui.byText("Tjocklek t").click(); accept(ui.sent.at(-1));
    assert.equal(ui.byClass("gp-colour-bounds").parent.hidden, true);
  }
  const text = element => element.textContent + element.children.map(text).join("");
  const rows = () => ui.elements().filter(e => e.className === "gp-colour-legend-row")
    .map(row => row.children.slice(1).map(text));
  const captions = ["Med isolering · inget bidrag", "Utan isolering · inget bidrag", "Utan isolering · bidrag i Xg",
    "Utan isolering · bidrag i Yg", "Utan isolering · bidrag i Xg och Yg"];
  const counts = values => captions.flatMap((caption, i) => values[i] > 0 ? [[caption, String(values[i])]] : []);
  assert.deepEqual(rows(), counts([1, 1, 1, 2, 1]));
  assert.equal(ui.byClass("gp-colour-legend-title").textContent, "Isolering och glidmotstånd");
  assert.equal(ui.elements().filter(e => e.tag === "sub" && e.closest(".gp-colour-legend")).length, 4);
  const marker = id => ui.find(e => e.className.split(" ").includes("gp-tag") && e.dataset.tagId === id);
  assert.equal(new Set(["tag1", "pad", "x", "y", "xy"].map(id => marker(id).style["--gp-tag-bg"])).size, 5);
  assert.equal(marker("y").style["--gp-tag-bg"], marker("horizontal").style["--gp-tag-bg"]);
  for (const [id, suffix] of [["tag1", "1"], ["pad", "0"], ["x", "x"], ["y", "y"], ["xy", "xy"], ["horizontal", "y"]]) {
    assert.equal(marker(id).dataset.colourGroup, "isolering:" + suffix);
    assert.ok(marker(id).className.includes(id === "horizontal" ? "gp-tag-horizontal" : "gp-tag-ok"),
      "Grouping keeps the calculation status");
  }
  assert.deepEqual(ui.data.state.tags, before, "Colour grouping leaves inputs and results unchanged");
  ui.tag.values.isolering = false; ui.changed();
  assert.deepEqual(rows(), counts([0, 1, 1, 2, 2]));
  assert.equal(marker("tag1").style["--gp-tag-bg"], marker("xy").style["--gp-tag-bg"]);
  ui.tag.values.glid_y = false; ui.changed();
  assert.deepEqual(rows(), counts([0, 1, 2, 2, 1]));
  assert.equal(marker("tag1").style["--gp-tag-bg"], marker("x").style["--gp-tag-bg"]);
  ui.tag.values.isolering = true; ui.changed();
  assert.deepEqual(rows(), counts([1, 1, 1, 2, 1]), "A group returns when a footing uses it again");
  assert.equal(marker("tag1").style["--gp-tag-bg"], "#cce7ff");
  if (readOnly) assert.equal(ui.sent.length, 0);
  else {
    const picker = ui.find(e => e.type === "color" && e.getAttribute("aria-label") === "Färg för Utan isolering · bidrag i X_g och Y_g");
    picker.value = "#c8e0d8"; picker.dispatch("change"); accept(ui.sent.at(-1));
    assert.deepEqual(ui.sent.at(-1).settings, {colors: {"isolering:xy": "#c8e0d8"}});
    assert.equal(marker("xy").style["--gp-tag-bg"], "#c8e0d8");
    assert.equal(marker("x").style["--gp-tag-bg"], "#ffdfba");
  }
});

for (const readOnly of [false, true]) test(`load legends show occupied intervals while retaining all colour choices (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly, standalone: readOnly});
  Object.assign(ui.tag.values, {lang: 0, F_vy: 150});
  ui.model.get("state").tags = ui.data.state.tags;
  colourFixture(ui, {category: "V", colors: {"V:brott:pad:2.000000000000e2:4.000000000000e2": "#c8e0d8"}});
  const rows = () => ui.elements().filter(e => e.className === "gp-colour-legend-row")
    .map(row => row.children[1].textContent);
  assert.deepEqual(rows(), ["100 ≤ V < 200"]);
  if (!readOnly) assert.equal(ui.elements().filter(e => e.type === "color").length, 4);
  ui.tag.values.F_vy = 250; ui.changed();
  assert.deepEqual(rows(), ["200 ≤ V < 400"]);
  assert.equal(ui.marker().style["--gp-tag-bg"], "#c8e0d8", "A previously empty interval keeps its saved colour");
  ui.data.state.tags = []; ui.model.get("state").tags = []; ui.changed();
  assert.deepEqual(rows(), []);
  assert.equal(ui.elements().filter(e => e.className === "gp-colour-legend-section").length, 0);
});

test("colour legend moves, scales with corner and zoom, cancels drags and supports keyboard", t => {
  const ui = setup(t), accept = colourFixture(ui);
  const legend = ui.byClass("gp-colour-legend"), header = ui.find(e => e.tag === "button" && e.closest(".gp-colour-legend")), handle = ui.byClass("gp-colour-resize");
  header.click(); assert.equal(handle.hidden, false);
  ui.start(header); ui.move(380, 360); ui.finish(380, 360);
  let request = ui.sent.at(-1);
  assert.equal(request.action, "colour_placement"); near(request.position.x, .75); near(request.position.y, .18);
  accept(request);
  ui.start(handle); ui.move(450, 410); ui.finish(450, 410);
  request = ui.sent.at(-1); near(request.position.size, 450); accept(request);
  assert.equal(legend.style.transform, "scale(1.5)");
  ui.byText("+").click(); assert.equal(legend.style.transform, "scale(1.875)");
  const count = ui.sent.length;
  ui.start(handle); ui.move(550, 550); ui.viewport.dispatch("pointercancel");
  assert.equal(ui.sent.length, count); assert.equal(legend.style.transform, "scale(1.875)");
  handle.dispatch("keydown", {key: "-", shiftKey: true});
  near(ui.sent.at(-1).position.size, 430); accept(ui.sent.at(-1));
  header.dispatch("keydown", {key: "ArrowLeft"});
  near(ui.sent.at(-1).position.x, .75 - 5 / 800);
});

test("read-only HTML keeps grouping and legend with no editing commands", t => {
  const ui = setup(t, {readOnly: true, standalone: true}); colourFixture(ui, {category: "b"});
  assert.ok(ui.marker().style["--gp-tag-bg"].startsWith("#"));
  assert.equal(ui.byClass("gp-colour-legend").hidden, false);
  assert.equal(ui.byClass("gp-colour-resize").hidden, true);
  assert.equal(ui.elements().some(e => e.className.includes("gp-colour-controls")), false);
  const before = structuredClone(ui.data.state), header = ui.find(e => e.tag === "button" && e.closest(".gp-colour-legend"));
  ui.start(header); ui.move(500, 500); ui.finish(500, 500);
  header.dispatch("keydown", {key: "ArrowLeft"});
  assert.deepEqual(ui.data.state, before); assert.equal(ui.sent.length, 0);
});

const tableFold = (ui, label) => ui.find(e => e.getAttribute("aria-label") === "Visa eller dölj " + label);
for (const readOnly of [false, true]) test(`table groups fold independently, restore saved choices and preserve controls (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly, standalone: readOnly});
  const cell = ui.find(e => e.dataset.field === "b" && e.dataset.tagId === "tag1").parent;
  const geometry = tableFold(ui, "Geometri"), original = structuredClone(ui.model.get("state").tags);
  geometry.click();
  assert.equal(geometry.getAttribute("aria-expanded"), "false");
  assert.equal(geometry.parent.getAttribute("colspan"), "1");
  assert.equal(cell.hidden, true);
  assert.equal(tableSortButton(ui, "label").parent.hidden, false);
  const comment = ui.find(e => e.dataset.field === "kommentar" && e.dataset.tagId === "tag1");
  assert.equal(comment.parent.hidden, false);
  tableFold(ui, "Laster – Brott").click();
  assert.equal(geometry.getAttribute("aria-expanded"), "false");
  geometry.click();
  assert.equal(geometry.getAttribute("aria-expanded"), "true");
  assert.equal(cell.hidden, false);
  assert.equal(tableFold(ui, "Laster – Brott").getAttribute("aria-expanded"), "false");
  if (readOnly) assert.deepEqual(ui.model.get("state").table_view.collapsed, ["F_vy"]);
  else {
    const request = ui.sent.at(-1);
    ui.data.state.table_view = {collapsed: ["F_vy", "kommentar"], sort: {key: "b", direction: "descending"}};
    ui.changed(); ui.ack(request);
    assert.equal(comment.parent.hidden, true);
    assert.equal(tableSortButton(ui, "b").parent.getAttribute("aria-sort"), "descending");
  }
  assert.deepEqual(ui.model.get("state").tags, original);
});

test("all columns sort numerically or by text with natural littera ties and missing values last", t => {
  const ui = setup(t);
  const ids = ["tag1", "tag2", "tag3", "tag4"];
  ui.data.state.tags = [
    {id: "tag1", label: "VS10", values: {b: .6, kommentar: "B", glid_x: true, glid_mu: .4}},
    {id: "tag2", label: "VS2", values: {b: .6, kommentar: "A", glid_x: false, glid_mu: .5}},
    {id: "tag3", label: "VS1", values: {b: 1.4, kommentar: "A", glid_x: false, glid_mu: null}},
    {id: "tag4", label: "VS4", values: {b: .4, kommentar: "", endast_h_stabilitet: true, glid_mu: .6}},
  ].map(item => ({...structuredClone(ui.tag), ...item, values: {...ui.tag.values, ...item.values}}));
  ui.changed();
  assert.equal(ui.elements().filter(e => e.className === "gp-table-sort").length, names.length + 4);
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1", "tag3", "tag4"]);
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag1", "tag4"]);
  tableSortButton(ui, "kommentar").click();
  assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag1", "tag4"]);
  tableSortButton(ui, "kommentar").click();
  assert.deepEqual(tableOrder(ui), ["tag1", "tag3", "tag2", "tag4"]);
  tableSortButton(ui, "glid_x").click();
  assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag4", "tag1"]);
  tableSortButton(ui, "glid_mu").click();
  assert.deepEqual(tableOrder(ui), ["tag1", "tag2", "tag4", "tag3"]);
  tableSortButton(ui, "glid_mu").click();
  assert.deepEqual(tableOrder(ui), ["tag4", "tag2", "tag1", "tag3"]);
  assert.deepEqual(ui.data.state.tags.map(tag => tag.id), ids);
});

test("standalone HTML sorting and folding are local and cannot edit comments or input values", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  ui.model.get("state").tags.push({...structuredClone(ui.tag), id: "tag2", label: "VS2", values: {...ui.tag.values, b: .4}});
  ui.changed();
  const before = structuredClone(ui.model.get("state").tags);
  tableSortButton(ui, "b").click();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1"]);
  tableFold(ui, "Geometri").click();
  assert.deepEqual(ui.model.get("state").table_view, {collapsed: ["lang"], sort: {key: "b", direction: "ascending"}});
  ui.model.send({action: "update", id: "tag1", values: {kommentar: "Ändrat"}});
  ui.model.send({action: "table_view", settings: {sort: {key: "unknown", direction: "ascending"}}});
  assert.equal(ui.model.get("state").table_view.sort.key, "b");
  assert.deepEqual(ui.model.get("state").tags, before);
});

for (const readOnly of [false, true]) test(`comment bubble is conditional, opens the comment section and never drags (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  assert.equal(ui.elements().some(e => e.className === "gp-tag-comment"), false);
  ui.tag.values.kommentar = " \n "; ui.changed();
  assert.equal(ui.elements().some(e => e.className === "gp-tag-comment"), false);
  ui.tag.values.kommentar = "Kontrollera entré\nJustera last"; ui.changed();
  const bubble = ui.byClass("gp-tag-comment");
  assert.equal(bubble.title, ui.tag.values.kommentar);
  assert.equal(bubble.children[0].children.filter(e => e.tag === "circle").length, 3);
  ui.start(bubble); ui.move(700, 650); ui.finish(700, 650);
  assert.equal(ui.sent.length, 0);
  bubble.click();
  const section = inputSection(ui, "Kommentar");
  assert.equal(section.open, true); assert.equal(section.hidden, false);
  if (readOnly) {
    assert.ok(ui.elements().some(e => e.className === "gp-value" && e.textContent === ui.tag.values.kommentar));
    assert.equal(ui.elements().some(e => e.tag === "textarea"), false);
  } else {
    assert.equal(document.activeElement, ui.field("kommentar"));
    assert.equal(ui.field("kommentar").tag, "textarea");
    ui.field("kommentar").value = "Ny\nkommentar"; ui.field("kommentar").dispatch("input");
    assert.equal(ui.sent.at(-1).action, "update"); assert.equal(ui.sent.at(-1).values.kommentar, "Ny\nkommentar");
    assert.match(ui.marker().className, /gp-tag-ok/);
  }
});

test("multiline table comments edit all selected mixed types without invalidating bearing", t => {
  const ui = setup(t), bulk = bulkFixture(ui); bulk.second.values.lang = 0; ui.changed();
  selectTableRow(ui, "VS1"); selectTableRow(ui, "VS2");
  const control = tableField(ui, "tag1", "kommentar");
  assert.equal(control.tag, "textarea"); assert.equal(control.disabled, false);
  control.focus(); control.value = "Gemensam\nkommentar"; control.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"]);
  assert.deepEqual(ui.sent.at(-1).values, {kommentar: "Gemensam\nkommentar"});
  let prevented = false;
  control.dispatch("keydown", {key: "Enter", shiftKey: true, preventDefault() {prevented = true;}});
  assert.equal(prevented, false); assert.equal(document.activeElement, control);
  assert.equal(ui.elements().filter(e => e.className === "gp-tag-comment").length, 2);
  assert.ok(ui.elements().filter(e => e.className.split(" ").includes("gp-tag")).every(e => e.className.includes("gp-tag-ok")));
});

test("two category buttons produce combination colours and allow deselecting either choice", t => {
  const ui = setup(t), accept = colourFixture(ui);
  Object.assign(ui.tag.values, {t: .3, b: .6});
  ui.data.state.tags.push(...[
    {id: "tag2", label: "VS2", values: {t: .3, b: .6}},
    {id: "tag3", label: "VS3", values: {t: .3, b: .8}},
    {id: "tag4", label: "VS4", values: {t: .4, b: .6}},
  ].map(item => ({...structuredClone(ui.tag), ...item, values: {...ui.tag.values, ...item.values}})));
  ui.changed(); ui.byText("Bredd bₓ").click(); accept(ui.sent.at(-1));
  assert.equal(ui.byText("Tjocklek t").getAttribute("aria-pressed"), "true");
  assert.equal(ui.byText("Bredd bₓ").getAttribute("aria-pressed"), "true");
  assert.equal(ui.byText("Vertikallast V").disabled, true);
  const markers = ui.elements().filter(e => e.className.split(" ").includes("gp-tag"));
  assert.equal(markers[0].dataset.colourGroup, markers[1].dataset.colourGroup);
  assert.equal(new Set(markers.map(e => e.style["--gp-tag-bg"])).size, 3);
  assert.equal(ui.elements().filter(e => e.className === "gp-colour-legend-row").length, 3);
  const input = ui.find(e => e.type === "color"); input.value = "#c8e0d8"; input.dispatch("change"); accept(ui.sent.at(-1));
  const saved = structuredClone(ui.data.state.colour_grouping);
  ui.byText("Färggruppering").click(); accept(ui.sent.at(-1));
  ui.byText("Färggruppering").click(); accept(ui.sent.at(-1));
  assert.deepEqual(ui.data.state.colour_grouping, saved);
  ui.byText("Tjocklek t").click(); accept(ui.sent.at(-1));
  assert.equal(ui.data.state.colour_grouping.category, "b"); assert.equal(ui.data.state.colour_grouping.secondary, null);
  ui.byText("Vertikallast V").click(); accept(ui.sent.at(-1));
  assert.equal(ui.byClass("gp-colour-bounds").parent.hidden, false, "V interval controls also work as the second category");
});

for (const readOnly of [false, true]) test(`insulation widget excludes H-only footings from counts and uninsulated littera (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  Object.assign(ui.tag.values, {isolering: true});
  ui.data.state.tags.push(...[
    {id: "tag2", label: "VS10", values: {isolering: false}},
    {id: "tag3", label: "VS2", values: {isolering: false}},
    {id: "tag4", label: "VS1", values: {isolering: true, endast_h_stabilitet: true}},
    {id: "tag5", label: "H-GR.1", values: {isolering: false, endast_h_stabilitet: true}},
  ].map(item => ({...structuredClone(ui.tag), ...item, values: {...ui.tag.values, ...item.values}})));
  ui.data.state.insulation_widget = {enabled: true, x: .65, y: .55, size: 450}; ui.changed();
  assert.equal(ui.byClass("gp-insulation-widget").hidden, false);
  assert.equal(ui.byClass("gp-insulation-widget").style.transform, "scale(1.5)");
  assert.deepEqual(ui.elements().filter(e => e.className === "gp-insulation-count").map(e => e.children.map(child => child.textContent)),
    [["Med isolering", "1"], ["Utan isolering", "2"]]);
  assert.equal(ui.byClass("gp-insulation-list").textContent, "VS2, VS10");
  ui.data.state.tags = ui.data.state.tags.filter(tag => tag.values.endast_h_stabilitet); ui.changed();
  assert.deepEqual(ui.elements().filter(e => e.className === "gp-insulation-count").map(e => e.children.map(child => child.textContent)),
    [["Med isolering", "0"], ["Utan isolering", "0"]]);
  assert.equal(ui.byClass("gp-insulation-list").textContent, "Inga sulor");
  if (readOnly) assert.equal(ui.byClass("gp-insulation-resize").hidden, true);
});

test("insulation widget immediately excludes a footing changed to H-only before the kernel replies", t => {
  const ui = setup(t);
  ui.data.state.insulation_widget = {enabled: true, x: .65, y: .55, size: 300}; ui.changed();
  const counts = () => ui.elements().filter(e => e.className === "gp-insulation-count").map(e => e.children[1].textContent);
  assert.deepEqual(counts(), ["0", "1"]);
  assert.equal(ui.byClass("gp-insulation-list").textContent, "VS1");
  ui.marker().click();
  ui.field("endast_h_stabilitet").checked = true; ui.field("endast_h_stabilitet").dispatch("input");
  assert.deepEqual(counts(), ["0", "0"]);
  assert.equal(ui.byClass("gp-insulation-list").textContent, "Inga sulor");
  assert.equal(ui.tag.values.endast_h_stabilitet, false, "The widget follows the draft before the kernel updates project state");
  ui.field("endast_h_stabilitet").checked = false; ui.field("endast_h_stabilitet").dispatch("input");
  assert.deepEqual(counts(), ["0", "1"]);
  assert.equal(ui.byClass("gp-insulation-list").textContent, "VS1");
});

test("insulation widget toggle retains placement and drag, resize and cancel leave engineering inputs intact", t => {
  const ui = setup(t);
  const accept = request => {
    const settings = ui.data.state.insulation_widget || {enabled: false, x: .65, y: .55, size: 300};
    ui.data.state.insulation_widget = {...settings, ...(request.settings || request.position)};
    ui.changed(); ui.ack(request);
  };
  const before = structuredClone(ui.tag);
  ui.byText("Widget: Isolering").click(); accept(ui.sent.at(-1));
  const widget = ui.byClass("gp-insulation-widget"), header = widget.children[0], resize = ui.byClass("gp-insulation-resize");
  assert.equal(widget.hidden, false); assert.equal(ui.byText("Widget: Isolering").getAttribute("aria-pressed"), "true");
  ui.start(header); ui.move(380, 360); ui.finish(380, 360);
  let request = ui.sent.at(-1);
  assert.equal(request.action, "insulation_placement"); near(request.position.x, .75); near(request.position.y, .65); accept(request);
  assert.equal(resize.hidden, false);
  widget.clientWidth = 300; widget.clientHeight = 160;
  ui.start(resize); ui.move(450, 380); ui.finish(450, 380);
  request = ui.sent.at(-1); near(request.position.size, 450); accept(request);
  assert.equal(widget.style.transform, "scale(1.5)");
  ui.start(header); ui.move(400, 400); ui.viewport.dispatch("pointercancel");
  near(parseFloat(widget.style.left), 75); near(parseFloat(widget.style.top), 65);
  ui.byText("Widget: Isolering").click(); accept(ui.sent.at(-1)); assert.equal(widget.hidden, true);
  ui.byText("Widget: Isolering").click(); accept(ui.sent.at(-1));
  assert.equal(widget.hidden, false); assert.equal(widget.style.transform, "scale(1.5)");
  assert.deepEqual(ui.tag, before);
});

for (const readOnly of [false, true]) test(`support length has independent geometry and notation (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  slidingFixture(ui);
  ui.tag.values.L_vagg = .6; ui.tag.values.L_vagg_minst_1 = false; ui.tag.values.glid_L = 3;
  ui.changed(); ui.marker().click();
  const row = readOnly ? ui.find(e => e.getAttribute("aria-label")?.startsWith("L_vagg")) : ui.field("L_vagg").parent;
  assert.equal(row.hidden, false);
  assert.equal(row.parent.children[0].textContent, "Geometri");
  assert.match(elementText(ui.byClass("gp-basis")), /Lvägg/);
  assert.match(elementText(ui.byClass("gp-tag-sliding-inputs")), /Lsu3 mLvägg0,6 m/);
  if (!readOnly) {
    assert.equal(ui.field("L_vagg").required, true);
    assert.equal(ui.field("glid_L").required, false, "Known support length determines the EQU total");
    ui.field("L_vagg").value = "0,4"; ui.field("L_vagg").dispatch("input");
    assert.equal(ui.sent.at(-1).values.L_vagg, .4);
    assert.equal(ui.sent.at(-1).values.glid_L, 3);
    assert.equal(ui.field("glid_L").value, "3");
    ui.tag.values.endast_h_stabilitet = true;
    ui.changed(); ui.ack(ui.sent.at(-1));
    assert.equal(ui.field("L_vagg").parent.hidden, false, "Support length is also needed for H-only");
    assert.equal(ui.field("L_vagg").disabled, false);
  }
});

test("support length is excluded from pads and mixed bulk length edits", t => {
  const ui = setup(t);
  ui.tag.values.lang = 0; ui.changed(); ui.marker().click();
  assert.equal(ui.field("L_vagg").parent.hidden, true);
  assert.equal(ui.field("L_vagg").disabled, true);
  assert.equal(tableField(ui, "tag1", "L_vagg").disabled, true);
});

test("support length table edits preserve the separate footing length and invalidate bearing", t => {
  const ui = setup(t);
  ui.tag.values.L_vagg = .6; ui.tag.values.L_vagg_minst_1 = false; ui.tag.values.glid_L = 3; ui.changed();
  const control = tableField(ui, "tag1", "L_vagg");
  control.value = "0,4"; control.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).values, {L_vagg: .4});
  assert.equal(ui.tag.values.glid_L, 3);
  assert.match(ui.marker().className, /gp-tag-stale/);
});

for (const readOnly of [false, true]) test(`long support uses compact local checkbox while retaining full sliding length (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  slidingFixture(ui);
  Object.assign(ui.tag.values, {L_vagg: 5, L_vagg_minst_1: true, glid_L: 7});
  ui.changed(); ui.marker().click();
  assert.match(elementText(ui.byClass("gp-basis")), /1 m \(Minst 1 m\)/);
  assert.match(elementText(ui.byClass("gp-tag-sliding-inputs")), /Lsu7 mLvägg5 m/);
  if (readOnly) {
    assert.equal(resultTableValue(ui, "tag1", "L_vagg").textContent, "1");
    assert.equal(resultTableValue(ui, "tag1", "L_vagg_minst_1").textContent, "Ja");
    assert.equal(ui.sent.length, 0);
  } else {
    const minimum = ui.field("L_vagg_minst_1"), length = ui.field("L_vagg");
    assert.equal(minimum.checked, true);
    assert.equal(minimum.parent.className, "gp-length-override");
    assert.equal(length.hidden, true); assert.equal(length.disabled, true);
    assert.equal(length.value, "5", "Full support length is retained for global EQU");
    assert.equal(ui.byClass("gp-wall-length-default").textContent, "1");
    assert.equal(tableField(ui, "tag1", "L_vagg").value, "1");
    assert.equal(tableField(ui, "tag1", "L_vagg").disabled, true);
    minimum.checked = false; minimum.dispatch("input");
    assert.equal(length.hidden, false); assert.equal(length.disabled, false);
    assert.equal(length.required, true);
    assert.equal(ui.sent.at(-1).values.L_vagg, 5);
    assert.equal(ui.sent.at(-1).values.L_vagg_minst_1, false);
    length.value = "0,6"; length.dispatch("input");
    assert.equal(ui.sent.at(-1).values.L_vagg, .6);
    assert.equal(ui.sent.at(-1).values.L_vagg_minst_1, false);
    assert.equal(ui.sent.at(-1).values.glid_L, 7);
    minimum.checked = true; minimum.dispatch("input");
    assert.equal(length.hidden, true);
    assert.equal(ui.sent.at(-1).values.L_vagg, .6, "Local toggle does not overwrite global support data");
    assert.equal(ui.sent.at(-1).values.L_vagg_minst_1, true);
  }
});

test("local minimum can be changed for selected table rows and bulk short lengths", t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {L_vagg: 5, L_vagg_minst_1: true});
  const second = {...structuredClone(ui.tag), id: "tag2", label: "VS2"};
  second.values.L_vagg = 3;
  ui.data.state.tags.push(second); ui.changed();
  selectTableRow(ui, "VS1"); selectTableRow(ui, "VS2");
  const minimum = tableField(ui, "tag1", "L_vagg_minst_1");
  minimum.checked = false; minimum.dispatch("change");
  assert.deepEqual(ui.sent.at(-1).ids, ["tag1", "tag2"]);
  assert.deepEqual(ui.sent.at(-1).values, {L_vagg_minst_1: false});
  assert.equal(tableField(ui, "tag1", "L_vagg").disabled, false);
  assert.equal(tableField(ui, "tag2", "L_vagg").disabled, false);
  ui.tag.values.L_vagg_minst_1 = second.values.L_vagg_minst_1 = false;
  ui.changed(); ui.ack(ui.sent.at(-1));
  const length = tableField(ui, "tag1", "L_vagg");
  length.value = "0,6"; length.dispatch("input");
  assert.deepEqual(ui.sent.at(-1).values, {L_vagg: .6});
  assert.equal(ui.tag.values.L_vagg, 5); assert.equal(second.values.L_vagg, 3);
  ui.tag.values.L_vagg_minst_1 = second.values.L_vagg_minst_1 = true;
  ui.changed(); ui.ack(ui.sent.at(-1));
  ui.byText("Ändra markerade").click();
  assert.equal(ui.field("bulk_L_vagg").disabled, true);
  const bulkMinimum = ui.field("bulk_L_vagg_minst_1");
  bulkMinimum.value = "false"; bulkMinimum.dispatch("change");
  assert.equal(ui.field("bulk_L_vagg").disabled, false);
  ui.field("bulk_L_vagg").value = "0,4"; ui.field("bulk_L_vagg").dispatch("input");
  ui.byText("Tillämpa").click();
  assert.deepEqual(ui.sent.at(-1).values, {L_vagg_minst_1: false, L_vagg: .4});
});

test("H-only exposes the full support length and hides the local minimum checkbox", t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {endast_h_stabilitet: true, L_vagg: 5, L_vagg_minst_1: true});
  ui.changed(); ui.marker().click();
  assert.equal(ui.field("L_vagg_minst_1").parent.hidden, true);
  assert.equal(ui.field("L_vagg").hidden, false);
  assert.equal(ui.field("L_vagg").disabled, false);
  assert.equal(ui.field("L_vagg").value, "5");
  assert.equal(tableField(ui, "tag1", "L_vagg").value, "5");
  assert.equal(tableField(ui, "tag1", "L_vagg_minst_1").disabled, true);
});

test("support length sorting uses the local displayed length and leaves pads without a value", t => {
  const ui = setup(t);
  ui.data.state.tags = [
    {id: "tag1", label: "VS10", values: {L_vagg: 3, L_vagg_minst_1: true}},
    {id: "tag2", label: "VS2", values: {L_vagg: 5, L_vagg_minst_1: true}},
    {id: "tag3", label: "VS7", values: {L_vagg: .6, L_vagg_minst_1: false}},
    {id: "tag4", label: "PS1", values: {lang: 0, L_vagg: null, L_vagg_minst_1: true}},
  ].map(item => ({...structuredClone(ui.tag), ...item, values: {...ui.tag.values, ...item.values}}));
  ui.changed();
  assert.equal(tableField(ui, "tag4", "L_vagg").value, "");
  tableSortButton(ui, "L_vagg").click();
  assert.deepEqual(tableOrder(ui), ["tag3", "tag2", "tag1", "tag4"]);
  tableSortButton(ui, "L_vagg").click();
  assert.deepEqual(tableOrder(ui), ["tag2", "tag1", "tag3", "tag4"]);
});


const panelHandle = (ui, kind) => ui.find(e => e.getAttribute("aria-controls")?.startsWith("gp-" + kind + "-panel-"));
function resizePanel(ui, kind, dx, dy, finish = true) {
  const handle = panelHandle(ui, kind);
  handle.dispatch("pointerdown", {clientX: 500, clientY: 500});
  handle.dispatch("pointermove", {clientX: 500 + dx, clientY: 500 + dy});
  if (finish) handle.dispatch("pointerup", {clientX: 500 + dx, clientY: 500 + dy});
  return handle;
}

test("corner drags resize panels independently without engineering updates, pan or closing input", t => {
  const ui = setup(t);
  ui.marker().click(); ui.field("b").value = "0,"; ui.field("b").dispatch("input");
  const original = structuredClone(ui.tag), sheet = ui.byClass("gp-sheet"), position = {...sheet.style};
  const sentBefore = ui.sent.length;
  const table = ui.byClass("gp-table-scroll"); table.scrollLeft = 200; table.scrollTop = 150;
  const handle = resizePanel(ui, "board", -180, 140, false);
  assert.equal(handle.parent, ui.byClass("gp-workspace"));
  assert.equal(panelHandle(ui, "table").parent, ui.byClass("gp-table-section"));
  assert.equal(ui.byClass("gp-board").style.height, "788px");
  assert.equal(ui.byClass("gp-workspace").style.width, "668px");
  assert.equal(table.style.height, ""); assert.equal(ui.byClass("gp-table-section").style.width, "");
  assert.equal(ui.sent.length, sentBefore, "Only the finished gesture is saved");
  assert.equal(ui.byClass("gp-dialog").hidden, false); assert.equal(ui.field("b").value, "0,");
  handle.dispatch("pointerup", {clientX: 320, clientY: 640});
  assert.equal(handle.hasPointerCapture(1), false);
  const request = ui.sent.at(-1);
  assert.equal(request.action, "layout"); assert.deepEqual(request.settings, {board_width: 668, board_height: 788});
  ui.data.state.layout = {board_width: 668, board_height: 788}; ui.changed(); ui.ack(request);
  resizePanel(ui, "table", 0, -220);
  assert.equal(ui.byClass("gp-board").style.height, "788px"); assert.equal(ui.byClass("gp-workspace").style.width, "668px");
  assert.equal(table.style.height, "428px"); assert.equal(table.style.maxHeight, "428px");
  assert.deepEqual(ui.sent.at(-1).settings, {table_height: 428});
  assert.equal(table.scrollLeft, 200); assert.equal(table.scrollTop, 150);
  assert.deepEqual(ui.tag, original); assert.deepEqual({...sheet.style}, position);
});

test("cancelled corner drags restore both dimensions and cannot be completed by another pointer", t => {
  const ui = setup(t); ui.data.state.layout = {board_height: 700, table_height: 350, board_width: 700, table_width: 620}; ui.changed();
  for (const action of ["pointercancel", "lostpointercapture", "Escape"]) {
    const handle = resizePanel(ui, "board", -100, 100, false);
    handle.dispatch("pointermove", {pointerId: 9, clientX: 600, clientY: 1000});
    handle.dispatch("pointerup", {pointerId: 9}); assert.equal(ui.sent.length, 0);
    assert.equal(ui.byClass("gp-board").style.height, "800px"); assert.equal(ui.byClass("gp-workspace").style.width, "600px");
    if (action === "Escape") handle.dispatch("keydown", {key: action}); else handle.dispatch(action);
    assert.equal(ui.byClass("gp-board").style.height, "700px"); assert.equal(ui.byClass("gp-workspace").style.width, "700px");
    assert.equal(ui.byClass("gp-table-scroll").style.height, "350px"); assert.equal(ui.byClass("gp-table-section").style.width, "620px");
    handle.dispatch("pointerup"); assert.equal(ui.sent.length, 0);
  }
  const handle = panelHandle(ui, "board");
  handle.dispatch("pointerdown", {button: 2}); handle.dispatch("pointermove", {clientX: 1000, clientY: 1000}); handle.dispatch("pointerup");
  assert.equal(ui.sent.length, 0); assert.equal(ui.byClass("gp-board").style.height, "700px");
  handle.dispatch("pointerdown", {clientX: 500, clientY: 500}); handle.dispatch("pointermove", {clientX: 501, clientY: 501}); handle.dispatch("pointerup");
  assert.equal(ui.sent.length, 0, "A click/jitter cannot lock automatic dimensions");
});

test("corner resizing respects limits and rapid independent changes retain the latest width and height", t => {
  const ui = setup(t); ui.data.state.layout = {board_width: 600, table_width: 700}; ui.changed();
  resizePanel(ui, "board", 10000, 10000); const first = ui.sent.at(-1);
  assert.deepEqual(first.settings, {board_width: 848, board_height: 2400}, "Width stays within the notebook container");
  resizePanel(ui, "table", -10000, -10000); const second = ui.sent.at(-1);
  assert.deepEqual(second.settings, {table_width: 320, table_height: 160});
  ui.data.state.layout = {board_width: 848, board_height: 2400, table_width: 700, table_height: null}; ui.changed(); ui.ack(first);
  assert.equal(ui.byClass("gp-table-scroll").style.height, "160px"); assert.equal(ui.byClass("gp-table-section").style.width, "320px");
  Object.assign(ui.data.state.layout, second.settings); ui.changed(); ui.ack(second);
  assert.equal(ui.byClass("gp-board").style.height, "2400px"); assert.equal(ui.byClass("gp-workspace").style.width, "848px");
  assert.equal(ui.byClass("gp-table-scroll").style.height, "160px"); assert.equal(ui.byClass("gp-table-section").style.width, "320px");
  resizePanel(ui, "board", -10000, -10000); assert.deepEqual(ui.sent.at(-1).settings, {board_width: 320, board_height: 280});
});

test("corner tracks the pointer when narrowing wraps toolbar text, and returning to start sends no update", t => {
  const ui = setup(t), workspace = ui.byClass("gp-workspace");
  const handle = resizePanel(ui, "board", -200, 100, false);
  workspace.panelChromeHeight = 240;
  handle.dispatch("pointermove", {clientX: 300, clientY: 600});
  assert.equal(ui.byClass("gp-board").style.height, "708px", "Wrapped chrome reduces drawing height to preserve the requested outer height");
  handle.dispatch("pointermove", {clientX: 300, clientY: 600});
  assert.equal(ui.byClass("gp-board").style.height, "708px", "Identical pointer events do not accumulate dimension changes");
  workspace.panelChromeHeight = 200;
  handle.dispatch("pointermove", {clientX: 500, clientY: 500}); handle.dispatch("pointerup");
  assert.equal(ui.sent.length, 0); assert.equal(workspace.style.width, ""); assert.equal(ui.byClass("gp-board").style.height, "");
});

for (const standalone of [false, true]) test(`corner handles support width/height keyboard adjustment and independent reset (standalone=${standalone})`, t => {
  const ui = setup(t, {readOnly: standalone, standalone}), original = structuredClone(ui.model.get("state").tags);
  const handle = panelHandle(ui, "board");
  assert.equal(handle.getAttribute("role"), "button");
  assert.match(handle.children[1].textContent, /Bredd 848 px, höjd 648 px/);
  const accept = () => { if (!standalone) {
    const request = ui.sent.at(-1); ui.data.state.layout = {...ui.data.state.layout, ...request.settings}; ui.changed(); ui.ack(request);
  }};
  handle.dispatch("keydown", {key: "ArrowDown"}); accept(); assert.equal(ui.byClass("gp-board").style.height, "668px");
  handle.dispatch("keydown", {key: "ArrowUp", shiftKey: true}); accept(); assert.equal(ui.byClass("gp-board").style.height, "568px");
  handle.dispatch("keydown", {key: "ArrowLeft"}); accept(); assert.equal(ui.byClass("gp-workspace").style.width, "828px");
  handle.dispatch("keydown", {key: "ArrowLeft", shiftKey: true}); accept(); assert.equal(ui.byClass("gp-workspace").style.width, "728px");
  handle.dispatch("keydown", {key: "ArrowRight"}); accept(); assert.equal(ui.byClass("gp-workspace").style.width, "748px");
  handle.dispatch("keydown", {key: "Home"}); accept();
  assert.equal(ui.byClass("gp-board").style.height, "280px"); assert.equal(ui.byClass("gp-workspace").style.width, "320px");
  handle.dispatch("keydown", {key: "End"}); accept();
  assert.equal(ui.byClass("gp-board").style.height, "2400px"); assert.equal(ui.byClass("gp-workspace").style.width, "848px");
  resizePanel(ui, "table", -150, 80); accept();
  assert.equal(ui.byClass("gp-table-scroll").style.height, "728px"); assert.equal(ui.byClass("gp-table-section").style.width, "698px");
  handle.dispatch("dblclick"); accept();
  assert.equal(ui.byClass("gp-board").style.height, ""); assert.equal(ui.byClass("gp-workspace").style.width, "");
  assert.equal(ui.model.get("state").layout.board_height, null); assert.equal(ui.model.get("state").layout.board_width, null);
  assert.equal(ui.model.get("state").layout.table_height, 728); assert.equal(ui.model.get("state").layout.table_width, 698);
  panelHandle(ui, "table").dispatch("keydown", {key: "Enter"}); accept();
  assert.equal(ui.model.get("state").layout.table_height, null); assert.equal(ui.model.get("state").layout.table_width, null);
  assert.deepEqual(ui.model.get("state").tags, original);
  if (standalone) {
    const before = structuredClone(ui.model.get("state").layout);
    ui.model.send({action: "layout", settings: {table_height: -10, table_width: 600}});
    assert.deepEqual(ui.model.get("state").layout, before);
    ui.model.send({action: "update", id: "tag1", values: {b: 99}});
    assert.deepEqual(ui.model.get("state").tags, original);
  }
});

test("size validation restores missing widths in old projects and rejects invalid display dimensions", () => {
  assert.deepEqual(validateLayout({}), {board_height: null, table_height: null, board_width: null, table_width: null});
  assert.deepEqual(validateLayout({board_height: 280, table_height: 1800}), {board_height: 280, table_height: 1800, board_width: null, table_width: null});
  assert.deepEqual(validateLayout({board_width: 320, table_width: 4000}), {board_height: null, table_height: null, board_width: 320, table_width: 4000});
  for (const value of [null, [], 5, {unknown: 400}, {toString: 5}, {board_height: true},
    {board_height: Infinity}, {board_height: "700"}, {board_height: 279}, {table_height: 1801},
    {board_width: true}, {table_width: NaN}, {board_width: 319}, {table_width: 4001}]) assert.throws(() => validateLayout(value));
});

for (const readOnly of [false, true]) test(`pad models expose the load basis and full wall length independently of model geometry (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  Object.assign(ui.tag.values, {lang: 0, lasttyp: 1, L_vagg: 2.4, L_vagg_minst_1: true, t: .275,
    F_vy: 200, F_vy_bruk: 100, V_Ed_EQU: 150, isolering: true});
  ui.tag.load_resultants = {brott: 480, bruk: 240};
  ui.data.state.sliding = {enabled: true}; ui.changed(); ui.marker().click();
  assert.match(elementText(ui.byClass('gp-basis')), /hela Lvägg/);
  assert.match(elementText(ui.marker()), /V 200 kN\/m → 480 kN/);
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 75 % · bₓ 1 m · bᵧ 1 m · t 0,275 m");
  assert.equal(ui.byClass("gp-governing").textContent, "Styrande: Jord · brott");
  assert.equal(resultTableValue(ui, 'tag1', 'V_res_brott').textContent, '480');
  assert.equal(resultTableValue(ui, 'tag1', 'V_res_bruk').textContent, '240');
  if (!readOnly) {
    assert.equal(ui.field('lasttyp').parent.hidden, false);
    assert.equal(ui.field('L_vagg').disabled, false);
    assert.equal(ui.field('L_vagg').hidden, false);
    assert.equal(ui.field('L_vagg').required, true);
    assert.equal(ui.field('L_vagg').value, '2.4');
    assert.equal(ui.field('L_vagg_minst_1').parent.hidden, true);
    assert.equal(ui.field('F_vy').parent.children.find(e => e.className === 'gp-unit').textContent, 'kN/m');
    assert.equal(tableField(ui, 'tag1', 'L_vagg').value, '2,4');
    assert.equal(tableField(ui, 'tag1', 'L_vagg').disabled, false);
    ui.field('lasttyp').value = '0'; ui.field('lasttyp').dispatch('input');
    assert.equal(ui.sent.at(-1).values.lasttyp, 0);
    assert.equal(ui.field('L_vagg').parent.hidden, true);
    assert.equal(ui.field('F_vy').parent.children.find(e => e.className === 'gp-unit').textContent, 'kN');
    assert.equal(resultTableValue(ui, 'tag1', 'V_res_brott').textContent, '—', 'Pending changes cannot display old totals');
  } else {
    assert.equal(resultTableValue(ui, 'tag1', 'lasttyp').textContent, 'Linjelast [kN/m]');
    assert.equal(resultTableValue(ui, 'tag1', 'L_vagg').textContent, '2,4');
  }
});

test('a wall switched to a pad retains line input, while a new pad defaults to total input', t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {lasttyp: 1, L_vagg: .6}); ui.changed(); ui.marker().click();
  assert.equal(ui.field('lasttyp').parent.hidden, true);
  assert.equal(tableField(ui, 'tag1', 'lasttyp').hidden, true);
  ui.field('lang').value = '0'; ui.field('lang').dispatch('input');
  assert.equal(ui.sent.at(-1).values.lasttyp, 1);
  assert.equal(ui.sent.at(-1).values.F_vy, 1, 'Changing models cannot multiply stored inputs');
  assert.equal(ui.field('lasttyp').parent.hidden, false);
  assert.equal(ui.field('L_vagg').value, '0.6');
  assert.equal(ui.field('L_vagg').disabled, false);
  ui.field('lasttyp').value = '0'; ui.field('lasttyp').dispatch('input');
  assert.equal(ui.field('L_vagg').parent.hidden, true);
});

for (const readOnly of [false, true]) test(`resultant columns are locked, sortable and folded with their load group (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  ui.data.state.tags = [['tag1', 'VS10', 120, 60], ['tag2', 'VS2', 120, 60], ['tag3', 'VS1', 80, 0]]
    .map(([id, label, brott, bruk]) => ({...structuredClone(ui.tag), id, label, load_resultants: {brott, bruk}}));
  ui.changed();
  const result = resultTableValue(ui, 'tag1', 'V_res_brott');
  assert.equal(result.tag, 'span'); assert.equal(result.listeners.size, 0);
  assert.equal(ui.elements().some(e => e.name === 'table_V_res_brott' || e.name === 'V_res_brott'), false);
  const sort = ui.find(e => e.getAttribute('aria-label') === 'Sortera efter Yttre lastresultant – brott');
  sort.click(); assert.deepEqual(tableOrder(ui), ['tag3', 'tag2', 'tag1']);
  const request = ui.sent.at(-1);
  if (!readOnly) {ui.data.state.table_view = {collapsed: [], sort: {key: 'V_res_brott', direction: 'ascending'}}; ui.changed(); ui.ack(request);}
  sort.click(); assert.deepEqual(tableOrder(ui), ['tag2', 'tag1', 'tag3']);
  const fold = ui.find(e => e.getAttribute('aria-label') === 'Visa eller dölj Laster – Brott');
  fold.click(); assert.equal(result.parent.hidden, true);
  assert.equal(resultTableValue(ui, 'tag1', 'V_res_bruk').parent.hidden, false);
});

test('line pad import updates discard old load and length drafts but retain chosen model and geometry', async t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {lang: 0, lasttyp: 1, L_vagg: 2.4}); ui.changed(); ui.marker().click();
  ui.field('b').value = '1,23'; ui.field('b').dispatch('input'); ui.ack(ui.sent.at(-1));
  ui.field('F_vy').value = '999'; ui.field('F_vy').dispatch('input'); ui.ack(ui.sent.at(-1));
  const input = ui.find(e => e.getAttribute('aria-label') === 'Lasteffektfil');
  const buffer = new TextEncoder().encode('{"schemaVersion":1}').buffer;
  input.files = [{name: 'updated.json', size: buffer.byteLength, arrayBuffer: async () => buffer}];
  await input.listeners.get('change')[0]();
  const request = ui.sent.at(-1);
  Object.assign(ui.tag.values, {F_vy: 220, L_vagg: 3}); ui.changed();
  ui.ack(request, {report: {updated: 1, new: 0, updated_ids: ['tag1']}});
  ui.marker().click();
  assert.equal(ui.field('F_vy').value, '220');
  assert.equal(ui.field('L_vagg').value, '3');
  assert.equal(ui.field('b').value, '1,23');
  ui.field('L_vagg').value = '2,8'; ui.field('L_vagg').dispatch('input');
  assert.equal(ui.sent.at(-1).values.lang, 0);
  assert.equal(ui.sent.at(-1).values.lasttyp, 1);
  assert.equal(ui.sent.at(-1).values.L_vagg, 2.8);
  assert.equal(ui.sent.at(-1).values.b, 1.23);
});

test('mixed load units block joint loads while allowing geometry and an explicit common load basis', t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {lang: 0, lasttyp: 1, L_vagg: .6});
  const other = structuredClone(ui.tag); other.id = 'tag2'; other.label = 'PS2'; other.values.lasttyp = 0;
  ui.data.state.tags.push(other); ui.changed();
  selectTableRow(ui, 'VS1'); selectTableRow(ui, 'PS2');
  assert.equal(tableField(ui, 'tag1', 'F_vy').disabled, true);
  assert.equal(tableField(ui, 'tag1', 'b').disabled, false);
  assert.equal(tableField(ui, 'tag1', 'lasttyp').disabled, false);
  ui.byText('Ändra markerade').click();
  assert.equal(ui.field('bulk_F_vy').disabled, true);
  ui.field('bulk_lasttyp').value = '1'; ui.field('bulk_lasttyp').dispatch('change');
  assert.equal(ui.field('bulk_F_vy').disabled, false);
  assert.equal(ui.field('bulk_L_vagg').disabled, false);
  ui.field('bulk_L_vagg').value = '2,4'; ui.field('bulk_L_vagg').dispatch('input');
  ui.byText('Tillämpa').click();
  assert.deepEqual(ui.sent.at(-1).values, {lasttyp: 1, L_vagg: 2.4});
});

test('load colour intervals use input units rather than the bearing model', t => {
  const ui = setup(t);
  Object.assign(ui.tag.values, {lang: 0, lasttyp: 1, F_vy: 150});
  const settings = {enabled: true, category: 'V', secondary: null, phase: 'brott', colors: {}, bounds: {pad: [100, 200], wall: [100, 200]}};
  const group = colourGroups([ui.tag], settings).assignments.get('tag1');
  assert.equal(group.kind, 'wall'); assert.equal(group.unit, 'kN/m');
});

test('drawing heading and date buttons create independent objects and prevent duplicate pending requests', t => {
  const ui = setup(t);
  const before = structuredClone(ui.tag);
  const add = ui.byText('Lägg till rubrik');
  add.click(); const request = ui.sent.at(-1);
  assert.equal(request.action, 'text_add'); assert.equal(request.kind, 'heading');
  assert.equal(request.text, ui.data.state.title); assert.equal(request.subtitle, ui.data.state.subtitle);
  assert.equal(request.width, ui.byClass('gp-subtitle').clientWidth + 8);
  assert.equal(request.size, 20);
  assert.equal(add.disabled, true);
  add.click(); assert.equal(ui.sent.at(-1), request);
  ui.data.state.text_objects = [{id: 'heading1', kind: 'heading', text: 'Rubrik', x: request.x, y: request.y, size: 28}];
  ui.changed(); ui.ack(request, {id: 'heading1'});
  assert.equal(ui.byClass('gp-text-resize').hidden, false);
  ui.byText('Lägg till datum (åå/mm/dd)').click(); const date = ui.sent.at(-1);
  assert.equal(date.kind, 'date');
  ui.data.state.text_objects.push({id: 'date1', kind: 'date', text: '26/10/08', x: date.x, y: date.y, size: 18});
  ui.changed(); ui.ack(date, {id: 'date1'});
  const elements = ui.elements().filter(e => e.className.includes('gp-text-annotation'));
  assert.equal(elements.length, 2);
  assert.equal(elementText(elements[1].children[0]), '26/10/08');
  assert.equal(elements[1].children.some(e => e.className.includes('gp-annotation-subtitle-editor')), false);
  assert.deepEqual(ui.tag, before);
});

test('add heading copies current header typing and its width even before older edits are acknowledged', t => {
  const ui = setup(t), title = ui.byClass('gp-title'), subtitle = ui.byClass('gp-subtitle');
  title.value = 'Grundläggningssulor - Hus 1'; title.dispatch('input'); const first = ui.sent.at(-1);
  subtitle.value = '26017 - Norrbodahöjden\nKontroller: bärighet, isolering och H-stabilitet\nV-last bottenplan ej inkluderad';
  subtitle.dispatch('input'); const latest = ui.sent.at(-1);
  Object.assign(ui.data.state, {title:first.title, subtitle:first.subtitle}); ui.changed(); ui.ack(first);
  subtitle.clientWidth = 1250;
  ui.byText('+').click(); // The drawing zooms to 125%; the interface heading stays at 20 px.
  ui.byText('Lägg till rubrik').click(); const copied = ui.sent.at(-1);
  assert.equal(copied.text, latest.title); assert.equal(copied.subtitle, latest.subtitle); assert.equal(copied.width, 1258);
  near(copied.size * 1.25, 20);
  ui.data.state.text_objects = [{id:'copied', kind:'heading', text:copied.text, subtitle:copied.subtitle,
    width:copied.width, x:copied.x, y:copied.y, size:copied.size}]; ui.changed(); ui.ack(copied, {id:'copied'});
  assert.equal(ui.byClass('gp-annotation-heading').style.transform, 'scale(1)');
  assert.equal(ui.byClass('gp-annotation-heading').style.width, '1258px');
  assert.equal(ui.byClass('gp-annotation-title').textContent, latest.title);
  assert.equal(ui.byClass('gp-annotation-subtitle').textContent, latest.subtitle);
  assert.equal(ui.byClass('gp-annotation-editor').hidden, true, 'The copy is ready without typing again');
});

test('drawing text drag, proportional resize, cancel and pending edit replies retain the latest values', t => {
  const ui = setup(t);
  const original = structuredClone(ui.tag);
  ui.data.state.text_objects = [{id:'text1', kind:'heading', text:'Hus 1', subtitle:'Grundsulor', width:200, x:.1, y:.2, size:20}]; ui.changed();
  const element = ui.byClass('gp-text-annotation'), text = ui.byClass('gp-annotation-text'), resize = ui.byClass('gp-text-resize');
  const accept = request => {
    Object.assign(ui.data.state.text_objects[0], request.changes); ui.changed(); ui.ack(request);
  };
  ui.start(text); ui.move(400, 375); ui.finish(400, 375);
  const move = ui.sent.at(-1); assert.equal(move.action, 'text_update'); assert.equal(move.id, 'text1');
  near(move.changes.x, .225); near(move.changes.y, .325);
  element.clientWidth=200; element.clientHeight=50;
  ui.start(resize); ui.move(400, 325); ui.finish(400, 325);
  const scale = ui.sent.at(-1); near(scale.changes.size, 30);
  accept(move); assert.equal(element.style.transform, 'scale(1.5)', 'An old move cannot undo the pending resize');
  accept(scale);
  ui.start(text); ui.move(700, 550); ui.viewport.dispatch('pointercancel');
  near(parseFloat(element.style.left), 22.5); near(parseFloat(element.style.top), 32.5);
  text.click(); ui.byText('Redigera').click();
  const editor = ui.byClass('gp-annotation-editor'); assert.equal(editor.hidden, false);
  const subtitle = ui.byClass('gp-annotation-subtitle-editor'); assert.equal(subtitle.hidden, false);
  assert.equal(subtitle.value, 'Grundsulor');
  editor.value='Revision A'; editor.dispatch('input'); const first = ui.sent.at(-1);
  editor.value='Grundsulor – Hus 1'; editor.dispatch('input'); const second = ui.sent.at(-1);
  subtitle.value='Revision B\nKontroll av bärighet'; subtitle.dispatch('input'); const last = ui.sent.at(-1);
  accept(first); accept(second);
  assert.equal(editor.value, last.changes.text); assert.equal(subtitle.value, last.changes.subtitle);
  accept(last); subtitle.dispatch('keydown', {key:'Enter', shiftKey:true}); assert.equal(subtitle.hidden, false);
  subtitle.dispatch('keydown', {key:'Enter', shiftKey:false});
  assert.equal(editor.hidden, true); assert.equal(subtitle.hidden, true);
  assert.equal(ui.byClass('gp-annotation-title').textContent, last.changes.text);
  assert.equal(ui.byClass('gp-annotation-subtitle').textContent, last.changes.subtitle);
  const count = ui.sent.length;
  ui.byClass('an-grundplan').dispatch('keydown', {key:'Escape'}); assert.equal(resize.hidden, true); assert.equal(ui.sent.length, count);
  assert.deepEqual(ui.tag, original);
});

test('drawing text deletion removes only that annotation', t => {
  const ui = setup(t);
  ui.data.state.text_objects = [{id:'text1', kind:'heading', text:'Hus 1', x:.1, y:.1, size:28},
    {id:'date1', kind:'date', text:'26/10/08', x:.1, y:.2, size:18}]; ui.changed();
  ui.byClass('gp-annotation-text').click();
  const remove = ui.find(e => e.getAttribute('aria-label') === 'Ta bort textobjekt'); remove.click();
  const request = ui.sent.at(-1); assert.equal(request.action, 'text_delete'); assert.equal(request.id, 'text1');
  remove.click(); assert.equal(ui.sent.at(-1), request);
  ui.data.state.text_objects.shift(); ui.changed(); ui.ack(request);
  assert.equal(elementText(ui.byClass('gp-annotation-text')), '26/10/08');
  assert.equal(ui.data.state.tags.length, 1);
});

test('HTML drawing headings and dates display saved text and geometry without editing controls', t => {
  const ui = setup(t, {readOnly:true});
  ui.data.state.text_objects = [{id:'text1', kind:'heading', text:'Rubrik', subtitle:'Revision A\nGrundsulor', width:1200, x:.2, y:.3, size:40}]; ui.changed();
  const element = ui.byClass('gp-text-annotation'), text = ui.byClass('gp-annotation-text');
  assert.equal(ui.byClass('gp-annotation-title').textContent, 'Rubrik'); assert.equal(text.tag, 'span');
  assert.equal(ui.byClass('gp-annotation-subtitle').textContent, 'Revision A\nGrundsulor');
  assert.equal(element.style.transform, 'scale(2)'); assert.equal(element.style.left, '20%');
  assert.equal(element.style.width, '1200px');
  assert.ok(!ui.elements().some(e => e.className === 'gp-annotation-editor'));
  assert.ok(!ui.elements().some(e => e.textContent === 'Lägg till rubrik'));
  ui.start(text); ui.move(400, 400); ui.finish(400, 400); assert.equal(ui.sent.length, 0);
});

for (const readOnly of [false, true]) test(`comment widget shows only filled comments in natural order and updates immediately (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly});
  ui.tag.label = 'VS10'; ui.tag.values.kommentar = 'Första raden\nAndra raden';
  ui.data.state.tags.push(...[
    {id: 'tag2', label: 'VS2', kommentar: 'Utan isolering enligt föreskrift.'},
    {id: 'tag3', label: 'PS1', kommentar: ' \n '},
  ].map(item => ({...structuredClone(ui.tag), id: item.id, label: item.label,
    values: {...ui.tag.values, kommentar: item.kommentar}})));
  ui.data.state.comment_widget = {enabled: true, x: .2, y: .3, size: 615}; ui.changed();
  const widget = ui.byClass('gp-comment-widget'), body = ui.byClass('gp-comment-widget-body');
  assert.equal(widget.hidden, false); assert.equal(widget.style.transform, 'scale(1.5)');
  assert.equal(body.children[0].textContent, '2 sulor med kommentarer');
  let rows = ui.byClass('gp-comment-table').children[1].children;
  assert.deepEqual(rows.map(row => row.children[0].textContent), ['VS2', 'VS10']);
  assert.equal(rows[1].children[1].textContent, 'Första raden\nAndra raden');
  assert.doesNotMatch(elementText(body), /PS1|Endast sulor med kommentarer/);
  assert.equal(ui.byClass('gp-comment-resize').hidden, true);
  if (readOnly) {
    assert.equal(ui.elements().some(e => e.textContent === 'Lägg till kommentarer'), false);
    const before = ui.sent.length;
    ui.start(widget.children[0]); ui.move(390, 360); ui.finish(390, 360);
    assert.equal(ui.sent.length, before);
    ui.tag.values.kommentar = ''; ui.changed();
  } else {
    const field = tableField(ui, 'tag1', 'kommentar');
    field.value = ''; field.dispatch('input');
    assert.deepEqual(ui.sent.at(-1).values, {kommentar: ''});
  }
  assert.equal(body.children[0].textContent, '1 sula med kommentar');
  assert.doesNotMatch(elementText(body), /VS10/);
  ui.data.state.tags = []; ui.changed();
  assert.equal(body.children[0].textContent, 'Inga sulor med kommentarer');
});

test('comments toggle preserves placement, proportional resize and cancelling a drag', t => {
  const ui = setup(t), before = structuredClone(ui.tag);
  const accept = request => {
    const settings = ui.data.state.comment_widget || {enabled: false, x: .08, y: .55, size: 410};
    ui.data.state.comment_widget = {...settings, ...(request.settings || request.position)};
    ui.changed(); ui.ack(request);
  };
  ui.byText('Lägg till kommentarer').click(); accept(ui.sent.at(-1));
  const widget = ui.byClass('gp-comment-widget'), header = widget.children[0], resize = ui.byClass('gp-comment-resize');
  assert.equal(widget.hidden, false); assert.equal(ui.byText('Lägg till kommentarer').getAttribute('aria-pressed'), 'true');
  ui.start(header); ui.move(380, 360); ui.finish(380, 360);
  let request = ui.sent.at(-1);
  assert.equal(request.action, 'comment_placement'); near(request.position.x, .18); near(request.position.y, .65); accept(request);
  assert.equal(resize.hidden, false);
  ui.start(resize); ui.move(505, 390); ui.finish(505, 390);
  request = ui.sent.at(-1); near(request.position.size, 615); accept(request);
  assert.equal(widget.style.transform, 'scale(1.5)');
  ui.start(header); ui.move(400, 400); ui.viewport.dispatch('pointercancel');
  near(parseFloat(widget.style.left), 18); near(parseFloat(widget.style.top), 65);
  ui.byText('Lägg till kommentarer').click(); accept(ui.sent.at(-1)); assert.equal(widget.hidden, true);
  ui.byText('Lägg till kommentarer').click(); accept(ui.sent.at(-1));
  assert.equal(widget.hidden, false); assert.equal(widget.style.transform, 'scale(1.5)');
  assert.deepEqual(ui.tag, before);
});

for (const readOnly of [false, true]) test(`H-only objects stay uncoloured and uncounted with geometry combinations (readOnly=${readOnly})`, t => {
  const ui = setup(t, {readOnly}); colourFixture(ui);
  ui.tag.values.endast_h_stabilitet = true;
  ui.data.state.tags.push({...structuredClone(ui.tag), id: 'tag2', label: 'VS2', values: {...ui.tag.values, endast_h_stabilitet: false}});
  for (const [category, secondary] of [['t', null], ['b', 'isolering'], ['V', 'l']]) {
    Object.assign(ui.data.state.colour_grouping, {category, secondary}); ui.changed();
    const markers = ui.elements().filter(e => e.className.split(' ').includes('gp-tag'));
    assert.equal(markers[0].dataset.colourGroup, undefined);
    assert.ok(markers[1].dataset.colourGroup);
    assert.doesNotMatch(elementText(ui.byClass('gp-colour-legend-body')), /Ej tillämpligt/);
    assert.equal(ui.elements().filter(e => e.className === 'gp-colour-group-count').reduce((sum, e) => sum + Number(e.textContent), 0), 1);
  }
});
