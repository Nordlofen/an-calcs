"""Interaktiv grundplan för JupyterLab, med Python som enda beräkningsmotor."""

import base64
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import uuid

try:
    import anywidget
    import traitlets
    from PIL import Image, ImageOps
except ImportError as exc:
    raise ImportError(
        'Grundplan kräver notebook-tilläggen. Installera med: pip install -e ".[notebook]"'
    ) from exc

from an_calcs.geo import allmanna_barighetsekvationen


_ASSETS = Path(__file__).parent
_CALCULATOR_FILE = _ASSETS.parent / "geo" / "allmanna_barighetsekvationen.py"
_CALCULATOR_VERSION = hashlib.sha256(_CALCULATOR_FILE.read_bytes()).hexdigest()
_FORMAT = "an-calcs-grundplan"
_MAX_FILE_BYTES = 40 * 1024 * 1024
_MAX_PROJECT_BYTES = 60 * 1024 * 1024
_MAX_TAGS = 1000
_FIELDS = allmanna_barighetsekvationen.panel_schema["fields"]
_NAMES = allmanna_barighetsekvationen.panel_schema["px"]
_DEFAULTS = {field["name"]: field["default"] for field in _FIELDS}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} måste vara ett ändligt tal.")
    return value


def _values(values, *, draft=False):
    if not isinstance(values, dict) or set(values) != set(_NAMES):
        raise ValueError("Indata måste innehålla precis beräkningens 25 fält.")
    for name, value in values.items():
        if draft and value is None and name != "lang":
            continue
        _number(value, name)
    if values["lang"] not in (0, 1):
        raise ValueError("Fundamenttyp måste vara 0 eller 1.")
    return copy.deepcopy(values)


def _label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise ValueError("Littera måste innehålla 1–80 tecken.")
    return value.strip()


def _page_number(page, count):
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= count:
        raise ValueError(f"Sida måste vara ett heltal mellan 1 och {count}.")
    return page


def _label_size(value):
    if not 60 <= _number(value, "Etikettstorlek") <= 180:
        raise ValueError("Etikettstorlek måste ligga mellan 60 och 180 procent.")
    return value


def _render_source(data, filename, page=1):
    """Normalisera rasterbilder och rendera en PDF-sida lokalt till PNG."""
    if not data or len(data) > _MAX_FILE_BYTES:
        raise ValueError("Ritningen måste vara mellan 1 byte och 40 MB.")
    if data.startswith(b"%PDF-"):
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise ImportError("PDF kräver pypdfium2. Installera notebook-tilläggen.") from exc
        with pdfium.PdfDocument(data) as document:
            count = len(document)
            _page_number(page, count)
            pdf_page = document[page - 1]
            try:
                width, height = pdf_page.get_size()
                if min(width, height) <= 0:
                    raise ValueError("PDF-sidan har ogiltiga mått.")
                scale = min(2.0, 2800 / max(width, height))
                bitmap = pdf_page.render(scale=scale)
                try:
                    img = bitmap.to_pil().convert("RGB")
                finally:
                    bitmap.close()
            finally:
                pdf_page.close()
    else:
        _page_number(page, 1)
        count = 1
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP", "TIFF", "BMP"}:
                raise ValueError("Välj PDF, PNG, JPEG, WebP, TIFF eller BMP.")
            source.load()
            rgba = ImageOps.exif_transpose(source).convert("RGBA")
            img = Image.new("RGBA", rgba.size, "white")
            img.alpha_composite(rgba)
            img = img.convert("RGB")
        img.thumbnail((2800, 2800))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return {
        "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
        "width": img.width,
        "height": img.height,
        "name": Path(filename).name,
        "page": page,
        "page_count": count,
    }


