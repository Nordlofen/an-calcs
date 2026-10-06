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
    if (this.tag === "img") return { left: parseFloat(this.parent.style.left) || 0, top: parseFloat(this.parent.style.top) || 0,
      width: parseFloat(this.parent.style.width), height: parseFloat(this.parent.style.height) };
    return { left: 0, top: 0, width: this.clientWidth, height: this.clientHeight };
  }
}

const source = await readFile(new URL("../src/an_calcs/notebook/grundplan.js", import.meta.url), "utf8");
const { default: widget } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const resultSource = await readFile(new URL("../src/an_calcs/notebook/grundplan_html.js", import.meta.url), "utf8");
const { createResultModel } = await import("data:text/javascript;base64," + Buffer.from(resultSource).toString("base64"));
const names = ["lang", "b", "l", "t", "d", "e_b_plac", "e_l_plac", "F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b", "c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "delta_h", "beta", "alpha", "eta", "gamma_m", "gamma_m0", "gamma_Rd"];
names.push("isolering", "isolerprodukt", "f_d_brott", "f_d_bruk", "F_vy_bruk", "M_insp_l_bruk", "M_insp_b_bruk");
names.push("glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L");
const loadGroups = [{label: "Brott", fields: [["F_vy", "V", "kN"], ["F_hb", "Hₓ", "kN"], ["F_hl", "Hᵧ", "kN"], ["M_insp_b", "Mₓ", "kNm"], ["M_insp_l", "Mᵧ", "kNm"]]},
  {label: "Bruk", fields: [["F_vy_bruk", "V", "kN"], ["M_insp_b_bruk", "Mₓ", "kNm"], ["M_insp_l_bruk", "Mᵧ", "kNm"]]}]
  .map(group => ({...group, fields: group.fields.map(([name, symbol, unit]) => ({name, symbol, unit}))}));

function setup(t, { readOnly = false, standalone = false } = {}) {
  globalThis.document = Object.assign(new Element("document"), {
    createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag), activeElement: null, downloads: [] });
  globalThis.window = { confirm: () => true };
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
  globalThis.requestAnimationFrame = fn => fn();
  const tag = { id: "tag1", label: "VS1", x: .3, y: .4, page: 1,
    values: Object.fromEntries(names.map(name => [name, 1])), status: "calculated",
      summary: { utnyttjandegrad: .75, b: 1, last: 100, barformaga: 133, q_bd: 133, b_ef: 1, lastenhet: "kN/m" } };
  Object.assign(tag.values, {isolering: false, isolerprodukt: "", f_d_brott: null, f_d_bruk: null, F_vy_bruk: null});
  Object.assign(tag.values, {glid_x: false, glid_y: false, V_Ed_EQU: null, glid_mu: null, glid_L: null});
  const data = { state: { title: "Test", subtitle: "Projektets underrubrik", tags: [tag], label_size: 100 },
    background: { url: "data:test", width: 800, height: 600, page: 1, page_count: 1 },
    schema: { load_groups: loadGroups, fields: names.map(name => ({ name, label: name, type: name === "isolerprodukt" ? "text" : ["isolering", "glid_x", "glid_y"].includes(name) ? "bool" : name === "lang" ? "choice" : "number",
      unit: "m", options: [{ value: 0 }, { value: 1 }] })) } };
  const sent = [], handlers = new Map();
  const snapshot = { state: data.state, schema: data.schema, page: 1,
    pages: [data.background, { ...data.background, page: 2, url: "data:second" }] };
  snapshot.pages.forEach(page => { page.page_count = 2; });
  const model = standalone ? createResultModel(snapshot) : { get: name => data[name], send: payload => sent.push(payload),
    on: (name, fn) => handlers.set(name, fn), off: name => handlers.delete(name) };
  const host = new Element("host");
  t.after(widget.render({ model, el: host, readOnly }));
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
  const start = (target = marker(), x = 300, y = 300) => viewport.dispatch("pointerdown", { target, clientX: x, clientY: y });
  const move = (x, y) => viewport.dispatch("pointermove", { clientX: x, clientY: y });
  const finish = (x, y) => viewport.dispatch("pointerup", { clientX: x, clientY: y });
  const drag = (dx, dy) => { start(); move(300 + dx, 300 + dy); finish(300 + dx, 300 + dy); };
  const place = (x = 400, y = 400) => { start(byClass("gp-picture"), x, y); finish(x, y); };
  return { tag, data, model, snapshot, elements: () => walk(host), sent, byClass, byText, find, viewport, marker, position, ack, changed,
    start, move, finish, drag, place, field: name => find(element => element.name === name),
    label: () => byClass("gp-label-row").children[0] };
}

