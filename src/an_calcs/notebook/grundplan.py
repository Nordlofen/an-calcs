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

from an_calcs.geo import allmanna_barighetsekvationen, isolering_under_sula
from .grundplan_labels import DISPLAY_LABELS, LOAD_GROUPS


_ASSETS = Path(__file__).parent
_CALCULATOR_FILE = _ASSETS.parent / "geo" / "allmanna_barighetsekvationen.py"
_INSULATION_FILE = _ASSETS.parent / "geo" / "isolering_under_sula.py"
_CALCULATOR_VERSION = hashlib.sha256(
    _CALCULATOR_FILE.read_bytes() + _INSULATION_FILE.read_bytes() + b"\0grundplan:direct-moments-v1"
).hexdigest()
_FORMAT = "an-calcs-grundplan"
_DEFAULT_SUBTITLE = "Sulgrundläggning · jordens bärighet"
_MAX_FILE_BYTES = 40 * 1024 * 1024
_MAX_PROJECT_BYTES = 60 * 1024 * 1024
_MAX_TAGS = 1000
_SOIL_NAMES = allmanna_barighetsekvationen.panel_schema["px"]
# Service horizontal forces had no purpose beyond the removed lever-arm moment.
_REMOVED_FIELDS = {"l_h", "l_h_bruk", "F_hb_bruk", "F_hl_bruk"}
_NAMES = [name for name in _SOIL_NAMES if name not in _REMOVED_FIELDS]
_FIELDS = [field for field in allmanna_barighetsekvationen.panel_schema["fields"]
           if field["name"] not in _REMOVED_FIELDS]
_INSULATION_FIELDS = [field for field in isolering_under_sula.panel_schema["fields"]
                      if field["name"] not in _SOIL_NAMES and field["name"] not in _REMOVED_FIELDS]
_EXTRA_FIELDS = [
    {"name": "isolering", "type": "bool", "label": "Underliggande isolering", "unit": "", "default": False},
    {"name": "isolerprodukt", "type": "text", "label": "Isolerprodukt", "unit": "", "default": ""},
    *_INSULATION_FIELDS,
]
_FIELDS = [{**field, "label": DISPLAY_LABELS.get(field["name"], field["label"])}
           for field in [*_FIELDS, *_EXTRA_FIELDS]]
_DEFAULTS = {field["name"]: field["default"] for field in _FIELDS}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} måste vara ett ändligt tal.")
    return value


def _values(values, *, draft=False):
    if (not isinstance(values, dict) or not set(_NAMES) <= set(values)
            or set(values) - (set(_DEFAULTS) | _REMOVED_FIELDS)):
        raise ValueError("Indata måste innehålla jordberäkningens 24 fält och endast kända tilläggsfält.")
    # Old project/API fields cannot reintroduce hidden moment contributions.
    values = {**_DEFAULTS, **{name: value for name, value in values.items() if name not in _REMOVED_FIELDS}}
    if not isinstance(values["isolering"], bool):
        raise ValueError("isolering måste vara True eller False.")
    for name, value in values.items():
        if name == "isolering":
            continue
        if name == "isolerprodukt":
            if not isinstance(value, str):
                raise ValueError("Isolerprodukt måste vara en text.")
            continue
        optional = name not in _NAMES and not values["isolering"]
        if (draft or optional) and value is None and name != "lang":
            continue
        _number(value, name)
    if values["lang"] not in (0, 1):
        raise ValueError("Fundamenttyp måste vara 0 eller 1.")
    return copy.deepcopy(values)


def _label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise ValueError("Littera måste innehålla 1–80 tecken.")
    return value.strip()


