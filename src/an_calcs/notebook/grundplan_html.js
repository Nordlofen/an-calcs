/* Local display state for an exported result view. No kernel or calculation engine. */
export function createResultModel(snapshot) {
  const handlers = new Map();
  const data = {
    state: { ...snapshot.state },
    schema: snapshot.schema,
    background: snapshot.pages.find(page => page.page === snapshot.page) || snapshot.pages[0],
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
      } else {
        Object.assign(reply, { ok: false, error: "Beräkningsvärdena kan inte ändras i resultatvyn." });
      }
      emit("msg:custom", reply);
    },
  };
}