function near(actual, expected) { assert.ok(Math.abs(actual - expected) < 1e-10, `${actual} is close to ${expected}`); }

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

test("gliding inputs follow footing type and edits hide old resistance without invalidating bearing", t => {
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
  assert.equal(ui.field("V_Ed_EQU").parent.children.at(-1).textContent, "kN");
  ui.field("isolering").checked = true; ui.field("isolering").dispatch("input");
  assert.equal(ui.field("glid_x").disabled, true);
  assert.equal(ui.field("V_Ed_EQU").parent.hidden, true);
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

test("standalone sliding overlays and contributions remain visible but cannot be edited", t => {
  const ui = setup(t, {readOnly: true, standalone: true});
  slidingFixture(ui);
  assert.equal(ui.byClass("gp-global-axes").hidden, false);
  assert.equal(ui.byClass("gp-sliding-legend").hidden, false);
  ui.byText("144 kN"); ui.byText("Godkänd");
  assert.equal(ui.byClass("gp-axis-resize").hidden, true);
  const symbol = ui.byClass("gp-global-axes"), legend = ui.byClass("gp-sliding-legend");
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
  const soil = ui.byText("Jord och grundvatten").parent;
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
  assert.equal(ui.byText("Jord och grundvatten").parent.open, true);
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
  assert.ok(!ui.elements().some(element => element.textContent === "Bruk"));
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
  title.value = "Hus B"; title.dispatch("input");
  const first = ui.sent.at(-1);
  subtitle.value = "Revision A – ÅÄÖ"; subtitle.dispatch("input");
  const latest = ui.sent.at(-1);
  assert.equal(latest.action, "heading");
  assert.equal(latest.title, "Hus B");
  assert.equal(latest.subtitle, "Revision A – ÅÄÖ");
  Object.assign(ui.data.state, {title: first.title, subtitle: first.subtitle});
  ui.changed(); ui.ack(first);
  assert.equal(subtitle.value, "Revision A – ÅÄÖ", "Earlier response must not discard the newest text");
  ui.byText("Exportera HTML").click();
  assert.equal(ui.sent.at(-1).action, "export_html", "Heading update is sent before the export request");
  Object.assign(ui.data.state, {title: latest.title, subtitle: latest.subtitle});
  ui.changed(); ui.ack(latest);
  assert.equal(title.value, "Hus B");
  assert.equal(subtitle.value, "Revision A – ÅÄÖ");
  assert.deepEqual(ui.tag, original);
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
  const forbidden = ["Beräkna", "Kopiera sula", "Ta bort", "Öppna ritning", "Öppna projekt", "Spara projekt", "Kopiera projekt + key", "Exportera JSON", "+ Väggsula", "+ Pelarsula", "Exportera PDF", "Exportera HTML"];
  assert.ok(ui.elements().every(element => !forbidden.includes(element.textContent)));
  ui.marker().click();
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 75 % · 1,8 × 2,4 m");
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

test("standalone page and label-size controls work locally and reject calculation commands", t => {
  const ui = setup(t, { readOnly: true, standalone: true });
  const original = structuredClone(ui.snapshot);
  const replies = [];
  ui.model.on("msg:custom", reply => replies.push(reply));
  const page = ui.byClass("gp-page-label").children[0];
  page.value = 2; page.dispatch("change");
  assert.equal(ui.byClass("gp-picture").src, "data:second");
  assert.equal(ui.byClass("gp-markers").children.length, 0);
  page.value = 1; page.dispatch("change");
  ui.marker().click();
  const size = ui.byClass("gp-size-label").children[0];
  size.value = 180; size.dispatch("input"); size.dispatch("change");
  assert.equal(ui.model.get("state").label_size, 180);
  assert.equal(ui.byClass("gp-dialog").hidden, false);
  for (const action of ["calculate", "update", "delete", "copy", "add", "save", "export_pdf", "sliding", "sliding_placement"]) {
    ui.model.send({ action, id: ui.tag.id, values: { b: 55 }, view: "test", request: 1 });
    assert.equal(replies.at(-1).ok, false);
  }
  ui.model.send({ action: "page", page: 500 });
  assert.equal(replies.at(-1).ok, false);
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

test("raw input drafts survive minimize and stale calculation acknowledgments", t => {
  const ui = setup(t);
  const reopen = () => { ui.byText("Minimera").dispatch("click"); ui.marker().dispatch("click"); };
  ui.marker().dispatch("click");
  ui.byText("Geometri").parent.open = false;
  ui.byText("Laster – Brott").parent.open = false;
  ui.byText("Isolering").parent.open = true;
  ui.field("b").value = "1,20"; ui.field("b").dispatch("input");
  ui.label().value = "VS2"; ui.label().dispatch("input");
  reopen();
  assert.equal(ui.field("b").value, "1,20");
  assert.equal(ui.label().value, "VS2");
  assert.equal(ui.byText("Geometri").parent.open, false);
  assert.equal(ui.byText("Laster – Brott").parent.open, false);
  assert.equal(ui.byText("Isolering").parent.open, true);
  const other = { ...structuredClone(ui.tag), id: "tag2", label: "VS4" };
  ui.data.state.tags.push(other); ui.changed();
  const open = id => ui.find(element => element.dataset.tagId === id).dispatch("click");
  open(other.id);
  assert.equal(ui.byText("Geometri").parent.open, true, "A new tag starts with its own section settings");
  assert.equal(ui.byText("Isolering").parent.open, false);
  ui.byText("Laster – Bruk").parent.open = true;
  open(ui.tag.id);
  assert.equal(ui.byText("Geometri").parent.open, false);
  assert.equal(ui.byText("Isolering").parent.open, true);
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
  assert.equal(ui.field("b").value, "1.2");
  assert.equal(ui.label().value, "VS3");
});

test("insulation toggles required capacities and service loads, retaining drafts and boolean values", t => {
  const ui = setup(t);
  ui.marker().dispatch("click");
  ui.byText("Laster – Brott"); ui.byText("Laster – Bruk"); ui.byText("Isolering");
  const enabled = ui.field("isolering");
  assert.equal(enabled.type, "checkbox");
  assert.equal(enabled.checked, false);
  assert.equal(ui.field("f_d_bruk").parent.hidden, true);
  assert.equal(ui.field("F_vy_bruk").disabled, true);
  assert.equal(ui.field("F_vy_bruk").required, false);
  ui.byClass("gp-form").dispatch("submit");
  const soil = ui.sent.at(-1);
  assert.equal(soil.action, "calculate", "Empty inactive fields cannot block the soil calculation");
  assert.equal(soil.values.isolering, false);
  for (const name of ["l_h", "l_h_bruk", "F_hb_bruk", "F_hl_bruk"]) {
    assert.equal(name in soil.values, false, "Removed lever-arm inputs are not sent for calculation");
  }
  ui.ack(soil);
  enabled.checked = true; enabled.dispatch("input");
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Med isolering", "The draft is shown before the kernel replies");
  assert.equal(ui.byClass("gp-tag-result").textContent, "Ändrad · beräkna");
  assert.equal(ui.field("f_d_brott").parent.hidden, false);
  assert.equal(ui.field("F_vy_bruk").disabled, false);
  assert.equal(ui.field("F_vy_bruk").required, true);
  const before = ui.sent.length;
  ui.byClass("gp-form").dispatch("submit");
  assert.equal(ui.sent.length, before, "Active insulation requires strengths and an explicit long-term load");
  assert.equal(ui.field("F_vy_bruk").closest("details").open, true);
  assert.equal(ui.field("f_d_bruk").closest("details").open, true);
  for (const [name, value] of [["F_vy_bruk", "70,5"], ["f_d_brott", "200"], ["f_d_bruk", "80"]]) {
    ui.field(name).value = value; ui.field(name).dispatch("input");
  }
  ui.byText("Minimera").dispatch("click"); ui.marker().dispatch("click");
  assert.equal(ui.field("isolering").checked, true);
  assert.equal(ui.field("F_vy_bruk").value, "70,5");
  ui.byClass("gp-form").dispatch("submit");
  const request = ui.sent.at(-1);
  assert.equal(request.action, "calculate");
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
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 160 % · bₓ 1 m");
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
