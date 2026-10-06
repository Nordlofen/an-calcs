/* Shared plan view. All engineering calculations run in the Python kernel. */
function render({ model, el, readOnly = false }) {
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
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
  const positions = new Map(), pendingPositions = new Map();
  const pending = new Map(), dirty = new Set(), inputs = new Map(), edits = new Map(), drafts = new Map();
  const sectionStates = new Map(), inputSections = [], resultSections = [];
  const state = () => model.get("state") || { tags: [] };
  const background = () => model.get("background") || {};
  const current = () => state().tags.find((tag) => tag.id === active);
  const number = (value, digits = 2) => new Intl.NumberFormat("sv-SE", {
    maximumFractionDigits: digits,
  }).format(value);
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
  const loadDrawing = button("Öppna ritning", () => fileInput.click());
  const loadProject = button("Öppna projekt", () => {
    if (!state().tags.length || window.confirm("Ersätt projektet? Spara först om du vill behålla dina ändringar.")) {
      projectInput.click();
    }
  });
  const saveProject = button("Spara projekt", () => {
    command("save", {}, [], (reply) => {
      if (!reply.ok) return;
      const url = URL.createObjectURL(new Blob([reply.download], { type: "application/json" }));
      const a = node("a");
      a.href = url;
      a.download = "grundplan.json";
      root.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showMessage("Projektet har exporterats till din nedladdningsmapp.");
    });
  });
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
  if (!readOnly) toolbar.append(loadDrawing, loadProject, saveProject, ...exports.map(entry => entry.button), node("span", "gp-separator"));
  const modes = new Map();
  for (const [key, label] of [["pan", "Panorera"], ["vaggsula", "+ Väggsula"], ["pelarsula", "+ Pelarsula"]]) {
    const b = button(label, () => setMode(key));
    modes.set(key, b);
    if (!readOnly) toolbar.append(b);
  }
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
    setMode("pan");
    closeDialog();
    command("page", { page: Number(pageSelect.value) });
  });
  toolbar.append(pageLabel);
  const board = node("div", "gp-board");
  const viewport = node("div", "gp-viewport");
  viewport.tabIndex = 0;
  viewport.setAttribute("aria-label", readOnly ? "Grundplan. Klicka på en etikett för indata och resultat." : "Grundplan. Välj Väggsula eller Pelarsula och klicka på ritningen.");
  const sheet = node("div", "gp-sheet");
  const picture = node("img", "gp-picture");
  picture.alt = "Grundläggningsritning";
  picture.draggable = false;
  const markers = node("div", "gp-markers");
  sheet.append(picture, markers);
  viewport.append(sheet);
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
  if (readOnly) form.append(results, basis, fieldsBox);
  else form.append(labelRow, basis, fieldsBox, results, footer);
  dialog.append(dialogHeader, form);
  board.append(viewport, empty, zoomBar, dialog);
  const status = node("div", "gp-status");
  status.setAttribute("role", "status");
  const legend = node("div", "gp-legend", "○ Ej beräknad   ● U ≤ 100 %   ● U > 100 %   ◌ Ändrad");
  const help = node("p", "gp-help",
    "Dra en etikett för att flytta den. Klicka för indata och Kopiera sula. Dra i ritningen för att panorera. Etiketterna följer ritningens zoom.");
  root.append(heading, toolbar, board, status, legend);
  if (!readOnly) root.append(help, fileInput, projectInput);
  el.append(root);

  function showMessage(message, error = false) {
    status.textContent = message;
    status.classList.toggle("gp-error-text", error);
  }
  async function upload(input, action) {
    const file = input.files[0];
    if (!file) return;
    if (file.size > (action === "drawing" ? 40 : 60) * 1024 * 1024) {
      showMessage("Filen är för stor.", true);
      input.value = "";
      return;
    }
    showMessage("Öppnar " + file.name + "…");
    try {
      const buffer = await file.arrayBuffer();
      if (disposed) return;
      command(action, { name: file.name }, [buffer], (reply) => {
        if (reply.ok) {
          active = null;
          formId = null;
          dirty.clear();
          drafts.clear();
          edits.clear();
          positions.clear();
          pendingPositions.clear();
          sectionStates.clear();
          headingDraft = null;
          inputSections.length = resultSections.length = 0;
          setMode("pan");
          update();
          showMessage(file.name + " öppnad.");
        }
      });
    } catch (error) {
      showMessage(error.message, true);
    }
    input.value = "";
  }
  fileInput.addEventListener("change", () => upload(fileInput, "drawing"));
  projectInput.addEventListener("change", () => upload(projectInput, "open"));
  function setMode(value) {
    mode = value;
    if (value !== "copy") copySource = null;
    cancelCopy.hidden = value !== "copy";
    for (const [key, b] of modes) {
      b.classList.toggle("gp-selected", key === value);
      b.setAttribute("aria-pressed", String(key === value));
    }
    viewport.style.cursor = value === "pan" ? "grab" : "crosshair";
    if (value === "copy") showMessage("Klicka på ritningen för att placera en kopia av " + copySource.label + ". Escape avbryter.");
    else if (value !== "pan") showMessage("Klicka på ritningen där du vill placera en " +
      (value === "vaggsula" ? "väggsula." : "pelarsula."));
  }
  function showLabelSize(value) {
    sizeInput.value = value;
    sizeText.textContent = value + "%";
    root.style.setProperty("--gp-tag-scale", String(value / 100 * zoom));
  }
  function setZoom(value) {
    const bg = background();
    if (!bg.width) return;
    const previous = zoom;
    zoom = Math.max(0.02, Math.min(4, value));
    const cx = viewport.clientWidth / 2, cy = viewport.clientHeight / 2;
    panX = cx + (panX - cx) * zoom / previous;
    panY = cy + (panY - cy) * zoom / previous;
    sheet.style.width = bg.width * zoom + "px";
    sheet.style.height = bg.height * zoom + "px";
    showLabelSize(sizeDraft ?? state().label_size ?? 100);
    placeSheet();
    zoomText.textContent = Math.round(zoom * 100) + "%";
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
    renderMarkers();
  }
  function openDialog(tag) {
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
    dialog.style.left = Math.max(8, Math.min(board.clientWidth - dialog.offsetWidth - 8, x)) + "px";
    dialog.style.top = Math.max(8, Math.min(board.clientHeight - dialog.offsetHeight - 8, y)) + "px";
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
        if (!event.detail) openDialog(tag);
      }, "gp-tag gp-tag-" + color);
      marker.dataset.tagId = tag.id;
      marker.title = readOnly ? "Klicka för indata och resultat" : "Dra för att flytta · klicka för indata och kopiering";
      const position = positions.get(tag.id) || tag;
      marker.style.left = position.x * 100 + "%";
      marker.style.top = position.y * 100 + "%";
      marker.classList.toggle("gp-active", active === tag.id);
      const heading = node("strong", "", tag.label);
      const text = summary
        ? "U " + number(summary.utnyttjandegrad * 100, 1) + "% · b " + number(summary.b) + " m"
        : ({ new: "Ej beräknad", stale: "Ändrad · beräkna", error: "Kontrollera indata" }[tagState] || "Ej beräknad");
      marker.setAttribute("aria-label", tag.label + ", " + text);
      marker.append(heading, node("span", "", text));
      if (summary?.isolering) marker.append(node("span", "gp-governing", "Styrande: " + summary.styrande));
      markers.append(marker);
    }
  }
  const groups = [
    ["Geometri", ["lang", "b", "l", "t", "d", "e_b_plac", "e_l_plac"]],
    ["Laster – Brott", ["F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b", "l_h"],
      "Yttre dimensionerande laster. Sulans egentyngd tillkommer med faktor 1,5."],
    ["Laster – Bruk", ["F_vy_bruk", "F_hb_bruk", "F_hl_bruk", "M_insp_l_bruk", "M_insp_b_bruk", "l_h_bruk"],
      "Yttre långtidslaster för isoleringskontrollen. Sulans egentyngd tillkommer med faktor 1,0. Aktivera underliggande isolering för att ange värden."],
    ["Jord och grundvatten", ["c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "delta_h", "beta", "alpha"]],
    ["Koefficienter", ["eta", "gamma_m", "gamma_m0", "gamma_Rd"]],
    ["Isolering", ["isolering", "isolerprodukt", "f_d_brott", "f_d_bruk"],
      "Ange färdiga dimensionerande bärförmågor. Kontroll: N / (b_eff × l_eff) i respektive lastkombination. Isoleringen förutsätts täcka hela den effektiva arean."],
  ];
  const fieldSchema = new Map(model.get("schema").fields.map((field) => [field.name, field]));
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
      if (note && !readOnly) group.append(node("p", "gp-field-note", note));
      for (const name of names) {
        const field = fieldSchema.get(name);
        const row = node(readOnly ? "div" : "label", "gp-field");
        const caption = node("span", "gp-field-caption", field.label);
        if (readOnly) {
          const value = tag.values[name];
          const text = field.type === "bool" ? (value ? "Ja" : "Nej")
            : field.type === "choice" ? (value === 1 ? "Väggsula (per meter)" : "Pelarsula")
            : field.type === "text" ? (value || "—")
            : value == null ? "—" : number(value, 10);
          const output = node("span", "gp-value", text);
          const unit = node("span", "gp-unit", field.unit);
          if (["text", "choice", "bool"].includes(field.type)) {
            row.classList.add("gp-text-field");
            row.append(caption, output);
          } else row.append(caption, output, unit);
          group.append(row);
          inputs.set(name, { input: output, unit, row, group });
          continue;
        }
        const input = node(field.type === "choice" ? "select" : "input");
        input.name = name;
        input.setAttribute("aria-label", field.label);
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
        else row.append(caption, input, unit);
        group.append(row);
        inputs.set(name, { input, unit, row, group });
        input.addEventListener("input", () => edit(field.type !== "text"));
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
      input.setCustomValidity(input.disabled || Number.isFinite(value) ? "" : "Ange ett tal.");
      return [name, Number.isFinite(value) ? value : null];
    }));
  }
  function fieldUnits() {
    const strip = readOnly ? current()?.values.lang === 1 : inputs.get("lang")?.input.value === "1";
    const insulated = readOnly ? current()?.values.isolering : inputs.get("isolering")?.input.checked;
    basis.textContent = readOnly
      ? (strip ? "Väggsula: laster och moment avser en meter vägg." : "Pelarsula: laster och moment avser hela sulan.") + " Egentyngd ingår i beräkningsresultatet."
      : strip
        ? "Väggsula: samtliga laster och moment avser en meter vägg. Egentyngd tillkommer i beräkningen."
        : "Pelarsula: ange totala laster och moment. Egentyngd tillkommer i beräkningen.";
    for (const [name, entry] of inputs) {
      const unit = fieldSchema.get(name).unit;
      entry.unit.textContent = strip && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
      const insulationField = name.endsWith("_bruk") || name === "f_d_brott";
      if (readOnly) {
        entry.row.hidden = (strip && name === "l") || (!insulated && insulationField);
        continue;
      }
      entry.input.disabled = insulationField && !insulated;
      entry.input.required = entry.input.type !== "checkbox" && fieldSchema.get(name).type !== "text" && !entry.input.disabled;
      if (entry.input.disabled) entry.input.setCustomValidity("");
      entry.row.hidden = (strip && name === "l") || (!insulated && name.startsWith("f_d_"));
    }
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
    showResult();
    renderMarkers();
    const label = labelInput.value.trim();
    command("update", { id: active, values, ...(label ? { label } : {}) });
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
      ["Dimensionerande last – brott", number(r.last) + " " + r.lastenhet],
      ["Jordens bärförmåga", number(r.barformaga) + " " + r.lastenhet],
      ["Bärförmåga q_bd", number(r.q_bd) + " kPa"],
      ["Effektiv bredd", number(r.b_ef, 3) + " m"],
    ]) table.append(node("dt", "", label), node("dd", "", value));
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
    if (r.isolering) {
      for (const [phase, label] of [["brott", "Brott"], ["bruk", "Bruk · långtidslast"]]) {
        const values = r.isolering;
        const group = makeSection(tag.id, "result:" + phase, "Isolering – " + label, false, resultSections);
        group.classList.add("gp-insulation-result");
        const list = node("dl", "gp-result-list");
        for (const [name, caption, unit] of [
          ["N", "Last inkl. egentyngd", r.lastenhet],
          ["b_eff", "Effektiv bredd", "m"], ["l_eff", "Effektiv längd", "m"],
          ["A_eff", "Effektiv area", "m²"],
          ["q_Ed", "Lasteffekt q_Ed", "kPa"], ["f_d", "Bärförmåga f_d." + phase, "kPa"],
        ]) list.append(node("dt", "", caption), node("dd", "", number(values["isolering_" + name + "_" + phase], 3) + " " + unit));
        group.append(list);
        results.append(group);
      }
      results.append(node("p", "gp-result-note", "Isolering: q_Ed = N / (b_eff × l_eff). U = q_Ed / f_d. Bruk avser långtidslast; deformation och sättning beräknas inte."));
    }
  }
  function update() {
    const bg = background();
    const data = state();
    showHeading();
    showLabelSize(sizeDraft ?? data.label_size ?? 100);
    total.textContent = data.tags.length + (data.tags.length === 1 ? " sula" : " sulor");
    loadDrawing.disabled = data.tags.length > 0;
    loadDrawing.title = loadDrawing.disabled ? "Starta en ny Grundplan för en annan ritning." : "";
    saveProject.disabled = !bg.url;
    for (const entry of exports) entry.button.disabled = entry.busy || !bg.url;
    empty.hidden = !!bg.url;
    sheet.hidden = !bg.url;
    zoomBar.hidden = !bg.url;
    for (const b of modes.values()) b.disabled = !bg.url;
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
    }
    renderMarkers();
  }
  let drag = null;
  function cancelDrag() {
    const previous = drag;
    drag = null;
    if (previous?.id) {
      if (pendingPositions.has(previous.id)) positions.set(previous.id, pendingPositions.get(previous.id));
      else positions.delete(previous.id);
    }
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    if (previous && viewport.hasPointerCapture(previous.pointerId)) viewport.releasePointerCapture(previous.pointerId);
    if (previous?.id) renderMarkers();
  }
  viewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || drag || !background().url) return;
    const marker = event.target.closest(".gp-tag");
    const tag = marker && state().tags.find((t) => t.id === marker.dataset.tagId);
    if (!tag && event.target.closest("button")) return;
    event.preventDefault();
    const position = tag && (positions.get(tag.id) || tag);
    drag = { x: event.clientX, y: event.clientY, left: panX, top: panY,
      moved: false, pointerId: event.pointerId, id: tag?.id, position };
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 4) drag.moved = true;
    if (drag.moved) {
      if (drag.id) {
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
    const { moved, id } = drag;
    drag = null;
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    if (id) {
      const tag = state().tags.find((t) => t.id === id);
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
    if (readOnly || moved || mode === "pan") return;
    const rect = picture.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
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
  let dialogDrag = null;
  dialogHeader.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button")) return;
    dialogDrag = { x: event.clientX, y: event.clientY, left: dialog.offsetLeft, top: dialog.offsetTop };
    dialogHeader.setPointerCapture(event.pointerId);
  });
  dialogHeader.addEventListener("pointermove", (event) => {
    if (!dialogDrag) return;
    placeDialog(dialogDrag.left + event.clientX - dialogDrag.x, dialogDrag.top + event.clientY - dialogDrag.y);
  });
  dialogHeader.addEventListener("pointerup", () => { dialogDrag = null; });
  dialogHeader.addEventListener("pointercancel", () => { dialogDrag = null; });
  root.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Escape") { cancelDrag(); closeDialog(); setMode("pan"); showMessage(readOnly ? "Klicka på en etikett för indata och resultat." : "Klicka på en etikett för indata eller dra den för att flytta."); }
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
  });
  resizeObserver.observe(board);
  model.on("change:state", update);
  model.on("change:background", update);
  model.on("msg:custom", receive);
  setMode("pan");
  showMessage(background().url
    ? (readOnly ? "Klicka på en etikett för indata och resultat. Dra i ritningen för att panorera." : "Välj Väggsula eller Pelarsula och klicka på ritningen.")
    : "Öppna en ritning eller ett sparat projekt.");
  update();
  return () => {
    disposed = true;
    resizeObserver.disconnect();
    model.off("change:state", update);
    model.off("change:background", update);
    model.off("msg:custom", receive);
    pending.clear();
    root.remove();
  };
}

export default { render };