def _calculate(values):
    values = _values(values)
    details = allmanna_barighetsekvationen([values[name] for name in _NAMES])
    result = {item["namn"]: item["value"] for item in details["slutresultat"]["items"]}
    for section in ("indata", "delresultat", "slutresultat"):
        for item in details[section]["items"]:
            _number(item["value"], item["namn"])
    if result["F_bd"] <= 0:
        raise ValueError("Beräknad bärförmåga är inte positiv. Kontrollera indata.")
    # Långsträckt fundament räknas redan på en 1 m-remsa i ursprungsfunktionen.
    utilization = result["F_v"] / result["F_bd"]
    _number(utilization, "Utnyttjandegrad")
    summary = {
        "utnyttjandegrad": utilization,
        "last": result["F_v"],
        "barformaga": result["F_bd"],
        "lastenhet": "kN/m" if values["lang"] == 1 else "kN",
        "q_bd": result["q_bd"],
        "b": values["b"],
        "b_ef": result["b_ef"],
    }
    return details, summary


class Grundplan(anywidget.AnyWidget):
    """Visa PDF/bild med individuella sulberäkningar direkt i en notebook.

    Exempel:
        from an_calcs.notebook import Grundplan
        plan = Grundplan("grundplan.pdf", sida=1)
        plan

    Koordinater för taggar är relativa bildkoordinater (0–1), med origo uppe
    till vänster. Mått och laster anges manuellt. Varje väggsula beräknas per
    meter; ritningslängden används inte för att fördela en total last.
    """

    _esm = _ASSETS / "grundplan.js"
    _css = _ASSETS / "grundplan.css"
    schema = traitlets.Dict().tag(sync=True)
    state = traitlets.Dict().tag(sync=True)
    background = traitlets.Dict().tag(sync=True)

    def __init__(self, ritning=None, *, sida=1, titel="Grundplan"):
        super().__init__()
        self._source = b""
        self._filename = ""
        self._details = {}
        self._tags = []
        self._title = str(titel)
        self._label_size = 100
        self.schema = copy.deepcopy(allmanna_barighetsekvationen.panel_schema)
        self.background = {}
        if ritning is not None:
            path = Path(ritning)
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    raise ValueError("Ritningen får vara högst 40 MB.")
                self._set_source(path.read_bytes(), path.name, sida)
            except Exception:
                self.close()
                raise
        self._publish()
        self.on_msg(self._on_message)

    def _publish(self):
        # Never accept client state as calculation evidence.
        self.state = {
            "title": self._title,
            "tags": copy.deepcopy(self._tags),
            "label_size": self._label_size,
            "calculator_version": _CALCULATOR_VERSION,
        }

    def _set_source(self, data, filename, page=1):
        rendered = _render_source(data, filename, page)
        self._source = bytes(data)
        self._filename = Path(filename).name
        self.background = rendered

    def _tag(self, tagg):
        for tag in self._tags:
            if tag["id"] == tagg:
                return tag
        raise ValueError("Taggen finns inte.")

    def lagg_till(self, x, y, *, littera=None, typ="vaggsula", sida=None, indata=None):
        """Lägg till tagg vid relativa bildkoordinater. Returnerar taggens id."""
        if not self.background:
            raise ValueError("Öppna en ritning först.")
        if len(self._tags) >= _MAX_TAGS:
            raise ValueError(f"Projektet får innehålla högst {_MAX_TAGS} taggar.")
        for name, value in (("x", x), ("y", y)):
            if not 0 <= _number(value, name) <= 1:
                raise ValueError(f"{name} måste ligga mellan 0 och 1.")
        if typ not in ("vaggsula", "pelarsula"):
            raise ValueError("Typ måste vara vaggsula eller pelarsula.")
        page = _page_number(
            self.background["page"] if sida is None else sida, self.background["page_count"]
        )
        values = {**_DEFAULTS, "lang": 1 if typ == "vaggsula" else 0}
        values.update(indata or {})
        values = _values(values, draft=True)
        prefix = "VS" if values["lang"] == 1 else "PS"
        if littera is None:
            existing = {tag["label"] for tag in self._tags}
            n = 1
            while f"{prefix}{n}" in existing:
                n += 1
            littera = f"{prefix}{n}"
        tag = {
            "id": uuid.uuid4().hex,
            "label": _label(littera),
            "x": x, "y": y, "page": page, "values": values,
            "status": "new", "summary": None, "error": "",
        }
        self._tags.append(tag)
        self._publish()
        return tag["id"]

    def kopiera(self, tagg, x, y, *, littera=None, sida=None, indata=None):
        """Kopiera en sulas indata till en ny tagg som behöver beräknas.

        Kopian får ett eget id och nästa lediga VS-/PS-littera. Källans sida
        används om sida utelämnas; indata kan åsidosätta enskilda parametrar.
        """
        source = self._tag(tagg)
        values = copy.deepcopy(source["values"])
        if indata is not None:
            values.update(indata)
        return self.lagg_till(
            x, y, littera=littera,
            typ="vaggsula" if source["values"]["lang"] == 1 else "pelarsula",
            sida=source["page"] if sida is None else sida, indata=values,
        )

    def uppdatera(self, tagg, *, indata=None, littera=None, x=None, y=None):
        """Ändrade beräkningsindata gör taggens gamla resultat inaktuellt."""
        tag = self._tag(tagg)
        updated = copy.deepcopy(tag)
        if indata is not None:
            updated["values"] = _values({**tag["values"], **indata}, draft=True)
        if littera is not None:
            updated["label"] = _label(littera)
        for name, value in (("x", x), ("y", y)):
            if value is not None:
                if not 0 <= _number(value, name) <= 1:
                    raise ValueError(f"{name} måste ligga mellan 0 och 1.")
                updated[name] = value
        if updated["values"] != tag["values"]:
            updated.update(status="stale", summary=None, error="")
            self._details.pop(tagg, None)
        tag.update(updated)
        self._publish()

    def berakna(self, tagg):
        """Beräkna en tagg och returnera samma details-format som i an_calcs."""
        tag = self._tag(tagg)
        try:
            details, summary = _calculate(tag["values"])
        except (ValueError, ArithmeticError) as exc:
            tag.update(status="error", summary=None, error=str(exc))
            self._details.pop(tagg, None)
            self._publish()
            raise ValueError(str(exc)) from exc
        tag.update(status="calculated", summary=summary, error="")
        self._details[tagg] = details
        self._publish()
        return copy.deepcopy(details)

    def ta_bort(self, tagg):
        self._tag(tagg)
        self._tags = [tag for tag in self._tags if tag["id"] != tagg]
        self._details.pop(tagg, None)
        self._publish()

    @property
    def taggar(self):
        """Kopior av taggar, indata och aktuella resultatsammanfattningar."""
        return copy.deepcopy(self._tags)

    @property
    def resultat(self):
        """Aktuella details per tagg-id, användbara i an_print.CalcBlock."""
        return copy.deepcopy(self._details)

    @property
    def etikettstorlek(self):
        """Etiketternas grundstorlek i procent (60–180), vid 100 % ritningszoom."""
        return self._label_size

    @etikettstorlek.setter
    def etikettstorlek(self, value):
        self._label_size = _label_size(value)
        self._publish()

    def visa_sida(self, sida):
        if not self._source:
            raise ValueError("Öppna en ritning först.")
        self.background = _render_source(self._source, self._filename, sida)

    def _document(self):
        return {
            "format": _FORMAT,
            "version": 1,
            "calculator_version": _CALCULATOR_VERSION,
            "title": self._title,
            "label_size": self._label_size,
            "drawing": {
                "name": self._filename,
                "data": base64.b64encode(self._source).decode("ascii"),
                "page": self.background.get("page", 1),
            },
            "tags": [
                {**{key: copy.deepcopy(tag[key]) for key in
                    ("id", "label", "x", "y", "page", "values")},
                 "calculated": tag["status"] == "calculated"}
                for tag in self._tags
            ],
        }

    def spara(self, fil):
        """Spara ett portabelt JSON-projekt inklusive originalritningen."""
        path = Path(fil)
        data = json.dumps(self._document(), ensure_ascii=False, indent=2, allow_nan=False)
        # An interrupted write must not destroy an existing project.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    @classmethod
    def oppna(cls, fil):
        """Öppna sparat projekt; verifiera sparade resultat genom omberäkning."""
        path = Path(fil)
        if path.stat().st_size > _MAX_PROJECT_BYTES:
            raise ValueError("Projektfilen får vara högst 60 MB.")
        plan = cls()
        try:
            plan._load_document(path.read_bytes())
        except Exception:
            plan.close()
            raise
        return plan

    def _load_document(self, data):
        if len(data) > _MAX_PROJECT_BYTES:
            raise ValueError("Projektfilen får vara högst 60 MB.")
        document = json.loads(data)
        if not isinstance(document, dict) or document.get("format") != _FORMAT or document.get("version") != 1:
            raise ValueError("Filen är inte ett Grundplan-projekt av version 1.")
        label_size = _label_size(document.get("label_size", 100))
        drawing = document["drawing"]
        source = base64.b64decode(drawing["data"], validate=True)
        rendered = _render_source(source, drawing["name"], drawing["page"]) if source else {}
        tags = document["tags"]
        if not isinstance(tags, list) or len(tags) > _MAX_TAGS:
            raise ValueError("Projektet har för många eller ogiltiga taggar.")
        valid_tags, details_by_id, ids = [], {}, set()
        same_calculator = document.get("calculator_version") == _CALCULATOR_VERSION
        for saved in tags:
            ident = saved["id"]
            if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in ids:
                raise ValueError("Projektet innehåller ogiltiga eller upprepade tagg-id.")
            ids.add(ident)
            page = _page_number(saved["page"], rendered.get("page_count", 0))
            for name in ("x", "y"):
                if not 0 <= _number(saved[name], name) <= 1:
                    raise ValueError("Taggens position ligger utanför ritningen.")
            tag = {
                "id": ident, "label": _label(saved["label"]), "page": page,
                "x": saved["x"], "y": saved["y"],
                "values": _values(saved["values"], draft=True),
                "status": "stale", "summary": None, "error": "",
            }
            if saved.get("calculated") is True and same_calculator:
                try:
                    details, summary = _calculate(tag["values"])
                    tag.update(status="calculated", summary=summary)
                    details_by_id[ident] = details
                except (ValueError, ArithmeticError) as exc:
                    tag.update(status="error", error=str(exc))
            valid_tags.append(tag)
        # Replace the current project only after the entire input is validated.
        self._source = source
        self._filename = Path(drawing["name"]).name
        self._title = str(document.get("title", "Grundplan"))[:200]
        self._label_size = label_size
        self._tags = valid_tags
        self._details = details_by_id
        self.background = rendered
        self._publish()

    def _on_message(self, widget, content, buffers):
        """UI commands; files arrive as bytes, never as browser-supplied paths."""
        reply = {"request": content.get("request"), "view": content.get("view")}
        try:
            action = content["action"]
            if action == "add":
                reply["id"] = self.lagg_till(content["x"], content["y"], typ=content["kind"])
            elif action == "copy":
                reply["id"] = self.kopiera(
                    content["id"], content["x"], content["y"],
                    sida=content.get("page"), indata=content.get("values"),
                )
            elif action == "update":
                self.uppdatera(
                    content["id"], indata=content.get("values"), littera=content.get("label"),
                    x=content.get("x"), y=content.get("y"),
                )
            elif action == "calculate":
                self.uppdatera(content["id"], indata=content["values"], littera=content["label"])
                self.berakna(content["id"])
            elif action == "delete":
                self.ta_bort(content["id"])
            elif action == "page":
                self.visa_sida(content["page"])
            elif action == "label_size":
                self.etikettstorlek = content["value"]
            elif action == "drawing":
                if self._tags:
                    raise ValueError("Starta en ny Grundplan för att byta ritning när taggar finns.")
                self._set_source(bytes(buffers[0]), content["name"])
                self._publish()
            elif action == "open":
                self._load_document(bytes(buffers[0]))
            elif action == "save":
                reply["download"] = json.dumps(self._document(), ensure_ascii=False, allow_nan=False)
            else:
                raise ValueError("Okänt kommando.")
            reply["ok"] = True
        except Exception as exc:
            # Exceptions in widget callbacks otherwise disappear in kernel logs.
            reply.update(ok=False, error=str(exc) or type(exc).__name__)
        self.send(reply)
