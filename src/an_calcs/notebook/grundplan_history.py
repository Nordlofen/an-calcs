"""Session history of trusted kernel state, recorded once per UI command.

Entries contain only changed fields/footings. Immutable drawing bytes and image
strings are shared, so ordinary edits never duplicate the imported drawing.
"""

import copy
from functools import wraps


_MISSING = object()
_FIELDS = ("_source", "_filename", "_initial_page", "background", "_title", "_subtitle",
           "_label_size", "_calibration", "_gliding", "_colour", "_layout",
           "_insulation_widget", "_comment_widget", "_reference_widget", "_text_objects",
           "_placement_locks", "_canvas_bounds", "_drawing_layout", "_object_layout", "_load_import")
_ACTIONS = {"add", "copy", "import_loads", "place_import", "import_control", "update",
            "move_tags", "move_objects", "transform_objects", "object_order", "drawing_layout",
            "drawing_commit", "canvas_bounds", "placement_lock", "leader", "calculate",
            "bulk_update", "delete", "delete_all", "label_size", "calibration", "heading",
            "sliding", "colour_grouping", "layout", "insulation_widget", "comment_widget",
            "reference_widget", "footing_type", "text_add", "text_update", "text_delete",
            "insulation_placement", "comment_placement", "reference_placement",
            "colour_placement", "sliding_placement", "drawing"}
_ACTIONS.update({"input_lock", "auto_bx_apply"})


def snapshot(plan):
    values = {name: getattr(plan, name) for name in _FIELDS}
    values["_tag_order"] = [tag["id"] for tag in plan._tags]
    values.update(("tag:" + tag["id"], tag) for tag in plan._tags)
    values.update(("details:" + ident, value) for ident, value in plan._details.items())
    return copy.deepcopy(values)


def restore(plan, values):
    for name in _FIELDS:
        setattr(plan, name, copy.deepcopy(values[name]))
    plan._tags = [copy.deepcopy(values["tag:" + ident]) for ident in values["_tag_order"]]
    plan._details = {key[8:]: copy.deepcopy(value) for key, value in values.items() if key.startswith("details:")}


def difference(before, after):
    return {key: (before.get(key, _MISSING), after.get(key, _MISSING))
            for key in before.keys() | after.keys() if before.get(key, _MISSING) != after.get(key, _MISSING)}


def description(content, before, after):
    action = content["action"]
    tag = before.get("tag:" + str(content.get("id")), {})
    label = tag.get("label", "sula")
    if action in ("add", "copy", "place_import"):
        added = next((v["label"] for k, v in after.items() if k.startswith("tag:") and k not in before), "sula")
        return ("Kopiera " if action == "copy" else "Placera ") + added
    if action == "delete": return "Radera " + label
    if action == "delete_all": return f"Radera {len(before['_tag_order'])} sulor"
    if action == "update": return ("Flytta " if "x" in content or "y" in content else "Ändra ") + label
    if action in ("move_tags", "move_objects", "transform_objects", "object_order", "placement_lock"):
        count = len(content.get("objects", content.get("positions", [])))
        verb = {"move_tags": "Flytta", "move_objects": "Flytta", "transform_objects": "Skala",
                "placement_lock": "Lås" if content.get("locked") else "Lås upp",
                "object_order": {"forward": "Flytta fram", "backward": "Flytta bak",
                                 "front": "Flytta längst fram", "back": "Flytta längst bak"}.get(content.get("operation"), "Ändra lager för")}[action]
        return f"{verb} {count} objekt"
    if action == "bulk_update": return f"Ändra {len(content.get('ids', []))} sulor"
    if action == "input_lock":
        return ("Lås indata för " if content.get("locked") else "Lås upp indata för ") + f"{len(content.get('ids', []))} sulor"
    if action == "auto_bx_apply":
        changed = sum(k.startswith("tag:") and v.get("values") != before.get(k, {}).get("values")
                      for k, v in after.items() if isinstance(v, dict))
        return f"Tilldela bₓ för {changed} sulor"
    if action == "leader": return "Ändra spline för " + label
    if action == "footing_type": return "Ändra sultyp för " + label
    if action in ("text_update", "text_delete", "text_add"):
        item = next((t for t in before["_text_objects"] if t["id"] == content.get("id")), {})
        kind = content.get("kind", item.get("kind"))
        verb = "Radera" if action == "text_delete" else "Lägg till" if action == "text_add" else (
            "Flytta" if {"x", "y"} & content.get("changes", {}).keys() else
            "Skala" if {"size", "width"} & content.get("changes", {}).keys() else "Ändra")
        return verb + (" datum" if kind == "date" else " rubrik")
    return {"import_loads": "Importera lasteffekt", "import_control": "Ändra lasteffektplacering",
            "drawing": "Uppdatera ritningsunderlag", "drawing_commit": "Redigera ritningsunderlag",
            "drawing_layout": "Redigera ritningsunderlag", "canvas_bounds": "Beskär ritningsytan",
            "label_size": "Ändra etikettstorlek", "calibration": "Ändra måttkalibrering",
            "heading": "Ändra rubrik", "sliding": "Ändra glidningskontroll",
            "colour_grouping": "Ändra färggruppering", "layout": "Ändra visningsstorlek",
            "insulation_widget": "Ändra isoleringswidget", "comment_widget": "Ändra kommentarwidget",
            "reference_widget": "Ändra referenswidget", "calculate": "Beräkna " + label,
            "insulation_placement": "Flytta isoleringswidget", "comment_placement": "Flytta kommentarwidget",
            "reference_placement": "Flytta referenswidget", "colour_placement": "Flytta färglegend",
            "sliding_placement": "Flytta glidningswidget"}.get(action, "Ändra projektet")


