/* Shared plan view. All engineering calculations run in the Python kernel. */
function render({ model, el }) {
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const root = node("div", "an-grundplan");
  const view = Math.random().toString(36).slice(2);
  let sequence = 0, active = null, mode = "pan", zoom = 1, disposed = false;
  let lastBackground = "", formId = null;
  const pending = new Map(), dirty = new Set(), inputs = new Map(), edits = new Map(), drafts = new Map();
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
    const request = ++sequence;
    pending.set(request, onDone);
    model.send({ action, ...payload, request, view }, undefined, buffers);
  }
  const heading = node("header", "gp-heading");
  const headingText = node("div");
  const title = node("h3", "", state().title);
  headingText.append(title, node("p", "", "Sulgrundläggning · jordens bärighet"));
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
  toolbar.append(loadDrawing, loadProject, saveProject, node("span", "gp-separator"));
  const modes = new Map();
  for (const [key, label] of [["pan", "Panorera"], ["vaggsula", "+ Väggsula"], ["pelarsula", "+ Pelarsula"]]) {
    const b = button(label, () => setMode(key));
    modes.set(key, b);
    toolbar.append(b);
  }
  const pageLabel = node("label", "gp-page-label", "Sida ");
  const pageSelect = node("select");
  pageSelect.setAttribute("aria-label", "PDF-sida");
  pageLabel.append(pageSelect);
  pageSelect.addEventListener("change", () => {
    closeDialog();
    command("page", { page: Number(pageSelect.value) });
  });
  toolbar.append(pageLabel);
  const board = node("div", "gp-board");
  const viewport = node("div", "gp-viewport");
  viewport.tabIndex = 0;
  viewport.setAttribute("aria-label", "Grundplan. Välj Väggsula eller Pelarsula och klicka på ritningen.");
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
        }
      });
      closeDialog();
    }
  }, "gp-delete");
  footer.append(remove, calculate);
  form.append(labelRow, basis, fieldsBox, results, footer);
  dialog.append(dialogHeader, form);
  board.append(viewport, empty, zoomBar, dialog);
  const status = node("div", "gp-status");
  status.setAttribute("role", "status");
  const legend = node("div", "gp-legend", "○ Ej beräknad   ● U ≤ 100 %   ● U > 100 %   ◌ Ändrad");
  const help = node("p", "gp-help",
    "Markeringarna anger läge på ritningen. Sulmått och laster anges i beräkningen. Dra i ritningen för att panorera.");
  root.append(heading, toolbar, board, status, legend, help, fileInput, projectInput);
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
    for (const [key, b] of modes) {
      b.classList.toggle("gp-selected", key === value);
      b.setAttribute("aria-pressed", String(key === value));
    }
    viewport.style.cursor = value === "pan" ? "grab" : "crosshair";
    if (value !== "pan") showMessage("Klicka på ritningen där du vill placera en " +
      (value === "vaggsula" ? "väggsula." : "pelarsula."));
  }
  function setZoom(value) {
    const bg = background();
    if (!bg.width) return;
    const previous = zoom;
    zoom = Math.max(0.12, Math.min(4, value));
    const cx = viewport.scrollLeft + viewport.clientWidth / 2;
    const cy = viewport.scrollTop + viewport.clientHeight / 2;
    sheet.style.width = bg.width * zoom + "px";
    sheet.style.height = bg.height * zoom + "px";
    viewport.scrollLeft = cx * zoom / previous - viewport.clientWidth / 2;
    viewport.scrollTop = cy * zoom / previous - viewport.clientHeight / 2;
    zoomText.textContent = Math.round(zoom * 100) + "%";
  }
  function fit() {
    const bg = background();
    if (!bg.width) return;
    setZoom(Math.min((viewport.clientWidth - 48) / bg.width,
      (viewport.clientHeight - 48) / bg.height));
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  }
  function closeDialog() {
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
    labelInput.focus({ preventScroll: true });
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
      const marker = button("", (event) => { event.stopPropagation(); openDialog(tag); }, "gp-tag gp-tag-" + color);
      marker.style.left = tag.x * 100 + "%";
      marker.style.top = tag.y * 100 + "%";
      marker.classList.toggle("gp-active", active === tag.id);
      const heading = node("strong", "", tag.label);
      const text = summary
        ? "U " + number(summary.utnyttjandegrad * 100, 1) + "% · b " + number(summary.b) + " m"
        : ({ new: "Ej beräknad", stale: "Ändrad · beräkna", error: "Kontrollera indata" }[tagState] || "Ej beräknad");
      marker.setAttribute("aria-label", tag.label + ", " + text);
      marker.append(heading, node("span", "", text));
      markers.append(marker);
    }
  }
  const groups = [
    ["Geometri", ["lang", "b", "l", "t", "d", "e_b_plac", "e_l_plac"]],
    ["Laster", ["F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b", "l_h"]],
    ["Jord och grundvatten", ["c_prime", "c_uk", "gamma", "gamma_prime", "phi_k", "delta_h", "beta", "alpha"]],
    ["Koefficienter", ["eta", "gamma_m", "gamma_m0", "gamma_Rd"]],
  ];
  const fieldSchema = new Map(model.get("schema").fields.map((field) => [field.name, field]));
  function buildFields(tag) {
    fieldsBox.replaceChildren();
    inputs.clear();
    const draft = drafts.get(tag.id);
    for (const [index, [label, names]] of groups.entries()) {
      const group = node("details", "gp-group");
      group.open = index < 2;
      group.append(node("summary", "", label));
      for (const name of names) {
        const field = fieldSchema.get(name);
        const row = node("label", "gp-field");
        const caption = node("span", "gp-field-caption", field.label);
        const input = node(field.type === "choice" ? "select" : "input");
        input.name = name;
        input.setAttribute("aria-label", field.label);
        if (field.type === "choice") {
          for (const option of field.options) {
            const opt = node("option", "", option.value === 1 ? "Väggsula (per meter)" : "Pelarsula");
            opt.value = option.value;
            input.append(opt);
          }
        } else {
          input.type = "text";
          input.inputMode = "decimal";
          input.required = true;
        }
        input.value = draft?.values[name] ?? tag.values[name] ?? "";
        const unit = node("span", "gp-unit", field.unit);
        row.append(caption, input, unit);
        group.append(row);
        inputs.set(name, { input, unit, row });
        input.addEventListener("input", () => edit(true));
      }
      fieldsBox.append(group);
    }
  }
  function readValues() {
    return Object.fromEntries([...inputs].map(([name, { input }]) => {
      const raw = input.value.trim().replace(",", ".");
      const value = raw === "" ? NaN : Number(raw);
      input.setCustomValidity(Number.isFinite(value) ? "" : "Ange ett tal.");
      return [name, Number.isFinite(value) ? value : null];
    }));
  }
  function fieldUnits() {
    const strip = inputs.get("lang")?.input.value === "1";
    basis.textContent = strip
      ? "Väggsula: samtliga laster och moment avser en meter vägg. Egentyngd tillkommer i beräkningen."
      : "Pelarsula: ange totala laster och moment. Egentyngd tillkommer i beräkningen.";
    for (const [name, entry] of inputs) {
      const unit = fieldSchema.get(name).unit;
      entry.unit.textContent = strip && ["kN", "kNm"].includes(unit) ? unit + "/m" : unit;
      entry.row.hidden = strip && name === "l";
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
      values: Object.fromEntries([...inputs].map(([name, { input }]) => [name, input.value])),
    });
    const values = readValues();
    fieldUnits();
    showResult();
    renderMarkers();
    const label = labelInput.value.trim();
    command("update", { id: active, values, ...(label ? { label } : {}) });
  }
  labelInput.addEventListener("input", () => edit(false));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const values = readValues();
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
    results.replaceChildren();
    if (!tag) return;
    if (dirty.has(tag.id) || tag.status === "stale") {
      results.append(node("p", "", "Indata ändrade. Beräkna för att uppdatera resultatet."));
      return;
    }
    if (tag.error) {
      results.append(node("p", "gp-error-text", tag.error));
      return;
    }
    const r = tag.summary;
    if (!r) {
      results.append(node("p", "", "Startvärdena är exempel. Anpassa dem och tryck Beräkna."));
      return;
    }
    const headline = node("div", "gp-result-main " + (r.utnyttjandegrad <= 1 ? "gp-pass" : "gp-fail"));
    headline.append(node("span", "", "Utnyttjandegrad"), node("strong", "", number(r.utnyttjandegrad * 100, 1) + "%"));
    const table = node("dl", "gp-result-list");
    for (const [label, value] of [
      ["Dimensionerande last", number(r.last) + " " + r.lastenhet],
      ["Bärförmåga", number(r.barformaga) + " " + r.lastenhet],
      ["Bärförmåga q_bd", number(r.q_bd) + " kPa"],
      ["Effektiv bredd", number(r.b_ef, 3) + " m"],
    ]) table.append(node("dt", "", label), node("dd", "", value));
    results.append(headline, table, node("p", "gp-result-note",
      "U = last / bärförmåga enligt befintlig modell. Avser jordens bärighet i brottgränstillstånd."));
  }
  function update() {
    const bg = background();
    const data = state();
    title.textContent = data.title;
    total.textContent = data.tags.length + (data.tags.length === 1 ? " sula" : " sulor");
    loadDrawing.disabled = data.tags.length > 0;
    loadDrawing.title = loadDrawing.disabled ? "Starta en ny Grundplan för en annan ritning." : "";
    saveProject.disabled = !bg.url;
    empty.hidden = !!bg.url;
    sheet.hidden = !bg.url;
    zoomBar.hidden = !bg.url;
    for (const b of modes.values()) b.disabled = !bg.url;
    if (bg.url !== lastBackground) {
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
      } else if (!dirty.has(tag.id)) {
        for (const [name, { input }] of inputs) {
          if (document.activeElement !== input) input.value = draft?.values[name] ?? tag.values[name] ?? "";
        }
        if (document.activeElement !== labelInput) labelInput.value = draft?.label ?? tag.label;
      }
      fieldUnits();
      showResult();
    }
    renderMarkers();
  }
  let drag = null;
  viewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button") || !background().url) return;
    drag = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop, moved: false };
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 4) drag.moved = true;
    if (drag.moved) {
      viewport.scrollLeft = drag.left - dx;
      viewport.scrollTop = drag.top - dy;
    }
  });
  viewport.addEventListener("pointerup", (event) => {
    if (!drag) return;
    const moved = drag.moved;
    drag = null;
    if (moved || mode === "pan") return;
    const rect = picture.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    command("add", { x, y, kind: mode }, [], (reply) => {
      if (!reply.ok) return;
      setMode("pan");
      const tag = state().tags.find((t) => t.id === reply.id);
      if (tag) openDialog(tag);
    });
  });
  viewport.addEventListener("pointercancel", () => { drag = null; });
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
    if (event.key === "Escape") { closeDialog(); setMode("pan"); }
  });
  function receive(reply) {
    if (reply.view !== view) return;
    if (!reply.ok) showMessage(reply.error, true);
    const onDone = pending.get(reply.request);
    pending.delete(reply.request);
    onDone?.(reply);
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
    ? "Välj Väggsula eller Pelarsula och klicka på ritningen."
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
