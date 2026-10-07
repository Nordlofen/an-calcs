/* Local display state for an exported result view. No kernel or calculation engine. */
export function createResultModel(snapshot, validateCalibration) {
  const handlers = new Map();
  const data = {
    state: { ...snapshot.state },
    schema: snapshot.schema,
    background: snapshot.pages.find(page => page.page === snapshot.page) || snapshot.pages[0],
    pdf: snapshot.pdf,
  };
  const emit = (name, ...args) => {
    for (const callback of handlers.get(name) || []) callback(...args);
  };
  return {
    get: name => data[name],
    on(name, callback) {
      if (!handlers.has(name)) handlers.set(name, new Set());
      handlers.get(name).add(callback);
    },
    off(name, callback) { handlers.get(name)?.delete(callback); },
    send(message) {
      const reply = { request: message.request, view: message.view, ok: true };
      if (message.action === "label_size" && typeof message.value === "number" &&
                 Number.isFinite(message.value) && message.value >= 60 && message.value <= 180) {
        data.state = { ...data.state, label_size: message.value };
        emit("change:state");
      } else if (message.action === "calibration") {
        try {
          data.state = {...data.state, calibration: validateCalibration(message.calibration, data.background)};
          emit("change:state");
        } catch (error) {
          Object.assign(reply, {ok: false, error: error.message});
        }
      } else if (message.action === "export_pdf" && snapshot.pdf) {
        try {
          const bytes = Uint8Array.from(atob(snapshot.pdf.data), character => character.charCodeAt(0));
          emit("msg:custom", {...reply, filename: snapshot.pdf.filename}, [bytes.buffer]);
          return;
        } catch (error) {
          Object.assign(reply, {ok: false, error: "Den inbäddade PDF-filen kunde inte läsas."});
        }
      } else {
        Object.assign(reply, { ok: false, error: "Beräkningsvärdena kan inte ändras i resultatvyn." });
      }
      emit("msg:custom", reply);
    },
  };
}
