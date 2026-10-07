/* Shared plan view. All engineering calculations run in the Python kernel. */
const lineLoads = values => Number(values.lang) === 1 || Number(values.lasttyp ?? 0) === 1;
const COLOUR_DEFAULTS = {enabled: false, category: "t", secondary: null, phase: "brott", edit_type: "pad", show_legend: true,
  bounds: {pad: [100, 200, 400], wall: [100, 200, 400]}, colors: {}, legend: {x: .65, y: .08, size: 300}};
const COLOUR_CATEGORIES = {t: "Tjocklek t", b: "Bredd bₓ", l: "Längd bᵧ", V: "Vertikallast V", isolering: "Isolering"};
const COLOUR_PHASES = {brott: "Brott", bruk: "Bruk", EQU: "EQU"};
const INSULATION_WIDGET_DEFAULTS = {enabled: false, x: .65, y: .55, size: 300};
const LAYOUT_DEFAULTS = {board_height: null, table_height: null, board_width: null, table_width: null};
const LAYOUT_LIMITS = {board_height: [280, 2400], table_height: [160, 1800], board_width: [320, 4000], table_width: [320, 4000]};
export function validateLayout(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)
      || Object.keys(value).some(key => !Object.hasOwn(LAYOUT_DEFAULTS, key))) throw new Error("Ogiltiga storleksinställningar.");
  const result = {...LAYOUT_DEFAULTS, ...value};
  for (const [name, [low, high]] of Object.entries(LAYOUT_LIMITS)) {
    const size = result[name];
    if (size !== null && (typeof size !== "number" || !Number.isFinite(size) || size < low || size > high))
      throw new Error("Ogiltig storlek för " + name + ".");
  }
  return result;
}
const COLOUR_PALETTE = ["#cce7ff", "#e5d8ff", "#ffdfba", "#cfeee5", "#ffd9e5", "#f3edbb",
  "#d6e0ff", "#dcf0ca", "#f3d8ca", "#d2eef3", "#eedaf1", "#e7e3d1"];
const COLOUR_INSULATION_GROUPS = [
  ["1", "Med isolering · inget bidrag", "#cce7ff"],
  ["0", "Utan isolering · inget bidrag", "#e4e9ed"],
  ["x", "Utan isolering · bidrag i X_g", "#ffdfba"],
  ["y", "Utan isolering · bidrag i Y_g", "#e5d8ff"],
  ["xy", "Utan isolering · bidrag i X_g och Y_g", "#cfeee5"],
];
const colourNumberKey = value => {const [m, e] = value.toExponential(12).split("e"); return m + "e" + Number(e);};
const colourPalette = index => {
  if (index < COLOUR_PALETTE.length) return COLOUR_PALETTE[index];
  const code = Math.imul(index, 2654435761) & 0xffffff;
  return "#" + [16, 8, 0].map(shift => (195 + ((code >> shift) & 255) % 45).toString(16).padStart(2, "0")).join("");
};
const colourBackground = color => {
  const channels = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16));
  const weight = Math.min(...channels) >= 150 ? 1 : .3;
  return "#" + channels.map(channel => Math.floor(channel * weight + 255 * (1 - weight) + .5).toString(16).padStart(2, "0")).join("");
};
export function colourGroups(tags, settings = COLOUR_DEFAULTS) {
  if (settings.secondary) {
    const categories = Object.keys(COLOUR_CATEGORIES).filter(name => [settings.category, settings.secondary].includes(name));
    const parts = categories.map(category => colourGroups(tags, {...settings, category, secondary: null}));
    const order = parts.map(part => new Map(part.groups.map((group, index) => [group.key, index])));
    const pairs = new Map(), groups = [], assignments = new Map();
    for (const tag of tags) {
      const pair = parts.map(part => part.assignments.get(tag.id).key), key = "combo:" + JSON.stringify(pair);
      if (!pairs.has(key)) pairs.set(key, {pair, ids: []});
      pairs.get(key).ids.push(tag.id);
    }
    for (const [key, {ids}] of [...pairs].sort(([, a], [, b]) =>
      order[0].get(a.pair[0]) - order[0].get(b.pair[0]) || order[1].get(a.pair[1]) - order[1].get(b.pair[1]))) {
      const color = settings.colors[key] || colourPalette(groups.length);
      const group = {key, color, background: colourBackground(color), count: ids.length, kind: "combination", unit: "",
        categories, parts: parts.map(part => part.assignments.get(ids[0]))};
      groups.push(group); for (const id of ids) assignments.set(id, group);
    }
    return {groups, assignments};
  }
  const {category, phase} = settings, groups = [], assignments = new Map(), byKey = new Map(), special = new Map();
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const make = (key, data, defaultColor = colourPalette(groups.length)) => {
    const color = settings.colors[key] || defaultColor;
    const group = {key, color, background: colourBackground(color), count: 0, ...data};
    groups.push(group); return group;
  };
  if (category === "isolering") {
    for (const [suffix, label, color] of COLOUR_INSULATION_GROUPS) {
      byKey.set(suffix, make("isolering:" + suffix, {label, kind: "insulation", unit: ""}, color));
    }
  } else if (category === "V") {
    for (const kind of ["pad", "wall"]) {
      if (!tags.some(tag => lineLoads(tag.values) === (kind === "wall"))) continue;
      const bounds = settings.bounds[kind];
      for (let i = 0; i <= bounds.length; i++) {
        const low = i ? bounds[i - 1] : null, high = bounds[i] ?? null;
        const key = `V:${phase}:${kind}:${low == null ? "*" : colourNumberKey(low)}:${high == null ? "*" : colourNumberKey(high)}`;
        byKey.set(kind + ":" + i, make(key, {kind, low, high, unit: kind === "wall" ? "kN/m" : "kN"}));
      }
    }
  } else {
    const values = [...new Set(tags.filter(tag => !tag.values.endast_h_stabilitet && finite(tag.values[category]))
      .map(tag => tag.values[category]))].sort((a, b) => a - b);
    for (const value of values) {
      const key = category + ":" + colourNumberKey(value);
      if (!byKey.has(key)) byKey.set(key, make(key, {value, unit: "m", kind: "geometry"}));
    }
  }
  for (const tag of tags) {
    const values = tag.values;
    if (category === "isolering") {
      const insulated = !values.endast_h_stabilitet && values.isolering === true;
      const direction = (values.glid_x ? "x" : "") + (values.glid_y ? "y" : "");
      const group = byKey.get(insulated ? "1" : direction || "0");
      group.count++; assignments.set(tag.id, group); continue;
    }
    const na = values.endast_h_stabilitet && (category !== "V" || phase !== "EQU");
    const value = values[category === "V" ? {brott: "F_vy", bruk: "F_vy_bruk", EQU: "V_Ed_EQU"}[phase] : category];
    let group;
    if (na || !finite(value)) {
      const key = na ? "na" : "missing";
      if (!special.has(key)) {
        const color = settings.colors[key] || "#d5dde1";
        const item = make(key, {label: na ? "Ej tillämpligt" : "Saknar värde", kind: "special", unit: ""});
        Object.assign(item, {color, background: colourBackground(color)}); special.set(key, item);
      }
      group = special.get(key);
    } else if (category === "V") {
      const kind = lineLoads(values) ? "wall" : "pad";
      const index = settings.bounds[kind].filter(bound => value >= bound).length;
      group = byKey.get(kind + ":" + index);
    } else group = byKey.get(category + ":" + colourNumberKey(value));
    group.count++; assignments.set(tag.id, group);
  }
  return {groups, assignments};
}

const drawingDistance = (start, end, background) => Math.hypot(
  (end.x - start.x) * background.width, (end.y - start.y) * background.height);
export function validateCalibration(value, background) {
  if (value == null) return null;
  if (!background?.url) throw new Error("Öppna en ritning före kalibrering.");
  const validPoint = point => point && [point.x, point.y].every(n => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1);
  if (!validPoint(value.start) || !validPoint(value.end) || typeof value.length_m !== "number"
    || !Number.isFinite(value.length_m) || value.length_m <= 0) throw new Error("Ange två punkter och ett positivt referensmått.");
  const distance = drawingDistance(value.start, value.end, background);
  if (!Number.isFinite(distance) || distance < 1e-6 || !Number.isFinite(value.length_m / distance))
    throw new Error("Ange ett positivt referensmått mellan två olika punkter.");
  return {start: {x: value.start.x, y: value.start.y}, end: {x: value.end.x, y: value.end.y}, length_m: value.length_m};
}
export function measuredDistance(start, end, background, calibration) {
  return drawingDistance(start, end, background) / drawingDistance(calibration.start, calibration.end, background) * calibration.length_m;
}