class History:
    limit = 100

    def __init__(self):
        self.undo, self.redo = [], []
        self.baseline = None
        self.in_command = self.replaying = False
        self.merge_group = None
        self.pending_state = None

    @property
    def state(self):
        return {"undo": self.undo[-1]["description"] if self.undo else None,
                "redo": self.redo[-1]["description"] if self.redo else None,
                "undo_count": len(self.undo), "redo_count": len(self.redo)}

    def clear(self):
        self.undo.clear(); self.redo.clear()
        self.baseline = self.merge_group = None

    def observe(self, plan):
        # Direct Python changes are a new baseline, never silently undone as UI edits.
        if not self.in_command and not self.replaying and self.baseline is not None and snapshot(plan) != self.baseline:
            self.clear()

    def record(self, content, before, after):
        patch = difference(before, after)
        if not patch: return
        group = content.get("history_group")
        group = (content.get("view"), group) if isinstance(group, str) and 0 < len(group) <= 160 else None
        self.redo.clear()
        if group and group == self.merge_group and self.undo:
            entry = self.undo[-1]
            for key, pair in patch.items():
                entry["patch"][key] = (entry["patch"].get(key, pair)[0], pair[1])
            entry["patch"] = {k: v for k, v in entry["patch"].items() if v[0] != v[1]}
            if not entry["patch"]: self.undo.pop()
        else:
            self.undo.append({"description": description(content, before, after), "patch": patch})
            del self.undo[:-self.limit]
        self.merge_group = group

    def apply(self, plan, *, redo=False):
        stack, other = (self.redo, self.undo) if redo else (self.undo, self.redo)
        if not stack: raise ValueError("Det finns inget att göra om." if redo else "Det finns inget att ångra.")
        entry = stack[-1]
        before = snapshot(plan)
        values = dict(before)
        for key, pair in entry["patch"].items():
            value = pair[1 if redo else 0]
            if value is _MISSING: values.pop(key, None)
            else: values[key] = value
        self.replaying = True
        try:
            restore(plan, values)
            plan._restore_history_calculations(before)
        except Exception:
            restore(plan, before)
            raise
        else:
            stack.pop(); other.append(entry)
            self.merge_group = None
            plan._publish()
            self.baseline = snapshot(plan)
        finally:
            self.replaying = False
        return entry["description"]


def history_command(fn):
    @wraps(fn)
    def wrapped(plan, widget, content, buffers):
        history = plan._history
        action = content.get("action")
        record = action in _ACTIONS and not (action == "drawing" and content.get("draft")) \
            and not (action == "import_control" and content.get("operation") != "cancel")
        before = snapshot(plan) if record else None
        history.in_command = True
        history.pending_state = None
        try:
            reply = fn(plan, widget, content, buffers)
            if reply is None:  # Binary exports already sent their buffers.
                history.merge_group = None
                return
            if action == "open" and reply.get("ok"):
                history.clear()
            elif record:
                history.record(content, before, snapshot(plan))
            elif action not in ("undo", "redo"):
                history.merge_group = None
            history.baseline = snapshot(plan) if history.undo or history.redo else None
            # Send the updated history before acknowledgement enables another gesture.
            if history.pending_state is not None:
                plan.state = {**history.pending_state, "history": history.state}
            elif plan.state.get("history") != history.state:
                plan.state = {**plan.state, "history": history.state}
            plan.send(reply)
            return reply
        finally:
            history.in_command = False
            history.pending_state = None
    return wrapped
