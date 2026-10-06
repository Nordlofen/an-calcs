/* Shared plan view. All engineering calculations run in the Python kernel. */
function definitionSketch(strip) {
  const make = (name, attributes, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const svg = make("svg", { viewBox: "0 0 440 435", role: "img", "aria-label": strip
    ? "Väggsula: x tvärs väggen, y längs väggen, en meters beräkningsremsa."
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
  dimension(114, 58, 114, 184); text(96, 126, strip ? "1 m" : "bᵧ", 16, "end");
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
    text(cx, 425, axis === "x" ? "bₓ" : strip ? "1 m beräkningsremsa" : "bᵧ", strip && axis === "y" ? 12 : 17);
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
  const overlayPositions = new Map(), pendingOverlayPositions = new Map(), slidingDirty = new Set();
  const slidingNames = new Set(["glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L"]);
  const sliding = () => slidingDraft || state().sliding || {enabled: false, check_x: false, check_y: false, placements: {}};
  const positions = new Map(), pendingPositions = new Map();
  const pending = new Map(), dirty = new Set(), inputs = new Map(), edits = new Map(), drafts = new Map();
  const sectionStates = new Map(), inputSections = [], resultSections = [];
  const sketchStates = new Map();
  const areaPhases = new Map();
  let sketchInline = false, sketchType = null;
  const selected = new Set(), bulkInputs = new Map();
  let bulkIds = [], bulkBusy = false, bulkSignature = "";
  let importBusy = false, lastImportToken = null;
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
    if (readOnly && !["page", "label_size"].includes(action)) return;
    const request = ++sequence;
    pending.set(request, onDone);
    model.send({ action, ...payload, request, view }, undefined, buffers);
  }
  const heading = node("header", "gp-heading");
  const headingText = node("div", "gp-heading-text");
  const title = node(readOnly ? "h3" : "input", "gp-title");
  const subtitle = node(readOnly ? "p" : "input", "gp-subtitle");
  function showHeading() {
    const values = headingDraft || state();
    for (const [element, value] of [[title, values.title ?? "Grundplan"],
      [subtitle, values.subtitle ?? "Sulgrundläggning · jordens bärighet"]]) {
      if (readOnly) element.textContent = value;
      else if (element.value !== value) element.value = value;
    }
    subtitle.hidden = readOnly && !subtitle.textContent;
  }
  if (!readOnly) {
    for (const [input, label] of [[title, "Rubrik"], [subtitle, "Underrubrik"]]) {
      input.type = "text";
      input.maxLength = 200;
      input.placeholder = label;
      input.setAttribute("aria-label", label);
      input.title = "Klicka för att redigera " + label.toLowerCase();
      input.addEventListener("input", () => {
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
  }
  headingText.append(title, subtitle);
  const total = node("span", "gp-count");
  heading.append(headingText, total);
  const toolbar = node("div", "gp-toolbar");
  const fileInput = node("input");
  fileInput.type = "file";
  fileInput.accept = ".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp";
  fileInput.hidden = true;
  const projectInput = node("input");
  projectInput.type = "file";
  projectInput.accept = ".json";
  projectInput.hidden = true;
  const loadsInput = node("input");
  loadsInput.type = "file"; loadsInput.accept = ".json"; loadsInput.hidden = true;
  loadsInput.setAttribute("aria-label", "Lasteffektfil");
  const loadDrawing = button("Öppna ritning", () => fileInput.click());
  const loadProject = button("Öppna projekt", () => {
    if (!state().tags.length || window.confirm("Ersätt projektet? Spara först om du vill behålla dina ändringar.")) {
      projectInput.click();
    }
  });
  const loadEffects = button("Importera Lasteffekt", () => loadsInput.click());
  loadEffects.title = "Läs stödens vertikallaster och placera sulorna med ett klick per stöd.";
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
      showMessage("Exporterar alla ritningssidor med etiketter…");
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
  if (!readOnly) toolbar.append(loadDrawing, loadProject, loadEffects, saveProject, exportJson, ...exports.map(entry => entry.button), node("span", "gp-separator"));
  const modes = new Map();
  for (const [key, label] of [["vaggsula", "+ Väggsula"], ["pelarsula", "+ Pelarsula"]]) {
    const b = button(label, () => setMode(mode === key ? "pan" : key));
    b.title = "Välj för att placera en sula. Klicka igen eller tryck Escape för att avbryta.";
    modes.set(key, b);
    if (!readOnly) toolbar.append(b);
  }
  const selectMany = button("Markera flera", () => {
    if (bulkBusy) return;
    closeDialog(); closeBulk();
    setMode(mode === "select" ? "pan" : "select");
    viewport.focus({preventScroll: true});
  });
  selectMany.title = "Shift + vänsterdrag ritar en urvalsruta. Shift + klick växlar markeringen. Vanligt klick öppnar objektets redigering.";
  modes.set("select", selectMany);
  const selectionBar = node("div", "gp-selection-bar");
  selectionBar.hidden = true;
  const selectionCount = node("span", "gp-selection-count");
  const editMany = button("Ändra markerade", openBulk, "gp-primary");
  const clearMany = button("Avmarkera", () => {
    if (bulkBusy) return;
    selected.clear(); bulkSignature = ""; closeBulk(); renderMarkers(); showSelection();
  });
  selectionBar.append(selectionCount, editMany, clearMany);
  if (!readOnly) toolbar.append(selectMany);
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
  toolbar.append(sizeLabel);
  const pageLabel = node("label", "gp-page-label", "Sida ");
  const pageSelect = node("select");
  pageSelect.setAttribute("aria-label", "PDF-sida");
  pageLabel.append(pageSelect);
  pageSelect.addEventListener("change", () => {
    cancelDrag();
    setMode(loadImport() && !loadImport().paused ? "import" : "pan");
    closeDialog();
    selected.clear(); bulkSignature = ""; closeBulk(); showSelection();
    command("page", { page: Number(pageSelect.value) });
  });
  toolbar.append(pageLabel);
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
  overlays.append(axesOverlay, slidingLegend);
  sheet.append(picture, markers, overlays);
  viewport.append(sheet, selectionBox);
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
  const calculate = node("button", "gp-primary", "Beräkna");
  calculate.type = "submit";
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
  footer.append(remove, copy, calculate);
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
  const applyMany = button("Tillämpa", () => applyBulk(false));
  const calculateMany = button("Tillämpa och beräkna", () => applyBulk(true), "gp-primary");
  bulkFooter.append(applyMany, calculateMany);
  bulkForm.append(bulkNote, bulkFeedback, bulkFields, bulkFooter);
  bulkForm.addEventListener("submit", event => { event.preventDefault(); applyBulk(true); });
  bulkDialog.append(bulkHeader, bulkForm);
  board.append(viewport, empty, zoomBar, dialog, sketch, bulkDialog);
  const status = node("div", "gp-status");
  status.setAttribute("role", "status");
  const legend = node("div", "gp-legend");
  legend.setAttribute("role", "list");
  legend.setAttribute("aria-label", "Etikettförklaring");
  for (const [state, label] of [["new", "Ej beräknad"], ["ok", "U ≤ 100 %"],
    ["over", "U > 100 %"], ["stale", "Ändrad"]]) {
    const item = node("span", "gp-legend-item gp-tag-" + state, label);
    item.setAttribute("role", "listitem");
    legend.append(item);
  }
  const help = node("p", "gp-help",
    "Dra i ritningen med vänster eller höger musknapp för att panorera. Shift + scroll zoomar vid muspekaren. Shift + vänsterdrag ritar en urvalsruta. Shift + drag eller Shift + klick lägger till omarkerade etiketter och avmarkerar markerade. Dra direkt i en etikett för att flytta den. Klicka för indata och Kopiera sula. Klicka utanför rutan för att minimera. Etiketterna följer ritningens zoom.");
  root.append(heading, toolbar);
  if (!readOnly) root.append(importBar);
  if (!readOnly) root.append(selectionBar);
  if (!readOnly) root.append(savePanel, projectFile, argumentsFallback);
  root.append(board, status, legend);
  if (!readOnly) root.append(help, fileInput, projectInput, loadsInput);
  el.append(root);

  function showMessage(message, error = false) {
    status.textContent = message;
    status.classList.toggle("gp-error-text", error);
  }
  async function upload(input, action) {
    const file = input.files[0];
    if (!file) return;
    if (file.size > (action === "drawing" ? 40 : action === "import_loads" ? 5 : 60) * 1024 * 1024) {
      showMessage("Filen är för stor.", true);
      input.value = "";
      return;
    }
    showMessage("Öppnar " + file.name + "…");
    if (action === "import_loads") { importBusy = true; showLoadImport(); }
    try {
      const buffer = await file.arrayBuffer();
      if (disposed) return;
      command(action, { name: file.name }, [buffer], (reply) => {
        if (action === "import_loads") {
          importBusy = false;
          if (reply.ok) {
            closeDialog(); closeBulk(); selected.clear(); bulkSignature = "";
            setMode("import"); viewport.focus({preventScroll: true});
          }
          update();
          if (!reply.ok) showMessage(reply.error, true);
          return;
        }
        if (reply.ok) {
          active = null;
          selected.clear(); bulkIds = []; bulkSignature = ""; closeBulk();
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
          overlayPositions.clear(); pendingOverlayPositions.clear(); slidingDirty.clear();
          inputSections.length = resultSections.length = 0;
          setMode("pan");
          update();
          showMessage(file.name + " öppnad.");
        }
      });
    } catch (error) {
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
    mode = value;
    if (value !== "copy") copySource = null;
    cancelCopy.hidden = value !== "copy";
    for (const [key, b] of modes) {
      b.classList.toggle("gp-selected", key === value);
      b.setAttribute("aria-pressed", String(key === value));
    }
    viewport.style.cursor = value === "pan" ? "grab" : "crosshair";
    if (value === "copy") showMessage("Klicka på ritningen för att placera en kopia av " + copySource.label + ". Escape avbryter.");
    else if (value === "import") showMessage(importCaption());
    else if (value === "select") showMessage("Shift + vänsterdrag ritar en urvalsruta. Shift + klick väljer eller avmarkerar en etikett; vanligt klick öppnar redigering. Tryck Ändra markerade när urvalet är klart.");
    else if (value !== "pan") showMessage("Klicka på ritningen där du vill placera en " +
      (value === "vaggsula" ? "väggsula." : "pelarsula."));
    else showMessage("Dra i ritningen för att panorera. Shift + vänsterdrag markerar för flerredigering. Välj Väggsula eller Pelarsula för att placera en ny sula.");
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
    loadEffects.disabled = !background().url || !!queue || importBusy || bulkBusy;
    importPause.disabled = importCancel.disabled = importBusy;
    pageSelect.disabled = bulkBusy || importBusy;
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
      + (strip ? " · L " + precise(values.glid_L) + " m" : "");
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
  function overlayPosition(kind) {
    const key = background().page + ":" + kind;
    const defaults = kind === "symbol" ? {x: .06, y: .55, size: 160} : {x: .50, y: .04, size: 410};
    return {...defaults, ...(overlayPositions.get(key) || sliding().placements?.[background().page]?.[kind])};
  }
  function overlaySize(kind, value) {
    const [low, high] = kind === "symbol" ? [50, 600] : [205, 1230];
    return Math.max(low, Math.min(high, value));
  }
  function saveOverlayPosition(kind, page, position) {
    const key = page + ":" + kind;
    overlayPositions.set(key, position);
    pendingOverlayPositions.set(key, position);
    command("sliding_placement", {kind, page, position}, [], () => {
      if (pendingOverlayPositions.get(key) === position) pendingOverlayPositions.delete(key);
      if (overlayPositions.get(key) === position) overlayPositions.delete(key);
      renderSlidingGeometry();
    });
  }
  for (const [element, kind, resize] of [[axesButton, "symbol", false], [axesResize, "symbol", true],
      [slidingHeader, "legend", false], [legendResize, "legend", true]]) {
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
    for (const [element, kind] of [[axesOverlay, "symbol"], [slidingLegend, "legend"]]) {
      const p = overlayPosition(kind);
      element.hidden = !sliding().enabled || !background().url;
      element.style.left = p.x * 100 + "%";
      element.style.top = p.y * 100 + "%";
      element.classList.toggle("gp-overlay-selected", !readOnly && overlaySelected === kind);
      if (kind === "symbol") {
        element.style.width = element.style.height = p.size * zoom + "px";
        axesResize.hidden = readOnly || overlaySelected !== "symbol";
      } else {
        const scale = zoom * p.size / 410;
        element.style.transform = "scale(" + scale + ")";
        legendResize.hidden = readOnly || overlaySelected !== "legend";
        // Keep the corner target usable even when the whole legend is small.
        legendResize.style.transform = "scale(" + 1 / scale + ")";
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
          node("span", "gp-sliding-value", waiting || value == null ? "—" : compactNumber(value, 2) + " kN"));
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
    if (bulkBusy) return;
    closeBulk();
    if (!readOnly) { selected.clear(); bulkSignature = ""; showSelection(); }
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
    const open = !!tag && !!sketchStates.get(tag.id) && !dialog.hidden;
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
    for (const tag of state().tags.filter((t) => t.page === background().page)) {
      const summary = dirty.has(tag.id) ? null : tag.summary;
      const tagState = dirty.has(tag.id) ? "stale" : tag.status;
      const color = summary ? (summary.utnyttjandegrad <= 1 ? "ok" : "over") : tagState;
      const marker = button("", (event) => {
        event.stopPropagation();
        // Pointer clicks are handled on pointerup, so dragging never opens the form.
        if (!event.detail) {
          if (!readOnly && (event.shiftKey || event.ctrlKey || event.metaKey)) toggleTag(tag);
          else openDialog(tag);
        }
      }, "gp-tag gp-tag-" + color);
      marker.dataset.tagId = tag.id;
      marker.title = readOnly ? "Klicka för indata och resultat" : "Dra för att flytta · klicka för indata och kopiering";
      const position = positions.get(tag.id) || tag;
      marker.style.left = position.x * 100 + "%";
      marker.style.top = position.y * 100 + "%";
      marker.classList.toggle("gp-active", active === tag.id);
      marker.classList.toggle("gp-multi-selected", selected.has(tag.id));
      if (!readOnly) marker.setAttribute("aria-pressed", String(selected.has(tag.id)));
      const draft = drafts.get(tag.id);
      const values = draft?.values || tag.values;
      const insulated = values.isolering === true;
      const insulationText = insulated ? "Med isolering" : "Utan isolering";
      const label = draft?.label.trim() || tag.label;
      const heading = node("span", "gp-tag-heading");
      const insulation = node("span", "gp-tag-insulation");
      insulation.append(insulationIcon(insulated), node("span", "", insulationText));
      heading.append(node("strong", "", label), insulation);
      const geometry = summary ? (tag.values.lang === 1 ? "bₓ " + number(summary.b) + " m"
        : number(summary.b) + " × " + number(tag.values.l) + " m") : "";
      const showSlidingBlock = sliding().enabled && !insulated && (values.glid_x || values.glid_y);
      const rawLength = values.glid_L;
      const length = rawLength == null || rawLength === "" ? NaN : Number(String(rawLength).replace(",", "."));
      const lengthText = Number(values.lang) === 1 && Number.isFinite(length) && length > 0 && !showSlidingBlock
        ? " · L " + precise(length) + " m" : "";
      const text = (summary
        ? "U " + number(summary.utnyttjandegrad * 100, 1) + " % · " + geometry
        : ({ new: "Ej beräknad", stale: "Ändrad · beräkna", error: "Kontrollera indata" }[tagState] || "Ej beräknad")) + lengthText;
      const accessibleGeometry = summary && tag.values.lang === 0 ? ", mått i ordningen bₓ × bᵧ" : "";
      const governing = summary?.isolering ? ", styrande: " + summary.styrande : "";
      marker.setAttribute("aria-label", label + ", " + insulationText + ", " + text + accessibleGeometry + governing);
      marker.title += accessibleGeometry + governing;
      marker.append(heading, node("span", "gp-tag-result", text));
      if (summary?.isolering) marker.append(node("span", "gp-governing", "Styrande: " + summary.styrande));
      const loads = node("span", "gp-tag-loads");
      const accessibleLoads = [];
      for (const group of model.get("schema").load_groups || []) {
        if (group.label === "Bruk" && !insulated) continue;
        const tokens = [];
        for (const field of group.fields) {
          const raw = values[field.name];
          const value = typeof raw === "string" ? Number(raw.replace(",", ".")) : raw;
          if (typeof value !== "number" || !Number.isFinite(value) || value === 0) continue;
          const unit = field.unit + (Number(values.lang) === 1 ? "/m" : "");
          tokens.push(field.symbol + " " + precise(value) + " " + unit);
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
        add(data, "V", "Ed,EQU", value("V_Ed_EQU", values.lang == 1 ? "kN/m" : "kN"));
        if (values.lang == 1) add(data, "L", "", value("glid_L", "m"));
        for (const axis of ["x", "y"]) if (values["glid_" + axis]) {
          const capacity = slidingDirty.has(tag.id) ? null : tag.sliding?.[axis];
          add(capacities, "H", axis + ",Rd,i", capacity == null ? "—" : compactNumber(capacity, 3) + " kN", true);
        }
        grid.append(data, capacities); section.append(grid); marker.append(section);
      }
      markers.append(marker);
    }
  }
  const groups = [
    ["Geometri", ["lang", "b", "l", "t", "d", "e_b_plac", "e_l_plac"]],
    ["Laster – Brott", ["F_vy", "F_hb", "F_hl", "M_insp_b", "M_insp_l"],
      "Yttre dimensionerande laster. Ange moment direkt vid sulan; inga moment från horisontallaster läggs till. Sulans egentyngd tillkommer med faktor 1,5."],
    ["Laster – Bruk", ["F_vy_bruk", "M_insp_b_bruk", "M_insp_l_bruk"],
      "Yttre långtidslaster och direkt angivna moment för isoleringskontrollen. Sulans egentyngd tillkommer med faktor 1,0. Värden kan anges även utan isolering; kontrollen används när isolering aktiveras."],
    ["Jord och grundvatten", ["c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "delta_h", "beta", "alpha"]],
    ["Koefficienter", ["eta", "gamma_m", "gamma_m0", "gamma_Rd"]],
    ["Isolering", ["isolering", "isolerprodukt", "f_d_brott", "f_d_bruk"],
      "Ange färdiga dimensionerande bärförmågor f_d,brott och f_d,bruk. Kontroll: V / (b_x,eff × b_y,eff) i respektive lastkombination. Isoleringen förutsätts täcka hela den effektiva arean."],
    ["Glidning", ["glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L"],
      "V_Ed,EQU ska redan inkludera sulans egentyngd. X_g och Y_g är separata lastfall. Välj de riktningar där sulans glidmotstånd får utnyttjas. Isolerade sulor bidrar med 0 kN."],
  ];
  const fieldSchema = new Map(model.get("schema").fields.map((field) => [field.name, field]));
  const sameTypeFields = new Set(model.get("schema").bulk_same_type ||
    ["l", "glid_L", "V_Ed_EQU", ...groups[1][1], ...groups[2][1]]);
  function selectionTags() { return state().tags.filter(tag => selected.has(tag.id)); }
  function showSelection() {
    // Keep the canvas at the same screen position while the selection box is drawn.
    if (drag?.box) return;
    selectionBar.hidden = readOnly || !selected.size;
    selectionCount.textContent = selected.size + " markerade";
    const titles = selectionTags().map(tag => tag.label).join(", ");
    selectionCount.title = titles;
    selectionBar.setAttribute("aria-label", "Markerade sulor: " + titles);
    editMany.disabled = clearMany.disabled = bulkBusy;
    selectMany.disabled = bulkBusy || !background().url;
    pageSelect.disabled = bulkBusy || importBusy;
  }
  function toggleTag(tag) {
    if (readOnly || bulkBusy) return;
    // Shift-click on an open single footing adds that footing to the selection.
    if (active) selected.add(active);
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
    bulkNote.textContent = "Kryssa i de fält som ska ersättas för alla markerade sulor. Övriga värden behålls. "
      + (mixed ? "Blandade sultyper: last- och längdfält kräver att du väljer enbart väggsulor eller enbart pelarsulor. "
        : strip ? "Väggsulor: laster anges per meter. " : "Pelarsulor: laster anges för hela sulan. ")
      + "Urval: " + tags.map(tag => tag.label).join(", ");
    for (const [index, [label, names, note]] of groups.entries()) {
      if (label === "Glidning" && !sliding().enabled) continue;
      const group = node("details", "gp-group");
      group.open = index === 0 || label === "Isolering";
      group.append(node("summary", "", label));
      if (note) group.append(mathText("p", "gp-field-note", note));
      for (const name of names) {
        const field = fieldSchema.get(name);
        if (!field || name === "lang" || (strip && name === "l") || (!mixed && !strip && name === "glid_L")) continue;
        const row = node("div", "gp-bulk-field");
        const choose = node("input");
        choose.type = "checkbox";
        choose.setAttribute("aria-label", "Ändra " + field.label);
        choose.title = "Ändra " + field.label + " för alla markerade sulor";
        const controlRow = node("div", "gp-field");
        const input = node(field.type === "bool" ? "select" : "input");
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
        } else {
          input.type = "text";
          if (field.type !== "text") input.inputMode = "decimal";
          input.value = same ? value ?? "" : "";
          input.placeholder = same ? "Ej angivet" : "Olika värden";
          if (field.type === "text") controlRow.classList.add("gp-text-field");
        }
        const caption = node("span", "gp-field-caption", field.label);
        const symbol = symbolNode(field.display_symbol || {}, "gp-field-symbol");
        symbol.setAttribute("aria-hidden", "true");
        const unit = (field.unit || "").replace("^3", "³").replace(/^deg$/, "°");
        const unitText = strip && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
        if (field.type === "text") controlRow.append(caption, input);
        else if (field.type === "bool") controlRow.append(caption, symbol, input);
        else controlRow.append(caption, symbol, input, node("span", "gp-unit", unitText));
        const blocked = mixed && sameTypeFields.has(name);
        choose.disabled = input.disabled = blocked;
        if (blocked) row.title = "Välj samma sultyp för att ändra detta fält gemensamt.";
        const sync = () => { input.setCustomValidity(""); row.classList.toggle("gp-bulk-changed", choose.checked); };
        choose.addEventListener("change", sync);
        input.addEventListener(field.type === "bool" ? "change" : "input", () => {
          choose.checked = true; sync();
        });
        row.append(choose, controlRow); group.append(row);
        bulkInputs.set(name, {choose, input, row, group, blocked});
      }
      bulkFields.append(group);
    }
  }
  function applyBulk(recalculate) {
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
    applyMany.disabled = calculateMany.disabled = bulkMinimize.disabled = true;
    for (const entry of bulkInputs.values()) entry.choose.disabled = entry.input.disabled = true;
    showSelection();
    showLoadImport();
    bulkFeedback.textContent = recalculate ? "Ändrar och beräknar markerade sulor…" : "Ändrar markerade sulor…";
    command("bulk_update", {ids, values: patch, calculate: recalculate}, [], reply => {
      bulkBusy = false;
      applyMany.disabled = calculateMany.disabled = bulkMinimize.disabled = false;
      if (reply.ok) {
        for (const id of ids) { dirty.delete(id); drafts.delete(id); slidingDirty.delete(id); edits.delete(id); }
        const report = reply.report;
        const message = recalculate ? report.calculated + " av " + report.updated + " sulor beräknade."
          : report.updated + " sulor uppdaterade. Ändrade beräkningsindata behöver beräknas på nytt.";
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
        if (!field) continue;
        const row = node(readOnly ? "div" : "label", "gp-field");
        const caption = node("span", "gp-field-caption", field.label);
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
            : field.type === "choice" ? (value === 1 ? "Väggsula (per meter)" : "Pelarsula")
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
        const input = node(field.type === "choice" ? "select" : "input");
        input.name = name;
        input.setAttribute("aria-label", accessibleLabel);
        if (field.type === "choice") {
          for (const option of field.options) {
            const opt = node("option", "", option.value === 1 ? "Väggsula (per meter)" : "Pelarsula");
            opt.value = option.value;
            input.append(opt);
          }
        } else if (field.type === "bool") {
          input.type = "checkbox";
          row.classList.add("gp-check-field");
        } else if (field.type === "text") {
          input.type = "text";
          input.placeholder = "Kommentar, t.ex. EPS S200";
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
    const insulated = readOnly ? current()?.values.isolering : inputs.get("isolering")?.input.checked;
    const selected = readOnly ? current()?.values.glid_x || current()?.values.glid_y
      : inputs.get("glid_x")?.input.checked || inputs.get("glid_y")?.input.checked;
    basis.textContent = readOnly
      ? (strip ? "Väggsula: laster och moment avser en meter vägg." : "Pelarsula: laster och moment avser hela sulan.") + " Egentyngd ingår i beräkningsresultatet."
      : strip
        ? "Väggsula: samtliga laster och moment avser en meter vägg. Egentyngd tillkommer i beräkningen."
        : "Pelarsula: ange totala laster och moment. Egentyngd tillkommer i beräkningen.";
    for (const [name, entry] of inputs) {
      if (slidingNames.has(name)) {
        entry.group.hidden = !sliding().enabled;
        const numeric = !["glid_x", "glid_y"].includes(name);
        const length = name === "glid_L";
        const disabled = !sliding().enabled || (length ? !strip : insulated);
        entry.row.hidden = length ? !strip : numeric && insulated;
        entry.unit.textContent = name === "V_Ed_EQU" ? (strip ? "kN/m" : "kN") : fieldSchema.get(name).unit;
        if (!readOnly) { entry.input.disabled = disabled; entry.input.required = numeric && !disabled && selected && !insulated;
          if (disabled) entry.input.setCustomValidity(""); }
        continue;
      }
      const unit = (fieldSchema.get(name).unit || "").replace("^3", "³").replace(/^deg$/, "°");
      entry.unit.textContent = strip && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
      const insulationField = name.startsWith("f_d_");
      if (readOnly) {
        entry.row.hidden = (strip && name === "l") || (!insulated && (insulationField || name.endsWith("_bruk")));
        continue;
      }
      entry.input.disabled = insulationField && !insulated;
      entry.input.required = entry.input.type !== "checkbox" && fieldSchema.get(name).type !== "text"
        && !entry.input.disabled && (insulated || !name.endsWith("_bruk"));
      if (entry.input.disabled) entry.input.setCustomValidity("");
      entry.row.hidden = (strip && name === "l") || (!insulated && name.startsWith("f_d_"));
    }
    showSketch();
  }
  function edit(calculationInput) {
    if (!current()) return;
    if (calculationInput) {
      dirty.add(active);
    }
    edits.set(active, (edits.get(active) || 0) + 1);
    // Keep raw text until calculation is acknowledged, including across minimization.
    drafts.set(active, {
      label: labelInput.value,
      values: Object.fromEntries([...inputs].map(([name, { input }]) => [name, input.type === "checkbox" ? input.checked : input.value])),
    });
    fieldUnits();
    const values = readValues();
    if (sliding().enabled) slidingDirty.add(active);
    showResult();
    renderMarkers();
    showSliding();
    const label = labelInput.value.trim();
    const id = active, revision = edits.get(id);
    command("update", { id, values, ...(label ? { label } : {}) }, [], () => {
      if (edits.get(id) === revision) slidingDirty.delete(id);
      showSliding(); renderMarkers();
    });
  }
  labelInput.addEventListener("input", () => edit(false));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (readOnly) return;
    const values = readValues();
    for (const { input, group } of inputs.values()) {
      if (!input.disabled && input.validity && !input.validity.valid) group.open = true;
    }
    if (!form.reportValidity()) return;
    const id = active;
    const revision = edits.get(id) || 0;
    calculate.disabled = true;
    calculate.textContent = "Beräknar…";
    command("calculate", { id, values, label: labelInput.value.trim() }, [], (reply) => {
      calculate.disabled = false;
      calculate.textContent = "Beräkna";
      // A result must never clear edits made while the kernel was calculating.
      if (revision === (edits.get(id) || 0)) {
        dirty.delete(id);
        if (reply.ok) drafts.delete(id);
        update();
      }
      if (reply.ok) showMessage("Beräkningen är uppdaterad.");
    });
  });
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
        node("p", "gp-result-note", "Ekvivalent effektiv area för bärighetskontroll, inte en beräknad kontakttrycksfördelning. " + (tag.values.lang === 1 ? "Väggsulan visas som en 1 m-remsa." : "Lokala axlar; skissen är inte orienterad efter ritningen.")));
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
      results.append(node("p", "", readOnly ? "Indata ändrade. Inget aktuellt resultat vid exporten." : "Indata ändrade. Beräkna för att uppdatera resultatet."));
      return;
    }
    if (tag.error) {
      results.append(node("p", "gp-error-text", tag.error));
      return;
    }
    const r = tag.summary;
    if (!r) {
      results.append(node("p", "", readOnly ? "Sulan var inte beräknad vid exporten." : "Ingen aktuell beräkning. Kontrollera indata och tryck Beräkna."));
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
      results.append(mathText("p", "gp-result-note", "Isolering: q_Ed = V / (b_x,eff × b_y,eff). U = q_Ed / f_d. Bruk avser långtidslast; deformation och sättning beräknas inte."));
    }
  }
  function update() {
    const bg = background();
    const data = state();
    for (const id of selected) {
      if (!data.tags.some(tag => tag.id === id && tag.page === bg.page)) selected.delete(id);
    }
    if (!bulkDialog.hidden && bulkIds.some(id => !selected.has(id))) {
      closeBulk(); bulkSignature = "";
    }
    showHeading();
    showLabelSize(sizeDraft ?? data.label_size ?? 100);
    const storage = data.storage;
    showStorage(storage);
    total.textContent = data.tags.length + (data.tags.length === 1 ? " sula" : " sulor");
    loadDrawing.disabled = data.tags.length > 0;
    loadDrawing.title = loadDrawing.disabled ? "Starta en ny Grundplan för en annan ritning." : "";
    saveProject.disabled = saving;
    exportJson.disabled = !bg.url;
    for (const entry of exports) entry.button.disabled = entry.busy || !bg.url;
    empty.hidden = !!bg.url;
    sheet.hidden = !bg.url;
    zoomBar.hidden = !bg.url;
    for (const b of modes.values()) b.disabled = !bg.url;
    showSelection();
    showLoadImport();
    if (bg.url !== lastBackground) {
      cancelDrag();
      lastBackground = bg.url;
      if (bg.url) picture.src = bg.url;
      else picture.removeAttribute("src");
      pageSelect.replaceChildren();
      for (let n = 1; n <= (bg.page_count || 0); n++) {
        const opt = node("option", "", String(n));
        opt.value = n;
        pageSelect.append(opt);
      }
      pageSelect.value = bg.page;
      pageLabel.hidden = !bg.url || bg.page_count < 2;
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
    if (![0, 2].includes(event.button) || drag || !background().url) return;
    if (event.button === 2) {
      event.preventDefault();
      viewport.focus({preventScroll: true});
      drag = {pan: true, x: event.clientX, y: event.clientY, left: panX, top: panY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    if (bulkBusy) return;
    const overlay = event.target.closest(".gp-sliding-overlay");
    if (importBusy && (overlay || event.target.closest(".gp-tag"))) return;
    if (overlay) {
      const resize = event.target === axesResize || event.target === legendResize;
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
      box: !tag && !readOnly && (event.shiftKey || event.ctrlKey || event.metaKey),
      beforeSelection: new Set(selected),
      select: !!tag && !readOnly && (event.shiftKey || event.ctrlKey || event.metaKey) };
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 4) drag.moved = true;
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
    const { moved, id, overlay, page, select, placementBlocked, pan, box, beforeSelection } = drag;
    drag = null;
    selectionBox.hidden = true;
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    viewport.classList.remove("gp-selecting");
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    if (pan) return;
    if (box) {
      if (moved) {
        if (selected.size !== beforeSelection.size || [...selected].some(id => !beforeSelection.has(id))) bulkSignature = "";
        setMode("select"); showSelection(); renderMarkers();
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
    if (readOnly || moved || placementBlocked || mode === "pan" || mode === "select") return;
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
        if (reply.ok && reply.finished) showMessage("Alla " + reply.total + " importerade sulor är placerade. Anpassa övriga indata och beräkna.");
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
      if (source) showMessage("Kopian har fått egna indata. Anpassa last och geometri och tryck Beräkna.");
    });
  });
  viewport.addEventListener("pointercancel", cancelDrag);
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
      const selecting = !!drag?.box || mode === "select" || selected.size > 0;
      cancelDrag(); overlaySelected = null; renderSlidingGeometry(); closeDialog(); closeBulk();
      if (!bulkBusy) { selected.clear(); bulkSignature = ""; showSelection(); renderMarkers(); }
      setMode("pan"); showMessage(selecting && !bulkBusy ? "Markeringen avbröts."
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
    if (!dialog.hidden) placeDialog(dialog.offsetLeft, dialog.offsetTop);
    if (!bulkDialog.hidden) {
      bulkDialog.style.left = Math.max(8, Math.min(board.clientWidth - bulkDialog.offsetWidth - 8, parseFloat(bulkDialog.style.left) || 8)) + "px";
      bulkDialog.style.top = Math.max(8, Math.min(board.clientHeight - bulkDialog.offsetHeight - 8, parseFloat(bulkDialog.style.top) || 8)) + "px";
    }
  });
  resizeObserver.observe(board);
  model.on("change:state", update);
  model.on("change:background", update);
  model.on("msg:custom", receive);
  setMode("pan");
  showMessage(background().url
    ? (readOnly ? "Klicka på en etikett för indata och resultat. Klicka utanför rutan för att minimera. Dra för att panorera och använd Shift + scroll för att zooma." : "Dra för att panorera och använd Shift + scroll för att zooma. Shift + vänsterdrag markerar för flerredigering; välj en sula och klicka för att placera.")
    : "Öppna en ritning eller ett sparat projekt.");
  update();
  return () => {
    disposed = true;
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