function definitionSketch(strip) {
  const make = (name, attributes, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const svg = make("svg", { viewBox: "0 0 440 435", role: "img", "aria-label": strip
    ? "Väggsula: x tvärs väggen, y längs väggen, bᵧ är beräkningsremsans längd."
    : "Pelarsula: lokala x- och y-axlar med sulmåtten bₓ och bᵧ." });
  const line = (x1, y1, x2, y2, color = "#58717a", width = 1) =>
    svg.append(make("line", { x1, y1, x2, y2, stroke: color, "stroke-width": width }));
  const text = (x, y, value, size = 14, anchor = "middle", color = "#18333b") =>
    svg.append(make("text", { x, y, "font-size": size, "text-anchor": anchor, fill: color }, value));
  const rect = (x, y, width, height, fill = "#e7efee") =>
    svg.append(make("rect", { x, y, width, height, fill, stroke: "#18333b", "stroke-width": 1.5 }));
  const head = (x, y, dx, dy, color, size = 6) => {
    const length = Math.hypot(dx, dy), ux = dx / length, uy = dy / length;
    svg.append(make("path", { d: `M${x} ${y}L${x - size * ux + size * .4 * uy} ${y - size * uy - size * .4 * ux}L${x - size * ux - size * .4 * uy} ${y - size * uy + size * .4 * ux}Z`, fill: color }));
  };
  const arrow = (x1, y1, x2, y2, color = "#14695e") => {
    line(x1, y1, x2, y2, color, 1.7); head(x2, y2, x2 - x1, y2 - y1, color);
  };
  const dimension = (x1, y1, x2, y2) => {
    line(x1, y1, x2, y2); head(x1, y1, x1 - x2, y1 - y2, "#58717a", 5);
    head(x2, y2, x2 - x1, y2 - y1, "#58717a", 5);
  };
  text(220, 22, strip ? "Planvy – väggsula" : "Planvy – pelarsula", 16);
  rect(130, 58, 180, 126);
  if (strip) rect(207, 58, 26, 126, "#d0dcd9");
  else rect(200, 101, 40, 40, "#d0dcd9");
  arrow(220, 121, 352, 121); text(363, 126, "x", 17, "middle", "#14695e");
  arrow(220, 121, 220, 39); text(231, 43, "y", 17, "start", "#14695e");
  for (const x of [130, 310]) line(x, 190, x, 208);
  dimension(130, 201, 310, 201); text(220, 223, "bₓ", 17);
  for (const y of [58, 184]) line(110, y, 124, y);
  dimension(114, 58, 114, 184); text(96, 126, "bᵧ", 16, "end");
  text(322, 177, strip ? "vägg" : "pelare", 12, "start", "#58717a");
  line(316, 173, 240, 150);
  for (const [origin, axis, moment] of [[0, "x", "Mᵧ"], [224, "y", "Mₓ"]]) {
    const cx = origin + 106, load = "#a6473e";
    text(cx, 259, "Snitt i " + axis + "-led", 15);
    const path = `M${cx - 33} 303 Q${cx} 257 ${cx + 33} 303`;
    svg.append(make("path", { d: path, fill: "none", stroke: load, "stroke-width": 1.8 }));
    // Existing engine convention: positive moments add positive eccentricity.
    head(cx + 33, 303, 33, 46, load);
    text(cx + 43, 283, moment, 17, "start", load);
    arrow(cx, 310, cx, 342, load); text(cx + 10, 329, "V", 18, "start", load);
    arrow(origin + 14, 347, cx - 23, 347, load); text(origin + 17, 337, axis === "x" ? "Hₓ" : "Hᵧ", 16, "start", load);
    rect(cx - 11, 345, 22, 10, load); rect(origin + 29, 355, 152, 29);
    arrow(origin + 186, 377, origin + 212, 377); text(origin + 197, 368, axis, 15, "middle", "#14695e");
    for (const x of [origin + 29, origin + 181]) line(x, 390, x, 407);
    dimension(origin + 29, 401, origin + 181, 401);
    text(cx, 425, axis === "x" ? "bₓ" : "bᵧ", 17);
  }
  return svg;
}

function render({ model, el, readOnly = false }) {
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const symbolNode = (notation, className = "") => {
    const symbol = node("span", "gp-math " + className);
    if (notation.text) {
      symbol.textContent = notation.text;
      symbol.classList.add("gp-field-symbol-plain");
    } else {
      if (notation.prefix) symbol.append(node("span", "", notation.prefix));
      if (notation.base) symbol.append(node("i", "", notation.base));
      if (notation.subscript) symbol.append(node("sub", "", notation.subscript));
      if (notation.suffix) symbol.append(node("span", "", notation.suffix));
    }
    return symbol;
  };
  // Only controlled display text uses this notation; no HTML is parsed.
  const mathText = (tag, className, text) => {
    const matches = [...text.matchAll(/([\p{L}]+)_([\p{L}\d]+(?:,[\p{L}\d]+)*)/gu)];
    if (!matches.length) return node(tag, className, text);
    const element = node(tag, className);
    let offset = 0;
    for (const match of matches) {
      if (match.index > offset) element.append(node("span", "", text.slice(offset, match.index)));
      element.append(symbolNode({base: match[1], subscript: match[2]}));
      offset = match.index + match[0].length;
    }
    if (offset < text.length) element.append(node("span", "", text.slice(offset)));
    return element;
  };
  const root = node("div", "an-grundplan");
  root.classList.toggle("gp-readonly", readOnly);
  // Keep JupyterLab's cell shortcuts from consuming keys intended for the widget.
  root.setAttribute("data-lm-suppress-shortcuts", "true");
  const view = Math.random().toString(36).slice(2);
  let sequence = 0, active = null, mode = "pan", zoom = 1, panX = 24, panY = 24, disposed = false;
  let lastBackground = "", formId = null, copySource = null, sizeDraft = null;
  let headingDraft = null;
  let slidingDraft = null, overlaySelected = null;
  let colourDraft = null, colourEditType = null;
  let insulationWidgetDraft = null;
  let layoutDraft = null, panelDrag = null;
  const layout = () => ({...LAYOUT_DEFAULTS, ...(layoutDraft || state().layout)});
  const overlayPositions = new Map(), pendingOverlayPositions = new Map(), slidingDirty = new Set();
  const slidingNames = new Set(["glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L"]);
  const bearingOnlyNames = new Set(["b", "l", "l_override", "L_vagg_minst_1", "t", "d", "e_b_plac", "e_l_plac", "F_vy", "F_hb", "F_hl", "M_insp_b", "M_insp_l",
    "F_vy_bruk", "M_insp_b_bruk", "M_insp_l_bruk", "c_prime", "c_uk", "gamma", "gamma_prime", "phi_k",
    "delta_h", "beta", "alpha", "eta", "gamma_m", "gamma_m0", "gamma_Rd", "f_d_brott", "f_d_bruk"]);
  const insulationNames = new Set(["isolering", "isolerprodukt", "f_d_brott", "f_d_bruk"]);
  const sliding = () => slidingDraft || state().sliding || {enabled: false, check_x: false, check_y: false, placements: {}};
  const colour = () => colourDraft || state().colour_grouping || COLOUR_DEFAULTS;
  const insulationWidget = () => insulationWidgetDraft || state().insulation_widget || INSULATION_WIDGET_DEFAULTS;
  const positions = new Map(), pendingPositions = new Map();
  const pending = new Map(), dirty = new Set(), inputs = new Map(), edits = new Map(), drafts = new Map();
  const sectionStates = new Map(), inputSections = [], resultSections = [];
  const sketchStates = new Map();
  const areaPhases = new Map();
  let sketchInline = false, sketchType = null;
  const selected = new Set(), bulkInputs = new Map();
  let tableAnchor = null;
  let bulkIds = [], bulkBusy = false, bulkSignature = "";
  let importBusy = false, drawingBusy = false, deleteBusy = false, lastImportToken = null;
  let measurePoints = [], measureCursor = null, calibrationDraft = null, calibrationBusy = false;
  const state = () => model.get("state") || { tags: [] };
  const loadImport = () => state().load_import;
  const background = () => model.get("background") || {};
  const current = () => state().tags.find((tag) => tag.id === active);
  const number = (value, digits = 2) => new Intl.NumberFormat("sv-SE", {
    maximumFractionDigits: digits,
  }).format(value);
  const precise = value => value !== 0 && (Math.abs(value) < 1e-6 || Math.abs(value) >= 1e9)
    ? value.toExponential(2).replace(".", ",") : number(value, 6);
  const compactNumber = (value, digits) => value !== 0 && (Math.abs(value) < 1e-6 || Math.abs(value) >= 1e9)
    ? precise(value) : number(value, digits);
  const button = (text, fn, className = "") => {
    const b = node("button", className, text);
    b.type = "button";
    b.addEventListener("click", fn);
    return b;
  };
  function command(action, payload = {}, buffers = [], onDone) {
    if (readOnly && !["label_size", "calibration", "export_pdf", "table_view", "layout"].includes(action)) return;
    const request = ++sequence;
    pending.set(request, onDone);
    model.send({ action, ...payload, request, view }, undefined, buffers);
  }
  const heading = node("header", "gp-heading");
  const headingText = node("div", "gp-heading-text");
  const title = node(readOnly ? "h3" : "input", "gp-title");
  const subtitle = node(readOnly ? "p" : "textarea", "gp-subtitle");
  function resizeSubtitle() {
    if (readOnly) return;
    subtitle.style.height = "auto";
    subtitle.style.height = Math.max(21, (subtitle.scrollHeight || 0) + 2) + "px";
  }
  function showHeading() {
    const values = headingDraft || state();
    for (const [element, value] of [[title, values.title ?? "Grundplan"],
      [subtitle, values.subtitle ?? "Sulgrundläggning · jordens bärighet"]]) {
      if (readOnly) element.textContent = value;
      else if (element.value !== value) element.value = value;
    }
    subtitle.hidden = readOnly && !subtitle.textContent;
    resizeSubtitle();
  }
  if (!readOnly) {
    for (const [input, label] of [[title, "Rubrik"], [subtitle, "Underrubrik"]]) {
      if (input === title) input.type = "text";
      else input.rows = 1;
      input.maxLength = 200;
      input.placeholder = label;
      input.setAttribute("aria-label", label);
      input.title = "Klicka för att redigera " + label.toLowerCase()
        + (input === subtitle ? ". Shift + Enter lägger till en ny rad." : "");
      input.addEventListener("input", () => {
        resizeSubtitle();
        const draft = { title: title.value, subtitle: subtitle.value };
        headingDraft = draft;
        command("heading", draft, [], () => {
          // Older acknowledgments must not replace more recent typing.
          if (headingDraft === draft) {
            headingDraft = null;
            showHeading();
          }
        });
      });
    }
    subtitle.addEventListener("keydown", event => {
      if (event.key !== "Enter") return;
      event.stopPropagation();
      if (!event.shiftKey) { event.preventDefault(); subtitle.blur(); }
    });
  }
  headingText.append(title, subtitle);
  const total = node("span", "gp-count");
  heading.append(headingText, total);
  const toolbar = node("div", "gp-toolbar");
  const fileInput = node("input");
  fileInput.type = "file";
  fileInput.accept = ".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp";
  fileInput.hidden = true;
  fileInput.setAttribute("aria-label", "Ritningsfil");
  const projectInput = node("input");
  projectInput.type = "file";
  projectInput.accept = ".json";
  projectInput.hidden = true;
  const loadsInput = node("input");
  loadsInput.type = "file"; loadsInput.accept = ".json"; loadsInput.hidden = true;
  loadsInput.setAttribute("aria-label", "Lasteffektfil");
  const loadDrawing = button("Importera/Uppdatera ritning", () => fileInput.click());
  const loadProject = button("Öppna projekt", () => {
    if (!state().tags.length || window.confirm("Ersätt projektet? Spara först om du vill behålla dina ändringar.")) {
      projectInput.click();
    }
  });
  const loadEffects = button("Importera/Uppdatera lasteffekt", () => loadsInput.click());
  loadEffects.title = "Uppdatera laster och linjestödslängd för matchande littera. Manuellt ändrad sulängd behålls. Placera nya sulor med ett klick per stöd.";
  const deleteAll = button("Radera samtliga sulor", () => {
    if (deleteBusy || importBusy || bulkBusy || (!state().tags.length && !loadImport())) return;
    const count = state().tags.length;
    if (!window.confirm("Radera samtliga " + count + " sulor?"
      + (loadImport() ? " Även återstående placeringar avbryts." : ""))) return;
    deleteBusy = true;
    cancelDrag(); closeDialog(); closeBulk();
    update();
    command("delete_all", {}, [], reply => {
      deleteBusy = false;
      if (reply.ok) {
        selected.clear(); tableAnchor = null; bulkIds = []; bulkSignature = ""; formId = null;
        tableSortScope = null;
        tableFeedback.replaceChildren();
        dirty.clear(); drafts.clear(); edits.clear(); slidingDirty.clear();
        positions.clear(); pendingPositions.clear(); sectionStates.clear(); sketchStates.clear(); areaPhases.clear();
        inputSections.length = resultSections.length = 0;
        setMode("pan");
      }
      update();
      showMessage(reply.ok ? "Samtliga " + (reply.deleted ?? count) + " sulor har raderats." : reply.error, !reply.ok);
    });
  }, "gp-delete");
  deleteAll.title = "Radera vyns sulor. Ritning och projektinställningar behålls.";
  const importBar = node("section", "gp-import-bar");
  importBar.hidden = true;
  importBar.setAttribute("aria-label", "Placera importerade sulor");
  const importInstruction = node("strong", "gp-import-instruction");
  importInstruction.setAttribute("aria-live", "polite");
  const importLoads = node("p", "gp-import-loads");
  const importPause = button("Pausa placering", () => controlImport(loadImport()?.paused ? "resume" : "pause"));
  const importCancel = button("Avbryt import", () => controlImport("cancel"));
  importCancel.title = "Avsluta kön. Redan placerade sulor behålls; återstående stöd skapas inte.";
  const importActions = node("div", "gp-import-actions");
  importActions.append(importPause, importCancel);
  importBar.append(importInstruction, importLoads,
    node("p", "gp-field-note", "Dra i ritningen för att panorera. Shift + scroll zoomar. Vänsterklick placerar nästa sula; Shift + vänsterdrag markerar flera etiketter. Kontrollera övriga indata före beräkning. Endast placerade sulor sparas. Escape pausar kön."), importActions);
  const downloadProject = reply => {
    const url = URL.createObjectURL(new Blob([reply.download], { type: "application/json" }));
    const a = node("a");
    a.href = url;
    a.download = "grundplan.json";
    root.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showMessage("Projektet har exporterats till din nedladdningsmapp.");
  };
  const savePanel = node("section", "gp-save-panel");
  savePanel.hidden = true;
  savePanel.setAttribute("role", "dialog");
  savePanel.setAttribute("aria-label", "Spara projekt");
  const saveFields = node("div", "gp-save-fields");
  const saveInputs = {};
  let saveChoices = [], saveGeneration = 0;
  const projectChoice = node("select"), keyChoice = node("select");
  projectChoice.setAttribute("aria-label", "Välj projekt");
  keyChoice.setAttribute("aria-label", "Välj sparat fall");
  function fillChoices(select, choices, placeholder) {
    select.replaceChildren();
    const empty = node("option", "", placeholder);
    empty.value = "";
    select.append(empty);
    for (const choice of choices) {
      const option = node("option", "", choice.label);
      option.value = choice.value;
      select.append(option);
    }
  }
  function showKeyChoices(choice) {
    fillChoices(keyChoice, (choice?.keys || []).map(key => ({value: key, label: key})), "Nytt fall…");
    keyChoice.hidden = !choice?.keys.length;
    keyChoice.value = choice?.keys.includes(saveInputs.key.value) ? saveInputs.key.value : "";
    saveInputs.key.hidden = !!keyChoice.value;
  }
  projectChoice.addEventListener("change", () => {
    const choice = saveChoices.find(choice => choice.state_file === projectChoice.value);
    saveInputs.state_file.hidden = !!choice;
    saveInputs.state_file.value = choice?.state_file || "";
    if (choice && !choice.keys.includes(saveInputs.key.value)) saveInputs.key.value = choice.keys[0] || "";
    showKeyChoices(choice);
  });
  keyChoice.addEventListener("change", () => {
    saveInputs.key.value = keyChoice.value;
    saveInputs.key.hidden = !!keyChoice.value;
    if (!keyChoice.value) saveInputs.key.focus();
  });
  for (const [name, caption, placeholder] of [
    ["state_file", "Projekt", "Ange projektnamn"], ["key", "Fall (key)", "Ange fallnamn"],
  ]) {
    const label = node("label", "", caption);
    const input = node("input");
    input.type = "text";
    input.required = true;
    input.maxLength = name === "key" ? 200 : 4096;
    input.setAttribute("aria-label", name === "state_file" ? "Projektfil" : "key");
    input.placeholder = placeholder;
    saveInputs[name] = input;
    label.append(name === "state_file" ? projectChoice : keyChoice, input);
    saveFields.append(label);
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); saveSettings(); }
    });
    if (name === "key") input.addEventListener("input", () => {
      const choice = saveChoices.find(choice => choice.state_file === projectChoice.value);
      keyChoice.value = choice?.keys.includes(input.value) ? input.value : "";
    });
  }
  fillChoices(projectChoice, [], "Nytt projekt…");
  fillChoices(keyChoice, [], "Nytt fall…");
  keyChoice.hidden = true;
  const saveError = node("p", "gp-save-error");
  const saveActions = node("div", "gp-save-actions");
  let saving = false;
  const cancelSave = button("Avbryt", () => { savePanel.hidden = true; saveProject.focus(); });
  const confirmSave = button("Spara", () => saveSettings(), "gp-primary");
  function saveSettings(overwrite = false, settings) {
    if (saving) return;
    settings ||= {state_file: saveInputs.state_file.value.trim(), key: saveInputs.key.value.trim()};
    saveError.textContent = "";
    for (const name of ["state_file", "key"]) {
      if (!settings[name]) {
        saveError.textContent = "Ange både projektfil och key.";
        saveInputs[name].focus();
        return;
      }
    }
    saving = true;
    confirmSave.textContent = "Sparar…";
    for (const element of [confirmSave, cancelSave, projectChoice, keyChoice, ...Object.values(saveInputs)]) element.disabled = true;
    saveProject.disabled = true;
    command("save", {...settings, overwrite}, [], reply => {
      saving = false;
      confirmSave.textContent = "Spara";
      for (const element of [confirmSave, cancelSave, projectChoice, keyChoice, ...Object.values(saveInputs)]) element.disabled = false;
      saveProject.disabled = false;
      if (!reply.ok) {
        saveError.textContent = reply.error;
        if (reply.conflict && window.confirm(reply.error)) saveSettings(true, settings);
        return;
      }
      savePanel.hidden = true;
      if (reply.storage) showStorage(reply.storage);
      showMessage("Projektet sparat i " + reply.saved_file);
    });
  }
  const saveProject = button("Spara projekt", () => {
    const generation = ++saveGeneration;
    const storage = projectStorage;
    saveChoices = [];
    saveInputs.state_file.value = storage?.state_file || "";
    const initialFile = saveInputs.state_file.value;
    saveInputs.key.value = storage?.key || "";
    saveInputs.key.hidden = false;
    saveInputs.state_file.hidden = false;
    fillChoices(projectChoice, [], "Nytt projekt…");
    keyChoice.hidden = true;
    saveError.textContent = "";
    savePanel.hidden = false;
    saveInputs.state_file.focus();
    command("save_choices", {}, [], reply => {
      if (!reply.ok || savePanel.hidden || saving || generation !== saveGeneration) return;
      saveChoices = reply.choices;
      fillChoices(projectChoice, saveChoices.map(choice => ({value: choice.state_file, label: choice.name})), "Nytt projekt…");
      const selected = saveChoices.find(choice => choice.state_file === saveInputs.state_file.value
        || (saveInputs.state_file.value === initialFile && storage && choice.path === storage.path));
      projectChoice.value = selected?.state_file || "";
      if (selected) {
        saveInputs.state_file.value = selected.state_file;
        saveInputs.state_file.hidden = true;
      }
      showKeyChoices(selected);
    });
  });
  saveActions.append(cancelSave, confirmSave);
  savePanel.append(node("h4", "", "Spara projekt"), saveFields,
    node("p", "gp-save-note", "Projektet sparas som JSON; .json läggs till om filändelse saknas. Relativa sökvägar avser kernelns arbetsmapp. Kopiera argumenten till notebooken för automatisk återställning."),
    saveError, saveActions);
  const copyArguments = button("Kopiera projekt + key", async () => {
    const argumentsText = projectStorage?.arguments;
    if (!argumentsText) return;
    try {
      await navigator.clipboard.writeText(argumentsText);
      if (!disposed) showMessage("Argumenten är kopierade. Klistra in dem i Grundplan(...).");
    } catch {
      if (disposed) return;
      argumentsFallback.hidden = false;
      argumentsFallback.value = argumentsText;
      argumentsFallback.focus();
      argumentsFallback.select?.();
      showMessage("Kopiera argumenten från textfältet under verktygsraden.");
    }
  }, "gp-copy-storage");
  if (!readOnly) heading.append(copyArguments, total);
  const argumentsFallback = node("input", "gp-copy-arguments");
  argumentsFallback.type = "text";
  argumentsFallback.readOnly = true;
  argumentsFallback.hidden = true;
  argumentsFallback.setAttribute("aria-label", "Argument för Grundplan");
  const exportJson = button("Exportera JSON", () => {
    command("export_json", {}, [], reply => { if (reply.ok) downloadProject(reply); });
  });
  const projectFile = node("p", "gp-project-file");
  let projectStorage = null;
  function showStorage(storage) {
    projectStorage = storage;
    projectFile.hidden = !storage;
    projectFile.textContent = storage ? "Projekt: " + storage.name + " · Fall: " + storage.key : "";
    projectFile.title = storage?.path || "";
    saveProject.title = storage ? "Välj projektfil och key. Nuvarande fil: " + storage.path : "Ange projektfil och key för lokal sparning";
    copyArguments.disabled = !storage?.arguments;
    argumentsFallback.hidden = true;
  }
  const exports = [];
  for (const [format, mime] of [["PDF", "application/pdf"], ["HTML", "text/html;charset=utf-8"]]) {
    const entry = { busy: false };
    entry.button = button("Exportera " + format, () => {
      entry.busy = true;
      entry.button.disabled = true;
      showMessage("Exporterar ritningssidan med etiketter…");
      command("export_" + format.toLowerCase(), {}, [], (reply, buffers) => {
        entry.busy = false;
        entry.button.disabled = !background().url;
        if (!reply.ok) return;
        const url = URL.createObjectURL(new Blob(buffers, { type: mime }));
        const a = node("a");
        a.href = url;
        a.download = reply.filename;
        root.append(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        showMessage(format + " med ritning och etiketter har exporterats till din nedladdningsmapp.");
      });
    });
    exports.push(entry);
  }
  if (!readOnly) toolbar.append(loadDrawing, loadProject, loadEffects, deleteAll, saveProject, exportJson, ...exports.map(entry => entry.button), node("span", "gp-separator"));
  if (readOnly && model.get("pdf")) toolbar.append(exports[0].button);
  const modes = new Map();
  for (const [key, label] of [["vaggsula", "+ Väggsula"], ["pelarsula", "+ Pelarsula"]]) {
    const b = button(label, () => setMode(mode === key ? "pan" : key));
    b.title = "Välj för att placera en sula. Klicka igen eller tryck Escape för att avbryta.";
    modes.set(key, b);
    if (!readOnly) toolbar.append(b);
  }
  const selectionBar = node("div", "gp-selection-bar");
  selectionBar.hidden = true;
  const selectionCount = node("span", "gp-selection-count");
  const editMany = button("Ändra markerade", openBulk, "gp-primary");
  const clearMany = button("Avmarkera", () => {
    if (bulkBusy) return;
    selected.clear(); tableAnchor = null; bulkSignature = ""; closeBulk(); renderMarkers(); showSelection();
  });
  selectionBar.append(selectionCount);
  if (!readOnly) selectionBar.append(editMany);
  selectionBar.append(clearMany);
  const slidingToggle = button("Glidningskontroll", () => {
    setMode("pan");
    setSliding({enabled: !sliding().enabled});
  });
  slidingToggle.title = "Visa globala riktningskontroller, koordinatsymbol och glidningsresultat.";
  if (!readOnly) toolbar.append(slidingToggle);
  const slidingControls = node("div", "gp-sliding-controls");
  const globalInputs = new Map();
  for (const axis of ["x", "y"]) {
    const choice = node("label", "gp-sliding-choice");
    const check = node("input");
    check.type = "checkbox";
    check.setAttribute("aria-label", "Kontroll " + axis.toUpperCase() + "_g");
    const caption = node("span");
    caption.append(node("span", "", "Kontroll "), symbolNode({base: axis.toUpperCase(), subscript: "g"}));
    choice.append(check, caption);
    const demand = node("label", "gp-sliding-demand");
    const input = node("input");
    input.type = "text"; input.inputMode = "decimal";
    input.setAttribute("aria-label", "Global H_" + axis + ",Ed i kN, EQU");
    input.title = "Total dimensionerande horisontallast i EQU. Riktningarna kontrolleras var för sig.";
    demand.append(symbolNode({base: "H", subscript: axis + ",Ed"}), input, node("span", "", "kN"));
    const group = node("div", "gp-sliding-control");
    group.append(choice, demand);
    slidingControls.append(group);
    check.addEventListener("change", () => setSliding({["check_" + axis]: check.checked}));
    input.addEventListener("input", () => {
      const value = input.value.trim().replace(",", ".");
      const numeric = value === "" ? NaN : Number(value);
      setSliding({["H_" + axis + "_Ed"]: Number.isFinite(numeric) ? numeric : null});
    });
    globalInputs.set(axis, {check, input, demand});
  }
  if (!readOnly) toolbar.append(slidingControls);
  const colourToggle = button("Färggruppering", () => setColour({enabled: !colour().enabled}), "gp-colour-toggle");
  colourToggle.title = "Gruppera etiketternas bakgrund efter mått eller vertikallast. Senaste inställningen behålls.";
  if (!readOnly) toolbar.append(colourToggle);
  const insulationWidgetToggle = button("Widget: Isolering", () => {
    const patch = {enabled: !insulationWidget().enabled};
    if (!patch.enabled) {cancelDrag(); overlaySelected = null;}
    const draft = {...insulationWidget(), ...patch}; insulationWidgetDraft = draft; update();
    command("insulation_widget", {settings: patch}, [], reply => {
      if (insulationWidgetDraft === draft) {insulationWidgetDraft = null; update();}
      if (!reply.ok) showMessage(reply.error, true);
    });
  });
  insulationWidgetToggle.title = "Visa antal sulor med och utan isolering samt littera utan isolering.";
  if (!readOnly) toolbar.append(insulationWidgetToggle);
  const colourControls = node("section", "gp-colour-controls");
  colourControls.hidden = true;
  colourControls.setAttribute("aria-label", "Inställningar för färggruppering");
  const colourCategories = node("div", "gp-colour-row");
  const colourCategoryButtons = new Map(), colourPhaseButtons = new Map(), colourTypeButtons = new Map();
  colourCategories.append(node("span", "gp-colour-caption", "Gruppera efter"));
  const categoryChoices = node("div", "gp-colour-choices");
  for (const [category, caption] of Object.entries(COLOUR_CATEGORIES)) {
    const choice = button(caption, () => {
      const current = colour();
      if (category === current.secondary) setColour({secondary: null});
      else if (category === current.category) {
        if (current.secondary) setColour({category: current.secondary, secondary: null});
      } else if (!current.secondary) setColour({secondary: category});
    });
    colourCategoryButtons.set(category, choice); categoryChoices.append(choice);
  }
  const colourLegendChoice = node("label", "gp-colour-legend-choice");
  const colourLegendCheck = node("input"); colourLegendCheck.type = "checkbox";
  colourLegendCheck.setAttribute("aria-label", "Visa färglegend");
  colourLegendCheck.addEventListener("change", () => setColour({show_legend: colourLegendCheck.checked}));
  colourLegendChoice.append(colourLegendCheck, node("span", "", "Visa legend"));
  colourCategories.append(categoryChoices, colourLegendChoice);
  const colourLoadOptions = node("div", "gp-colour-row");
  colourLoadOptions.append(node("span", "gp-colour-caption", "Lastfall"));
  const phaseChoices = node("div", "gp-colour-choices");
  for (const [phase, caption] of Object.entries(COLOUR_PHASES)) {
    const choice = button(caption, () => setColour({phase}));
    colourPhaseButtons.set(phase, choice); phaseChoices.append(choice);
  }
  const typeChoices = node("div", "gp-colour-choices");
  for (const [kind, caption] of [["pad", "Totala laster [kN]"], ["wall", "Linjelaster [kN/m]"]]) {
    const choice = button(caption, () => {
      colourError.textContent = ""; colourBounds.setCustomValidity("");
      colourEditType = kind; colourBounds.value = colour().bounds[kind].map(value => String(value).replace(".", ",")).join("; ");
      setColour({edit_type: kind});
    });
    choice.title = "Välj vilka sulors intervall och färger du vill ändra. Båda typerna grupperas på ritningen.";
    colourTypeButtons.set(kind, choice); typeChoices.append(choice);
  }
  colourLoadOptions.append(phaseChoices, node("span", "gp-colour-caption", "Intervall för"), typeChoices);
  const colourBoundsRow = node("div", "gp-colour-row");
  const colourBoundsLabel = node("label", "gp-colour-bounds");
  const colourBounds = node("input"); colourBounds.type = "text";
  colourBounds.maxLength = 600;
  colourBounds.setAttribute("aria-label", "Intervallgränser för färggruppering");
  colourBounds.placeholder = "100; 200; 400";
  colourBounds.title = "Ange gränser i stigande ordning, separerade med semikolon. Kommaseparerade heltal går också bra.";
  const colourBoundsCaption = node("span");
  colourBoundsLabel.append(colourBoundsCaption, colourBounds);
  const colourError = node("span", "gp-colour-error"); colourError.setAttribute("role", "status");
  const saveColourBounds = () => {
    const raw = colourBounds.value.trim();
    const parts = raw.includes(";") ? raw.split(";").map(value => value.trim().replace(",", ".")) : raw.split(",").map(value => value.trim());
    const bounds = parts.map(Number);
    const valid = parts.every(value => value !== "") && bounds.length <= 20 && bounds.every(Number.isFinite)
      && bounds.every((value, i) => !i || value > bounds[i - 1]);
    colourError.textContent = valid ? "" : "Ange 1–20 gränser i stigande ordning, t.ex. 100; 200; 400.";
    colourBounds.setCustomValidity(colourError.textContent);
    if (valid) setColour({bounds: {[colourEditType || colour().edit_type]: bounds}});
  };
  colourBounds.addEventListener("change", saveColourBounds);
  colourBounds.addEventListener("keydown", event => {if (event.key === "Enter") {event.preventDefault(); saveColourBounds();}});
  colourBoundsRow.append(colourBoundsLabel, colourError);
  const colourHint = node("p", "gp-colour-hint");
  const colourSwatches = node("div", "gp-colour-swatches");
  colourControls.append(colourCategories, colourLoadOptions, colourBoundsRow, colourHint, colourSwatches);
  const cancelCopy = button("Avbryt kopiering", () => {
    setMode("pan");
    showMessage("Kopieringen avbröts.");
  });
  cancelCopy.hidden = true;
  const sizeLabel = node("label", "gp-size-label", "Etikettstorlek ");
  sizeLabel.title = "Grundstorlek vid 100 % ritningszoom. Etiketterna följer ritningens zoom.";
  const sizeInput = node("input");
  sizeInput.type = "range";
  sizeInput.min = "60";
  sizeInput.max = "180";
  sizeInput.step = "10";
  sizeInput.setAttribute("aria-label", "Etikettstorlek i procent");
  const sizeText = node("output");
  sizeLabel.append(sizeInput, sizeText);
  sizeInput.addEventListener("input", () => {
    sizeDraft = Number(sizeInput.value);
    showLabelSize(sizeDraft);
  });
  sizeInput.addEventListener("change", () => {
    const value = Number(sizeInput.value);
    sizeDraft = value;
    command("label_size", { value }, [], () => {
      if (sizeDraft === value) {
        sizeDraft = null;
        showLabelSize(state().label_size ?? 100);
      }
    });
  });
  if (!readOnly) toolbar.append(cancelCopy);
  if (!readOnly) toolbar.append(sizeLabel);
  const measuring = () => mode === "measure" || mode === "calibrate";
  const calibration = () => calibrationDraft || state().calibration;
  const measureTool = button("Mät", () => {
    cancelDrag(); closeDialog(); closeBulk();
    setMode(measuring() ? "pan" : calibration() ? "measure" : "calibrate");
    viewport.focus({preventScroll: true});
  });
  measureTool.title = "Kalibrera med ett känt avstånd och mät mellan två punkter i meter.";
  toolbar.append(measureTool);
  const measurementBar = node("section", "gp-measurement-bar");
  measurementBar.hidden = true;
  measurementBar.setAttribute("aria-label", "Mätverktyg");
  const measurementHint = node("span", "gp-measurement-hint");
  const measurementOutput = node("output", "gp-measurement-value");
  measurementOutput.setAttribute("aria-label", "Uppmätt längd i meter");
  measurementOutput.setAttribute("aria-live", "polite");
  const calibrationFields = node("div", "gp-calibration-fields");
  const referenceLabel = node("label", "", "Referensmått ");
  const referenceInput = node("input");
  referenceInput.type = "text"; referenceInput.inputMode = "decimal";
  referenceInput.setAttribute("aria-label", "Känt referensmått i meter");
  referenceLabel.append(referenceInput, node("span", "", " m"));
  const referenceValue = () => Number(referenceInput.value.trim().replace(",", "."));
  const calibrationApply = button("Spara kalibrering", () => {
    if (calibrationBusy || drawingBusy || measurePoints.length !== 2) return;
    let value;
    try {
      value = validateCalibration({start: measurePoints[0], end: measurePoints[1], length_m: referenceValue()}, background());
    } catch (error) { showMessage(error.message, true); return; }
    calibrationDraft = value; calibrationBusy = true; showMeasurement();
    command("calibration", {calibration: value}, [], reply => {
      calibrationDraft = null; calibrationBusy = false;
      if (reply.ok && mode === "calibrate") setMode("measure");
      showMeasurement();
      if (!reply.ok) showMessage(reply.error, true);
    });
  }, "gp-primary");
  referenceInput.addEventListener("input", showMeasurement);
  referenceInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {event.preventDefault(); calibrationApply.click();}
  });
  calibrationFields.append(referenceLabel, calibrationApply);
  const calibrateTool = button("Kalibrera om", () => {cancelDrag(); setMode("calibrate");});
  const clearMeasurement = button("Rensa mått", () => {
    measurePoints = []; measureCursor = null; showMeasurement();
  });
  measurementBar.append(measurementHint, measurementOutput, calibrationFields, calibrateTool, clearMeasurement);
  const board = node("div", "gp-board");
  const viewport = node("div", "gp-viewport");
  viewport.tabIndex = 0;
  viewport.setAttribute("aria-label", readOnly ? "Grundplan. Klicka på en etikett för indata och resultat. Dra för att panorera. Shift + scroll zoomar."
    : "Grundplan. Dra för att panorera. Shift + scroll zoomar. Shift + vänsterdrag markerar för flerredigering. Klicka på en etikett för indata.");
  const sheet = node("div", "gp-sheet");
  const picture = node("img", "gp-picture");
  picture.alt = "Grundläggningsritning";
  picture.draggable = false;
  const markers = node("div", "gp-markers");
  const selectionBox = node("div", "gp-selection-box");
  selectionBox.hidden = true;
  selectionBox.setAttribute("aria-hidden", "true");
  const overlays = node("div", "gp-overlays");
  const axesOverlay = node("div", "gp-sliding-overlay gp-global-axes");
  axesOverlay.dataset.kind = "symbol";
  const axesButton = button("", () => { overlaySelected = "symbol"; renderSlidingGeometry(); }, "gp-axis-symbol gp-sliding-handle");
  axesButton.setAttribute("aria-label", "Globalt koordinatsystem: X_g åt höger, Y_g uppåt." + (readOnly ? "" : " Dra för att flytta."));
  const svgNode = (name, attributes, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const measurementOverlay = node("div", "gp-measurement-overlay");
  measurementOverlay.setAttribute("aria-hidden", "true");
  measurementOverlay.hidden = true;
  const measurementSvg = svgNode("svg", {"aria-hidden": "true"});
  measurementOverlay.append(measurementSvg);
  const axesSvg = svgNode("svg", {viewBox: "0 0 200 200", "aria-hidden": "true"});
  axesSvg.append(svgNode("path", {d: "M32 156H158M32 156V36", fill: "none", stroke: "currentColor", "stroke-width": 3}),
    svgNode("path", {d: "M158 156L147 151V161ZM32 36L27 47H37Z", fill: "currentColor"}),
    svgNode("circle", {cx: 32, cy: 156, r: 4, stroke: "currentColor", "stroke-width": 2, fill: "white"}));
  for (const [letter, x, y] of [["X", 168, 163], ["Y", 24, 24]]) {
    const text = svgNode("text", {x, y, fill: "currentColor", "font-size": 22, "font-style": "italic"}, letter);
    text.append(svgNode("tspan", {"baseline-shift": "sub", "font-size": 13}, "g"));
    axesSvg.append(text);
  }
  axesButton.append(axesSvg);
  const axesResize = button("", () => {}, "gp-axis-resize");
  axesResize.setAttribute("aria-label", "Ändra koordinatsymbolens storlek. Dra hörnet eller använd plus och minus.");
  axesResize.title = "Dra hörnet för att förstora eller förminska proportionellt";
  axesOverlay.append(axesButton, axesResize);
  const slidingLegend = node("section", "gp-sliding-overlay gp-sliding-legend");
  slidingLegend.dataset.kind = "legend";
  slidingLegend.setAttribute("aria-label", "Globala glidningsresultat");
  const slidingHeader = button("Glidningskontroll", () => {
    if (!readOnly) { overlaySelected = "legend"; renderSlidingGeometry(); }
  }, "gp-sliding-header gp-sliding-handle");
  slidingHeader.title = readOnly ? "Globala glidningsresultat" : "Dra rubriken för att flytta resultatrutan";
  slidingHeader.setAttribute("aria-label", "Glidningskontroll." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const slidingBody = node("div", "gp-sliding-body");
  slidingBody.setAttribute("aria-live", "polite");
  const legendResize = button("", () => {}, "gp-overlay-resize gp-legend-resize");
  legendResize.setAttribute("aria-label", "Ändra glidningsrutans storlek. Dra hörnet eller använd plus och minus.");
  legendResize.title = "Dra hörnet för att förstora eller förminska hela rutan proportionellt";
  slidingLegend.addEventListener("click", () => {
    if (!readOnly) { overlaySelected = "legend"; renderSlidingGeometry(); }
  });
  slidingLegend.append(slidingHeader, node("p", "gp-sliding-note", "X och Y kontrolleras var för sig"), slidingBody, legendResize);
  const colourLegend = node("section", "gp-sliding-overlay gp-colour-legend");
  colourLegend.dataset.kind = "colour";
  colourLegend.setAttribute("aria-label", "Legend för färggruppering");
  const colourHeader = button("Färggruppering", () => {
    if (!readOnly) {overlaySelected = "colour"; renderSlidingGeometry();}
  }, "gp-sliding-header gp-sliding-handle");
  colourHeader.setAttribute("aria-label", "Färggruppering." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const colourLegendBody = node("div", "gp-colour-legend-body");
  const colourResize = button("", () => {}, "gp-overlay-resize gp-colour-resize");
  colourResize.setAttribute("aria-label", "Ändra färglegendens storlek. Dra hörnet eller använd plus och minus.");
  colourResize.title = "Dra hörnet för att förstora eller förminska proportionellt";
  colourLegend.addEventListener("click", () => {
    if (!readOnly) {overlaySelected = "colour"; renderSlidingGeometry();}
  });
  colourLegend.append(colourHeader, colourLegendBody, colourResize);
  const insulationLegend = node("section", "gp-sliding-overlay gp-insulation-widget");
  insulationLegend.dataset.kind = "insulation"; insulationLegend.setAttribute("aria-label", "Isolering – sammanställning av sulor");
  const insulationHeader = button("Isolering", () => {
    if (!readOnly) {overlaySelected = "insulation"; renderSlidingGeometry();}
  }, "gp-sliding-header gp-sliding-handle");
  insulationHeader.setAttribute("aria-label", "Isolering." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const insulationBody = node("div", "gp-insulation-widget-body");
  const insulationResize = button("", () => {}, "gp-overlay-resize gp-insulation-resize");
  insulationResize.setAttribute("aria-label", "Ändra isoleringswidgetens storlek. Dra hörnet eller använd plus och minus.");
  insulationResize.title = "Dra hörnet för att förstora eller förminska proportionellt";
  insulationLegend.addEventListener("click", () => {
    if (!readOnly) {overlaySelected = "insulation"; renderSlidingGeometry();}
  });
  insulationLegend.append(insulationHeader, insulationBody, insulationResize);
  overlays.append(axesOverlay, slidingLegend, colourLegend, insulationLegend);
  sheet.append(picture, markers, overlays);
  viewport.append(sheet, selectionBox, measurementOverlay);
  const empty = node("div", "gp-empty");
  empty.append(node("span", "gp-empty-symbol", "＋"), node("h4", "", "Börja med din grundplan"),
    node("p", "", "Öppna en PDF eller bild. Placera sedan en tagg vid varje sula du vill beräkna."),
    button("Välj ritning", () => fileInput.click(), "gp-primary"));
  const zoomBar = node("div", "gp-zoom");
  const zoomText = node("span");
  zoomBar.append(button("−", () => setZoom(zoom / 1.25)), zoomText,
    button("+", () => setZoom(zoom * 1.25)), button("Anpassa", fit));
  const dialog = node("section", "gp-dialog");
  dialog.hidden = true;
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-label", "Sulans indata och resultat");
  const dialogHeader = node("div", "gp-dialog-header");
  const dialogTitle = node("strong");
  const minimize = button("Minimera", closeDialog);
  dialogHeader.append(dialogTitle, minimize);
  const form = node("form", "gp-form");
  // Reveal invalid fields inside collapsed groups before browser validation.
  form.noValidate = true;
  const fieldsBox = node("div", "gp-fields");
  const labelRow = node("label", "gp-label-row", "Littera");
  const labelInput = node("input");
  labelInput.type = "text";
  labelInput.maxLength = 80;
  labelInput.required = true;
  labelRow.append(labelInput);
  const basis = node("p", "gp-basis");
  const sketchToggle = button("Visa definitionsskiss", () => {
    if (!current()) return;
    sketchStates.set(active, !sketchStates.get(active));
    showSketch();
  }, "gp-sketch-toggle");
  const sketchSlot = node("div", "gp-sketch-slot");
  const sketch = node("section", "gp-sketch-panel");
  sketch.hidden = true;
  sketch.id = "gp-sketch-" + view;
  sketch.setAttribute("aria-label", "Definitionsskiss");
  sketchToggle.setAttribute("aria-controls", sketch.id);
  const sketchHeader = node("div", "gp-sketch-header");
  const sketchClose = button("Stäng", () => {
    sketchStates.set(active, false);
    showSketch();
    sketchToggle.focus({ preventScroll: true });
  });
  sketchClose.setAttribute("aria-label", "Stäng definitionsskissen");
  sketchHeader.append(node("strong", "", "Definitionsskiss"), sketchClose);
  const sketchBody = node("div", "gp-sketch-body");
  sketch.append(sketchHeader, sketchBody);
  const results = node("div", "gp-results");
  results.setAttribute("aria-live", "polite");
  const footer = node("div", "gp-dialog-footer");
  const remove = button("Ta bort", () => {
    const tag = current();
    if (tag && window.confirm("Ta bort " + tag.label + "?")) {
      command("delete", { id: tag.id }, [], (reply) => {
        if (reply.ok) {
          drafts.delete(tag.id);
          dirty.delete(tag.id);
          edits.delete(tag.id);
          sectionStates.delete(tag.id);
          sketchStates.delete(tag.id);
          areaPhases.delete(tag.id);
        }
      });
      closeDialog();
    }
  }, "gp-delete");
  const copy = button("Kopiera sula", () => {
    const tag = current();
    if (!tag) return;
    copySource = { id: tag.id, label: labelInput.value.trim() || tag.label, values: readValues() };
    closeDialog();
    setMode("copy");
    viewport.focus({ preventScroll: true });
  });
  copy.title = "Kopiera alla indata och välj en ny position på ritningen";
  footer.append(remove, copy);
  if (readOnly) form.append(results, basis, sketchToggle, sketchSlot, fieldsBox);
  else form.append(labelRow, basis, sketchToggle, sketchSlot, fieldsBox, results, footer);
  dialog.append(dialogHeader, form);
  const bulkDialog = node("section", "gp-dialog gp-bulk-dialog");
  bulkDialog.hidden = true;
  bulkDialog.setAttribute("role", "dialog");
  bulkDialog.setAttribute("aria-label", "Ändra markerade sulor");
  const bulkHeader = node("div", "gp-dialog-header");
  const bulkTitle = node("strong");
  const bulkMinimize = button("Minimera", closeBulk);
  bulkHeader.append(bulkTitle, bulkMinimize);
  const bulkForm = node("form", "gp-form gp-bulk-form");
  bulkForm.noValidate = true;
  const bulkNote = node("p", "gp-basis");
  const bulkFields = node("div", "gp-bulk-fields");
  const bulkFeedback = node("div", "gp-bulk-feedback");
  bulkFeedback.setAttribute("role", "status");
  const bulkFooter = node("div", "gp-dialog-footer");
  const applyMany = button("Tillämpa", applyBulk, "gp-primary");
  bulkFooter.append(applyMany);
  bulkForm.append(bulkNote, bulkFeedback, bulkFields, bulkFooter);
  bulkForm.addEventListener("submit", event => { event.preventDefault(); applyBulk(); });
  bulkDialog.append(bulkHeader, bulkForm);
  board.append(viewport, empty, zoomBar, dialog, sketch);
  if (!readOnly) board.append(bulkDialog);
  const status = node("div", "gp-status");
  status.setAttribute("role", "status");
  const legend = node("div", "gp-legend");
  legend.setAttribute("role", "list");
  legend.setAttribute("aria-label", "Etikettförklaring");
  for (const [state, label] of [["error", "Fel i indata"], ["ok", "U ≤ 100 %"],
    ["over", "U > 100 %"], ["horizontal", "Endast H-stabilitet"], ["stale", "Uppdaterar"]]) {
    const item = node("span", "gp-legend-item gp-tag-" + state, label);
    item.setAttribute("role", "listitem");
    legend.append(item);
  }
  const help = node("p", "gp-help",
    "Dra i ritningen med vänster eller höger musknapp för att panorera. Shift + scroll zoomar vid muspekaren. Shift + vänsterdrag ritar en urvalsruta. Shift + drag eller Shift + klick lägger till omarkerade etiketter och avmarkerar markerade. Dra direkt i en etikett för att flytta den. Klicka för indata och Kopiera sula. Klicka utanför rutan för att minimera. Etiketterna följer ritningens zoom.");
  const tableSection = node("section", "gp-table-section");
  const tableHeader = node("header", "gp-table-heading");
  const tableCount = node("span", "gp-table-count");
  const tableSelectionInfo = node("span", "gp-table-selection-info");
  tableHeader.append(node("h4", "", readOnly ? "Sulor – indata och resultat" : "Sulor – indata"), tableCount, tableSelectionInfo);
  const tableFeedback = node("div", "gp-table-feedback");
  tableFeedback.setAttribute("role", "status");
  const tableScroll = node("div", "gp-table-scroll");
  tableScroll.tabIndex = 0;
  tableScroll.setAttribute("role", "region");
  tableScroll.setAttribute("aria-label", readOnly ? "Indata och resultat för alla sulor" : "Redigerbar indatatabell för alla sulor");
  const inputTable = node("table", "gp-input-table");
  const tableHead = node("thead"), tableBody = node("tbody");
  const tableSelectAll = node("input"); tableSelectAll.type = "checkbox";
  tableSelectAll.setAttribute("aria-label", "Markera samtliga tabellrader");
  tableSelectAll.addEventListener("change", () => {
    if (bulkBusy || deleteBusy || importBusy) return;
    const checked = tableSelectAll.checked;
    closeDialog(); closeBulk(); selected.clear(); tableAnchor = null; bulkSignature = "";
    if (checked) for (const tag of state().tags) selected.add(tag.id);
    showSelection(); renderMarkers();
  });
  const tableRows = new Map();
  const tableSortHeads = new Map(), tableCollator = new Intl.Collator("sv", {numeric: true, sensitivity: "base"});
  let tableViewDraft = null;
  const tableView = () => tableViewDraft || state().table_view || {collapsed: [], sort: {key: null, direction: "ascending"}};
  let tableSort = tableView().sort;
  // Capture the sort scope only on a header click; selecting a range must not move its rows.
  let tableSortScope = null;
  tableScroll.addEventListener("focusout", () => requestAnimationFrame(() => {if (!disposed) sortTableRows();}));
  inputTable.append(tableHead, tableBody); tableScroll.append(inputTable);
  tableSection.append(tableHeader,
    node("p", "gp-field-note", readOnly
      ? "Värdena är låsta i denna resultatvy. Markeringar följs åt mellan ritning och tabell. Klicka på en grupp för att fälla ihop eller visa den, och på en kolumnrubrik för att sortera. Med markering sorteras bara markerade rader och samlas överst. Lasttypen avgör lastenheten. V_res visar yttre lastresultant i kN, exklusive egentyngd."
      : "Redigera direkt i cellerna; resultat uppdateras automatiskt. En ändring på en markerad rad gäller samma kolumn för alla markerade rader. Littera och fundamenttyp ändras individuellt. Markering i ritningen och tabellen följs åt. Klicka på grupper för att fälla ihop eller visa dem, och på kolumnrubriker för att sortera. Med markering sorteras bara markerade rader och samlas överst. Lasttypen avgör lastenheten. V_res visar yttre lastresultant i kN, exklusive egentyngd."),
    tableFeedback, tableScroll);
  const workspace = node("section", "gp-workspace");
  const panelHandles = new Map();
  const panelLimits = name => {
    const [low, high] = LAYOUT_LIMITS[name];
    return [low, name.endsWith("_width") ? Math.max(low, Math.min(high, root.clientWidth)) : high];
  };
  function showLayout() {
    const values = panelDrag?.preview || layout();
    for (const [kind, entry] of panelHandles) {
      const height = values[kind + "_height"], width = values[kind + "_width"];
      entry.target.style.height = height == null ? "" : height + "px";
      entry.wrapper.style.width = width == null ? "" : width + "px";
      if (kind === "table") entry.target.style.maxHeight = height == null ? "" : height + "px";
      entry.description.textContent = "Bredd " + Math.round(entry.wrapper.getBoundingClientRect().width)
        + " px, höjd " + Math.round(entry.target.getBoundingClientRect().height) + " px. " + entry.handle.title;
    }
  }
  function setLayout(patch) {
    const draft = {...layout(), ...patch}; layoutDraft = draft; showLayout();
    command("layout", {settings: patch}, [], reply => {
      if (layoutDraft === draft) {layoutDraft = null; showLayout();}
      if (!reply.ok) showMessage(reply.error, true);
    });
  }
  function endPanelDrag(commit = false) {
    const previous = panelDrag;
    if (!previous) return;
    panelDrag = null; root.classList.remove("gp-resizing-panels");
    if (previous.handle.hasPointerCapture(previous.pointerId)) previous.handle.releasePointerCapture(previous.pointerId);
    const patch = Object.fromEntries([previous.kind + "_width", previous.kind + "_height"]
      .filter(name => previous.preview[name] !== previous.saved[name]).map(name => [name, previous.preview[name]]));
    if (commit && previous.moved && Object.keys(patch).length) setLayout(patch); else showLayout();
  }
  function panelHandle(kind, wrapper, target, label) {
    const handle = node("div", "gp-panel-resize"), description = node("span", "gp-panel-size");
    handle.tabIndex = 0; handle.setAttribute("role", "button"); handle.setAttribute("aria-label", label);
    wrapper.id = "gp-" + kind + "-panel-" + view; handle.setAttribute("aria-controls", wrapper.id);
    description.id = "gp-" + kind + "-size-" + view; handle.setAttribute("aria-describedby", description.id);
    handle.title = "Dra för att ändra bredd och höjd. Piltangenter finjusterar; Shift ger större steg. Dubbelklick eller Enter återställer standardstorleken.";
    handle.append(node("span", "gp-panel-grip"), description);
    panelHandles.set(kind, {handle, wrapper, target, description});
    handle.addEventListener("pointerdown", event => {
      if (event.button !== 0 || panelDrag) return;
      event.preventDefault(); event.stopPropagation(); cancelDrag();
      handle.focus({preventScroll: true});
      panelDrag = {kind, handle, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY,
        startWidth: wrapper.getBoundingClientRect().width, startHeight: target.getBoundingClientRect().height,
        startPanelHeight: wrapper.getBoundingClientRect().height, saved: layout(), preview: layout(), moved: false};
      root.classList.add("gp-resizing-panels"); handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", event => {
      if (!panelDrag || panelDrag.pointerId !== event.pointerId || panelDrag.handle !== handle) return;
      event.preventDefault();
      const dx = event.clientX - panelDrag.startX, dy = event.clientY - panelDrag.startY;
      if (!panelDrag.moved && Math.hypot(dx, dy) < 3) return;
      panelDrag.moved = true;
      const widthName = kind + "_width", heightName = kind + "_height";
      const clamp = (name, value) => {const [low, high] = panelLimits(name); return Math.round(Math.max(low, Math.min(high, value)));};
      const width = clamp(widthName, panelDrag.startWidth + dx);
      panelDrag.preview[widthName] = width === Math.round(panelDrag.startWidth) ? panelDrag.saved[widthName] : width;
      showLayout();
      // Wrapped toolbar/help text should not push the dragged corner away from the pointer.
      const chromeHeight = wrapper.getBoundingClientRect().height - target.getBoundingClientRect().height;
      const height = clamp(heightName, panelDrag.startPanelHeight + dy - chromeHeight);
      panelDrag.preview[heightName] = height === Math.round(panelDrag.startHeight) ? panelDrag.saved[heightName] : height;
      showLayout();
    });
    handle.addEventListener("pointerup", event => {
      if (panelDrag?.handle === handle && panelDrag.pointerId === event.pointerId) endPanelDrag(true);
    });
    for (const eventName of ["pointercancel", "lostpointercapture"]) handle.addEventListener(eventName, event => {
      if (panelDrag?.handle === handle && panelDrag.pointerId === event.pointerId) endPanelDrag();
    });
    const reset = () => {endPanelDrag(); setLayout({[kind + "_height"]: null, [kind + "_width"]: null});};
    handle.addEventListener("dblclick", reset);
    handle.addEventListener("keydown", event => {
      if (event.key === "Escape" && panelDrag) {
        event.preventDefault(); event.stopPropagation(); endPanelDrag(); return;
      }
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "Enter", " "].includes(event.key)) return;
      event.preventDefault(); event.stopPropagation();
      if (["Enter", " "].includes(event.key)) {reset(); return;}
      const patch = {};
      for (const dimension of ["width", "height"]) {
        if (!["Home", "End"].includes(event.key) && (dimension === "width") !== ["ArrowLeft", "ArrowRight"].includes(event.key)) continue;
        const name = kind + "_" + dimension, [low, high] = panelLimits(name);
        const currentSize = dimension === "width" ? wrapper.getBoundingClientRect().width : target.getBoundingClientRect().height;
        const value = event.key === "Home" ? low : event.key === "End" ? high
          : currentSize + (["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1) * (event.shiftKey ? 100 : 20);
        patch[name] = Math.round(Math.max(low, Math.min(high, value)));
      }
      setLayout(patch);
    });
    return handle;
  }
  workspace.append(heading, toolbar);
  if (!readOnly) workspace.append(colourControls);
  workspace.append(measurementBar);
  if (!readOnly) workspace.append(importBar);
  workspace.append(selectionBar);
  if (!readOnly) workspace.append(savePanel, projectFile, argumentsFallback);
  workspace.append(board, status, legend);
  if (!readOnly) workspace.append(help, fileInput, projectInput, loadsInput);
  workspace.append(panelHandle("board", workspace, board, "Justera arbetsytans bredd och höjd"));
  tableSection.append(panelHandle("table", tableSection, tableScroll, "Justera tabellens bredd och höjd"));
  root.append(workspace, tableSection);
  el.append(root);

  function showMessage(message, error = false) {
    status.textContent = message;
    status.classList.toggle("gp-error-text", error);
  }
  async function upload(input, action) {
    const file = input.files[0];
    if (!file) return;
    if (deleteBusy || drawingBusy || (action === "drawing" && (importBusy || bulkBusy || calibrationBusy))
      || (action === "import_loads" && (importBusy || bulkBusy || loadImport()))) {
      input.value = "";
      return;
    }
    if (file.size > (action === "drawing" ? 40 : action === "import_loads" ? 5 : 60) * 1024 * 1024) {
      showMessage("Filen är för stor.", true);
      input.value = "";
      return;
    }
    showMessage("Öppnar " + file.name + "…");
    const updatingDrawing = action === "drawing" && !!background().url;
    if (action === "drawing") { drawingBusy = true; cancelDrag(); update(); }
    if (action === "import_loads") {
      importBusy = true;
      // Keep drafts, but prevent a dialog from submitting older loads during import.
      cancelDrag(); closeDialog(); closeBulk(); showLoadImport();
    }
    try {
      const buffer = await file.arrayBuffer();
      if (disposed) return;
      command(action, { name: file.name }, [buffer], (reply) => {
        if (action === "drawing") {
          drawingBusy = false;
          if (reply.ok) {
            measurePoints = []; measureCursor = null; calibrationDraft = null;
            if (measuring()) setMode(loadImport() && !loadImport().paused ? "import" : "pan");
            overlayPositions.clear(); pendingOverlayPositions.clear();
            update();
            showMessage(file.name + (updatingDrawing
              ? " uppdaterad. Sulor, indata och placeringar behållna. Kalibrera om mätverktyget vid behov."
              : " importerad."));
          } else { update(); showMessage(reply.error, true); }
          return;
        }
        if (action === "import_loads") {
          importBusy = false;
          if (reply.ok) {
            tableFeedback.replaceChildren();
            for (const id of reply.report?.updated_ids || []) {
              const tag = state().tags.find(tag => tag.id === id), draft = drafts.get(id);
              if (tag && draft) {
                // Keep unfinished geometry text, but never let an old load draft mask imported values.
                for (const name of ["lasttyp", "F_vy", "F_vy_bruk", "V_Ed_EQU", ...(lineLoads(tag.values) ? ["L_vagg", "L_vagg_minst_1", "glid_L"] : [])]) {
                  draft.values[name] = typeof tag.values[name] === "boolean" ? tag.values[name] : String(tag.values[name]).replace(".", ",");
                }
              }
              edits.set(id, (edits.get(id) || 0) + 1);
              slidingDirty.delete(id);
            }
            formId = null;
            closeDialog(); closeBulk(); selected.clear(); tableAnchor = null; bulkSignature = "";
            setMode(loadImport() ? "import" : "pan"); viewport.focus({preventScroll: true});
          }
          update();
          if (!reply.ok) showMessage(reply.error, true);
          else if (reply.report) showMessage(reply.report.updated + " befintliga sulor uppdaterade. "
            + (loadImport() ? reply.report.new + " nya sulor att placera. " + importCaption()
              : "Inga nya sulor att placera."));
          return;
        }
        if (reply.ok) {
          active = null;
          tableFeedback.replaceChildren();
          selected.clear(); tableAnchor = null; bulkIds = []; bulkSignature = ""; closeBulk();
          formId = null;
          dirty.clear();
          drafts.clear();
          edits.clear();
          positions.clear();
          pendingPositions.clear();
          sectionStates.clear();
          sketchStates.clear();
          areaPhases.clear();
          headingDraft = null;
          slidingDraft = null; overlaySelected = null;
          colourDraft = null; colourEditType = null; colourError.textContent = "";
          tableViewDraft = null; tableSortScope = null; insulationWidgetDraft = null;
          colourBounds.setCustomValidity("");
          overlayPositions.clear(); pendingOverlayPositions.clear(); slidingDirty.clear();
          inputSections.length = resultSections.length = 0;
          setMode("pan");
          update();
          showMessage(file.name + " öppnad.");
        }
      });
    } catch (error) {
      if (action === "drawing") { drawingBusy = false; update(); }
      if (action === "import_loads") { importBusy = false; showLoadImport(); }
      showMessage(error.message, true);
    }
    input.value = "";
  }
  fileInput.addEventListener("change", () => upload(fileInput, "drawing"));
  projectInput.addEventListener("change", () => upload(projectInput, "open"));
  loadsInput.addEventListener("change", () => upload(loadsInput, "import_loads"));
  function setMode(value) {
    if (mode === "import" && value !== "import" && loadImport() && !loadImport().paused && !importBusy) {
      command("import_control", {token: loadImport().token, operation: "pause"});
    }
    if (mode !== value || value === "calibrate") {
      measurePoints = []; measureCursor = null;
      if (value === "calibrate") referenceInput.value = "";
    }
    mode = value;
    if (value !== "copy") copySource = null;
    cancelCopy.hidden = value !== "copy";
    for (const [key, b] of modes) {
      b.classList.toggle("gp-selected", key === value);
      b.setAttribute("aria-pressed", String(key === value));
    }
    viewport.style.cursor = value === "pan" ? "grab" : "crosshair";
    showMeasurement();
    if (measuring()) return;
    if (value === "copy") showMessage("Klicka på ritningen för att placera en kopia av " + copySource.label + ". Escape avbryter.");
    else if (value === "import") showMessage(importCaption());
    else if (value !== "pan") showMessage("Klicka på ritningen där du vill placera en " +
      (value === "vaggsula" ? "väggsula." : "pelarsula."));
    else showMessage(readOnly
      ? "Shift + klick eller Shift + vänsterdrag framhäver valda sulor i tabellen. Escape avmarkerar. Dra för att panorera och använd Shift + scroll för att zooma."
      : "Dra i ritningen för att panorera. Shift + vänsterdrag markerar för flerredigering. Välj Väggsula eller Pelarsula för att placera en ny sula.");
  }
  function measurementPoint(event) {
    const rect = picture.getBoundingClientRect();
    const point = {x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height};
    return Object.values(point).every(value => Number.isFinite(value) && value >= 0 && value <= 1) ? point : null;
  }
  function chooseMeasurementPoint(event) {
    const point = measurementPoint(event);
    if (!point) {showMessage("Klicka på ritningen för att välja en mätpunkt."); return;}
    if (measurePoints.length === 2) measurePoints = [];
    if (measurePoints.length === 1 && drawingDistance(measurePoints[0], point, background()) < 1e-6) {
      showMessage("Välj en annan punkt än startpunkten.", true); return;
    }
    measurePoints.push(point); measureCursor = null;
    showMeasurement();
    if (mode === "calibrate" && measurePoints.length === 2) referenceInput.focus({preventScroll: true});
  }
  function showMeasurement() {
    measureTool.disabled = !background().url || calibrationBusy || bulkBusy || importBusy || drawingBusy || deleteBusy;
    measureTool.classList.toggle("gp-selected", measuring());
    measureTool.setAttribute("aria-pressed", String(measuring()));
    root.classList.toggle("gp-measuring", measuring());
    measurementBar.hidden = !measuring();
    calibrationFields.hidden = mode !== "calibrate" || measurePoints.length !== 2;
    calibrateTool.hidden = mode !== "measure";
    clearMeasurement.hidden = mode !== "measure" || !measurePoints.length;
    referenceInput.disabled = calibrationBusy || drawingBusy;
    calibrationApply.disabled = calibrationBusy || drawingBusy || !Number.isFinite(referenceValue()) || referenceValue() <= 0;
    const end = measurePoints[1] || measureCursor;
    measurementOutput.textContent = mode === "measure" && end && measurePoints[0] && calibration()
      ? new Intl.NumberFormat("sv-SE", {minimumFractionDigits: 1, maximumFractionDigits: 1}).format(measuredDistance(measurePoints[0], end, background(), calibration())) + " m" : "";
    measurementHint.textContent = mode === "calibrate"
      ? measurePoints.length === 2 ? "Ange det kända avståndet mellan punkterna." : "Kalibrering: klicka på " + (measurePoints.length ? "slutpunkten" : "startpunkten") + " för ett känt mått."
      : measurePoints.length === 2 ? "Klicka för att börja en ny mätning."
        : "Mätning: klicka på " + (measurePoints.length ? "slutpunkten" : "startpunkten") + ".";
    if (measuring()) showMessage(measurementHint.textContent + " Dra för att panorera. Shift + scroll zoomar. Escape avslutar.");
    renderMeasurement();
  }
  function renderMeasurement() {
    measurementOverlay.hidden = !measuring() || !measurePoints.length;
    measurementSvg.replaceChildren();
    if (measurementOverlay.hidden) return;
    const viewRect = viewport.getBoundingClientRect(), rect = picture.getBoundingClientRect();
    measurementSvg.setAttribute("viewBox", `0 0 ${viewRect.width} ${viewRect.height}`);
    const position = point => ({x: rect.left - viewRect.left + point.x * rect.width, y: rect.top - viewRect.top + point.y * rect.height});
    const start = position(measurePoints[0]), endPoint = measurePoints[1] || measureCursor;
    const color = mode === "calibrate" ? "#14695e" : "#a6473e";
    const dot = point => svgNode("circle", {cx: point.x, cy: point.y, r: 4, fill: "white", stroke: color, "stroke-width": 2});
    measurementSvg.append(dot(start));
    if (!endPoint) return;
    const end = position(endPoint);
    measurementSvg.append(svgNode("line", {x1: start.x, y1: start.y, x2: end.x, y2: end.y, stroke: color, "stroke-width": 2, "stroke-dasharray": measurePoints.length < 2 ? "5 4" : "none"}), dot(end));
    const caption = mode === "calibrate" ? "Referens" : measurementOutput.textContent;
    const x = (start.x + end.x) / 2, y = (start.y + end.y) / 2 - 12;
    const width = Math.max(74, caption.length * 8 + 14);
    measurementSvg.append(svgNode("rect", {x: x - width / 2, y: y - 17, width, height: 24, rx: 4, fill: "white", stroke: color}),
      svgNode("text", {x, y, fill: color, "text-anchor": "middle", "font-size": 14, "font-weight": 600}, caption));
  }
  function importCaption() {
    const queue = loadImport();
    if (!queue) return "Importera en lasteffektfil för att placera sulor.";
    return "Placera " + queue.next.label + " – " + (queue.next.kind === "vaggsula" ? "väggsula" : "pelarsula")
      + " (" + (queue.index + 1) + " av " + queue.total + ")";
  }
  function showLoadImport() {
    const queue = loadImport();
    importBar.hidden = readOnly || !queue;
    loadEffects.disabled = !background().url || !!queue || importBusy || drawingBusy || bulkBusy || deleteBusy;
    deleteAll.disabled = (!state().tags.length && !queue) || importBusy || bulkBusy || deleteBusy;
    importPause.disabled = importCancel.disabled = importBusy || deleteBusy;
    if (!queue) {
      lastImportToken = null;
      if (mode === "import") setMode("pan");
      return;
    }
    if (queue.token !== lastImportToken) {
      lastImportToken = queue.token;
      if (!queue.paused) { closeDialog(); closeBulk(); setMode("import"); }
    }
    importInstruction.textContent = (queue.paused ? "Placering pausad · " : "") + importCaption();
    importPause.textContent = queue.paused ? "Fortsätt placera" : "Pausa placering";
    const strip = queue.next.kind === "vaggsula", values = queue.next.values, unit = strip ? "kN/m" : "kN";
    importLoads.textContent = "Brott V " + precise(values.F_vy) + " " + unit
      + " · Bruk V " + precise(values.F_vy_bruk) + " " + unit
      + " · EQU V " + precise(values.V_Ed_EQU) + " " + unit
      + (strip ? " · Lvägg " + precise(values.L_vagg ?? values.glid_L) + " m" : "");
    if (!queue.paused && mode === "import") showMessage(importBusy ? "Placerar sula…" : importCaption());
  }
  function controlImport(operation) {
    const queue = loadImport();
    if (!queue || importBusy || readOnly) return;
    importBusy = true;
    if (operation !== "resume") setMode("pan");
    showLoadImport();
    command("import_control", {token: queue.token, operation}, [], reply => {
      importBusy = false;
      if (reply.ok && operation === "resume") { setMode("import"); viewport.focus({preventScroll: true}); }
      update();
      if (!reply.ok) showMessage(reply.error, true);
      if (reply.ok && operation === "cancel") showMessage("Importen avslutades. Redan placerade sulor behålls.");
    });
  }
  function showLabelSize(value) {
    sizeInput.value = value;
    sizeText.textContent = value + "%";
    root.style.setProperty("--gp-tag-scale", String(value / 100 * zoom));
  }
  function setSliding(patch) {
    if (patch.enabled === false) { cancelDrag(); overlaySelected = null; }
    const draft = {...sliding(), ...patch};
    slidingDraft = draft;
    update();
    command("sliding", {settings: patch}, [], () => {
      if (slidingDraft === draft) { slidingDraft = null; update(); }
    });
  }
  function setColour(patch) {
    if (patch.enabled === false || patch.show_legend === false) {cancelDrag(); overlaySelected = null;}
    const draft = {...colour(), ...patch};
    for (const name of ["bounds", "colors", "legend"]) {
      if (patch[name]) draft[name] = {...colour()[name], ...patch[name]};
    }
    colourDraft = draft;
    update();
    command("colour_grouping", {settings: patch}, [], reply => {
      if (colourDraft === draft) {colourDraft = null; update();}
      if (!reply.ok) showMessage(reply.error, true);
    });
  }
  function colourGroupCaption(group) {
    if (group.kind === "combination") return group.parts.map((part, index) => {
      const category = group.categories[index];
      const prefix = {t: "t ", b: "b_x ", l: "b_y "}[category] || "";
      return prefix + colourGroupCaption(part) + (["pad", "wall"].includes(part.kind) ? " " + part.unit : "");
    }).join(" · ");
    if (group.label) return group.label;
    if (group.kind === "geometry") return precise(group.value) + " m";
    return group.low == null ? "V < " + precise(group.high) : group.high == null ? "V ≥ " + precise(group.low)
      : precise(group.low) + " ≤ V < " + precise(group.high);
  }
  function showColour() {
    const settings = colour(), data = colourGroups(state().tags, settings);
    colourToggle.classList.toggle("gp-selected", settings.enabled);
    colourToggle.setAttribute("aria-pressed", String(settings.enabled));
    colourToggle.disabled = !background().url || drawingBusy;
    colourControls.hidden = !settings.enabled;
    const kind = colourEditType || settings.edit_type;
    const categories = [settings.category, settings.secondary].filter(Boolean), hasV = categories.includes("V");
    for (const [value, choice] of colourCategoryButtons) {
      const checked = categories.includes(value);
      choice.classList.toggle("gp-selected", checked); choice.setAttribute("aria-pressed", String(checked));
      choice.disabled = categories.length === 2 && !checked;
      choice.title = choice.disabled ? "Avmarkera en kategori för att välja en annan." : "Välj en eller två kategorier.";
    }
    for (const [buttons, selectedValue] of [[colourPhaseButtons, settings.phase], [colourTypeButtons, kind]]) {
      for (const [value, choice] of buttons) {
        choice.classList.toggle("gp-selected", value === selectedValue);
        choice.setAttribute("aria-pressed", String(value === selectedValue));
      }
    }
    colourLegendCheck.checked = settings.show_legend;
    colourLoadOptions.hidden = colourBoundsRow.hidden = !hasV;
    colourBoundsCaption.textContent = "Intervallgränser [" + (kind === "wall" ? "kN/m" : "kN") + "]";
    if (document.activeElement !== colourBounds && !colourBounds.validityMessage) {
      colourBounds.value = settings.bounds[kind].map(value => String(value).replace(".", ",")).join("; ");
    }
    colourHint.textContent = settings.secondary ? "Välj högst två kategorier. Samma kombination ger samma färg. Avmarkera en kategori för att byta. " + (hasV ? "Linjelaster och totala laster har separata intervall. " : "") + "Klicka på en färgruta för att välja färg."
      : settings.category === "V"
      ? "Linjelaster och totala laster har separata intervall. V är angiven last utan tillägg; EQU innehåller redan egentyngd. Klicka på en färgruta för att välja färg."
      : settings.category === "isolering" ? "Fem grupper efter isolering och valda bidragsriktningar under Glidning. Isolerade sulor bidrar inte. Klicka på en färgruta för att välja färg."
        : "En färg per unikt värde. Klicka på en färgruta för att välja färg.";
    colourSwatches.replaceChildren();
    for (const group of data.groups.filter(group => !hasV || (group.parts?.find(part => ["pad", "wall"].includes(part.kind))?.kind ?? group.kind) === kind || group.kind === "special" || group.parts?.some(part => part.kind === "special"))) {
      const row = node("label", "gp-colour-chip");
      const input = node("input"); input.type = "color"; input.value = group.color;
      input.setAttribute("aria-label", "Färg för " + colourGroupCaption(group) + (group.unit ? " [" + group.unit + "]" : ""));
      input.addEventListener("change", () => setColour({colors: {[group.key]: input.value}}));
      row.append(input, mathText("span", "", colourGroupCaption(group))); colourSwatches.append(row);
    }
    colourLegendBody.replaceChildren(node("p", "gp-colour-legend-title",
      settings.secondary ? categories.map(category => COLOUR_CATEGORIES[category]).join(" + ") + (hasV ? " · " + COLOUR_PHASES[settings.phase] : "")
        : settings.category === "isolering" ? "Isolering och glidmotstånd"
        : COLOUR_CATEGORIES[settings.category] + (settings.category === "V" ? " · " + COLOUR_PHASES[settings.phase] : " [m]")));
    let previousKind = null;
    for (const group of data.groups.filter(group => group.count > 0)) {
      if (settings.category === "V" && group.kind !== previousKind && ["pad", "wall"].includes(group.kind)) {
        colourLegendBody.append(node("strong", "gp-colour-legend-section",
          group.kind === "wall" ? "Linjelaster [kN/m]" : "Totala laster [kN]"));
      }
      previousKind = group.kind;
      const row = node("div", "gp-colour-legend-row");
      const swatch = node("span", "gp-colour-swatch"); swatch.style.background = group.background;
      row.append(swatch, mathText("span", "", colourGroupCaption(group)), node("span", "gp-colour-group-count", String(group.count)));
      colourLegendBody.append(row);
    }
    colourLegendBody.append(node("p", "gp-sliding-note", "Antal sulor visas till höger."));
    showInsulationWidget();
    renderSlidingGeometry();
  }
  function showInsulationWidget() {
    const settings = insulationWidget();
    insulationWidgetToggle.classList.toggle("gp-selected", settings.enabled);
    insulationWidgetToggle.setAttribute("aria-pressed", String(settings.enabled));
    insulationWidgetToggle.disabled = !background().url || drawingBusy;
    const tags = state().tags, uninsulated = tags.filter(tag => {
      const values = drafts.get(tag.id)?.values || tag.values;
      return values.endast_h_stabilitet || !values.isolering;
    });
    insulationBody.replaceChildren();
    for (const [caption, count] of [["Med isolering", tags.length - uninsulated.length], ["Utan isolering", uninsulated.length]]) {
      const row = node("div", "gp-insulation-count"); row.append(node("span", "", caption), node("strong", "", String(count)));
      insulationBody.append(row);
    }
    insulationBody.append(node("p", "gp-insulation-list-heading", "Föreskrivna utan isolering"),
      node("p", "gp-insulation-list", uninsulated.map(tag => drafts.get(tag.id)?.label.trim() || tag.label)
        .sort(tableCollator.compare).join(", ") || "Inga sulor"));
  }
  function overlayPosition(kind) {
    const key = background().page + ":" + kind;
    if (kind === "colour") return {...COLOUR_DEFAULTS.legend, ...(overlayPositions.get(key) || colour().legend)};
    if (kind === "insulation") {
      const {x, y, size} = overlayPositions.get(key) || insulationWidget(); return {x, y, size};
    }
    const defaults = kind === "symbol" ? {x: .06, y: .55, size: 160} : {x: .50, y: .04, size: 410};
    return {...defaults, ...(overlayPositions.get(key) || sliding().placements?.[background().page]?.[kind])};
  }
  function overlaySize(kind, value) {
    const [low, high] = kind === "symbol" ? [50, 600] : ["colour", "insulation"].includes(kind) ? [150, 900] : [205, 1230];
    return Math.max(low, Math.min(high, value));
  }
  function saveOverlayPosition(kind, page, position) {
    const key = page + ":" + kind;
    overlayPositions.set(key, position);
    pendingOverlayPositions.set(key, position);
    command(kind === "colour" ? "colour_placement" : kind === "insulation" ? "insulation_placement" : "sliding_placement", {kind, page, position}, [], () => {
      if (pendingOverlayPositions.get(key) === position) pendingOverlayPositions.delete(key);
      if (overlayPositions.get(key) === position) overlayPositions.delete(key);
      renderSlidingGeometry();
    });
  }
  for (const [element, kind, resize] of [[axesButton, "symbol", false], [axesResize, "symbol", true],
      [slidingHeader, "legend", false], [legendResize, "legend", true], [colourHeader, "colour", false], [colourResize, "colour", true],
      [insulationHeader, "insulation", false], [insulationResize, "insulation", true]]) {
    element.addEventListener("keydown", event => {
      if (readOnly) return;
      const p = {...overlayPosition(kind)}, step = event.shiftKey ? 20 : 5;
      if (resize && ["+", "=", "-"].includes(event.key)) {
        p.size = overlaySize(kind, p.size + (event.key === "-" ? -step : step));
      } else if (!resize && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        p.x = Math.max(0, Math.min(1, p.x + (event.key === "ArrowRight" ? step : event.key === "ArrowLeft" ? -step : 0) / background().width));
        p.y = Math.max(0, Math.min(1, p.y + (event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0) / background().height));
      } else return;
      event.preventDefault();
      saveOverlayPosition(kind, background().page, p);
      renderSlidingGeometry();
    });
  }
  function renderSlidingGeometry() {
    for (const [element, kind] of [[axesOverlay, "symbol"], [slidingLegend, "legend"], [colourLegend, "colour"], [insulationLegend, "insulation"]]) {
      const p = overlayPosition(kind);
      element.hidden = (kind === "colour" ? !colour().enabled || !colour().show_legend
        : kind === "insulation" ? !insulationWidget().enabled : !sliding().enabled) || !background().url;
      element.style.left = p.x * 100 + "%";
      element.style.top = p.y * 100 + "%";
      element.classList.toggle("gp-overlay-selected", !readOnly && overlaySelected === kind);
      if (kind === "symbol") {
        element.style.width = element.style.height = p.size * zoom + "px";
        axesResize.hidden = readOnly || overlaySelected !== "symbol";
      } else {
        const scale = zoom * p.size / (["colour", "insulation"].includes(kind) ? 300 : 410);
        element.style.transform = "scale(" + scale + ")";
        const resize = kind === "colour" ? colourResize : kind === "insulation" ? insulationResize : legendResize;
        resize.hidden = readOnly || overlaySelected !== kind;
        // Keep the corner target usable even when the whole legend is small.
        resize.style.transform = "scale(" + 1 / scale + ")";
      }
    }
  }
  function showSliding() {
    const settings = sliding();
    slidingToggle.classList.toggle("gp-selected", !!settings.enabled);
    slidingToggle.setAttribute("aria-pressed", String(!!settings.enabled));
    slidingToggle.disabled = !background().url;
    slidingControls.hidden = !settings.enabled;
    for (const [axis, {check, input, demand}] of globalInputs) {
      check.checked = !!settings["check_" + axis];
      demand.hidden = !check.checked;
      if (document.activeElement !== input) input.value = settings["H_" + axis + "_Ed"] ?? "";
    }
    slidingBody.replaceChildren();
    const table = node("table", "gp-sliding-table");
    const head = node("thead"), row = node("tr");
    for (const caption of ["Riktning", "Lasteffekt", "Motstånd", "U", "Sulor*"]) row.append(node("th", "", caption));
    head.append(row); table.append(head);
    const body = node("tbody");
    for (const axis of ["x", "y"]) {
      if (!settings["check_" + axis]) continue;
      const saved = state().sliding_result?.[axis];
      const r = saved || {status: "incomplete"};
      const waiting = slidingDraft || slidingDirty.size;
      const status = waiting ? "incomplete" : r.status;
      const tr = node("tr", "gp-slide-" + status);
      const direction = node("th");
      direction.append(symbolNode({base: axis.toUpperCase(), subscript: "g"}));
      tr.append(direction);
      for (const [value, suffix] of [[r.H_Ed, "Ed"], [r.H_Rd, "Rd"]]) {
        const cell = node("td");
        cell.append(symbolNode({base: "H", subscript: axis + "," + suffix}),
          node("span", "gp-sliding-value", waiting || value == null ? "—" : compactNumber(value, suffix === "Rd" ? 1 : 2) + " kN"));
        tr.append(cell);
      }
      const use = node("td");
      const label = {ok: "Godkänd", over: "Överskriden", off: "Ej vald", incomplete: "Ofullständig"}[status];
      use.append(node("strong", "", status === "incomplete" ? "—"
        : r.utilization == null ? "∞" : compactNumber(r.utilization * 100, 1) + " %"), node("small", "", label));
      const count = node("td", "gp-sliding-count", waiting ? "—" : String(r.count ?? 0));
      count.title = (r.contributors || []).map(tag => tag.label).join(", ") || "Inga sulor med positivt bidrag";
      tr.append(use, count); body.append(tr);
      if (!waiting && r.missing?.length) {
        const missing = node("tr"), cell = node("td", "gp-slide-missing", "Kontrollera glidningsindata: " + r.missing.join(", "));
        cell.setAttribute("colspan", "5"); missing.append(cell); body.append(missing);
      }
    }
    table.append(body);
    if (settings.check_x || settings.check_y) slidingBody.append(table,
      node("p", "gp-sliding-note", "* Sulor med positivt bidrag i respektive riktning."));
    else slidingBody.append(mathText("p", "gp-sliding-note", "Välj Kontroll X_g eller Kontroll Y_g i verktygsraden."));
    renderSlidingGeometry();
  }
  function setZoom(value, center) {
    const bg = background();
    if (!bg.width) return;
    const previous = zoom;
    zoom = Math.max(0.02, Math.min(4, value));
    const cx = center?.x ?? viewport.clientWidth / 2, cy = center?.y ?? viewport.clientHeight / 2;
    panX = cx + (panX - cx) * zoom / previous;
    panY = cy + (panY - cy) * zoom / previous;
    sheet.style.width = bg.width * zoom + "px";
    sheet.style.height = bg.height * zoom + "px";
    showLabelSize(sizeDraft ?? state().label_size ?? 100);
    placeSheet();
    zoomText.textContent = Math.round(zoom * 100) + "%";
    renderSlidingGeometry();
  }
  function placeSheet() {
    sheet.style.left = panX + "px";
    sheet.style.top = panY + "px";
    renderMeasurement();
  }
  function fit() {
    const bg = background();
    if (!bg.width) return;
    setZoom(Math.min((viewport.clientWidth - 48) / bg.width,
      (viewport.clientHeight - 48) / bg.height));
    panX = (viewport.clientWidth - bg.width * zoom) / 2;
    panY = (viewport.clientHeight - bg.height * zoom) / 2;
    placeSheet();
  }
  function closeDialog() {
    rememberSections(inputSections);
    rememberSections(resultSections);
    active = null;
    formId = null;
    dialog.hidden = true;
    sketch.hidden = true;
    renderMarkers();
  }
  function openDialog(tag) {
    if (bulkBusy || deleteBusy) return;
    closeBulk();
    if (!readOnly) { selected.clear(); tableAnchor = null; bulkSignature = ""; showSelection(); }
    active = tag.id;
    formId = null;
    update();
    const rect = board.getBoundingClientRect();
    const imageRect = picture.getBoundingClientRect();
    const left = imageRect.left - rect.left + tag.x * imageRect.width + 25;
    const top = imageRect.top - rect.top + tag.y * imageRect.height - 20;
    placeDialog(left, top);
    (readOnly ? minimize : labelInput).focus({ preventScroll: true });
  }
  function openComment(tag) {
    openDialog(tag);
    const entry = inputs.get("kommentar");
    if (!entry || active !== tag.id) return;
    entry.group.open = true;
    if (!sectionStates.has(tag.id)) sectionStates.set(tag.id, new Map());
    sectionStates.get(tag.id).set("input:kommentar", true);
    entry.group.scrollIntoView?.({block: "nearest"});
    if (!readOnly) entry.input.focus({preventScroll: true});
  }
  function commentBubble(tag, text) {
    const bubble = node("span", "gp-tag-comment");
    bubble.title = text; bubble.tabIndex = 0;
    bubble.setAttribute("role", "button"); bubble.setAttribute("aria-label", "Visa kommentar för " + tag.label);
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M5 3.5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-9l-5 4v-4a2 2 0 0 1-2-2v-10a2 2 0 0 1 2-2Z");
    path.setAttribute("fill", "none"); path.setAttribute("stroke", "currentColor"); path.setAttribute("stroke-width", "1.5");
    icon.append(path);
    for (const x of [8, 12, 16]) {
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", String(x)); dot.setAttribute("cy", "10.5"); dot.setAttribute("r", "1");
      dot.setAttribute("fill", "currentColor"); icon.append(dot);
    }
    bubble.append(icon);
    bubble.addEventListener("click", event => {event.stopPropagation(); openComment(tag);});
    bubble.addEventListener("keydown", event => {
      event.stopPropagation();
      if (["Enter", " "].includes(event.key)) {event.preventDefault(); openComment(tag);}
    });
    return bubble;
  }
  function placeDialog(x, y) {
    const inline = board.clientWidth < dialog.offsetWidth + 430 + 28;
    if (inline !== sketchInline) {
      sketchInline = inline;
      (inline ? sketchSlot : board).append(sketch);
      sketch.classList.toggle("gp-sketch-inline", inline);
    }
    const extra = !sketch.hidden && !inline ? 442 : 0;
    const left = Math.max(8, Math.min(board.clientWidth - dialog.offsetWidth - extra - 8, x));
    const top = Math.max(8, Math.min(board.clientHeight - dialog.offsetHeight - 8, y));
    dialog.style.left = left + "px";
    dialog.style.top = top + "px";
    if (!inline) {
      sketch.style.left = left + dialog.offsetWidth + 12 + "px";
      sketch.style.top = Math.max(8, Math.min(board.clientHeight - sketch.offsetHeight - 8, top)) + "px";
    }
  }
  function showSketch() {
    const tag = current();
    const onlyH = readOnly ? tag?.values.endast_h_stabilitet : inputs.get("endast_h_stabilitet")?.input.checked;
    sketchToggle.hidden = !!onlyH;
    const open = !!tag && !onlyH && !!sketchStates.get(tag.id) && !dialog.hidden;
    sketch.hidden = !open;
    sketchToggle.textContent = open ? "Dölj definitionsskiss" : "Visa definitionsskiss";
    sketchToggle.setAttribute("aria-expanded", String(open));
    if (open) {
      const strip = Number(readOnly ? tag.values.lang : inputs.get("lang")?.input.value ?? tag.values.lang) === 1;
      if (sketchType !== strip) {
        sketchType = strip;
        sketchBody.replaceChildren(definitionSketch(strip),
          node("p", "gp-sketch-axis-note", strip ? "x tvärs väggen · y längs väggen" : "Lokala axlar för sulan · måttordning bₓ × bᵧ"),
          node("p", "gp-field-note", "V är vertikallast. Mᵧ påverkar excentriciteten i x-led och Mₓ i y-led. Moment anges direkt vid sulan."),
          node("p", "gp-field-note", "Tecken enligt befintlig beräkning: positiva moment adderas till positiv placeringsexcentricitet i respektive led. Pilarna visar denna plusriktning."));
      }
      placeDialog(parseFloat(dialog.style.left) || 8, parseFloat(dialog.style.top) || 8);
    }
  }
  function insulationIcon(insulated) {
    const svgNode = (name, attributes) => {
      const element = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
      return element;
    };
    const icon = svgNode("svg", { viewBox: "0 0 104 60", "aria-hidden": "true", focusable: "false" });
    icon.append(
      svgNode("rect", { x: 10, y: 3, width: 84, height: 22, fill: "#eef3f3", stroke: "currentColor", "stroke-width": 3 }),
      svgNode("rect", { x: 10, y: 31, width: 84, height: 20, fill: "none", stroke: "currentColor", "stroke-width": 2.5 }),
    );
    for (let start = 0; start < 94; start += 14) {
      const a = Math.max(start, 10), b = Math.min(start + 20, 94);
      icon.append(svgNode("path", { d: `M${a} ${51 - (a - start)}L${b} ${51 - (b - start)}`,
        fill: "none", stroke: "currentColor", "stroke-width": 2 }));
    }
    if (!insulated) {
      // Strike only the insulation layer, leaving the footing intact.
      for (const [stroke, width] of [["var(--gp-tag-bg)", 8], ["currentColor", 3.5]]) {
        icon.append(svgNode("path", { d: "M1 56L103 30", fill: "none", stroke, "stroke-width": width }));
      }
    }
    return icon;
  }
  function renderMarkers() {
    markers.replaceChildren();
    const grouped = colour().enabled ? colourGroups(state().tags, colour()).assignments : null;
    for (const tag of state().tags.filter((t) => t.page === background().page)) {
      const summary = dirty.has(tag.id) ? null : tag.summary;
      const tagState = dirty.has(tag.id) ? "stale" : tag.status;
      const draft = drafts.get(tag.id);
      const values = draft?.values || tag.values;
      const onlyH = values.endast_h_stabilitet === true;
      const color = summary ? (onlyH ? "horizontal" : summary.utnyttjandegrad <= 1 ? "ok" : "over") : tagState;
      const marker = button("", (event) => {
        event.stopPropagation();
        // Pointer clicks are handled on pointerup, so dragging never opens the form.
        if (!event.detail) {
          if (measuring() && !(event.shiftKey || event.ctrlKey || event.metaKey)) return;
          if (event.shiftKey || event.ctrlKey || event.metaKey) toggleTag(tag);
          else openDialog(tag);
        }
      }, "gp-tag gp-tag-" + color);
      marker.dataset.tagId = tag.id;
      const group = grouped?.get(tag.id);
      if (group) {
        marker.style.setProperty("--gp-tag-bg", group.background);
        marker.dataset.colourGroup = group.key;
      }
      marker.title = readOnly ? "Klicka för indata och resultat · Shift + klick markerar raden i tabellen" : "Dra för att flytta · klicka för indata och kopiering";
      const position = positions.get(tag.id) || tag;
      marker.style.left = position.x * 100 + "%";
      marker.style.top = position.y * 100 + "%";
      marker.classList.toggle("gp-active", active === tag.id);
      marker.classList.toggle("gp-multi-selected", selected.has(tag.id));
      marker.setAttribute("aria-pressed", String(selected.has(tag.id)));
      const insulated = !onlyH && values.isolering === true;
      const insulationText = insulated ? "Med isolering" : "Utan isolering";
      const label = draft?.label.trim() || tag.label;
      const heading = node("span", "gp-tag-heading");
      const insulation = node("span", "gp-tag-insulation");
      insulation.append(insulationIcon(insulated), node("span", "", insulationText));
      heading.append(node("strong", "", label), insulation);
      const comment = typeof values.kommentar === "string" ? values.kommentar.trim() : "";
      if (comment) heading.append(commentBubble(tag, comment));
      const geometry = !onlyH && summary && Number.isFinite(summary.b) && Number.isFinite(tag.values.l) ? (tag.values.lang === 1 && tag.values.l === 1 ? "bₓ " + number(summary.b) + " m"
        : number(summary.b) + " × " + number(tag.values.l) + " m") : "";
      const showSlidingBlock = (sliding().enabled || onlyH) && !insulated && (values.glid_x || values.glid_y);
      const rawLength = values.glid_L;
      const length = rawLength == null || rawLength === "" ? NaN : Number(String(rawLength).replace(",", "."));
      const lengthText = !insulated && (values.glid_x || values.glid_y) && Number(values.lang) === 1 && Number.isFinite(length) && length > 0 && !showSlidingBlock
        ? " · L_su " + precise(length) + " m" : "";
      const text = (summary
        ? onlyH ? "Endast H-stabilitet" + (geometry ? " · " + geometry : "")
          : "U " + number(summary.utnyttjandegrad * 100, 1) + " % · " + geometry
        : ({ new: "Kontrollera indata", stale: "Uppdaterar…", error: "Kontrollera indata" }[tagState] || "Kontrollera indata")) + lengthText;
      const accessibleGeometry = !onlyH && summary && (tag.values.lang === 0 || tag.values.l !== 1) ? ", mått i ordningen bₓ × bᵧ" : "";
      const governing = summary?.isolering ? ", styrande: " + summary.styrande : "";
      marker.setAttribute("aria-label", label + ", " + insulationText + ", " + text + accessibleGeometry + governing);
      marker.title += accessibleGeometry + governing;
      if (group) marker.title += " · Färggrupp: " + colourGroupCaption(group) + (group.unit ? " [" + group.unit + "]" : "");
      marker.append(heading, mathText("span", "gp-tag-result", text));
      if (summary?.isolering) marker.append(node("span", "gp-governing", "Styrande: " + summary.styrande));
      const loads = node("span", "gp-tag-loads");
      const accessibleLoads = [];
      for (const group of model.get("schema").load_groups || []) {
        if (onlyH) continue;
        if (group.label === "Bruk" && !insulated) continue;
        const tokens = [];
        for (const field of group.fields) {
          const raw = values[field.name];
          const value = typeof raw === "string" ? Number(raw.replace(",", ".")) : raw;
          if (typeof value !== "number" || !Number.isFinite(value) || value === 0) continue;
          const unit = field.unit + (lineLoads(values) ? "/m" : "");
          let token = field.symbol + " " + precise(value) + " " + unit;
          if (Number(values.lang) === 0 && lineLoads(values) && ["F_vy", "F_vy_bruk"].includes(field.name)) {
            const total = dirty.has(tag.id) ? null : tag.load_resultants?.[field.name === "F_vy" ? "brott" : "bruk"];
            token += " → " + (Number.isFinite(total) ? precise(total) + " kN" : "—");
          }
          tokens.push(token);
        }
        if (!tokens.length) continue;
        const row = node("span", "gp-tag-load-row");
        const content = node("span", "gp-tag-load-values");
        content.append(...tokens.map(text => node("span", "", text)));
        row.append(node("strong", "", group.label), content);
        loads.append(row);
        accessibleLoads.push(group.label + ": " + tokens.join(", "));
      }
      if (accessibleLoads.length) {
        marker.append(loads);
        marker.title += " · Yttre laster, exklusive sulans egentyngd";
        marker.setAttribute("aria-label", marker.getAttribute("aria-label") + ", yttre laster: " + accessibleLoads.join("; "));
      }
      if (showSlidingBlock) {
        const section = node("span", "gp-tag-sliding");
        section.append(node("strong", "gp-tag-sliding-heading", "Glidmotstånd – globalt"));
        const grid = node("span", "gp-tag-sliding-grid");
        const data = node("span", "gp-tag-sliding-inputs"), capacities = node("span", "gp-tag-sliding-capacities");
        const add = (parent, base, subscript, value, bold = false) => {
          parent.append(symbolNode({base, subscript}), node(bold ? "b" : "span", "", value));
        };
        const value = (name, unit) => {
          const raw = values[name];
          const n = raw == null || raw === "" ? NaN : Number(String(raw).replace(",", "."));
          return Number.isFinite(n) ? compactNumber(n, 3) + " " + unit : "—";
        };
        add(data, "V", "Ed,EQU", value("V_Ed_EQU", lineLoads(values) ? "kN/m" : "kN"));
        if (values.lang == 1) {
          add(data, "L", "su", value("glid_L", "m"));
        }
        if (lineLoads(values) && values.L_vagg != null && values.L_vagg !== "") add(data, "L", "vägg", value("L_vagg", "m"));
        for (const axis of ["x", "y"]) if (values["glid_" + axis]) {
          const capacity = slidingDirty.has(tag.id) ? null : tag.sliding?.[axis];
          add(capacities, "H", axis + ",Rd,i", capacity == null ? "—" : compactNumber(capacity, 1) + " kN", true);
        }
        grid.append(data, capacities); section.append(grid); marker.append(section);
      }
      markers.append(marker);
    }
    syncTableSelection();
  }
  const groups = [
    ["Geometri", ["lang", "lasttyp", "endast_h_stabilitet", "b", "l", "l_override", "L_vagg_minst_1", "L_vagg", "t", "e_b_plac", "e_l_plac"]],
    ["Laster – Brott", ["F_vy", "F_hb", "F_hl", "M_insp_b", "M_insp_l"],
      "Yttre dimensionerande laster. Ange moment direkt vid sulan; inga moment från horisontallaster läggs till. Sulans egentyngd tillkommer med faktor 1,5."],
    ["Laster – Bruk", ["F_vy_bruk", "M_insp_b_bruk", "M_insp_l_bruk"],
      "Yttre långtidslaster och direkt angivna moment för isoleringskontrollen. Sulans egentyngd tillkommer med faktor 1,0. Värden kan anges även utan isolering; kontrollen används när isolering aktiveras."],
    ["Jord - Allm. Bärighets.", ["c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "d", "delta_h", "beta", "alpha",
      "eta", "gamma_m", "gamma_m0", "gamma_Rd"]],
    ["Isolering", ["isolering", "isolerprodukt", "f_d_brott", "f_d_bruk"],
      "Ange färdiga dimensionerande bärförmågor f_d,brott och f_d,bruk. Trycket över effektiv area kontrolleras i respektive lastkombination. Isoleringen förutsätts täcka hela den effektiva arean."],
    ["Glidning", ["glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L"],
      "V_Ed,EQU ska redan inkludera sulans egentyngd. X_g och Y_g är separata lastfall. Välj de riktningar där sulans glidmotstånd får utnyttjas. Isolerade sulor bidrar med 0 kN."],
    ["Kommentar", ["kommentar"]],
  ];
  const fieldSchema = new Map(model.get("schema").fields.map((field) => [field.name, field]));
  const resultantFields = new Map(["brott", "bruk"].map(phase => ["V_res_" + phase,
    {name: "V_res_" + phase, type: "result", phase, label: "Yttre lastresultant – " + phase, unit: "kN",
      display_symbol: {base: "V", subscript: "res"}}]));
  const tableSchema = new Map([...fieldSchema, ...resultantFields]);
  const tableGroups = groups.map(([label, names]) => [label, names.filter(name => fieldSchema.has(name))
    .flatMap(name => [name, ...(name === "F_vy" ? ["V_res_brott"] : name === "F_vy_bruk" ? ["V_res_bruk"] : [])])]);
  const groupedNames = new Set(tableGroups.flatMap(([, names]) => names));
  const extraNames = [...fieldSchema.keys()].filter(name => !groupedNames.has(name));
  if (extraNames.length) tableGroups.push(["Övrigt", extraNames]);
  const tableNames = tableGroups.flatMap(([, names]) => names);
  const tableGroupHeads = new Map(), tableFieldHeads = new Map();
  const tableFieldClass = field => ["bool", "choice", "text"].includes(field.type) ? "gp-table-" + field.type : "gp-table-number";
  function setTableView(patch) {
    const draft = {...tableView(), ...patch}; tableViewDraft = draft;
    update();
    command("table_view", {settings: patch}, [], reply => {
      if (tableViewDraft === draft) {tableViewDraft = null; update();}
      if (!reply.ok) showMessage(reply.error, true);
    });
  }
  function chooseTableSort(key) {
    tableSortScope = selected.size ? new Set(selected) : null;
    const sort = {key, direction: tableSort.key === key
      ? tableSort.direction === "ascending" ? "descending" : "ascending"
      : key === "status" ? "descending" : "ascending"};
    setTableView({sort}); sortTableRows(true);
  }
  function buildTableHeader() {
    const groupRow = node("tr"), fieldRow = node("tr");
    const selectHead = node("th", "gp-table-select");
    selectHead.setAttribute("rowspan", "2"); selectHead.setAttribute("scope", "col");
    selectHead.append(tableSelectAll); groupRow.append(selectHead);
    for (const [label, className, key] of [["Littera", "gp-table-label", "label"], ["Status / U", "gp-table-status", "status"]]) {
      const th = node("th", className);
      th.setAttribute("rowspan", "2"); th.setAttribute("scope", "col"); groupRow.append(th);
      const sortButton = button(label + " ↕", () => chooseTableSort(key), "gp-table-sort");
      sortButton.setAttribute("aria-label", "Sortera efter " + (key === "label" ? "littera" : "status och utnyttjandegrad"));
      th.setAttribute("aria-sort", "none");
      th.append(sortButton); tableSortHeads.set(key, {th, button: sortButton, label});
    }
    for (const [label, names] of tableGroups) {
      if (!names.length) continue;
      const th = node("th", "gp-table-group");
      th.setAttribute("colspan", String(names.length)); th.setAttribute("scope", "colgroup"); groupRow.append(th);
      const key = names[0], fold = button(label, () => {
        const collapsed = new Set(tableView().collapsed);
        if (collapsed.has(key)) collapsed.delete(key); else collapsed.add(key);
        setTableView({collapsed: [...collapsed]});
      }, "gp-table-fold");
      fold.setAttribute("aria-label", "Visa eller dölj " + label); th.append(fold);
      const placeholder = node("th", "gp-table-folded-space"); placeholder.hidden = true; fieldRow.append(placeholder);
      tableGroupHeads.set(key, {th, fold, placeholder, names, label});
      for (const name of names) {
        const field = tableSchema.get(name), head = node("th", tableFieldClass(field));
        head.setAttribute("scope", "col");
        head.title = label + ": " + field.label;
        head.setAttribute("aria-label", head.title);
        const notation = field.display_symbol || (name === "l_override" ? {prefix: "Egen ", base: "b", subscript: "y"}
          : name === "glid_x" || name === "glid_y"
          ? {prefix: "Bidrar ", base: name === "glid_x" ? "X" : "Y", subscript: "g"} : {});
        const sortButton = button("", () => chooseTableSort(name), "gp-table-sort");
        sortButton.setAttribute("aria-label", "Sortera efter " + field.label);
        if (notation.base || notation.text) sortButton.append(symbolNode(notation, "gp-table-symbol"));
        else sortButton.append(node("span", "", name === "lang" ? "Modell" : name === "lasttyp" ? "Lasttyp" : name === "endast_h_stabilitet" ? "Endast H"
          : name === "isolerprodukt" ? "Produkt" : field.label));
        const unit = (field.unit || "").replace("^3", "³").replace(/^deg$/, "°");
        if (unit) sortButton.append(node("span", "gp-table-unit", "[" + (field.type !== "result" && ["kN", "kNm"].includes(unit) ? unit + " / " + unit + "/m" : unit) + "]"));
        const arrow = node("span", "gp-table-sort-arrow", "↕"); sortButton.append(arrow); head.append(sortButton);
        head.setAttribute("aria-sort", "none");
        tableSortHeads.set(name, {th: head, button: sortButton, arrow}); tableFieldHeads.set(name, head);
        fieldRow.append(head);
      }
    }
    tableHead.append(groupRow, fieldRow);
  }
  buildTableHeader();
  const tableText = value => value == null ? "" : typeof value === "number" ? String(value).replace(".", ",") : value;
  function tableDisplayValue(name, value, tag) {
    if (resultantFields.has(name)) {
      const total = dirty.has(tag.id) ? null : tag.load_resultants?.[resultantFields.get(name).phase];
      return Number.isFinite(total) ? precise(total) : "—";
    }
    if (tag.values.endast_h_stabilitet && name === "isolering") return "Nej";
    if (tag.values.endast_h_stabilitet && insulationNames.has(name)) return "—";
    if (tag.values.endast_h_stabilitet && bearingOnlyNames.has(name)) return "—";
    if (["L_vagg_minst_1", "glid_L", "l_override"].includes(name) && tag.values.lang === 0) return "—";
    if (name === "lasttyp" && tag.values.lang === 1) return "—";
    if (name === "L_vagg" && !lineLoads(tag.values)) return "—";
    if (name === "L_vagg" && tag.values.lang === 1 && !tag.values.endast_h_stabilitet && tag.values.L_vagg_minst_1) return "1";
    if (value == null || value === "") return "—";
    const field = fieldSchema.get(name);
    if (field?.type === "bool") return value ? "Ja" : "Nej";
    if (name === "lang") return Number(value) === 1 ? "Väggsula" : "Pelarsula";
    if (field?.type === "choice") return field.options?.find(option => String(option.value) === String(value))?.label ?? tableText(value);
    return tableText(value);
  }
  function tableTargets(id, name) {
    return state().tags.filter(tag => tag.id === id ||
      (name !== "label" && name !== "lang" && selected.has(id) && selected.has(tag.id)));
  }
  function tableEdit(id, name, control) {
    if (readOnly || resultantFields.has(name) || importBusy || bulkBusy || deleteBusy) return;
    const tag = state().tags.find(tag => tag.id === id);
    if (!tag) return;
    tableFeedback.replaceChildren();
    const field = fieldSchema.get(name);
    const raw = field?.type === "bool" ? control.checked : control.value;
    if (name === "label" && (!raw.trim() || raw.length > 80)) {
      control.setCustomValidity("Ange ett littera med 1–80 tecken."); control.reportValidity(); return;
    }
    const targets = tableTargets(id, name), mixed = new Set(targets.map(tag => tag.values.lang)).size > 1;
    if (mixed && sameTypeFields.has(name)) {
      tableFeedback.replaceChildren(node("p", "gp-error-text", "Välj enbart väggsulor eller enbart pelarsulor för att ändra last- och längdfält gemensamt."));
      return;
    }
    if (loadTypeFields.has(name) && new Set(targets.map(tag => lineLoads(tag.values))).size > 1) {
      tableFeedback.replaceChildren(node("p", "gp-error-text", "Välj samma lasttyp för att ändra last- och linjestödslängdfält gemensamt."));
      return;
    }
    let value = raw;
    if (field && !["bool", "text"].includes(field.type)) {
      const text = raw.trim().replace(",", ".");
      value = text === "" ? null : Number(text);
      if (value !== null && !Number.isFinite(value)) value = null;
      control.setCustomValidity(text !== "" && value === null ? "Ange ett tal." : "");
    } else control.setCustomValidity("");
    closeBulk(); bulkSignature = "";
    const calculationInput = name !== "label" && field.type !== "text" && !slidingNames.has(name);
    const revisions = new Map();
    for (const target of targets) {
      const draft = drafts.get(target.id) || {label: target.label,
        values: Object.fromEntries([...fieldSchema].map(([key, field]) => [key,
          field.type === "bool" ? target.values[key] : tableText(target.values[key])]))};
      if (name === "label") draft.label = raw;
      else draft.values[name] = raw;
      if (draft.values.endast_h_stabilitet) draft.values.isolering = false;
      if (name === "l_override" && !value && target.values.lang === 1) draft.values.l = "1";
      drafts.set(target.id, draft);
      if (calculationInput && value !== target.values[name]) dirty.add(target.id);
      const revision = (edits.get(target.id) || 0) + 1;
      edits.set(target.id, revision); revisions.set(target.id, revision);
      slidingDirty.add(target.id);
      if (active === target.id) formId = null;
    }
    update();
    const shared = targets.length > 1;
    const payload = shared ? {ids: targets.map(tag => tag.id), values: {[name]: value}}
      : {id, ...(name === "label" ? {label: raw.trim()} : {values: {[name]: value}})};
    command(shared ? "bulk_update" : "update", payload, [], reply => {
      for (const [targetId, revision] of revisions) if (edits.get(targetId) === revision) {
        slidingDirty.delete(targetId);
        if (reply.ok) dirty.delete(targetId);
      }
      update();
      if (!reply.ok) {
        tableFeedback.replaceChildren(node("p", "gp-error-text", reply.error)); showMessage(reply.error, true);
      }
    });
  }
  function makeTableRow(tag) {
    const row = node("tr"); row.dataset.tagId = tag.id;
    const selectCell = node("td", "gp-table-select"), select = node("input"); select.type = "checkbox";
    selectCell.append(select); row.append(selectCell);
    // Native change events do not carry Shift; the preceding checkbox click does.
    let shiftClick = false;
    select.addEventListener("click", event => {shiftClick = event.shiftKey === true;});
    select.addEventListener("change", event => {
      const range = shiftClick || event.shiftKey === true;
      shiftClick = false;
      if (bulkBusy || deleteBusy || importBusy) return;
      const checked = select.checked;
      closeDialog(); closeBulk(); bulkSignature = "";
      const order = [...tableBody.children].map(row => row.dataset.tagId);
      const anchor = order.indexOf(tableAnchor), end = order.indexOf(tag.id);
      const ids = range && anchor >= 0 ? order.slice(Math.min(anchor, end), Math.max(anchor, end) + 1) : [tag.id];
      if (!range || anchor < 0) tableAnchor = tag.id;
      for (const id of ids) if (checked) selected.add(id); else selected.delete(id);
      showSelection(); renderMarkers();
    });
    const controls = new Map(), cells = new Map(), placeholders = new Map(), labelCell = node("td", "gp-table-label");
    const label = node(readOnly ? "span" : "input", readOnly ? "gp-table-value" : "");
    if (!readOnly) {label.type = "text"; label.maxLength = 80; label.name = "table_label";}
    labelCell.append(label); controls.set("label", label);
    const result = node("td", "gp-table-status");
    row.append(labelCell, result);
    for (const name of tableNames) {
      const field = tableSchema.get(name), cell = node("td", tableFieldClass(field));
      if (tableGroupHeads.has(name)) {
        const placeholder = node("td", "gp-table-folded-space"); placeholder.hidden = true;
        row.append(placeholder); placeholders.set(name, placeholder);
      }
      cells.set(name, cell);
      if (readOnly || field.type === "result") {
        const value = node("span", "gp-table-value");
        if (field.type === "result") {
          value.dataset.field = name;
          cell.title = "Yttre lastresultant i kN, exklusive sulans egentyngd. Uppdateras automatiskt.";
        }
        cell.append(value); row.append(cell); controls.set(name, value);
        continue;
      }
      const control = node(field.multiline ? "textarea" : field.type === "choice" ? "select" : "input");
      if (field.multiline) control.rows = 2;
      control.name = "table_" + name;
      if (field.type === "choice") {
        for (const option of field.options || []) {
          const caption = name === "lang" ? Number(option.value) === 1 ? "Väggsula" : "Pelarsula" : option.label ?? String(option.value);
          const item = node("option", "", caption); item.value = option.value; control.append(item);
        }
      } else if (!field.multiline) control.type = field.type === "bool" ? "checkbox" : "text";
      if (!["bool", "text", "choice"].includes(field.type)) control.inputMode = "decimal";
      if (field.type === "text") cell.classList.add("gp-table-text");
      cell.append(control); row.append(cell); controls.set(name, control);
    }
    for (const [name, control] of controls) {
      control.dataset.tagId = tag.id; control.dataset.field = name;
      if (readOnly || resultantFields.has(name)) continue;
      const field = fieldSchema.get(name);
      control.addEventListener(["bool", "choice"].includes(field?.type) ? "change" : "input", () => tableEdit(tag.id, name, control));
      control.addEventListener("keydown", event => {
        if (event.key !== "Enter" || field?.multiline) return;
        event.preventDefault();
        const rows = [...tableBody.children], index = rows.findIndex(row => row.dataset.tagId === control.dataset.tagId);
        tableRows.get(rows[index + (event.shiftKey ? -1 : 1)]?.dataset.tagId)?.controls.get(name)?.focus({preventScroll: false});
      });
    }
    tableBody.append(row);
    return {row, controls, cells, placeholders, result, select};
  }
  function syncTableSelection() {
    const tags = state().tags, busy = bulkBusy || importBusy || deleteBusy;
    tableSelectAll.checked = !!tags.length && tags.every(tag => selected.has(tag.id));
    tableSelectAll.indeterminate = selected.size > 0 && !tableSelectAll.checked;
    tableSelectAll.disabled = !tags.length || busy;
    tableSelectionInfo.hidden = !selected.size;
    tableSelectionInfo.textContent = selected.size + (readOnly ? " markerade" : " markerade · ändra en cell för gemensamt värde");
    const mixed = new Set(selectionTags().map(tag => tag.values.lang)).size > 1;
    const mixedLoads = new Set(selectionTags().map(tag => lineLoads(tag.values))).size > 1;
    for (const tag of tags) {
      const entry = tableRows.get(tag.id);
      if (!entry) continue;
      entry.select.checked = selected.has(tag.id); entry.select.disabled = busy;
      entry.select.setAttribute("aria-label", "Markera " + tag.label + " i tabellen");
      entry.select.title = "Shift + klick markerar eller avmarkerar intervallet från föregående vanliga klick.";
      entry.row.classList.toggle("gp-table-row-selected", selected.has(tag.id));
      if (readOnly) continue;
      for (const [name, control] of entry.controls) {
        if (resultantFields.has(name)) continue;
        const values = {...tag.values, ...drafts.get(tag.id)?.values};
        const blocked = selected.has(tag.id) && (mixed && sameTypeFields.has(name) || mixedLoads && loadTypeFields.has(name));
        const ownLength = drafts.get(tag.id)?.values.l_override ?? tag.values.l_override;
        const atLeastOne = drafts.get(tag.id)?.values.L_vagg_minst_1 ?? tag.values.L_vagg_minst_1;
        const ignored = (drafts.get(tag.id)?.values.endast_h_stabilitet ?? tag.values.endast_h_stabilitet)
          && (bearingOnlyNames.has(name) || insulationNames.has(name));
        control.hidden = name === "lasttyp" && Number(values.lang) === 1;
        control.disabled = busy || blocked || (["L_vagg_minst_1", "glid_L", "l_override"].includes(name) && Number(values.lang) === 0)
          || (name === "lasttyp" && Number(values.lang) === 1) || (name === "L_vagg" && !lineLoads(values))
          || ignored || (name === "l" && tag.values.lang === 1 && !ownLength)
          || (name === "L_vagg" && Number(values.lang) === 1 && atLeastOne && !(drafts.get(tag.id)?.values.endast_h_stabilitet ?? tag.values.endast_h_stabilitet));
        control.title = ignored ? name === "isolering" ? "Endast H-stabilitet använder alltid Utan isolering."
          : "Används inte vid Endast H-stabilitet. Det sparade värdet behålls."
          : blocked ? "Välj samma beräkningsmodell och lasttyp för att ändra detta fält gemensamt."
          : name === "label" || name === "lang" ? "Ändras endast för denna sula."
          : selected.has(tag.id) && selected.size > 1 ? "Ändrar denna kolumn för alla " + selected.size + " markerade sulor."
          : name === "L_vagg" && Number(values.lang) === 1 && atLeastOne ? "Minst 1 m: lokal kontroll använder 1 m. Hela sparade Lvägg används för glidning. Avmarkera för att ange ett kortare linjestöd."
          : name === "l" && tag.values.lang === 1 ? "Aktivera Egen längd för att ändra fördelningslängden 1 m. bᵧ ändrar kontaktarean, inte den yttre lastresultanten." : "";
      }
    }
  }
  function showTable() {
    tableSection.hidden = !background().url;
    const tags = state().tags, ids = new Set(tags.map(tag => tag.id));
    if (!ids.has(tableAnchor)) tableAnchor = null;
    for (const [id, row] of tableRows) if (!ids.has(id)) {row.row.remove(); tableRows.delete(id);}
    const errors = tags.filter(tag => tag.status === "error").length;
    tableCount.textContent = tags.length + " sulor" + (errors ? " · " + errors + " med fel i indata" : "");
    for (const tag of tags) {
      if (!tableRows.has(tag.id)) tableRows.set(tag.id, makeTableRow(tag));
      const {controls, result} = tableRows.get(tag.id), draft = drafts.get(tag.id);
      const stale = dirty.has(tag.id), summary = stale ? null : tag.summary;
      result.textContent = summary ? summary.endast_h_stabilitet ? "Endast H" : "U " + number(summary.utnyttjandegrad * 100, 1) + "%"
        : stale || tag.status === "stale" ? "Uppdaterar…" : tag.status === "error" ? "Fel i indata" : "Kontrollera indata";
      result.className = "gp-table-status " + (summary ? summary.endast_h_stabilitet ? "gp-horizontal"
        : summary.utnyttjandegrad <= 1 ? "gp-pass" : "gp-fail" : "");
      result.title = tag.error || (summary?.endast_h_stabilitet ? "Jordens bärighet och isolering kontrolleras inte." : summary?.styrande) || "";
      for (const [name, control] of controls) {
        const field = tableSchema.get(name);
        control.setAttribute("aria-label", tag.label + ": " + (field?.label || "Littera"));
        if (readOnly || field?.type === "result") {
          control.textContent = tableDisplayValue(name, name === "label" ? tag.label : tag.values[name], tag);
          continue;
        }
        if (control === document.activeElement) continue;
        const value = name === "label" ? draft?.label ?? tag.label : draft?.values[name] ?? tag.values[name];
        if (field?.type === "bool") control.checked = value ?? false;
        else control.value = name === "L_vagg" && tag.values.lang === 1 && !(draft?.values.endast_h_stabilitet ?? tag.values.endast_h_stabilitet)
          && (draft?.values.L_vagg_minst_1 ?? tag.values.L_vagg_minst_1) ? "1" : tableText(value);
      }
    }
    tableSort = tableView().sort;
    const collapsed = new Set(tableView().collapsed);
    for (const [key, {th, fold, placeholder, names, label}] of tableGroupHeads) {
      const hidden = collapsed.has(key);
      th.setAttribute("colspan", String(hidden ? 1 : names.length));
      th.classList.toggle("gp-table-group-folded", hidden);
      fold.textContent = (hidden ? "▸ " : "▾ ") + label;
      fold.setAttribute("aria-expanded", String(!hidden)); placeholder.hidden = !hidden;
      for (const name of names) tableFieldHeads.get(name).hidden = hidden;
      for (const entry of tableRows.values()) {
        entry.placeholders.get(key).hidden = !hidden;
        for (const name of names) entry.cells.get(name).hidden = hidden;
      }
    }
    sortTableRows();
    syncTableSelection();
  }
  function sortTableRows(force = false) {
    for (const [key, head] of tableSortHeads) {
      const direction = tableSort.key === key ? tableSort.direction : "none";
      head.th.setAttribute("aria-sort", direction);
      const arrow = direction === "ascending" ? "↑" : direction === "descending" ? "↓" : "↕";
      if (head.arrow) head.arrow.textContent = arrow;
      else head.button.textContent = head.label + " " + arrow;
    }
    if (!tableSort.key) return;
    // Wait until editing ends before moving rows, so typing keeps its focus and caret.
    if (!readOnly && !force && document.activeElement?.closest("tbody") === tableBody) return;
    const label = tag => drafts.get(tag.id)?.label ?? tag.label;
    const statusKey = tag => {
      const utilization = !dirty.has(tag.id) && tag.summary?.utnyttjandegrad;
      return tag.status === "error" ? [2, 0]
        : typeof utilization === "number" && Number.isFinite(utilization) ? [0, utilization] : [1, 0];
    };
    const direction = tableSort.direction === "ascending" ? 1 : -1;
    const tags = state().tags;
    const sorted = (tableSortScope ? tags.filter(tag => tableSortScope.has(tag.id)) : [...tags]).sort((a, b) => {
      if (tableSort.key === "label") return direction * tableCollator.compare(label(a), label(b));
      if (tableSort.key === "status") {
        const [rankA, valueA] = statusKey(a), [rankB, valueB] = statusKey(b);
        return direction * (rankA - rankB || valueA - valueB) || tableCollator.compare(label(a), label(b));
      }
      const name = tableSort.key, field = tableSchema.get(name);
      const value = tag => {
        if (field?.type === "result") return dirty.has(tag.id) ? null : tag.load_resultants?.[field.phase];
        const raw = drafts.get(tag.id)?.values[name] ?? tag.values[name];
        if (name === "L_vagg" && tag.values.lang === 1 && !tag.values.endast_h_stabilitet && tag.values.L_vagg_minst_1) return 1;
        if (tableDisplayValue(name, raw, tag) === "—" || typeof raw === "string" && !raw.trim()) return null;
        return ["text", "choice"].includes(field?.type) ? tableDisplayValue(name, raw, tag)
          : field?.type === "bool" ? Number(raw) : Number(String(raw).replace(",", "."));
      };
      const va = value(a), vb = value(b);
      const missingA = va == null || typeof va === "number" && !Number.isFinite(va);
      const missingB = vb == null || typeof vb === "number" && !Number.isFinite(vb);
      if (missingA !== missingB) return missingA ? 1 : -1;
      const difference = missingA ? 0 : typeof va === "number" ? va - vb : tableCollator.compare(va, vb);
      return direction * difference || tableCollator.compare(label(a), label(b));
    });
    const rows = sorted.map(tag => tableRows.get(tag.id)?.row).filter(Boolean);
    // Keep the other rows in their current display order, including newly appended objects.
    if (tableSortScope) rows.push(...[...tableBody.children].filter(row => !tableSortScope.has(row.dataset.tagId)));
    if (rows.some((row, index) => tableBody.children[index] !== row)) tableBody.append(...rows);
  }
  const sameTypeFields = new Set(model.get("schema").bulk_same_type ||
    ["lasttyp", "l", "l_override", "L_vagg", "L_vagg_minst_1", "glid_L", "V_Ed_EQU", ...groups[1][1], ...groups[2][1]]);
  const loadTypeFields = new Set(["L_vagg", "V_Ed_EQU", ...groups[1][1], ...groups[2][1]]);
  function selectionTags() { return state().tags.filter(tag => selected.has(tag.id)); }
  function showSelection() {
    // Keep the canvas at the same screen position while the selection box is drawn.
    if (drag?.box) return;
    selectionBar.hidden = !selected.size;
    selectionCount.textContent = selected.size + " markerade";
    const titles = selectionTags().map(tag => tag.label).join(", ");
    selectionCount.title = titles;
    selectionBar.setAttribute("aria-label", "Markerade sulor: " + titles);
    editMany.disabled = clearMany.disabled = bulkBusy;
    syncTableSelection();
  }
  function toggleTag(tag) {
    if (bulkBusy) return;
    // Shift-click on an open single footing adds that footing to the selection.
    if (!readOnly && active) selected.add(active);
    closeDialog(); closeBulk();
    if (selected.has(tag.id)) selected.delete(tag.id); else selected.add(tag.id);
    bulkSignature = "";
    showSelection(); renderMarkers();
    viewport.focus({preventScroll: true});
  }
  function closeBulk() {
    if (bulkBusy) return;
    bulkDialog.hidden = true;
  }
  function openBulk() {
    if (readOnly || bulkBusy || !selected.size) return;
    closeDialog();
    const signature = [...selected].sort().join(":");
    if (signature !== bulkSignature) {
      bulkFeedback.replaceChildren();
      buildBulkFields();
    }
    bulkDialog.hidden = false;
    bulkDialog.style.left = Math.max(8, (board.clientWidth - bulkDialog.offsetWidth) / 2) + "px";
    bulkDialog.style.top = "8px";
    bulkMinimize.focus({preventScroll: true});
  }
  function buildBulkFields() {
    const tags = selectionTags();
    bulkIds = tags.map(tag => tag.id);
    bulkSignature = [...bulkIds].sort().join(":");
    bulkInputs.clear(); bulkFields.replaceChildren();
    bulkTitle.textContent = "Ändra " + tags.length + " markerade sulor";
    const types = new Set(tags.map(tag => tag.values.lang)), mixed = types.size > 1;
    const strip = !mixed && types.has(1);
    const mixedLoads = new Set(tags.map(tag => lineLoads(tag.values))).size > 1;
    const onlyH = tags.every(tag => tag.values.endast_h_stabilitet);
    const syncLength = () => {
      const length = bulkInputs.get("l"), override = bulkInputs.get("l_override");
      if (strip && length && override) {
        const enabled = override.choose.checked ? override.input.value === "true" : tags.every(tag => tag.values.l_override);
        length.input.disabled = length.choose.disabled = !enabled;
        if (!enabled) length.choose.checked = false;
        length.row.title = enabled ? "" : "Aktivera Egen längd för att ändra bᵧ.";
      }
      const support = bulkInputs.get("L_vagg"), minimum = bulkInputs.get("L_vagg_minst_1");
      if (strip && support && minimum && !onlyH) {
        const enabled = minimum.choose.checked ? minimum.input.value === "false" : tags.every(tag => !tag.values.L_vagg_minst_1);
        support.input.disabled = support.choose.disabled = !enabled;
        if (!enabled) support.choose.checked = false;
        support.row.title = enabled ? "" : "Avmarkera Minst 1 m för att ange en kort linjestödslängd.";
      }
      if (!mixed && !strip) {
        const choice = bulkInputs.get("lasttyp");
        const common = choice?.choose.checked ? choice.input.value === "1" : !mixedLoads && tags.every(tag => lineLoads(tag.values));
        if (support) {
          support.blocked = !common;
          support.choose.disabled = support.input.disabled = !common;
          if (!common) support.choose.checked = false;
          support.row.hidden = !common;
        }
        for (const [name, entry] of bulkInputs) if (loadTypeFields.has(name) && name !== "L_vagg") {
          const blocked = mixedLoads && !choice?.choose.checked;
          entry.blocked = blocked;
          entry.choose.disabled = entry.input.disabled = blocked;
          if (blocked) entry.choose.checked = false;
          const unit = fieldSchema.get(name).unit;
          const unitElement = [...entry.row.children[1].children].find(child => child.className === "gp-unit");
          if (unitElement) unitElement.textContent = common && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
        }
      }
    };
    bulkNote.textContent = "Kryssa i de fält som ska ersättas för alla markerade sulor. Övriga värden behålls. "
      + (mixed ? "Blandade sultyper: last- och längdfält kräver att du väljer enbart väggsulor eller enbart pelarsulor. "
        : strip ? "Väggsulor: laster anges per meter. " : "Pelarsulemodell: lasttypen avgör om lasten anges per meter eller totalt. ")
      + "Urval: " + tags.map(tag => tag.label).join(", ");
    for (const [index, [label, names, note]] of groups.entries()) {
      if (label === "Glidning" && !sliding().enabled && !tags.some(tag => tag.values.endast_h_stabilitet)) continue;
      const available = names.filter(name => fieldSchema.has(name) && name !== "lang"
        && !(onlyH && (bearingOnlyNames.has(name) || insulationNames.has(name)))
        && !(strip && name === "lasttyp")
        && !(!mixed && !strip && ["L_vagg_minst_1", "glid_L", "l_override"].includes(name)));
      if (!available.length) continue;
      const group = node("details", "gp-group");
      group.open = index === 0 || label === "Isolering";
      group.append(node("summary", "", label));
      if (note) group.append(mathText("p", "gp-field-note", note));
      for (const name of available) {
        const field = fieldSchema.get(name);
        const row = node("div", "gp-bulk-field");
        const choose = node("input");
        choose.type = "checkbox";
        choose.setAttribute("aria-label", "Ändra " + field.label);
        choose.title = "Ändra " + field.label + " för alla markerade sulor";
        const controlRow = node("div", "gp-field");
        const input = node(field.multiline ? "textarea" : ["bool", "choice"].includes(field.type) ? "select" : "input");
        if (field.multiline) input.rows = 3;
        input.name = "bulk_" + name;
        input.setAttribute("aria-label", "Gemensamt värde: " + field.label);
        const same = tags.every(tag => tag.values[name] === tags[0].values[name]);
        const value = same ? tags[0].values[name] : null;
        if (field.type === "bool") {
          for (const [key, caption] of [["", "Olika värden"], ["true", "Ja"], ["false", "Nej"]]) {
            const option = node("option", "", caption); option.value = key; input.append(option);
          }
          input.value = same ? String(value) : "";
          controlRow.classList.add("gp-choice-field");
        } else if (field.type === "choice") {
          const empty = node("option", "", "Olika värden"); empty.value = ""; input.append(empty);
          for (const option of field.options) {
            const item = node("option", "", option.label); item.value = option.value; input.append(item);
          }
          input.value = same ? value : ""; controlRow.classList.add("gp-choice-field");
        } else {
          if (!field.multiline) input.type = "text";
          if (field.type !== "text") input.inputMode = "decimal";
          input.value = same ? value ?? "" : "";
          input.placeholder = same ? "Ej angivet" : "Olika värden";
          if (field.type === "text") controlRow.classList.add("gp-text-field");
        }
        const caption = node("span", "gp-field-caption", field.label);
        const symbol = symbolNode(field.display_symbol || {}, "gp-field-symbol");
        symbol.setAttribute("aria-hidden", "true");
        const unit = (field.unit || "").replace("^3", "³").replace(/^deg$/, "°");
        const unitText = tags.every(tag => lineLoads(tag.values)) && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
        if (field.type === "text") controlRow.append(caption, input);
        else if (["bool", "choice"].includes(field.type)) controlRow.append(caption, symbol, input);
        else controlRow.append(caption, symbol, input, node("span", "gp-unit", unitText));
        const blocked = mixed && sameTypeFields.has(name) || mixedLoads && loadTypeFields.has(name);
        choose.disabled = input.disabled = blocked;
        if (blocked) row.title = "Välj samma sultyp för att ändra detta fält gemensamt.";
        const sync = () => { input.setCustomValidity(""); row.classList.toggle("gp-bulk-changed", choose.checked); syncLength(); };
        choose.addEventListener("change", sync);
        input.addEventListener(["bool", "choice"].includes(field.type) ? "change" : "input", () => {
          choose.checked = true; sync();
        });
        row.append(choose, controlRow); group.append(row);
        bulkInputs.set(name, {choose, input, row, group, blocked});
      }
      bulkFields.append(group);
    }
    syncLength();
  }
  function applyBulk() {
    if (readOnly || bulkBusy) return;
    const patch = {};
    let valid = true;
    for (const [name, {choose, input, group, blocked}] of bulkInputs) {
      if (!choose.checked || blocked) continue;
      const field = fieldSchema.get(name);
      const raw = input.value.trim().replace(",", ".");
      const value = field.type === "bool" ? (input.value === "true" ? true : input.value === "false" ? false : null)
        : field.type === "text" ? input.value : raw === "" ? null : Number(raw);
      const ok = field.type === "text" || (field.type === "bool" ? value !== null : value !== null && Number.isFinite(value));
      input.setCustomValidity(ok ? "" : field.type === "bool" ? "Välj Ja eller Nej." : "Ange ett tal.");
      if (!ok) { valid = false; group.open = true; input.reportValidity(); }
      patch[name] = value;
    }
    if (!valid) return;
    if (!Object.keys(patch).length) {
      bulkFeedback.textContent = "Välj minst ett fält att ändra."; return;
    }
    const ids = [...bulkIds];
    bulkBusy = true;
    applyMany.disabled = bulkMinimize.disabled = true;
    for (const entry of bulkInputs.values()) entry.choose.disabled = entry.input.disabled = true;
    showSelection();
    showLoadImport();
    bulkFeedback.textContent = "Uppdaterar markerade sulor…";
    command("bulk_update", {ids, values: patch}, [], reply => {
      bulkBusy = false;
      applyMany.disabled = bulkMinimize.disabled = false;
      if (reply.ok) {
        for (const id of ids) { dirty.delete(id); drafts.delete(id); slidingDirty.delete(id); edits.delete(id); }
        const report = reply.report;
        const message = report.calculated + " av " + report.updated + " sulor beräknade automatiskt.";
        buildBulkFields(); bulkFeedback.replaceChildren(node("p", "", message));
        for (const error of report.errors) bulkFeedback.append(node("p", "gp-error-text", error.label + ": " + error.error));
        bulkForm.scrollTop = 0;
        showMessage(message, report.errors.length > 0);
      } else {
        bulkFeedback.textContent = reply.error;
        for (const entry of bulkInputs.values()) entry.choose.disabled = entry.input.disabled = entry.blocked;
      }
      update();
    });
  }
  function rememberSections(sections) {
    // Read the DOM before rebuilding; native toggle events can arrive after closing.
    for (const { tagId, key, group } of sections) {
      if (!sectionStates.has(tagId)) sectionStates.set(tagId, new Map());
      sectionStates.get(tagId).set(key, group.open);
    }
    sections.length = 0;
  }
  function makeSection(tagId, key, label, expanded, sections) {
    const group = node("details", "gp-group");
    group.open = sectionStates.get(tagId)?.get(key) ?? expanded;
    group.append(node("summary", "", label));
    sections.push({ tagId, key, group });
    return group;
  }
  function buildFields(tag) {
    rememberSections(inputSections);
    fieldsBox.replaceChildren();
    inputs.clear();
    const draft = drafts.get(tag.id);
    for (const [index, [label, names, note]] of groups.entries()) {
      if (readOnly && names[0] === "F_vy_bruk" && !tag.values.isolering) continue;
      const group = makeSection(tag.id, "input:" + names[0], label, !readOnly && index < 2, inputSections);
      if (note && !readOnly) group.append(mathText("p", "gp-field-note", note));
      for (const name of names) {
        const field = fieldSchema.get(name);
        if (!field || ["l_override", "L_vagg_minst_1"].includes(name)) continue;
        const row = node(readOnly || ["l", "L_vagg"].includes(name) ? "div" : "label", "gp-field");
        const caption = node("span", "gp-field-caption", field.label);
        if (name === "l" && fieldSchema.has("l_override")) {
          const override = node(readOnly ? "span" : "label", "gp-length-override");
          const control = node(readOnly ? "span" : "input");
          if (readOnly) {control.textContent = "Egen längd: " + (tag.values.l_override ? "Ja" : "Nej"); override.append(control);}
          else {
            control.type = "checkbox"; control.name = "l_override";
            control.setAttribute("aria-label", "Egen längd för bᵧ");
            control.checked = draft?.values.l_override ?? tag.values.l_override ?? false;
            control.title = "Avmarkerad använder bᵧ = 1 m. Markerad tillåter eget mått.";
            override.append(control, node("span", "", "Egen längd"));
            control.addEventListener("input", () => edit(true));
          }
          caption.append(override);
          inputs.set("l_override", {input: control, row: override, unit: node("span"), group});
        }
        if (name === "L_vagg" && fieldSchema.has("L_vagg_minst_1")) {
          const override = node(readOnly ? "span" : "label", "gp-length-override");
          const control = node(readOnly ? "span" : "input");
          if (readOnly) {control.textContent = "Minst 1 m: " + (tag.values.L_vagg_minst_1 ? "Ja" : "Nej"); override.append(control);}
          else {
            control.type = "checkbox"; control.name = "L_vagg_minst_1";
            control.setAttribute("aria-label", "Linjestöd minst 1 m vid lokal kontroll");
            control.checked = draft?.values.L_vagg_minst_1 ?? tag.values.L_vagg_minst_1 ?? true;
            control.title = "Lokal bärighets- och isoleringskontroll använder 1 m. Hela sparade linjestödslängden behålls för glidning.";
            override.append(control, node("span", "", "Minst 1 m"));
            control.addEventListener("input", () => edit(true));
          }
          caption.append(override);
          inputs.set("L_vagg_minst_1", {input: control, row: override, unit: node("span"), group});
        }
        const notation = field.display_symbol || {};
        const symbol = symbolNode(notation, "gp-field-symbol");
        symbol.setAttribute("aria-hidden", "true");
        const symbolText = notation.text || (notation.prefix || "") + (notation.base || "")
          + (notation.subscript ? "_" + notation.subscript : "") + (notation.suffix || "");
        const accessibleLabel = field.label + (symbolText ? ", " + symbolText : "");
        if (field.type === "choice") row.classList.add("gp-choice-field");
        if (readOnly) {
          const value = tag.values[name];
          const text = field.type === "bool" ? (value ? "Ja" : "Nej")
            : field.type === "choice" ? (name === "lang" ? value === 1 ? "Väggsula" : "Pelarsula"
              : field.options.find(option => option.value === value)?.label ?? "—")
            : field.type === "text" ? (value || "—")
            : value == null ? "—" : number(value, 10);
          const output = node("span", "gp-value", text);
          const unit = node("span", "gp-unit", field.unit);
          if (["text", "bool"].includes(field.type)) {
            row.classList.add("gp-text-field");
            row.append(caption, output);
          } else {
            row.setAttribute("role", "group");
            row.setAttribute("aria-label", accessibleLabel);
            if (field.type === "choice") row.append(caption, symbol, output);
            else row.append(caption, symbol, output, unit);
          }
          group.append(row);
          inputs.set(name, { input: output, unit, row, group });
          continue;
        }
        const input = node(field.multiline ? "textarea" : field.type === "choice" ? "select" : "input");
        if (field.multiline) input.rows = 4;
        input.name = name;
        input.setAttribute("aria-label", accessibleLabel);
        if (field.type === "choice") {
          for (const option of field.options) {
            const opt = node("option", "", name === "lang" ? option.value === 1 ? "Väggsula" : "Pelarsula" : option.label);
            opt.value = option.value;
            input.append(opt);
          }
        } else if (field.type === "bool") {
          input.type = "checkbox";
          row.classList.add("gp-check-field");
        } else if (field.type === "text") {
          if (!field.multiline) input.type = "text";
          input.placeholder = name === "kommentar" ? "Skriv en kommentar…" : "T.ex. EPS S200";
          input.title = "Sparas som kommentar och påverkar inte beräkningen.";
          row.classList.add("gp-text-field");
        } else {
          input.type = "text";
          input.inputMode = "decimal";
          input.required = true;
        }
        if (field.type === "bool") input.checked = draft?.values[name] ?? tag.values[name] ?? false;
        else input.value = draft?.values[name] ?? tag.values[name] ?? "";
        const unit = node("span", "gp-unit", field.unit);
        if (field.type === "bool") row.append(input, caption);
        else if (field.type === "text") row.append(caption, input);
        else if (field.type === "choice") row.append(caption, symbol, input);
        else row.append(caption, symbol, input, unit);
        group.append(row);
        inputs.set(name, { input, unit, row, group });
        if (name === "L_vagg") {
          const fixed = node("span", "gp-value gp-wall-length-default", "1");
          fixed.hidden = true; row.append(fixed); unit.style.gridColumn = "4"; inputs.get(name).fixed = fixed;
        }
        input.addEventListener("input", () => edit(field.type !== "text" && !slidingNames.has(name)));
      }
      fieldsBox.append(group);
    }
  }
  function readValues() {
    return Object.fromEntries([...inputs].map(([name, { input }]) => {
      if (input.type === "checkbox") return [name, input.checked];
      if (fieldSchema.get(name).type === "text") return [name, input.value];
      const raw = input.value.trim().replace(",", ".");
      const value = raw === "" ? NaN : Number(raw);
      input.setCustomValidity(input.disabled || (!input.required && raw === "") || Number.isFinite(value) ? "" : "Ange ett tal.");
      return [name, Number.isFinite(value) ? value : null];
    }));
  }
  function fieldUnits() {
    const strip = readOnly ? current()?.values.lang === 1 : inputs.get("lang")?.input.value === "1";
    if (strip && !readOnly && inputs.has("lasttyp")) inputs.get("lasttyp").input.value = "1";
    const line = strip || (readOnly ? lineLoads(current()?.values || {}) : inputs.get("lasttyp")?.input.value === "1");
    const onlyH = readOnly ? current()?.values.endast_h_stabilitet : inputs.get("endast_h_stabilitet")?.input.checked;
    const atLeastOne = readOnly ? current()?.values.L_vagg_minst_1 : inputs.get("L_vagg_minst_1")?.input.checked;
    if (onlyH && !readOnly && inputs.has("isolering")) inputs.get("isolering").input.checked = false;
    const insulated = !onlyH && (readOnly ? current()?.values.isolering : inputs.get("isolering")?.input.checked);
    const selected = readOnly ? current()?.values.glid_x || current()?.values.glid_y
      : inputs.get("glid_x")?.input.checked || inputs.get("glid_y")?.input.checked;
    basis.textContent = readOnly
      ? (strip ? "Väggsula: laster och moment avser en meter vägg." : "Pelarsula: laster och moment avser hela sulan.") + " Egentyngd ingår i beräkningsresultatet."
      : strip
        ? "Väggsula: samtliga laster och moment avser en meter vägg. Egentyngd tillkommer i beräkningen."
        : "Pelarsula: ange totala laster och moment. Egentyngd tillkommer i beräkningen.";
    if (strip) {
      basis.replaceChildren(mathText("span", "", "Väggsula: laster och moment anges per meter linjestöd. Yttre lastresultant = angivet värde × "
        + (atLeastOne ? "1 m (Minst 1 m)." : "kort L_vägg.")
        + " Sulmåttet b_y anger fördelningslängden under sulan och ändrar inte den yttre lastresultanten. Egentyngd tillkommer."));
    }
    if (!strip && line) basis.replaceChildren(mathText("span", "", "Pelarsulemodell med linjelast: laster och moment anges per meter linjestöd och multipliceras med hela L_vägg. b_x och b_y anger kontaktmåtten. Egentyngd tillkommer i beräkningen."));
    if (onlyH) basis.replaceChildren(mathText("span", "", "Endast H-stabilitet: jordens bärighet och isolering kontrolleras inte. V_Ed,EQU ska redan innehålla sulans egentyngd."));
    for (const [name, entry] of inputs) {
      if (name === "lasttyp") {
        entry.row.hidden = strip;
        if (!readOnly) {entry.input.disabled = strip; entry.input.required = !strip;}
        continue;
      }
      if (name === "l_override") {
        entry.row.hidden = !strip || onlyH;
        if (!readOnly) {entry.input.disabled = !strip || onlyH; entry.input.required = false;}
        continue;
      }
      if (name === "L_vagg_minst_1") {
        entry.row.hidden = !strip || onlyH;
        if (!readOnly) {entry.input.disabled = !strip || onlyH; entry.input.required = false;}
        continue;
      }
      if (name === "L_vagg") {
        entry.row.hidden = !line;
        entry.unit.textContent = "m";
        entry.row.title = strip ? "Bärighet/isolering: Minst 1 m använder 1 m, annars angiven kort längd. Glidning använder hela sparade linjestödslängden."
          : "Hela linjestödslängden används för att omräkna linjelasten till total kraft. Sulmåtten ändrar inte resultanten.";
        if (readOnly) entry.input.textContent = strip && atLeastOne && !onlyH ? "1" : current()?.values.L_vagg == null ? "—" : number(current().values.L_vagg, 10);
        else {
          entry.input.hidden = strip && atLeastOne && !onlyH;
          entry.fixed.hidden = !entry.input.hidden;
          entry.input.disabled = !line || (strip && atLeastOne && !onlyH);
          entry.input.required = line && !(strip && atLeastOne) && !onlyH;
          entry.input.placeholder = onlyH || !strip ? "Hela linjestödslängden" : "Kortare än 1 m";
          if (entry.input.disabled) entry.input.setCustomValidity("");
        }
        continue;
      }
      if (slidingNames.has(name)) {
        const numeric = !["glid_x", "glid_y"].includes(name);
        const length = name === "glid_L";
        const disabled = (!sliding().enabled && !onlyH) || (length ? !strip : insulated);
        entry.row.hidden = (!sliding().enabled && !onlyH) || (length ? !strip : numeric && insulated);
        entry.unit.textContent = name === "V_Ed_EQU" ? (line ? "kN/m" : "kN") : fieldSchema.get(name).unit;
        const supportRaw = inputs.get("L_vagg")?.input.value;
        const hasSupportLength = supportRaw != null && supportRaw !== "";
        if (!readOnly) { entry.input.disabled = disabled; entry.input.required = numeric && !disabled && selected && !insulated && !(length && hasSupportLength);
          if (disabled) entry.input.setCustomValidity(""); }
        continue;
      }
      const unit = (fieldSchema.get(name).unit || "").replace("^3", "³").replace(/^deg$/, "°");
      entry.unit.textContent = line && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
      const insulationField = name.startsWith("f_d_");
      const ignored = onlyH && (bearingOnlyNames.has(name) || insulationNames.has(name));
      if (readOnly) {
        entry.row.hidden = ignored || !insulated && (insulationField || name.endsWith("_bruk"));
        continue;
      }
      entry.input.disabled = ignored || (insulationField && !insulated)
        || (name === "l" && strip && !inputs.get("l_override")?.input.checked);
      if (name === "l" && strip && !inputs.get("l_override")?.input.checked) entry.input.value = "1";
      entry.input.required = entry.input.type !== "checkbox" && fieldSchema.get(name).type !== "text"
        && !entry.input.disabled && (insulated || !name.endsWith("_bruk"));
      if (entry.input.disabled) entry.input.setCustomValidity("");
      entry.row.hidden = ignored || !insulated && name.startsWith("f_d_");
    }
    for (const group of new Set([...inputs.values()].map(entry => entry.group))) {
      group.hidden = ![...inputs.values()].some(entry => entry.group === group && !entry.row.hidden);
    }
    showSketch();
  }
  function edit(calculationInput) {
    if (!current()) return;
    if (calculationInput) {
      dirty.add(active);
    }
    edits.set(active, (edits.get(active) || 0) + 1);
    fieldUnits();
    // Keep raw text until calculation is acknowledged, including across minimization.
    drafts.set(active, {
      label: labelInput.value,
      values: Object.fromEntries([...inputs].map(([name, { input }]) => [name, input.type === "checkbox" ? input.checked : input.value])),
    });
    const values = readValues();
    if (sliding().enabled || values.endast_h_stabilitet) slidingDirty.add(active);
    showResult();
    renderMarkers();
    showSliding();
    showColour();
    showTable();
    const label = labelInput.value.trim();
    const id = active, revision = edits.get(id);
    command("update", { id, values, ...(label ? { label } : {}) }, [], reply => {
      if (edits.get(id) === revision) {
        slidingDirty.delete(id);
        if (reply.ok) dirty.delete(id);
      }
      update();
      if (!reply.ok) showMessage(reply.error, true);
    });
  }
  labelInput.addEventListener("input", () => edit(false));
  form.addEventListener("submit", event => event.preventDefault());
  function areaResult(tag) {
    const group = makeSection(tag.id, "result:area", "Effektiv area – planvy", true, resultSections);
    const phases = tag.summary.effective_area;
    const select = node("select", "gp-area-phase");
    select.setAttribute("aria-label", "Lastkombination för effektiv area");
    for (const phase of Object.keys(phases)) {
      const option = node("option", "", phase === "brott" ? "Brott" : "Bruk · långtidslast");
      option.value = phase;
      select.append(option);
    }
    select.value = phases[areaPhases.get(tag.id)] ? areaPhases.get(tag.id) : "brott";
    select.hidden = Object.keys(phases).length < 2;
    const content = node("div", "gp-area-content");
    const draw = () => {
      const a = phases[select.value];
      content.replaceChildren();
      const make = (name, attrs, text) => {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
        if (text !== undefined) element.textContent = text;
        return element;
      };
      const svg = make("svg", {viewBox: "0 0 320 260", role: "img", "aria-label":
        `Effektiv area ${precise(a.area)} m². Resultant: eₓ ${precise(a.ex)} m, eᵧ ${precise(a.ey)} m.`});
      // One scale for both axes. Include the placement point even if opposing
      // moments move a point outside the footing back inside it.
      const xmin = Math.min(-a.bx / 2, a.ex_placement), xmax = Math.max(a.bx / 2, a.ex_placement);
      const ymin = Math.min(-a.by / 2, a.ey_placement), ymax = Math.max(a.by / 2, a.ey_placement);
      const scale = Math.min(230 / (xmax - xmin), 170 / (ymax - ymin));
      const px = x => 166 + (x - (xmin + xmax) / 2) * scale;
      const py = y => 119 - (y - (ymin + ymax) / 2) * scale;
      const line = (x1, y1, x2, y2, color, dash) => svg.append(make("line", {
        x1, y1, x2, y2, stroke: color, "stroke-width": 1.4, ...(dash ? {"stroke-dasharray": dash} : {})}));
      const text = (x, y, value, anchor = "middle", color = "#58717a") => svg.append(make("text", {
        x, y, "font-size": 12, "text-anchor": anchor, fill: color}, value));
      const arrow = (x1, y1, x2, y2, color) => {
        const length = Math.hypot(x2 - x1, y2 - y1);
        if (length < .01) return;
        line(x1, y1, x2, y2, color);
        const ux = (x2 - x1) / length, uy = (y2 - y1) / length, size = Math.min(6, length);
        svg.append(make("path", {fill: color, d: `M${x2} ${y2}l${-size * ux + size * .45 * uy} ${-size * uy - size * .45 * ux}l${-size * .9 * uy} ${size * .9 * ux}Z`}));
      };
      const rect = (x, y, w, h, fill, stroke, className) => svg.append(make("rect", {
        x: px(x), y: py(y), width: w * scale, height: h * scale, fill, stroke, "stroke-width": 1.5, class: className}));
      rect(-a.bx / 2, a.by / 2, a.bx, a.by, "#f0f3f3", "#829799", "gp-footing-outline");
      rect(a.ex - a.bx_eff / 2, a.ey + a.by_eff / 2, a.bx_eff, a.by_eff, "#c3e4dc", "#267c69", "gp-effective-rectangle");
      line(px(-a.bx / 2), py(0), px(a.bx / 2), py(0), "#94a6aa", "3 3");
      line(px(0), py(-a.by / 2), px(0), py(a.by / 2), "#94a6aa", "3 3");
      // Dashed placement offset, then My/V in x and Mx/V in y.
      line(px(0), py(0), px(a.ex_placement), py(a.ey_placement), "#796985", "3 3");
      arrow(px(a.ex_placement), py(a.ey_placement), px(a.ex), py(a.ey_placement), "#ad5040");
      arrow(px(a.ex), py(a.ey_placement), px(a.ex), py(a.ey), "#976915");
      svg.append(make("circle", {cx: px(a.ex_placement), cy: py(a.ey_placement), r: 4, fill: "white", stroke: "#796985", "stroke-width": 1.5}));
      svg.append(make("circle", {cx: px(a.ex), cy: py(a.ey), r: 3.5, fill: "#18333b"}));
      text(px(a.ex) + 7, py(a.ey) - 7, "R", "start", "#18333b");
      arrow(270, 26, 301, 26, "#58717a"); text(309, 30, "x");
      arrow(270, 26, 270, 6, "#58717a"); text(261, 12, "y");
      text(160, 230, `bₓ = ${precise(a.bx)} m · bᵧ = ${precise(a.by)} m`);
      const areaLabel = make("text", {x: 160, y: 248, "font-size": 12, "text-anchor": "middle", fill: "#267c69"});
      areaLabel.append(make("tspan", {"font-style": "italic"}, "A"),
        make("tspan", {"baseline-shift": "sub", "font-size": 9}, "eff"),
        make("tspan", {}, ` = ${precise(a.area)} m²`));
      svg.append(areaLabel);
      const legend = node("div", "gp-area-legend");
      for (const [className, caption] of [["outline", "□ Hela sulan"], ["area", "Effektiv area"], ["placement", "○ Placering"],
        ["moment-x", "→ M_y/V i x-led"], ["moment-y", "→ M_x/V i y-led"]]) {
        legend.append(mathText("span", "gp-area-key-" + className, caption));
      }
      const list = node("dl", "gp-result-list gp-area-numbers");
      for (const [caption, value] of [
        ["V inkl. egentyngd", precise(a.V) + " " + tag.summary.lastenhet],
        ["M_y → x-led", precise(a.My) + " " + tag.summary.lastenhet.replace("kN", "kNm")],
        ["M_x → y-led", precise(a.Mx) + " " + tag.summary.lastenhet.replace("kN", "kNm")],
        ["b_x,eff", precise(a.bx_eff) + " m"], ["b_y,eff", precise(a.by_eff) + " m"],
      ]) list.append(mathText("dt", "", caption), node("dd", "", value));
      content.append(svg, legend, list,
        mathText("p", "gp-area-equation", `e_x = ${precise(a.ex_placement)} + (${precise(a.ex_moment)}) = ${precise(a.ex)} m`),
        mathText("p", "gp-area-equation", `e_y = ${precise(a.ey_placement)} + (${precise(a.ey_moment)}) = ${precise(a.ey)} m`),
        node("p", "gp-field-note", "e = placering + moment/V. R är lastresultanten och centrum för den effektiva arean. Effektiva mått = sulmått − 2|e|. Tecken enligt beräkningens pilar; x åt höger, y uppåt."),
        node("p", "gp-result-note", "Ekvivalent effektiv area för bärighetskontroll, inte en beräknad kontakttrycksfördelning. " + (tag.values.lang === 1 ? "Väggsulan visas som en " + precise(a.by) + " m-remsa." : "Lokala axlar; skissen är inte orienterad efter ritningen.")));
    };
    select.addEventListener("change", () => { areaPhases.set(tag.id, select.value); draw(); });
    group.append(select, content);
    draw();
    return group;
  }
  function showResult() {
    const tag = current();
    rememberSections(resultSections);
    results.replaceChildren();
    if (!tag) return;
    if (dirty.has(tag.id) || tag.status === "stale") {
      results.append(node("p", "", readOnly ? "Indata ändrade. Inget aktuellt resultat vid exporten." : "Uppdaterar resultat automatiskt…"));
      return;
    }
    if (tag.error) {
      results.append(node("p", "gp-error-text", tag.error));
      return;
    }
    const r = tag.summary;
    if (!r) {
      results.append(node("p", "", readOnly ? "Sulan var inte beräknad vid exporten." : "Kontrollera indata. Resultatet uppdateras automatiskt."));
      return;
    }
    if (r.endast_h_stabilitet) {
      results.append(node("strong", "gp-horizontal", "Endast H-stabilitet"),
        node("p", "gp-result-note", "Jordens bärighet och isolering kontrolleras inte för denna sula."));
      const slidingResult = tag.sliding;
      if (!(tag.values.glid_x || tag.values.glid_y)) {
        results.append(node("p", "gp-result-note", "Välj bidragsriktning under Glidning."));
      } else {
        if (slidingDirty.has(tag.id)) results.append(node("p", "", "Uppdaterar glidmotstånd…"));
        else if (slidingResult?.error) results.append(node("p", "gp-error-text", slidingResult.error));
        const list = node("dl", "gp-result-list");
        for (const axis of ["x", "y"]) if (tag.values["glid_" + axis]) {
          const capacity = slidingDirty.has(tag.id) ? null : slidingResult?.[axis];
          list.append(mathText("dt", "", "Glidningsbidrag H_" + axis + ",Rd,i"),
            node("dd", "", capacity == null ? "—" : compactNumber(capacity, 1) + " kN"));
        }
        results.append(list);
      }
      return;
    }
    const headline = node("div", "gp-result-main " + (r.utnyttjandegrad <= 1 ? "gp-pass" : "gp-fail"));
    headline.append(node("span", "", "Utnyttjandegrad"), node("strong", "", number(r.utnyttjandegrad * 100, 1) + "%"));
    const table = node("dl", "gp-result-list");
    for (const [label, value] of [
      ["Vertikallast V – brott", number(r.last) + " " + r.lastenhet],
      ["Jordens bärförmåga", number(r.barformaga) + " " + r.lastenhet],
      ["Bärförmåga q_bd", number(r.q_bd) + " kPa"],
      ["Effektivt mått b_x,eff", number(r.b_ef, 3) + " m"],
    ]) table.append(mathText("dt", "", label), node("dd", "", value));
    results.append(headline);
    if (r.isolering) {
      const checks = node("dl", "gp-result-list gp-checks");
      for (const check of r.kontroller) {
        checks.append(node("dt", "", check.label), node("dd", check.utnyttjandegrad <= 1 ? "gp-pass" : "gp-fail",
          number(check.utnyttjandegrad * 100, 1) + "%"));
      }
      results.append(node("p", "gp-field-note", "Styrande: " + r.styrande), checks);
    }
    results.append(table, node("p", "gp-result-note", "Jord: U = last / bärförmåga i brottgränstillstånd enligt befintlig modell."));
    if (r.load_conversion) {
      const c = r.load_conversion;
      results.append(mathText("p", "gp-field-note", "Yttre V i brott: " + precise(tag.values.F_vy) + " kN/m × L_vägg "
        + precise(c.support_length) + " m" + (c.at_least_one ? " (Minst 1 m)" : "") + " = " + precise(c.brott) + " kN. Fördelningslängd b_y = " + precise(c.by)
        + " m och påverkar inte den yttre lastresultanten. Resultatet ovan inkluderar sulans egentyngd."));
    }
    if (r.effective_area) results.append(areaResult(tag));
    if (r.isolering) {
      for (const [phase, label] of [["brott", "Brott"], ["bruk", "Bruk · långtidslast"]]) {
        const values = r.isolering;
        const group = makeSection(tag.id, "result:" + phase, "Isolering – " + label, false, resultSections);
        group.classList.add("gp-insulation-result");
        const list = node("dl", "gp-result-list");
        for (const [name, caption, unit] of [
          ["N", "V inkl. egentyngd", r.lastenhet],
          ["b_eff", "Effektivt mått b_x,eff", "m"], ["l_eff", "Effektivt mått b_y,eff", "m"],
          ["A_eff", "Effektiv area A_eff", "m²"],
          ["q_Ed", "Lasteffekt q_Ed", "kPa"], ["f_d", "Bärförmåga f_d," + phase, "kPa"],
        ]) list.append(mathText("dt", "", caption), node("dd", "", number(values["isolering_" + name + "_" + phase], 3) + " " + unit));
        group.append(list);
        results.append(group);
      }
      results.append(mathText("p", "gp-result-note", "Isolering: q_Ed = "
        + (tag.values.lang === 1 && !r.load_conversion ? "V × b_y" : "V") + " / (b_x,eff × b_y,eff). U = q_Ed / f_d. "
        + (tag.values.lang === 1 && !r.load_conversion ? "V avser last per meter vägg. " : "V avser total kraft. ")
        + "Bruk avser långtidslast; deformation och sättning beräknas inte."));
    }
  }
  function update() {
    const bg = background();
    const data = state();
    for (const id of selected) {
      if (!data.tags.some(tag => tag.id === id)) selected.delete(id);
    }
    if (!bulkDialog.hidden && bulkIds.some(id => !selected.has(id))) {
      closeBulk(); bulkSignature = "";
    }
    showLayout();
    showHeading();
    showLabelSize(sizeDraft ?? data.label_size ?? 100);
    const storage = data.storage;
    showStorage(storage);
    total.textContent = data.tags.length + (data.tags.length === 1 ? " sula" : " sulor");
    loadDrawing.disabled = drawingBusy || importBusy || bulkBusy || calibrationBusy || deleteBusy;
    loadDrawing.title = "Ersätt PDF eller bild och behåll sulor, indata och relativa placeringar. Mätverktyget behöver kalibreras om.";
    saveProject.disabled = saving;
    exportJson.disabled = !bg.url;
    for (const entry of exports) entry.button.disabled = entry.busy || !bg.url;
    empty.hidden = !!bg.url;
    sheet.hidden = !bg.url;
    zoomBar.hidden = !bg.url;
    for (const b of modes.values()) b.disabled = !bg.url || drawingBusy;
    showSelection();
    showLoadImport();
    if (bg.url !== lastBackground) {
      cancelDrag();
      measurePoints = []; measureCursor = null; calibrationDraft = null;
      lastBackground = bg.url;
      if (bg.url) picture.src = bg.url;
      else picture.removeAttribute("src");
      requestAnimationFrame(() => { if (!disposed) fit(); });
    }
    const tag = current();
    dialog.hidden = !tag;
    if (tag) {
      const draft = drafts.get(tag.id);
      dialogTitle.textContent = tag.label;
      if (formId !== tag.id) {
        formId = tag.id;
        labelInput.value = draft?.label ?? tag.label;
        buildFields(tag);
      } else if (!readOnly && !dirty.has(tag.id)) {
        for (const [name, { input }] of inputs) {
          if (document.activeElement !== input) {
            if (input.type === "checkbox") input.checked = draft?.values[name] ?? tag.values[name] ?? false;
            else input.value = draft?.values[name] ?? tag.values[name] ?? "";
          }
        }
        if (document.activeElement !== labelInput) labelInput.value = draft?.label ?? tag.label;
      }
      fieldUnits();
      showResult();
    } else sketch.hidden = true;
    renderMarkers();
    showSliding();
    showColour();
    showTable();
    showLayout();
    showMeasurement();
  }
  let drag = null;
  function selectionRectangle(event) {
    const bounds = viewport.getBoundingClientRect();
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const x = clamp(event.clientX, bounds.left, bounds.left + bounds.width);
    const y = clamp(event.clientY, bounds.top, bounds.top + bounds.height);
    const left = Math.min(drag.x, x), top = Math.min(drag.y, y);
    const right = Math.max(drag.x, x), bottom = Math.max(drag.y, y);
    return {left, top, right, bottom, width: right - left, height: bottom - top,
      localLeft: left - bounds.left, localTop: top - bounds.top};
  }
  function previewSelection(event) {
    const rect = selectionRectangle(event);
    selectionBox.hidden = false;
    selectionBox.style.left = rect.localLeft + "px";
    selectionBox.style.top = rect.localTop + "px";
    selectionBox.style.width = rect.width + "px";
    selectionBox.style.height = rect.height + "px";
    // Always toggle against the selection at pointerdown, so repeated moves do not toggle again.
    const ids = new Set(drag.beforeSelection);
    if (rect.width > 0 && rect.height > 0) for (const marker of markers.children) {
      const bounds = marker.getBoundingClientRect();
      if (bounds.left < rect.right && bounds.left + bounds.width > rect.left
        && bounds.top < rect.bottom && bounds.top + bounds.height > rect.top) {
        const id = marker.dataset.tagId;
        if (ids.has(id)) ids.delete(id); else ids.add(id);
      }
    }
    selected.clear();
    for (const id of ids) selected.add(id);
    renderMarkers();
  }
  function cancelDrag() {
    const previous = drag;
    drag = null;
    selectionBox.hidden = true;
    if (previous?.box) {
      selected.clear();
      for (const id of previous.beforeSelection) {
        if (state().tags.some(tag => tag.id === id && tag.page === background().page)) selected.add(id);
      }
      renderMarkers(); showSelection();
    }
    if (previous?.id) {
      if (pendingPositions.has(previous.id)) positions.set(previous.id, pendingPositions.get(previous.id));
      else positions.delete(previous.id);
    }
    if (previous?.overlay) {
      const key = previous.page + ":" + previous.overlay;
      if (pendingOverlayPositions.has(key)) overlayPositions.set(key, pendingOverlayPositions.get(key));
      else overlayPositions.delete(key);
      renderSlidingGeometry();
    }
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    viewport.classList.remove("gp-selecting");
    if (previous && viewport.hasPointerCapture(previous.pointerId)) viewport.releasePointerCapture(previous.pointerId);
    if (previous?.id) renderMarkers();
  }
  viewport.addEventListener("pointerdown", (event) => {
    if (![0, 2].includes(event.button) || drag || drawingBusy || deleteBusy || !background().url) return;
    if (event.button === 2) {
      event.preventDefault();
      viewport.focus({preventScroll: true});
      drag = {pan: true, x: event.clientX, y: event.clientY, left: panX, top: panY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    if (event.target.closest(".gp-tag-comment")) return;
    if (bulkBusy) return;
    if (measuring() && !(event.shiftKey || event.ctrlKey || event.metaKey)) {
      if (calibrationBusy || importBusy) return;
      event.preventDefault(); viewport.focus({preventScroll: true});
      drag = {measurement: true, x: event.clientX, y: event.clientY, left: panX, top: panY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    const overlay = event.target.closest(".gp-sliding-overlay");
    if (importBusy && (overlay || event.target.closest(".gp-tag"))) return;
    if (overlay) {
      const resize = event.target === axesResize || event.target === legendResize || event.target === colourResize || event.target === insulationResize;
      if (readOnly || (!event.target.closest(".gp-sliding-handle") && !resize)) return;
      event.preventDefault();
      setMode("pan");
      overlaySelected = overlay.dataset.kind;
      renderSlidingGeometry();
      const rect = overlay.getBoundingClientRect();
      drag = {overlay: overlay.dataset.kind, page: background().page, resize,
        width: rect.width, height: rect.height,
        position: {...overlayPosition(overlay.dataset.kind)}, x: event.clientX, y: event.clientY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    overlaySelected = null;
    renderSlidingGeometry();
    const marker = event.target.closest(".gp-tag");
    const tag = marker && state().tags.find((t) => t.id === marker.dataset.tagId);
    if (!tag && event.target.closest("button")) return;
    event.preventDefault();
    viewport.focus({preventScroll: true});
    const position = tag && (positions.get(tag.id) || tag);
    drag = { x: event.clientX, y: event.clientY, left: panX, top: panY,
      moved: false, pointerId: event.pointerId, id: tag?.id, position,
      placementBlocked: importBusy,
      box: !tag && (event.shiftKey || event.ctrlKey || event.metaKey),
      beforeSelection: new Set(selected),
      select: !!tag && (event.shiftKey || event.ctrlKey || event.metaKey) };
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!drag && measuring() && measurePoints.length === 1) {
      measureCursor = measurementPoint(event); showMeasurement(); return;
    }
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 4) drag.moved = true;
    if (drag.measurement) {
      if (drag.moved) {
        panX = drag.left + dx; panY = drag.top + dy; placeSheet();
        viewport.classList.add("gp-panning");
      }
      return;
    }
    if (drag.select) return;
    if (drag.moved) {
      if (drag.box) {
        viewport.classList.add("gp-selecting");
        if (active) closeDialog();
        if (!bulkDialog.hidden) closeBulk();
        previewSelection(event);
      } else if (drag.overlay) {
        const p = {...drag.position};
        if (drag.resize) {
          const delta = drag.overlay === "symbol" ? (dx + dy) / (2 * zoom)
            : p.size * (dx * drag.width + dy * drag.height) / (drag.width ** 2 + drag.height ** 2);
          p.size = overlaySize(drag.overlay, p.size + delta);
        }
        else {
          const rect = picture.getBoundingClientRect();
          p.x = Math.max(0, Math.min(1, p.x + dx / rect.width));
          p.y = Math.max(0, Math.min(1, p.y + dy / rect.height));
        }
        overlayPositions.set(drag.page + ":" + drag.overlay, p);
        renderSlidingGeometry();
        closeDialog();
      } else if (drag.id) {
        if (readOnly) return;
        const rect = picture.getBoundingClientRect();
        positions.set(drag.id, {
          x: Math.max(0, Math.min(1, drag.position.x + dx / rect.width)),
          y: Math.max(0, Math.min(1, drag.position.y + dy / rect.height)),
        });
        viewport.classList.add("gp-dragging-tag");
        closeDialog();
      } else {
        panX = drag.left + dx;
        panY = drag.top + dy;
        placeSheet();
        viewport.classList.add("gp-panning");
      }
    }
  });
  viewport.addEventListener("pointerup", (event) => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.box && drag.moved) previewSelection(event);
    const { moved, id, overlay, page, select, placementBlocked, pan, box, beforeSelection, measurement } = drag;
    drag = null;
    selectionBox.hidden = true;
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    viewport.classList.remove("gp-selecting");
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    if (pan) return;
    if (measurement) {if (!moved) chooseMeasurementPoint(event); return;}
    if (box) {
      if (moved) {
        if (selected.size !== beforeSelection.size || [...selected].some(id => !beforeSelection.has(id))) bulkSignature = "";
        setMode("pan"); showSelection(); renderMarkers();
      }
      return;
    }
    if (overlay) {
      if (moved) saveOverlayPosition(overlay, page, overlayPositions.get(page + ":" + overlay));
      return;
    }
    if (id) {
      const tag = state().tags.find((t) => t.id === id);
      if (select) { if (!moved && tag) toggleTag(tag); return; }
      if (!moved) { if (tag) openDialog(tag); return; }
      if (readOnly) return;
      const position = positions.get(id);
      pendingPositions.set(id, position);
      command("update", { id, ...position }, [], (reply) => {
        // A delayed response must not roll back a subsequent drag.
        if (pendingPositions.get(id) === position) pendingPositions.delete(id);
        if (positions.get(id) === position) positions.delete(id);
        renderMarkers();
        if (reply.ok) showMessage((tag?.label || "Etiketten") + " flyttad.");
      });
      return;
    }
    if (readOnly || moved || placementBlocked || mode === "pan") return;
    const rect = picture.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    if (mode === "import") {
      const queue = loadImport();
      if (!queue || queue.paused || importBusy) return;
      importBusy = true; showLoadImport();
      command("place_import", {token: queue.token, index: queue.index, x, y, page: background().page}, [], reply => {
        importBusy = false;
        if (mode !== "import" && loadImport() && !loadImport().paused) {
          command("import_control", {token: loadImport().token, operation: "pause"});
        }
        update();
        if (!reply.ok) showMessage(reply.error, true);
        if (reply.ok && reply.finished) showMessage("Alla " + reply.total + " importerade sulor är placerade. Anpassa övriga indata; resultaten uppdateras automatiskt.");
      });
      return;
    }
    const source = copySource;
    const action = mode === "copy" ? "copy" : "add";
    const payload = source
      ? { id: source.id, values: source.values, x, y, page: background().page }
      : { x, y, kind: mode };
    // Consume the placement immediately, including when the kernel is slow.
    setMode("pan");
    command(action, payload, [], (reply) => {
      if (!reply.ok) return;
      const tag = state().tags.find((t) => t.id === reply.id);
      if (tag) openDialog(tag);
      if (source) showMessage("Kopian har fått egna indata. Anpassa last och geometri; resultatet uppdateras automatiskt.");
    });
  });
  viewport.addEventListener("pointercancel", cancelDrag);
  viewport.addEventListener("pointerleave", () => {
    if (!drag && measuring()) {measureCursor = null; showMeasurement();}
  });
  viewport.addEventListener("lostpointercapture", cancelDrag);
  viewport.addEventListener("contextmenu", event => event.preventDefault());
  viewport.addEventListener("wheel", event => {
    // Some browsers report Shift-wheel movement on the horizontal axis.
    const movement = event.deltaY || event.deltaX;
    if (!event.shiftKey || !background().url || !Number.isFinite(movement) || !movement) return;
    event.preventDefault();
    if (drag) return;
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1;
    const delta = Math.max(-240, Math.min(240, movement * unit));
    const rect = viewport.getBoundingClientRect();
    setZoom(zoom * Math.exp(-delta * .002), {x: event.clientX - rect.left, y: event.clientY - rect.top});
  }, {passive: false});
  let outsidePress = null;
  const insideDialog = target => target?.closest?.(".gp-dialog") === dialog
    || target?.closest?.(".gp-dialog") === bulkDialog
    || target?.closest?.(".gp-sketch-panel") === sketch;
  const outsideDown = event => {
    outsidePress = null;
    if (event.button !== 0 || (dialog.hidden && bulkDialog.hidden) || insideDialog(event.target)
      || event.target?.closest?.(".gp-panel-resize")
      || (event.target?.closest?.(".an-grundplan") === root && event.target.closest(".gp-tag"))) return;
    outsidePress = {pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      tagId: active, bulk: !bulkDialog.hidden, moved: false};
  };
  const outsideMove = event => {
    if (outsidePress && outsidePress.pointerId === event.pointerId
      && Math.hypot(event.clientX - outsidePress.x, event.clientY - outsidePress.y) > 4) outsidePress.moved = true;
  };
  const outsideUp = event => {
    if (!outsidePress || outsidePress.pointerId !== event.pointerId) return;
    const press = outsidePress;
    outsidePress = null;
    if (!press.moved && Math.hypot(event.clientX - press.x, event.clientY - press.y) <= 4
      && active === press.tagId && !insideDialog(event.target)) {
      if (press.bulk) closeBulk(); else closeDialog();
    }
  };
  const outsideCancel = () => { outsidePress = null; };
  // Capture outside the widget too; a pan/drag or another tag click stays distinct.
  document.addEventListener("pointerdown", outsideDown, true);
  document.addEventListener("pointermove", outsideMove, true);
  document.addEventListener("pointerup", outsideUp, true);
  document.addEventListener("pointercancel", outsideCancel, true);
  for (const [header, panel] of [[dialogHeader, dialog], [bulkHeader, bulkDialog]]) {
    let dialogDrag = null;
    header.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("button")) return;
      dialogDrag = { x: event.clientX, y: event.clientY, left: panel.offsetLeft, top: panel.offsetTop };
      header.setPointerCapture(event.pointerId);
    });
    header.addEventListener("pointermove", (event) => {
      if (!dialogDrag) return;
      const x = dialogDrag.left + event.clientX - dialogDrag.x, y = dialogDrag.top + event.clientY - dialogDrag.y;
      if (panel === dialog) placeDialog(x, y);
      else {
        panel.style.left = Math.max(8, Math.min(board.clientWidth - panel.offsetWidth - 8, x)) + "px";
        panel.style.top = Math.max(8, Math.min(board.clientHeight - panel.offsetHeight - 8, y)) + "px";
      }
    });
    header.addEventListener("pointerup", () => { dialogDrag = null; });
    header.addEventListener("pointercancel", () => { dialogDrag = null; });
  }
  root.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Escape" && !savePanel.hidden) {
      if (!saving) { savePanel.hidden = true; saveProject.focus(); }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      const selecting = !!drag?.box || selected.size > 0;
      const wasMeasuring = measuring();
      cancelDrag(); overlaySelected = null; renderSlidingGeometry(); closeDialog(); closeBulk();
      if (!bulkBusy) { selected.clear(); tableAnchor = null; bulkSignature = ""; showSelection(); renderMarkers(); }
      setMode("pan"); showMessage(wasMeasuring ? "Mätningen avslutades. Kalibreringen behålls." : selecting && !bulkBusy ? "Markeringen avbröts."
        : readOnly ? "Klicka på en etikett för indata och resultat." : "Klicka på en etikett för indata eller dra den för att flytta.");
    }
  });
  function receive(reply, buffers = []) {
    if (reply.view !== view) return;
    if (!reply.ok) showMessage(reply.error, true);
    const onDone = pending.get(reply.request);
    pending.delete(reply.request);
    onDone?.(reply, buffers);
  }
  const resizeObserver = new ResizeObserver(() => {
    showLayout();
    resizeSubtitle();
    renderMeasurement();
    if (!dialog.hidden) placeDialog(dialog.offsetLeft, dialog.offsetTop);
    if (!bulkDialog.hidden) {
      bulkDialog.style.left = Math.max(8, Math.min(board.clientWidth - bulkDialog.offsetWidth - 8, parseFloat(bulkDialog.style.left) || 8)) + "px";
      bulkDialog.style.top = Math.max(8, Math.min(board.clientHeight - bulkDialog.offsetHeight - 8, parseFloat(bulkDialog.style.top) || 8)) + "px";
    }
  });
  resizeObserver.observe(board);
  resizeObserver.observe(tableScroll);
  if (!readOnly) resizeObserver.observe(headingText);
  model.on("change:state", update);
  model.on("change:background", update);
  model.on("msg:custom", receive);
  setMode("pan");
  showMessage(background().url
    ? (readOnly ? "Klicka på en etikett för indata och resultat. Shift + klick eller Shift + vänsterdrag framhäver valda sulor i tabellen. Escape avmarkerar. Dra för att panorera och använd Shift + scroll för att zooma." : "Dra för att panorera och använd Shift + scroll för att zooma. Shift + vänsterdrag markerar för flerredigering; välj en sula och klicka för att placera.")
    : "Öppna en ritning eller ett sparat projekt.");
  update();
  return () => {
    disposed = true;
    endPanelDrag();
    document.removeEventListener("pointerdown", outsideDown, true);
    document.removeEventListener("pointermove", outsideMove, true);
    document.removeEventListener("pointerup", outsideUp, true);
    document.removeEventListener("pointercancel", outsideCancel, true);
    resizeObserver.disconnect();
    model.off("change:state", update);
    model.off("change:background", update);
    model.off("msg:custom", receive);
    pending.clear();
    root.remove();
  };
}

export default { render };
