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
    for (const child of children) { child.parent = this; this.children.push(child); }
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

function setup(t, { readOnly = false, standalone = false } = {}) {
  globalThis.document = { createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag), activeElement: null, downloads: [] };
  globalThis.window = { confirm: () => true };
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
  globalThis.requestAnimationFrame = fn => fn();
  const tag = { id: "tag1", label: "VS1", x: .3, y: .4, page: 1,
    values: Object.fromEntries(names.map(name => [name, 1])), status: "calculated",
      summary: { utnyttjandegrad: .75, b: 1, last: 100, barformaga: 133, q_bd: 133, b_ef: 1, lastenhet: "kN/m" } };
  Object.assign(tag.values, {isolering: false, isolerprodukt: "", f_d_brott: null, f_d_bruk: null, F_vy_bruk: null});
  const data = { state: { title: "Test", subtitle: "Projektets underrubrik", tags: [tag], label_size: 100 },
    background: { url: "data:test", width: 800, height: 600, page: 1, page_count: 1 },
    schema: { fields: names.map(name => ({ name, label: name, type: name === "isolerprodukt" ? "text" : name === "isolering" ? "bool" : name === "lang" ? "choice" : "number",
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
  const changed = () => handlers.get("change:state")();
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
  const forbidden = ["Beräkna", "Kopiera sula", "Ta bort", "Öppna ritning", "Öppna projekt", "Spara projekt", "+ Väggsula", "+ Pelarsula", "Exportera PDF", "Exportera HTML"];
  assert.ok(ui.elements().every(element => !forbidden.includes(element.textContent)));
  ui.marker().click();
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 75 % · 1,8 × 2,4 m");
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Utan isolering");
  assert.match(ui.marker().getAttribute("aria-label"), /bredd × längd/);
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
  for (const action of ["calculate", "update", "delete", "copy", "add", "save", "export_pdf"]) {
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
  assert.equal(ui.marker().children.length, 3);
  assert.equal(ui.byClass("gp-governing").textContent, "Styrande: Isolering · bruk");
  assert.equal(ui.byClass("gp-tag-insulation").children[1].textContent, "Med isolering");
  assert.equal(ui.byClass("gp-tag-result").textContent, "U 160 % · b 1 m");
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