def _heading_text(value, name):
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError(f"{name} måste vara en text med högst 200 tecken.")
    return value


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
    # Keep the shared calculation APIs compatible; Grundplan always supplies
    # zero lever arms so its user-entered moments act directly at the footing.
    engine_values = {**values, **dict.fromkeys(_REMOVED_FIELDS, 0.0)}
    details = allmanna_barighetsekvationen([engine_values[name] for name in _SOIL_NAMES])
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
    checks = [{"id": "jord_brott", "label": "Jord · brott", "utnyttjandegrad": utilization}]
    if values["isolering"]:
        insulation = isolering_under_sula([engine_values[name] for name in isolering_under_sula.panel_schema["px"]])
        insulation_values = {item["namn"]: item["value"] for section in ("delresultat", "slutresultat")
                             for item in insulation[section]["items"]}
        summary["isolering"] = insulation_values
        for phase in ("brott", "bruk"):
            checks.append({"id": "isolering_" + phase, "label": "Isolering · " + phase,
                           "utnyttjandegrad": insulation_values["isolering_U_" + phase]})
        for section in ("metodbeskrivning", "indata", "delresultat", "slutresultat", "ekvationer"):
            details[section]["items"].extend(insulation[section]["items"])
    governing = max(checks, key=lambda check: check["utnyttjandegrad"])
    summary.update(kontroller=checks, styrande=governing["label"],
                   utnyttjandegrad=governing["utnyttjandegrad"])
    # Plot data uses the actual calculated dimensions and preserves the signed
    # eccentricities before the bearing model takes their absolute values.
    intermediate = {item["namn"]: item["value"] for item in details["delresultat"]["items"]}
    areas = {}
    for phase in (("brott", "bruk") if values["isolering"] else ("brott",)):
        suffix = "_bruk" if phase == "bruk" else ""
        normal = summary["isolering"]["isolering_N_bruk"] if suffix else result["F_v"]
        moment_x = values["M_insp_b" + suffix]
        moment_y = values["M_insp_l" + suffix]
        dx = moment_y / normal if suffix else intermediate["e_b_last"]
        dy = moment_x / normal if suffix else intermediate["e_l_last"]
        bx = summary["isolering"]["isolering_b_eff_bruk"] if suffix else result["b_ef"]
        by = summary["isolering"]["isolering_l_eff_bruk"] if suffix else intermediate["l_ef"]
        areas[phase] = {
            "bx": values["b"], "by": intermediate["l_ref"],
            "bx_eff": bx, "by_eff": by, "area": bx * by, "V": normal,
            "Mx": moment_x, "My": moment_y,
            "ex_placement": values["e_b_plac"], "ey_placement": values["e_l_plac"],
            "ex_moment": dx, "ey_moment": dy,
            "ex": values["e_b_plac"] + dx, "ey": values["e_l_plac"] + dy,
        }
    summary["effective_area"] = areas
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

    def __init__(self, ritning=None, *, sida=1, titel="Grundplan", underrubrik=_DEFAULT_SUBTITLE):
        title = _heading_text(str(titel), "Rubrik")
        subtitle = _heading_text(str(underrubrik), "Underrubrik")
        super().__init__()
        self._source = b""
        self._filename = ""
        self._details = {}
        self._tags = []
        self._title = title
        self._subtitle = subtitle
        self._label_size = 100
        self.schema = copy.deepcopy(allmanna_barighetsekvationen.panel_schema)
        self.schema = {**self.schema, "fields": copy.deepcopy(_FIELDS), "px": list(_DEFAULTS),
                       "load_groups": copy.deepcopy(LOAD_GROUPS)}
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
            "subtitle": self._subtitle,
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
        if any(updated["values"][name] != value for name, value in tag["values"].items()
               if name != "isolerprodukt"):
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

    def _set_heading(self, title, subtitle):
        title = _heading_text(title, "Rubrik")
        subtitle = _heading_text(subtitle, "Underrubrik")
        self._title, self._subtitle = title, subtitle
        self._publish()

    @property
    def titel(self):
        """Projektets rubrik; sparas i JSON och följer med HTML-exporten."""
        return self._title

    @titel.setter
    def titel(self, value):
        self._set_heading(value, self._subtitle)

    @property
    def underrubrik(self):
        """Projektets underrubrik. Tom text döljer raden i HTML-exporten."""
        return self._subtitle

    @underrubrik.setter
    def underrubrik(self, value):
        self._set_heading(self._title, value)

    def visa_sida(self, sida):
        if not self._source:
            raise ValueError("Öppna en ritning först.")
        self.background = _render_source(self._source, self._filename, sida)

    def _document(self):
        return {
            "format": _FORMAT,
            "version": 3,
            "calculator_version": _CALCULATOR_VERSION,
            "title": self._title,
            "subtitle": self._subtitle,
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

    def _pdf_bytes(self):
        if not self._source:
            raise ValueError("Öppna en ritning först.")
        try:
            from .grundplan_pdf import render_pdf
        except ImportError as exc:
            raise ImportError("PDF-export kräver reportlab och pypdf. Uppdatera an-calcs[notebook].") from exc
        return render_pdf(self._source, self._tags, self._label_size, self._title)

    def exportera_pdf(self, fil):
        """Exportera alla ritningssidor med fasta etiketter till en PDF.

        Sparade lägen och etikettstorlek används oberoende av aktuell zoom.
        Inaktuella/ej beräknade sulor visas med status i stället för resultat.
        Projektet och beräkningarna ändras inte av exporten.
        """
        path = Path(fil)
        if path.suffix.lower() != ".pdf":
            raise ValueError("Välj ett filnamn som slutar med .pdf.")
        data = self._pdf_bytes()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    def _html_bytes(self):
        if not self._source:
            raise ValueError("Öppna en ritning först.")
        from .grundplan_html import render_html

        first = _render_source(self._source, self._filename, 1)
        pages = [first, *(_render_source(self._source, self._filename, page)
                          for page in range(2, first["page_count"] + 1))]
        return render_html({
            "state": {"title": self._title, "subtitle": self._subtitle,
                      "label_size": self._label_size, "tags": self.taggar},
            "schema": {"fields": copy.deepcopy(_FIELDS), "load_groups": copy.deepcopy(LOAD_GROUPS)},
            "pages": pages,
            "page": self.background.get("page", 1),
        })

    def exportera_html(self, fil):
        """Exportera en fristående resultatvy med öppningsbara etiketter.

        Alla ritningssidor och aktuella indata/resultat bäddas in. Filen fungerar
        utan Jupyter eller internet. Beräkningsvärdena kan inte ändras i vyn.
        Exporten räknar inte om sulor och ändrar inte projektet.
        """
        path = Path(fil)
        if path.suffix.lower() not in (".html", ".htm"):
            raise ValueError("Välj ett filnamn som slutar med .html eller .htm.")
        data = self._html_bytes()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as stream:
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
        if not isinstance(document, dict) or document.get("format") != _FORMAT or document.get("version") not in (1, 2, 3):
            raise ValueError("Filen är inte ett Grundplan-projekt av version 1, 2 eller 3.")
        label_size = _label_size(document.get("label_size", 100))
        title = str(document.get("title", "Grundplan"))[:200]
        subtitle = _heading_text(document.get("subtitle", _DEFAULT_SUBTITLE), "Underrubrik")
        drawing = document["drawing"]
        source = base64.b64decode(drawing["data"], validate=True)
        rendered = _render_source(source, drawing["name"], drawing["page"]) if source else {}
        tags = document["tags"]
        if not isinstance(tags, list) or len(tags) > _MAX_TAGS:
            raise ValueError("Projektet har för många eller ogiltiga taggar.")
        valid_tags, details_by_id, ids = [], {}, set()
        same_calculator = document["version"] == 3 and document.get("calculator_version") == _CALCULATOR_VERSION
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
        self._title = title
        self._subtitle = subtitle
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
            elif action == "heading":
                self._set_heading(content["title"], content["subtitle"])
            elif action == "drawing":
                if self._tags:
                    raise ValueError("Starta en ny Grundplan för att byta ritning när taggar finns.")
                self._set_source(bytes(buffers[0]), content["name"])
                self._publish()
            elif action == "open":
                self._load_document(bytes(buffers[0]))
            elif action == "save":
                reply["download"] = json.dumps(self._document(), ensure_ascii=False, allow_nan=False)
            elif action == "export_pdf":
                data = self._pdf_bytes()
                reply.update(ok=True, filename=Path(self._filename).stem + "_med_etiketter.pdf")
                self.send(reply, buffers=[data])
                return
            elif action == "export_html":
                data = self._html_bytes()
                reply.update(ok=True, filename=Path(self._filename).stem + "_resultat.html")
                self.send(reply, buffers=[data])
                return
            else:
                raise ValueError("Okänt kommando.")
            reply["ok"] = True
        except Exception as exc:
            # Exceptions in widget callbacks otherwise disappear in kernel logs.
            reply.update(ok=False, error=str(exc) or type(exc).__name__)
        self.send(reply)
