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
from .grundplan_labels import DISPLAY_LABELS, DISPLAY_SYMBOLS, LOAD_GROUPS
from .grundplan_text import today_text, validate_text_objects
from .grundplan_types import footing_type, infer_type, validate_model
from .grundplan_placement import object_key, validate_objects
from .grundplan_objects import drawing_layout, object_layout, scale_value, reorder
from .grundplan_canvas import DEFAULT_BOUNDS, COORDINATE_BOUNDS, validate_bounds, valid_coordinate, placement_bounds
from .grundplan_reference import (DEFAULT_SETTINGS as DEFAULT_REFERENCE,
    validate_settings as validate_reference, group_data as reference_groups)
from .grundplan_leaders import validate_leader
from .grundplan_loads import (read_loads, line_loads, bearing_load_length, load_resultants,
                             MAX_BYTES as _MAX_LOAD_BYTES)
from .grundplan_sliding import (FIELDS as SLIDING_FIELDS, NAMES as SLIDING_NAMES,
                               DEFAULT_SETTINGS, DEFAULT_PLACEMENT, contribution, project_results, validate_settings)
from .grundplan_colour import DEFAULT_SETTINGS as DEFAULT_COLOUR, validate_settings as validate_colour, remember_styles
from .grundplan_history import History, history_command


_ASSETS = Path(__file__).parent
_CALCULATOR_FILE = _ASSETS.parent / "geo" / "allmanna_barighetsekvationen.py"
_INSULATION_FILE = _ASSETS.parent / "geo" / "isolering_under_sula.py"
_CALCULATOR_VERSION = hashlib.sha256(
    _CALCULATOR_FILE.read_bytes() + _INSULATION_FILE.read_bytes() + b"\0grundplan:independent-load-type-v7"
).hexdigest()
_FORMAT = "an-calcs-grundplan"
_STATE_FORMAT = "an-calcs-grundplan-state"
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
    {"name": "inaktiv", "type": "bool", "label": "Inaktiv", "unit": "", "default": False},
    {"name": "lasttyp", "type": "choice", "label": "Last anges som", "unit": "", "default": 0,
     "options": [{"value": 1, "label": "Linjelast [kN/m]"}, {"value": 0, "label": "Punktlast [kN]"}]},
    {"name": "endast_h_stabilitet", "type": "bool", "label": "Endast H-stabilitet", "unit": "", "default": False},
    {"name": "l_override", "type": "bool", "label": "Egen längd", "unit": "", "default": False},
    {"name": "L_vagg_minst_1", "type": "bool", "label": "Minst 1 m", "unit": "", "default": True},
    {"name": "L_vagg", "type": "number", "label": "Längd linjestöd alt. längd ovanliggande vägg", "unit": "m", "default": None,
     "display_symbol": {"base": "L", "subscript": "vägg"}},
    {"name": "isolering", "type": "bool", "label": "Underliggande isolering", "unit": "", "default": False},
    {"name": "isolerprodukt", "type": "text", "label": "Isolerprodukt", "unit": "", "default": ""},
    *_INSULATION_FIELDS,
    *SLIDING_FIELDS,
    {"name": "kommentar", "type": "text", "multiline": True, "label": "Kommentar", "unit": "", "default": ""},
]
_FIELDS = [{**field, "label": DISPLAY_LABELS.get(field["name"], field["label"]),
            "display_symbol": DISPLAY_SYMBOLS.get(field["name"], field.get("display_symbol"))}
           for field in [*_FIELDS, *_EXTRA_FIELDS]]
_FIELDS = [{**field, "label": "Beräkningsmodell"} if field["name"] == "lang" else field for field in _FIELDS]
_DEFAULTS = {field["name"]: field["default"] for field in _FIELDS}
_TEXT_NAMES = {field["name"] for field in _FIELDS if field["type"] == "text"}
_TABLE_DEFAULTS = {"collapsed": [], "sort": {"key": None, "direction": "ascending"}}
_LAYOUT_DEFAULTS = {"board_height": None, "table_height": None, "board_width": None, "table_width": None}
_LAYOUT_LIMITS = {"board_height": (280, 2400), "table_height": (160, 1800), "board_width": (320, 4000), "table_width": (320, 4000)}
_TABLE_GROUPS = {"lang", "F_vy", "F_vy_bruk", "c_prime", "isolering", "glid_x", "kommentar"}
_INSULATION_WIDGET_DEFAULTS = {"enabled": False, "x": .65, "y": .55, "size": 300}
_COMMENT_WIDGET_DEFAULTS = {"enabled": False, "x": .08, "y": .55, "size": 410}
# These fields have different meanings/units for strips and pads.
_BULK_SAME_TYPE = {"l", "l_override", "L_vagg", "L_vagg_minst_1", "glid_L", "V_Ed_EQU", "F_vy", "F_hb", "F_hl",
                   "M_insp_l", "M_insp_b", "F_vy_bruk", "M_insp_l_bruk", "M_insp_b_bruk", "lasttyp"}
_BULK_LOAD_FIELDS = {"V_Ed_EQU", "F_vy", "F_hb", "F_hl", "M_insp_l", "M_insp_b",
                     "F_vy_bruk", "M_insp_l_bruk", "M_insp_b_bruk", "L_vagg", "glid_L"}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} måste vara ett ändligt tal.")
    return value


def _values(values, *, draft=False):
    if (not isinstance(values, dict) or not set(_NAMES) <= set(values)
            or set(values) - (set(_DEFAULTS) | _REMOVED_FIELDS)):
        raise ValueError("Indata måste innehålla jordberäkningens 24 fält och endast kända tilläggsfält.")
    # Older projects and direct Python inputs infer the local check from the
    # full support length. The full length remains available to global sliding.
    if "L_vagg_minst_1" not in values:
        length = values.get("L_vagg")
        values = {**values, "L_vagg_minst_1": length is None or _number(length, "L_vägg") >= 1}
    if "lasttyp" not in values:
        values = {**values, "lasttyp": 1 if values["lang"] == 1 else 0}
    # Old project/API fields cannot reintroduce hidden moment contributions.
    values = {**_DEFAULTS, **{name: value for name, value in values.items() if name not in _REMOVED_FIELDS}}
    boolean_names = {"isolering", "glid_x", "glid_y", "l_override", "L_vagg_minst_1", "endast_h_stabilitet", "inaktiv"}
    for name in boolean_names:
        if not isinstance(values[name], bool):
            raise ValueError(f"{name} måste vara True eller False.")
    if values["endast_h_stabilitet"]:
        # The mode represents an uninsulated sliding support. Enforce this for
        # creation, updates, copies and older saved projects alike.
        values["isolering"] = False
    for name, value in values.items():
        if name in boolean_names:
            continue
        if name in _TEXT_NAMES:
            if not isinstance(value, str):
                raise ValueError(f"{name} måste vara en text.")
            continue
        optional = name not in _NAMES and not values["isolering"]
        if (draft or values["inaktiv"] or values["endast_h_stabilitet"] or optional or name in SLIDING_NAMES or name == "L_vagg") and value is None and name not in {"lang", "lasttyp"}:
            continue
        _number(value, name)
    if values["lang"] not in (0, 1):
        raise ValueError("Fundamenttyp måste vara 0 eller 1.")
    if values["lasttyp"] not in (0, 1):
        raise ValueError("Lasttyp måste vara 0 (punktlast) eller 1 (linjelast).")
    if values["lang"] == 1:
        values["lasttyp"] = 1
    if values["lang"] == 1 and not values["l_override"]:
        values["l"] = 1.0
    return copy.deepcopy(values)


def _table_view(value):
    if not isinstance(value, dict) or set(value) - set(_TABLE_DEFAULTS):
        raise ValueError("Ogiltiga visningsval för tabellen.")
    result = {**copy.deepcopy(_TABLE_DEFAULTS), **copy.deepcopy(value)}
    collapsed, sort = result["collapsed"], result["sort"]
    if (not isinstance(collapsed, list) or any(not isinstance(key, str) or key not in _TABLE_GROUPS for key in collapsed)
            or len(set(collapsed)) != len(collapsed)):
        raise ValueError("Okänd tabellkategori.")
    if (not isinstance(sort, dict) or set(sort) != {"key", "direction"}
            or sort["key"] is not None and (not isinstance(sort["key"], str) or sort["key"] not in {*_DEFAULTS, "label", "status", "V_res_brott", "V_res_bruk"})
            or sort["direction"] not in ("ascending", "descending")):
        raise ValueError("Ogiltig tabellsortering.")
    return result


def _layout(value):
    if not isinstance(value, dict) or set(value) - set(_LAYOUT_DEFAULTS):
        raise ValueError("Ogiltiga storleksinställningar.")
    result = {**_LAYOUT_DEFAULTS, **value}
    for name, (low, high) in _LAYOUT_LIMITS.items():
        if result[name] is not None and not low <= _number(result[name], name) <= high:
            raise ValueError(f"{name} ska vara {low}–{high} px.")
    return result


def _insulation_widget(value, *, coordinate_bounds=DEFAULT_BOUNDS):
    if not isinstance(value, dict) or set(value) - set(_INSULATION_WIDGET_DEFAULTS):
        raise ValueError("Ogiltiga inställningar för isoleringswidgeten.")
    result = {**_INSULATION_WIDGET_DEFAULTS, **value}
    if type(result["enabled"]) is not bool:
        raise ValueError("enabled måste vara True eller False.")
    for axis in ("x", "y"):
        if not valid_coordinate(result[axis], axis, coordinate_bounds):
            raise ValueError("Widgetens placering ska vara inom ritningen.")
    if not 150 <= _number(result["size"], "size") <= 900:
        raise ValueError("Widgetens storlek ska vara 150–900.")
    return copy.deepcopy(result)


def _comment_widget(value, *, coordinate_bounds=DEFAULT_BOUNDS):
    if not isinstance(value, dict) or set(value) - set(_COMMENT_WIDGET_DEFAULTS):
        raise ValueError("Ogiltiga inställningar för kommentarwidgeten.")
    result = {**_COMMENT_WIDGET_DEFAULTS, **value}
    if type(result["enabled"]) is not bool:
        raise ValueError("enabled måste vara True eller False.")
    for axis in ("x", "y"):
        if not valid_coordinate(result[axis], axis, coordinate_bounds):
            raise ValueError("Widgetens placering ska vara inom ritningen.")
    if not 205 <= _number(result["size"], "size") <= 1230:
        raise ValueError("Widgetens storlek ska vara 205–1230.")
    return copy.deepcopy(result)


def _updated_values(current, updates):
    if current.get("inaktiv") and updates.get("inaktiv") is not False:
        if any(name not in {"inaktiv", "kommentar"} and value != current.get(name) for name, value in updates.items()):
            raise ValueError("Sulan är inaktiv. Endast kommentaren kan ändras; avmarkera Inaktiv för att ändra indata.")
    # Explicit Python length updates keep their existing meaning. The UI sends
    # the checkbox too, so unchecking it always restores the standard strip.
    values = {**current, **updates}
    if values["lang"] == 1 and "l" in updates and "l_override" not in updates:
        values["l_override"] = updates["l"] != 1
    if "L_vagg" in updates and "L_vagg_minst_1" not in updates:
        length = updates["L_vagg"]
        values["L_vagg_minst_1"] = length is None or _number(length, "L_vägg") >= 1
    return _values(values, draft=True)


def _label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise ValueError("Littera måste innehålla 1–80 tecken.")
    return value.strip()


def _storage_settings(key, state_file):
    key = _heading_text(str(key).strip(), "Key")
    if not key:
        raise ValueError("Key får inte vara tom.")
    argument = str(state_file).strip() if state_file is not None else ""
    if not argument:
        raise ValueError("Ange state_file för projektet.")
    if not Path(argument).suffix:
        argument += ".json"
    path = Path(argument).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("State-filen måste sluta med .json.")
    return key, path, argument


def _heading_text(value, name, *, max_length=200):
    if not isinstance(value, str):
        raise ValueError(f"{name} måste vara en text.")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{name} måste vara en text med högst {max_length} tecken.")
    return value


def _page_number(page, count):
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= count:
        raise ValueError(f"Sida måste vara ett heltal mellan 1 och {count}.")
    return page


def _label_size(value):
    if not 20 <= _number(value, "Etikettstorlek") <= 180:
        raise ValueError("Etikettstorlek måste ligga mellan 20 och 180 procent.")
    return value


def _calibration(value, background):
    if value is None:
        return None
    if not background:
        raise ValueError("Öppna en ritning före kalibrering.")
    if not isinstance(value, dict):
        raise ValueError("Kalibreringen måste innehålla två punkter och ett referensmått.")
    points = []
    for name in ("start", "end"):
        point = value.get(name)
        if not isinstance(point, dict):
            raise ValueError("Kalibreringen måste innehålla två punkter.")
        coords = {axis: _number(point.get(axis), "Kalibreringspunkt") for axis in ("x", "y")}
        if any(not valid_coordinate(coord, axis, COORDINATE_BOUNDS) for axis, coord in coords.items()):
            raise ValueError("Kalibreringspunkten ligger utanför ritningen.")
        points.append(coords)
    length = _number(value.get("length_m"), "Referensmått")
    distance = math.hypot((points[1]["x"] - points[0]["x"]) * background["width"],
                          (points[1]["y"] - points[0]["y"]) * background["height"])
    if length <= 0 or distance < 1e-6 or not math.isfinite(length / distance):
        raise ValueError("Ange ett positivt referensmått mellan två olika punkter.")
    return {"start": points[0], "end": points[1], "length_m": length}


def _render_source(data, filename, page=1, *, fallback_page=False):
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
            if fallback_page and page > count:
                page = 1
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
        if fallback_page and page > 1:
            page = 1
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
        width, height = img.width * .75, img.height * .75
        img.thumbnail((2800, 2800))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return {
        "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
        "width": img.width,
        "width_pt": width, "height_pt": height,
        "height": img.height,
        "name": Path(filename).name,
        "page": page,
        "page_count": count,
    }


def _inactive_result():
    return {"inaktiv": True, "kontroller": []}, {"inaktiv": True, "utnyttjandegrad": None, "kontroller": []}


def _calculate(values):
    values = _values(values)
    if values["inaktiv"]:
        return _inactive_result()
    if values["endast_h_stabilitet"]:
        # No bearing engine or insulation check applies to this footing. Its
        # sliding contribution is calculated separately from explicit EQU data.
        return {"endast_h_stabilitet": True, "kontroller": []}, {
            "endast_h_stabilitet": True, "utnyttjandegrad": None,
            "b": values["b"], "kontroller": [],
        }
    # Keep the shared calculation APIs compatible; Grundplan always supplies
    # zero lever arms so its user-entered moments act directly at the footing.
    engine_values = {**values, **dict.fromkeys(_REMOVED_FIELDS, 0.0)}
    support_length = bearing_load_length(values)
    if support_length is not None:
        if values["lang"] == 1 and values["l"] <= 0:
            raise ValueError("Sulmått b_y måste vara större än noll.")
        # Only the local support length determines the external resultant.
        # b_y spreads that same resultant over the footing contact area; the
        # division merely adapts it to the shared engines' per-metre API.
        factor = support_length / (values["l"] if values["lang"] == 1 else 1)
        for group in LOAD_GROUPS:
            for field in group["fields"]:
                name = field["name"]
                if engine_values[name] is not None:
                    engine_values[name] = _number(engine_values[name] * factor, name)
    options = {"remslangd": values["l"]} if values["lang"] == 1 and values["l"] != 1 else {}
    details = allmanna_barighetsekvationen([engine_values[name] for name in _SOIL_NAMES], **options)
    result = {item["namn"]: item["value"] for item in details["slutresultat"]["items"]}
    for section in ("indata", "delresultat", "slutresultat"):
        for item in details[section]["items"]:
            _number(item["value"], item["namn"])
    if result["F_bd"] <= 0:
        raise ValueError("Beräknad bärförmåga är inte positiv. Kontrollera indata.")
    # Strip forces remain per metre; l is its selected geometric reference length.
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
        insulation = isolering_under_sula([engine_values[name] for name in isolering_under_sula.panel_schema["px"]], **options)
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
        moment_x = engine_values["M_insp_b" + suffix]
        moment_y = engine_values["M_insp_l" + suffix]
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
    if support_length is not None:
        by = values["l"]
        to_total = by if values["lang"] == 1 else 1
        summary.update(last=_number(summary["last"] * to_total, "Total vertikallast"),
                       barformaga=_number(summary["barformaga"] * to_total, "Total bärförmåga"),
                       lastenhet="kN", load_conversion={"support_length": support_length, "by": by,
                       "full_support_length": values["L_vagg"], "at_least_one": values["lang"] == 1 and values["L_vagg_minst_1"],
                       "brott": _number(values["F_vy"] * support_length, "Yttre last, brott"),
                       "bruk": None if values["F_vy_bruk"] is None else
                       _number(values["F_vy_bruk"] * support_length, "Yttre last, bruk")})
        for area in areas.values():
            for name in ("V", "Mx", "My"):
                area[name] = _number(area[name] * to_total, name)
        if "isolering" in summary:
            for name in ("isolering_EG_k", "isolering_N_brott", "isolering_N_bruk"):
                summary["isolering"][name] = _number(summary["isolering"][name] * to_total, name)
        details["metodbeskrivning"]["items"].append({"rubrik": "Linjestöd och sula", "text": (
            "Pelarsulemodellen: alla yttre linjelaster och moment per meter multipliceras med hela angivna L_vägg. "
            "b_x och b_y anger sulans kontaktmått och ändrar inte den yttre lastresultanten. "
            "Sulans egentyngd beräknas separat från geometrin. Rapporten visar totala krafter och moment."
        ) if values["lang"] == 0 else (
            "Laster och moment per meter linjestöd multipliceras med 1 m när Minst 1 m är aktiverad, "
            "annars med angiven kort L_vägg. b_y anger fördelningslängden under sulan och ändrar inte "
            "den yttre lastresultanten. För den befintliga väggsulemodellens API divideras resultantlasterna "
            "med b_y. Egentyngden baseras på sulans geometri. Global glidning använder separat V_Ed,EQU och L_su. "
            "Grundplans sammanfattning och areaskiss visar totala krafter och moment; "
            "den gemensamma beräkningsmotorns rapport använder ekvivalenta värden per meter sula."
        )})
    area = areas["brott"]
    summary["q_Ed"] = _number(area["V"] / area["area"], "Lasteffekt q_Ed")
    return details, summary


class Grundplan(anywidget.AnyWidget):
    """Visa PDF/bild med individuella sulberäkningar direkt i en notebook.

    Exempel:
        from an_calcs.notebook import Grundplan
        plan = Grundplan("Hus A")  # Återställ lokalt sparat projekt med denna key.
        plan

    Koordinater för taggar är relativa originalritningen, med origo uppe
    till vänster. Originalramen är 0–1; tillagda marginaler kan ligga utanför.
    Mått och laster anges manuellt. Varje väggsula beräknas per
    meter; ritningslängden används inte för att fördela en total last.
    """

    _esm = _ASSETS / "grundplan.js"
    _css = _ASSETS / "grundplan.css"
    schema = traitlets.Dict().tag(sync=True)
    state = traitlets.Dict().tag(sync=True)
    background = traitlets.Dict().tag(sync=True)
    STATE_FILENAME = ".an_calcs_grundplan_state.json"
    _STATE_FILE = None

    def __init__(self, ritning=None, *, key=None, state_file=None, sida=1, titel="Grundplan", underrubrik=_DEFAULT_SUBTITLE):
        if isinstance(sida, bool) or not isinstance(sida, int) or sida < 1:
            raise ValueError("Sida måste vara ett positivt heltal.")
        self._initial_page = sida
        # Preserve existing drawing paths; a plain positional name is a project key.
        if key is None and isinstance(ritning, str) and not Path(ritning).suffix and not any(c in ritning for c in "/\\"):
            key, ritning = ritning, None
        self._key = self._state_file = self._state_file_argument = None
        if state_file is not None and key is None:
            raise ValueError("Ange key när du använder state_file.")
        if key is not None:
            self._key, self._state_file, self._state_file_argument = _storage_settings(
                key, state_file if state_file is not None else self._STATE_FILE or self.STATE_FILENAME)
        title = _heading_text(str(titel), "Rubrik")
        subtitle = _heading_text(str(underrubrik), "Underrubrik", max_length=None)
        super().__init__()
        self._source = b""
        self._filename = ""
        self._details = {}
        self._tags = []
        self._load_import = None
        self._title = title
        self._subtitle = subtitle
        self._label_size = 100
        self._calibration = None
        self._gliding = copy.deepcopy(DEFAULT_SETTINGS)
        self._colour = copy.deepcopy(DEFAULT_COLOUR)
        self._table_view = copy.deepcopy(_TABLE_DEFAULTS)
        self._layout = copy.deepcopy(_LAYOUT_DEFAULTS)
        self._insulation_widget = copy.deepcopy(_INSULATION_WIDGET_DEFAULTS)
        self._comment_widget = copy.deepcopy(_COMMENT_WIDGET_DEFAULTS)
        self._reference_widget = copy.deepcopy(DEFAULT_REFERENCE)
        self._text_objects = []
        self._placement_locks = {}
        self._canvas_bounds = dict(DEFAULT_BOUNDS)
        self._drawing_layout = drawing_layout({}, {})
        self._drawing_preview = None
        self._object_layout = {"scales": {}, "order": []}
        self._history = History()
        self.schema = copy.deepcopy(allmanna_barighetsekvationen.panel_schema)
        self.schema = {**self.schema, "fields": copy.deepcopy(_FIELDS), "px": list(_DEFAULTS),
                       "load_groups": copy.deepcopy(LOAD_GROUPS),
                       "bulk_same_type": sorted(_BULK_SAME_TYPE)}
        self.background = {}
        try:
            projects = self._read_state_file()["projects"] if self._key is not None else {}
            if self._key in projects:
                self._load_document(json.dumps(projects[self._key], ensure_ascii=False, allow_nan=False).encode("utf-8"))
            elif ritning is not None:
                path = Path(ritning)
                if path.stat().st_size > _MAX_FILE_BYTES:
                    raise ValueError("Ritningen får vara högst 40 MB.")
                self._set_source(path.read_bytes(), path.name, sida)
        except Exception:
            self.close()
            raise
        self._publish()
        self.on_msg(self._on_message)

    @classmethod
    def configure_state_file(cls, state_file):
        """Välj defaultfil för efterföljande Grundplan(key), som i Panel.

        Relativa sökvägar avser kernelns arbetsmapp. None återställer standardfilen.
        """
        cls._STATE_FILE = state_file

    @property
    def key(self):
        """Nyckeln för det lokalt sparade projektet, eller None i portabelt läge."""
        return self._key

    @property
    def state_file(self):
        """Lokal JSON-fil för nyckelstyrd lagring. Sökvägen binds när vyn skapas."""
        return self._state_file

    def _read_state_file(self, path=None):
        path = path if path is not None else self._state_file
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"format": _STATE_FORMAT, "version": 1, "projects": {}}
        except json.JSONDecodeError as exc:
            raise ValueError(f"State-filen innehåller ogiltig JSON: {path}") from exc
        if (not isinstance(state, dict) or state.get("format") != _STATE_FORMAT
                or state.get("version") != 1 or not isinstance(state.get("projects"), dict)):
            raise ValueError(f"Filen är inte en Grundplan-state-fil: {path}")
        return state

    def _storage(self):
        if self._key is None:
            return None
        return {"key": self._key, "path": str(self._state_file), "name": self._state_file.name,
                "state_file": self._state_file_argument,
                "arguments": f"state_file={self._state_file_argument!r}, key={self._key!r}"}

    def _save_as(self, key, state_file, *, overwrite=False):
        key, path, argument = _storage_settings(key, state_file)
        state = self._read_state_file(path)
        if (key, path) != (self._key, self._state_file) and key in state["projects"] and not overwrite:
            return False
        state["projects"][key] = self._document()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(path, state)
        # Only bind the new destination after a successful write.
        self._key, self._state_file, self._state_file_argument = key, path, argument
        self._publish()
        return True

    def _save_choices(self):
        folder = Path.cwd().resolve()
        paths = set(folder.glob("*.json"))
        if self._state_file is not None:
            paths.add(self._state_file)
        choices = []
        for path in sorted(paths):
            try:
                if not path.is_file():
                    continue
                state = self._read_state_file(path)
            except (OSError, ValueError, UnicodeError):
                continue
            try:
                argument = str(path.relative_to(folder))
            except ValueError:
                argument = str(path)
            if path == self._state_file:
                argument = self._state_file_argument
            choices.append({"state_file": argument, "path": str(path), "name": path.name,
                            "keys": sorted(key for key in state["projects"] if isinstance(key, str) and key)})
        return choices

    def _publish(self):
        self._object_layout = object_layout(self._object_layout, self._tags, self._text_objects, self.background.get("page"), prune=True)
        # Never accept client state as calculation evidence.
        if self._colour["enabled"]:
            self._colour = remember_styles(self._tags, self._colour)
        self._history.observe(self)
        state = {
            "history": self._history.state,
            "title": self._title,
            "subtitle": self._subtitle,
            "tags": self.taggar,
            "label_size": self._label_size,
            "calibration": self.kalibrering,
            "sliding": copy.deepcopy(self._gliding),
            "sliding_result": self.glidningsresultat,
            "colour_grouping": self.farggruppering,
            "table_view": self.tabellvy,
            "layout": self.visningsstorlekar,
            "insulation_widget": self.isoleringswidget,
            "comment_widget": self.kommentarwidget,
            "reference_widget": self.referens,
            "reference_data": self.referensgrupper,
            "text_objects": self.textobjekt,
            "placement_locks": self.placeringslas,
            "canvas_bounds": self.ritningsram,
            "drawing_layout": self.ritningsunderlag,
            "object_layout": self.objektlayout,
            "calculator_version": _CALCULATOR_VERSION,
            "storage": self._storage(),
            "load_import": self.lasteffekt_import,
        }
        if self._history.in_command:
            self._history.pending_state = state
        else:
            self.state = state

    def _set_source(self, data, filename, page=None):
        # Validate/render first; a failed replacement must leave the project intact.
        rendered = _render_source(data, filename, self._initial_page if page is None else page,
                                  fallback_page=page is None and bool(self.background))
        previous_page = self.background.get("page")
        layout = drawing_layout(self._drawing_layout if self.background else {}, rendered)
        placements = self._gliding["placements"].get(str(self.background.get("page")), {})
        self._gliding["placements"] = {str(rendered["page"]): placements} if placements else {}
        for tag in self._tags:
            tag["page"] = rendered["page"]
        self._placement_locks = {
            object_key(updated): updated for item in self._placement_locks.values()
            for updated in [{**item, "page": rendered["page"]} if item["type"] == "overlay" else item]}
        self._drawing_preview = None
        self._source = bytes(data)
        self._filename = Path(filename).name
        self._calibration = None
        self._drawing_layout = layout
        self._object_layout = {"scales": {key.replace(f"overlay:{previous_page}:", f"overlay:{rendered['page']}:", 1): value for key, value in self._object_layout["scales"].items()},
                               "order": [key.replace(f"overlay:{previous_page}:", f"overlay:{rendered['page']}:", 1) for key in self._object_layout["order"]]}
        self.background = self._drawing_background(rendered, layout)
        self._initial_page = rendered["page"]

    def importera_ritning(self, fil, *, sida=None):
        """Importera eller ersätt ritningen; behåll sulor och relativa placeringar.

        Mätkalibreringen återställs. Utan sida används den tidigare sidan om
        den finns, annars sida 1. Beräkningar och eventuell placeringskö behålls.
        """
        path = Path(fil)
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError("Ritningen får vara högst 40 MB.")
        self._set_source(path.read_bytes(), path.name, sida)
        self._publish()

    def _view_page(self, sida=None):
        if not self.background:
            raise ValueError("Öppna en ritning först.")
        page = _page_number(self.background["page"] if sida is None else sida,
                            self.background["page_count"])
        if page != self.background["page"]:
            raise ValueError(f"Varje Grundplan gäller en enda ritningssida. Öppna den andra sidan i en ny cell med egen key och sida={page}.")
        return page

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
            if not valid_coordinate(value, name, placement_bounds(self._canvas_bounds)):
                raise ValueError(f"{name} måste ligga inom ritningsytan.")
        if typ not in ("vaggsula", "pelarsula"):
            raise ValueError("Typ måste vara vaggsula eller pelarsula.")
        page = self._view_page(sida)
        values = {**_DEFAULTS, "lang": 1 if typ == "vaggsula" else 0}
        values.update(indata or {})
        if "lasttyp" not in (indata or {}):
            values["lasttyp"] = 1 if values["lang"] == 1 else 0
        if values["lang"] == 1 and "l" not in (indata or {}):
            values["l"] = 1.0
        values = _updated_values(values, indata or {})
        validate_model(typ, values)
        prefix = "VS" if typ == "vaggsula" else "PS"
        if littera is None:
            existing = {tag["label"] for tag in self._tags}
            n = 1
            while f"{prefix}{n}" in existing:
                n += 1
            littera = f"{prefix}{n}"
        tag = {
            "id": uuid.uuid4().hex,
            "label": _label(littera),
            "x": x, "y": y, "page": page, "values": values, "footing_type": typ,
            "status": "new", "summary": None, "error": "",
        }
        self._tags.append(tag)
        self._refresh_tag(tag)
        self._publish()
        return tag["id"]

    def kopiera(self, tagg, x, y, *, littera=None, sida=None, indata=None):
        """Kopiera en sulas indata till en ny tagg och beräkna den automatiskt.

        Kopian får ett eget id och nästa lediga VS-/PS-littera. Källans sida
        används om sida utelämnas; indata kan åsidosätta enskilda parametrar.
        """
        source = self._tag(tagg)
        values = copy.deepcopy(source["values"])
        if indata is not None:
            values = _updated_values(values, indata)
        ident = self.lagg_till(
            x, y, littera=littera,
            typ=footing_type(source),
            sida=source["page"] if sida is None else sida, indata=values,
        )
        if source.get("footing_type_inferred"):
            self._tag(ident)["footing_type_inferred"] = True
            self._publish()
        if "imported_length" in source:
            self._tag(ident)["imported_length"] = source["imported_length"]
            self._publish()
        return ident

    @property
    def lasteffekt_import(self):
        """Tillfällig placeringskö; endast placerade sulor sparas i projektet."""
        queue = self._load_import
        if queue is None:
            return None
        return {"token": queue["token"], "filename": queue["filename"],
                "index": queue["index"], "total": len(queue["items"]), "paused": queue["paused"],
                "next": copy.deepcopy(queue["items"][queue["index"]])}

    def importera_lasteffekt(self, fil):
        """Uppdatera matchande littera och köa nya stöd för manuell placering."""
        path = Path(fil)
        if path.stat().st_size > _MAX_LOAD_BYTES:
            raise ValueError("Lasteffektfilen får vara högst 5 MB.")
        self._start_load_import(path.read_bytes(), path.name)
        return self.lasteffekt_import

    def _start_load_import(self, data, filename):
        if not self.background:
            raise ValueError("Öppna en ritning innan du importerar lasteffekter.")
        if self._load_import is not None:
            raise ValueError("Slutför eller avbryt den pågående lasteffektimporten först.")
        items = read_loads(data, existing_labels=(tag["label"] for tag in self._tags),
                           available=_MAX_TAGS - len(self._tags))
        by_label = {}
        for tag in self._tags:
            by_label.setdefault(tag["label"], []).append(tag)
        prepared, new_items, skipped_inactive = [], [], []
        # Validate the entire update before changing any footing or starting placement.
        for item in items:
            matches = by_label.get(item["label"], [])
            if not matches:
                new_items.append(item)
                continue
            if len(matches) != 1:
                raise ValueError(f"Littera {item['label']} matchar flera sulor. Ge dem unika littera före uppdatering.")
            tag = matches[0]
            if tag["values"]["inaktiv"]:
                skipped_inactive.append(tag["id"])
                continue
            kind = "vaggsula" if line_loads(tag["values"]) else "pelarsula"
            if kind != item["kind"]:
                raise ValueError(f"{item['label']}: sultypen/lasttypen i filen skiljer sig från den befintliga lasttypen. Kontrollera littera och lasttyp.")
            updates = dict(item["values"])
            if kind == "vaggsula" and tag["values"]["glid_L"] is not None:
                if tag["values"]["glid_L"] != tag.get("imported_length"):
                    updates.pop("glid_L")
            values = _values({**tag["values"], **updates}, draft=True)
            prepared.append((tag, values, item["values"].get("L_vagg")))
        queue = ({"token": uuid.uuid4().hex, "filename": Path(filename).name,
                  "items": new_items, "index": 0, "paused": False} if new_items else None)
        for tag, values, imported_length in prepared:
            changed = any(values[name] != value for name, value in tag["values"].items()
                          if name not in _TEXT_NAMES and name not in SLIDING_NAMES)
            tag["values"] = values
            if imported_length is not None:
                tag["imported_length"] = imported_length
            if changed:
                tag.update(status="stale", summary=None, error="")
                self._details.pop(tag["id"], None)
            if changed or tag["summary"] is None:
                self._refresh_tag(tag)
        self._load_import = queue
        self._publish()
        return {"updated": len(prepared), "new": len(new_items),
                **({"skipped_inactive": len(skipped_inactive)} if skipped_inactive else {}),
                "updated_ids": [tag["id"] for tag, _, _ in prepared]}

    def _control_load_import(self, token, operation):
        if self._load_import is None or token != self._load_import["token"]:
            raise ValueError("Placeringskön är inte längre aktuell.")
        if operation == "cancel":
            self._load_import = None
        elif operation in ("pause", "resume"):
            self._load_import["paused"] = operation == "pause"
        else:
            raise ValueError("Okänd importåtgärd.")
        self._publish()

    def placera_lasteffekt(self, x, y, *, sida=None):
        """Placera nästa importerade stöd. Returnerar den nya sulans id."""
        return self._place_load_import(x, y, sida=sida)["id"]

    def _place_load_import(self, x, y, *, sida=None, token=None, index=None):
        queue = self._load_import
        if (queue is None or (token is not None and token != queue["token"])
                or (index is not None and (type(index) is not int or index != queue["index"]))):
            raise ValueError("Placeringskön har ändrats. Placera det stöd som visas nu.")
        if queue["paused"]:
            raise ValueError("Placeringen är pausad. Tryck Fortsätt placera.")
        item = queue["items"][queue["index"]]
        if any(tag["label"] == item["label"] for tag in self._tags):
            raise ValueError(f"Littera {item['label']} finns redan. Byt littera på den befintliga sulan innan du fortsätter.")
        ident = self.lagg_till(x, y, littera=item["label"], typ=item["kind"], sida=sida, indata=item["values"])
        if item["kind"] == "vaggsula":
            self._tag(ident)["imported_length"] = item["values"]["L_vagg"]
        queue["index"] += 1
        finished = queue["index"] == len(queue["items"])
        if finished:
            self._load_import = None
        self._publish()
        return {"id": ident, "label": item["label"], "finished": finished, "total": len(queue["items"])}

    def uppdatera(self, tagg, *, indata=None, littera=None, x=None, y=None):
        """Uppdatera indata och beräkna automatiskt; ogiltiga indata visas som fel."""
        tag = self._tag(tagg)
        updated = copy.deepcopy(tag)
        if indata is not None:
            updated["values"] = _updated_values(tag["values"], indata)
            validate_model(footing_type(tag), updated["values"])
        if littera is not None:
            updated["label"] = _label(littera)
            if updated["values"]["inaktiv"] and updated["label"] != tag["label"]:
                raise ValueError("Sulan är inaktiv. Endast kommentaren kan ändras; avmarkera Inaktiv för att ändra littera.")
        for name, value in (("x", x), ("y", y)):
            if value is not None:
                if value != tag[name]:
                    self._assert_placement_unlocked({"type": "tag", "id": tagg})
                if not valid_coordinate(value, name, placement_bounds(self._canvas_bounds, tag)):
                    raise ValueError(f"{name} måste ligga inom ritningsytan.")
                updated[name] = value
        changed = any(updated["values"][name] != value for name, value in tag["values"].items()
                      if name not in _TEXT_NAMES and name not in SLIDING_NAMES)
        if changed:
            updated.update(status="stale", summary=None, error="")
            self._details.pop(tagg, None)
        tag.update(updated)
        if changed or tag["summary"] is None:
            self._refresh_tag(tag)
        self._publish()

    def flytta_flera(self, placeringar):
        """Flytta etiketter atomärt utan att ändra indata eller beräkna om."""
        if not isinstance(placeringar, list) or not 1 <= len(placeringar) <= _MAX_TAGS:
            raise ValueError("Ange minst en giltig etikettplacering.")
        validated, ids = [], set()
        for position in placeringar:
            if not isinstance(position, dict) or set(position) != {"id", "x", "y"}:
                raise ValueError("Ogiltig etikettplacering.")
            ident = position["id"]
            if not isinstance(ident, str) or ident in ids:
                raise ValueError("Etiketternas id måste vara unika.")
            ids.add(ident)
            tag = self._tag(ident)
            self._assert_placement_unlocked({"type": "tag", "id": ident})
            coords = {axis: _number(position[axis], axis) for axis in ("x", "y")}
            if any(not valid_coordinate(value, axis, placement_bounds(self._canvas_bounds, tag)) for axis, value in coords.items()):
                raise ValueError("Etiketternas positioner måste ligga inom ritningen.")
            validated.append((tag, coords))
        for tag, coords in validated:
            tag.update(coords)
        self._publish()

    @staticmethod
    def _drawing_background(rendered, layout):
        if not rendered:
            return {}
        return {**rendered, "source_width": rendered.get("source_width", rendered["width"]),
                "source_height": rendered.get("source_height", rendered["height"]),
                "width": layout["canvas_width"], "height": layout["canvas_height"]}

    @property
    def ritningsunderlag(self):
        """Underlagets placering/skala i arbetsytans fasta koordinatsystem."""
        return copy.deepcopy(self._drawing_layout)

    @ritningsunderlag.setter
    def ritningsunderlag(self, changes):
        if not self.background:
            raise ValueError("Öppna en ritning först.")
        if not isinstance(changes, dict) or set(changes) - {"x", "y", "scale"}:
            raise ValueError("Ange x, y och/eller scale för ritningsunderlaget.")
        layout = drawing_layout({**self._drawing_layout, **changes}, self.background)
        if layout["scale"] != self._drawing_layout["scale"]:
            self._calibration = None
        self._drawing_layout = layout
        self._publish()

    @property
    def objektlayout(self):
        return object_layout(self._object_layout, self._tags, self._text_objects, self.background.get("page"), prune=True)

    def lagerordning(self, objekt, operation):
        """Flytta markerade objekt ett steg eller längst fram/bak; RU ligger alltid under."""
        objects = validate_objects(objekt, self._tags, self._text_objects, self.background.get("page"))
        layout = self.objektlayout
        layout["order"] = reorder(layout["order"], [object_key(item) for item in objects], operation)
        self._object_layout = layout
        self._publish()

    def transformera_objekt(self, objekt):
        """Spara position och visuell skala atomärt, utan att ändra beräkningsindata."""
        if not isinstance(objekt, list) or any(not isinstance(item, dict) or "scale" not in item for item in objekt):
            raise ValueError("Ange objekt med x, y och scale.")
        scales = [scale_value(item["scale"]) for item in objekt]
        objects = validate_objects([{k: v for k, v in item.items() if k != "scale"} for item in objekt],
                                   self._tags, self._text_objects, self.background.get("page"),
                                   coordinates=True, coordinate_bounds=COORDINATE_BOUNDS)
        for item in objects:
            self._assert_placement_unlocked(item)
            bounds = placement_bounds(self._canvas_bounds, self._placement_target(item))
            if any(not valid_coordinate(item[axis], axis, bounds) for axis in ("x", "y")):
                raise ValueError("Objektets position ska ligga inom ritningsytan.")
        layout = self.objektlayout
        for item, scale in zip(objects, scales):
            self._placement_target(item, create=True).update({axis: item[axis] for axis in ("x", "y")})
            layout["scales"][object_key(item)] = scale
        self._object_layout = layout
        self._publish()

    @property
    def ritningsram(self):
        """Synliga sidgränser, relativt originalritningen; negativa värden ger marginal."""
        return dict(self._canvas_bounds)

    @ritningsram.setter
    def ritningsram(self, bounds):
        if not self.background:
            raise ValueError("Öppna en ritning först.")
        self._canvas_bounds = validate_bounds(bounds)
        self._publish()

    @property
    def placeringslas(self):
        """Låsta etiketter/widgets; lås skyddar placering och storlek, inte indata."""
        return [copy.deepcopy(self._placement_locks[key]) for key in sorted(self._placement_locks)]

    def _assert_placement_unlocked(self, item):
        if object_key(item) in self._placement_locks:
            raise ValueError("Placeringen är låst. Lås upp objektet före förflyttning eller skalning.")

    def las_placering(self, objekt, *, last=True):
        """Lås eller lås upp markerade etiketter och widgets i en gemensam begäran."""
        if type(last) is not bool:
            raise ValueError("last måste vara True eller False.")
        objects = validate_objects(objekt, self._tags, self._text_objects, self.background.get("page"))
        for item in objects:
            key = object_key(item)
            if last:
                self._placement_locks[key] = item
            else:
                self._placement_locks.pop(key, None)
        self._publish()

    def _guard_overlay_position(self, kind, before, changes, page=None):
        for axis in ("x", "y"):
            if axis in changes and changes[axis] != before.get(axis) and not valid_coordinate(changes[axis], axis, placement_bounds(self._canvas_bounds, before)):
                raise ValueError("Widgetens placering ska vara inom ritningsytan.")
        if any(axis in changes and changes[axis] != before.get(axis) for axis in ("x", "y", "size", "width")):
            self._assert_placement_unlocked({"type": "overlay", "kind": kind,
                                            "page": self.background.get("page") if page is None else page})

    def _placement_target(self, item, *, create=False):
        if item["type"] == "tag":
            return self._tag(item["id"])
        kind = item["kind"]
        if kind.startswith("text:"):
            return next(text for text in self._text_objects if text["id"] == kind[5:])
        if kind == "colour":
            return self._colour["legend"]
        if kind in {"insulation", "comments", "reference"}:
            return {"insulation": self._insulation_widget, "comments": self._comment_widget,
                    "reference": self._reference_widget}[kind]
        if create:
            placements = self._gliding["placements"].setdefault(str(item["page"]), {})
            return placements.setdefault(kind, copy.deepcopy(DEFAULT_PLACEMENT[kind]))
        return self._gliding["placements"].get(str(item["page"]), {}).get(kind, DEFAULT_PLACEMENT[kind])

    def flytta_objekt(self, placeringar):
        """Flytta etiketter och widgets atomärt utan att beräkna om någon sula."""
        objects = validate_objects(placeringar, self._tags, self._text_objects,
                                   self.background.get("page"), coordinates=True, coordinate_bounds=COORDINATE_BOUNDS)
        for item in objects:
            self._assert_placement_unlocked(item)
            bounds = placement_bounds(self._canvas_bounds, self._placement_target(item))
            if any(not valid_coordinate(item[axis], axis, bounds) for axis in ("x", "y")):
                raise ValueError("Objektets position ska ligga inom ritningsytan.")
        for item in objects:
            self._placement_target(item, create=True).update({axis: item[axis] for axis in ("x", "y")})
        self._publish()

    def hanvisningslinje(self, tagg, linje):
        """Spara en spline i relativa ritningskoordinater, oberoende av indata."""
        tag = self._tag(tagg)
        if tag["values"]["inaktiv"]:
            raise ValueError("Sulan är inaktiv. Avmarkera Inaktiv för att ändra hänvisningslinjen.")
        tag["leader"] = validate_leader(linje, coordinate_bounds=COORDINATE_BOUNDS)
        self._publish()

    def _refresh_tag(self, tag):
        """En felaktig sula får aldrig behålla ett tidigare godkänt resultat."""
        if tag["values"]["inaktiv"]:
            details, summary = _inactive_result()
            tag.update(status="inactive", summary=summary, error="")
            self._details[tag["id"]] = details
            return
        try:
            details, summary = _calculate(tag["values"])
        except (ValueError, ArithmeticError) as exc:
            tag.update(status="error", summary=None, error=str(exc))
            self._details.pop(tag["id"], None)
        else:
            tag.update(status="calculated", summary=summary, error="")
            self._details[tag["id"]] = details

    def berakna(self, tagg):
        """Beräkna en tagg; inaktiva sulor hoppas över utan beräkningsresultat."""
        tag = self._tag(tagg)
        self._refresh_tag(tag)
        self._publish()
        if tag["error"]:
            raise ValueError(tag["error"])
        return copy.deepcopy(self._details[tagg])

    def uppdatera_flera(self, taggar, *, indata, berakna=True):
        """Ändra endast angivna fält för flera sulor och beräkna som standard.

        Alla id och indatavärden valideras före ändring. Beräkningsfel redovisas
        per sula; övriga sulor beräknas ändå. Littera och fundamenttyp behålls.
        """
        if (not isinstance(taggar, (list, tuple)) or not taggar
                or any(not isinstance(ident, str) for ident in taggar)
                or len(set(taggar)) != len(taggar)):
            raise ValueError("Ange en lista med unika tagg-id för de markerade sulorna.")
        if (not isinstance(indata, dict) or not indata
                or set(indata) - (set(_DEFAULTS) - {"lang"})):
            raise ValueError("Välj minst ett känt indatafält. Fundamenttyp ändras per sula.")
        if not isinstance(berakna, bool):
            raise ValueError("berakna måste vara True eller False.")
        tags = [self._tag(ident) for ident in taggar]
        types = {tag["values"]["lang"] for tag in tags}
        load_types = {line_loads(tag["values"]) for tag in tags}
        if len(types) > 1 and set(indata) & _BULK_SAME_TYPE:
            raise ValueError("Välj enbart väggsulor eller enbart pelarsulor för att ändra last- och längdfält.")
        if len(load_types) > 1 and set(indata) & _BULK_LOAD_FIELDS and not (types == {0} and "lasttyp" in indata):
            raise ValueError("Välj samma lasttyp för att ändra last- och linjestödslängdfält gemensamt.")
        if "glid_L" in indata and load_types == {False} and indata.get("lasttyp") != 1:
            raise ValueError("Sulängden L_su gäller endast linjelaster.")
        if "L_vagg" in indata and load_types == {False} and indata.get("lasttyp") != 1:
            raise ValueError("Linjestödslängden L_vägg gäller endast linjelaster.")
        if types == {0} and "L_vagg_minst_1" in indata:
            raise ValueError("Minst 1 m gäller endast väggsulemodellen.")
        if types == {0} and "l_override" in indata:
            raise ValueError("Egen remslängd gäller endast väggsulor.")
        prepared = [_updated_values(tag["values"], indata) for tag in tags]
        for tag, values in zip(tags, prepared):
            validate_model(footing_type(tag), values)
        for tag, values in zip(tags, prepared):
            changed = any(values[name] != value for name, value in tag["values"].items()
                          if name not in _TEXT_NAMES and name not in SLIDING_NAMES)
            tag["values"] = values
            if changed:
                tag.update(status="stale", summary=None, error="")
                self._details.pop(tag["id"], None)
            if values["inaktiv"]:
                self._refresh_tag(tag)
        report = {"updated": len(tags), "calculated": 0, "errors": []}
        inactive = sum(tag["values"]["inaktiv"] for tag in tags)
        if inactive:
            report["inactive"] = inactive
        if berakna:
            for tag in tags:
                if tag["values"]["inaktiv"]:
                    continue
                try:
                    details, summary = _calculate(tag["values"])
                except (ValueError, ArithmeticError) as exc:
                    tag.update(status="error", summary=None, error=str(exc))
                    self._details.pop(tag["id"], None)
                    report["errors"].append({"id": tag["id"], "label": tag["label"], "error": str(exc)})
                else:
                    tag.update(status="calculated", summary=summary, error="")
                    self._details[tag["id"]] = details
                    report["calculated"] += 1
        self._publish()
        return report

    def ta_bort(self, tagg):
        self._tag(tagg)
        self._tags = [tag for tag in self._tags if tag["id"] != tagg]
        self._details.pop(tagg, None)
        self._placement_locks.pop("tag:" + tagg, None)
        self._publish()

    def ta_bort_samtliga(self):
        """Radera alla sulor och avbryt eventuell placeringskö."""
        count = len(self._tags)
        self._tags.clear()
        self._placement_locks = {key: item for key, item in self._placement_locks.items() if item["type"] != "tag"}
        self._details.clear()
        self._load_import = None
        self._publish()
        return count

    @property
    def taggar(self):
        """Kopior av taggar, indata och aktuella resultatsammanfattningar."""
        return [{**copy.deepcopy(tag), "sliding": contribution(tag["values"]),
                 "load_resultants": load_resultants(tag["values"])} for tag in self._tags]

    @property
    def glidning(self):
        """Globala kontroller och placeringar. X och Y är separata lastfall."""
        return copy.deepcopy(self._gliding)

    @glidning.setter
    def glidning(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Glidning anges som en dict med inställningar.")
        settings = validate_settings({**self._gliding, **changes}, self.background.get("page_count"), coordinate_bounds=COORDINATE_BOUNDS)
        for page in settings["placements"]:
            self._view_page(int(page))
        for page in self._gliding["placements"].keys() | settings["placements"].keys():
            for kind in ("symbol", "legend"):
                before = self._gliding["placements"].get(page, {}).get(kind, DEFAULT_PLACEMENT[kind])
                position = settings["placements"].get(page, {}).get(kind, DEFAULT_PLACEMENT[kind])
                self._guard_overlay_position(kind, before, position, int(page))
        self._gliding = settings
        self._publish()

    @property
    def glidningsresultat(self):
        """Summerade, aktuella glidmotstånd från vyns sulor."""
        return project_results(self._tags, self._gliding)

    @property
    def farggruppering(self):
        """Visuella gruppfärger och legend. Inställningarna behålls även när vyn stängs av."""
        return copy.deepcopy(self._colour)

    @farggruppering.setter
    def farggruppering(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Färggruppering anges som en dict med inställningar.")
        settings = {**self._colour, **changes}
        if "categories" not in changes and {"category", "secondary"} & changes.keys():
            settings["categories"] = None
        for name in ("bounds", "colors", "styles", "legend"):
            if name in changes and isinstance(changes[name], dict):
                settings[name] = {**self._colour[name], **changes[name]}
        settings = validate_colour(settings, coordinate_bounds=COORDINATE_BOUNDS)
        self._guard_overlay_position("colour", self._colour["legend"], settings["legend"])
        self._colour = settings
        self._publish()

    @property
    def tabellvy(self):
        """Sparade fällbara tabellgrupper och sorteringskolumn."""
        return copy.deepcopy(self._table_view)

    @tabellvy.setter
    def tabellvy(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Tabellvy anges som en dict.")
        self._table_view = _table_view({**self._table_view, **changes})
        self._publish()

    @property
    def visningsstorlekar(self):
        """Arbetsytans och tabellens bredd/höjd i px; None använder standardstorleken."""
        return copy.deepcopy(self._layout)

    @visningsstorlekar.setter
    def visningsstorlekar(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Visningsstorlekar anges som en dict.")
        self._layout = _layout({**self._layout, **changes})
        self._publish()

    @property
    def visningshojder(self):
        """Arbetsytans och tabellens höjd i px; behålls för äldre notebookkod."""
        return {name: self._layout[name] for name in ("board_height", "table_height")}

    @visningshojder.setter
    def visningshojder(self, changes):
        if not isinstance(changes, dict) or set(changes) - {"board_height", "table_height"}:
            raise ValueError("Visningshöjder anges som en dict med board_height/table_height.")
        self.visningsstorlekar = changes

    @property
    def isoleringswidget(self):
        """Antal isolerade/oisolerade sulor och oisolerade littera på ritningen."""
        return copy.deepcopy(self._insulation_widget)

    @isoleringswidget.setter
    def isoleringswidget(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Isoleringswidget anges som en dict.")
        self._guard_overlay_position("insulation", self._insulation_widget, changes)
        self._insulation_widget = _insulation_widget({**self._insulation_widget, **changes}, coordinate_bounds=COORDINATE_BOUNDS)
        self._publish()

    @property
    def kommentarwidget(self):
        """Flyttbar och skalbar sammanställning av sulor med kommentarer."""
        return copy.deepcopy(self._comment_widget)

    @kommentarwidget.setter
    def kommentarwidget(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Kommentarwidget anges som en dict.")
        self._guard_overlay_position("comments", self._comment_widget, changes)
        self._comment_widget = _comment_widget({**self._comment_widget, **changes}, coordinate_bounds=COORDINATE_BOUNDS)
        self._publish()

    @property
    def referens(self):
        """Flyttbar Referens-widget för vidare dimensionering i Foundation."""
        return copy.deepcopy(self._reference_widget)

    @referens.setter
    def referens(self, changes):
        if not isinstance(changes, dict):
            raise ValueError("Referens anges som en dict.")
        self._guard_overlay_position("reference", self._reference_widget, changes)
        self._reference_widget = validate_reference({**self._reference_widget, **changes}, coordinate_bounds=COORDINATE_BOUNDS)
        self._publish()

    @property
    def referensgrupper(self):
        return reference_groups(self._tags)

    def bekrafta_sultyp(self, tagg, typ):
        """Resolve ambiguous legacy origin without changing the bearing model."""
        tag = self._tag(tagg)
        if not tag.get("footing_type_inferred"):
            raise ValueError("Sultypen är redan definierad när objektet skapades.")
        if tag["values"]["inaktiv"]:
            raise ValueError("Avmarkera Inaktiv för att bekräfta sultypen.")
        validate_model(typ, tag["values"])
        tag["footing_type"] = typ
        tag.pop("footing_type_inferred", None)
        self._publish()

    @property
    def resultat(self):
        """Aktuella details per tagg-id, användbara i an_print.CalcBlock."""
        return copy.deepcopy(self._details)

    @property
    def textobjekt(self):
        """Placerade rubriker och datum; storlek anges i px vid ritningszoom 100 %."""
        return copy.deepcopy(self._text_objects)

    def _add_text(self, kind, text, x, y, size, subtitle="", width=420):
        if not self._source:
            raise ValueError("Importera en ritning först.")
        if any(not valid_coordinate(v, axis, placement_bounds(self._canvas_bounds)) for axis, v in (("x", x), ("y", y))):
            raise ValueError("Textobjektets placering ska vara inom ritningsytan.")
        ident = uuid.uuid4().hex
        self._text_objects = validate_text_objects([*self._text_objects,
            {"id": ident, "kind": kind, "text": text, "subtitle": subtitle, "x": x, "y": y, "size": size, "width": width}], coordinate_bounds=COORDINATE_BOUNDS)
        self._publish()
        return ident

    def lagg_till_rubrik(self, text=None, *, underrubrik=None, x=.08, y=.08, storlek=20, bredd=420):
        """Kopiera befintlig rubrik och underrubrik om nya texter inte anges."""
        return self._add_text("heading", self._title if text is None else text, x, y, storlek,
                              self._subtitle if underrubrik is None else underrubrik, bredd)

    def lagg_till_datum(self, text=None, *, x=.08, y=.18, storlek=18):
        """Lägg till datum; dagens datum i Stockholm används om text utelämnas."""
        return self._add_text("date", today_text() if text is None else text, x, y, storlek)

    def uppdatera_text(self, ident, **changes):
        if set(changes) - {"text", "subtitle", "x", "y", "size", "width"}:
            raise ValueError("Ändra text, subtitle, x, y, size eller width för textobjektet.")
        if not any(item["id"] == ident for item in self._text_objects):
            raise ValueError("Textobjektet finns inte.")
        before = next(item for item in self._text_objects if item["id"] == ident)
        self._guard_overlay_position("text:" + ident, before, changes)
        self._text_objects = validate_text_objects([
            {**item, **changes} if item["id"] == ident else item for item in self._text_objects], coordinate_bounds=COORDINATE_BOUNDS)
        self._publish()

    def ta_bort_text(self, ident):
        if not any(item["id"] == ident for item in self._text_objects):
            raise ValueError("Textobjektet finns inte.")
        self._text_objects = [item for item in self._text_objects if item["id"] != ident]
        self._placement_locks.pop(f"overlay:{self.background['page']}:text:{ident}", None)
        self._publish()

    @property
    def etikettstorlek(self):
        """Etiketternas grundstorlek i procent (20–180), vid 100 % ritningszoom."""
        return self._label_size

    @etikettstorlek.setter
    def etikettstorlek(self, value):
        value = _label_size(value)
        layout = self.objektlayout
        for key in self._placement_locks:
            if key.startswith("tag:"):
                layout["scales"][key] = scale_value(layout["scales"].get(key, 1) * self._label_size / value)
        self._object_layout = layout
        self._label_size = value
        self._publish()

    def _set_heading(self, title, subtitle):
        title = _heading_text(title, "Rubrik")
        subtitle = _heading_text(subtitle, "Underrubrik", max_length=None)
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
        """Sidbyte ersätts av en separat Grundplan med egen key och sida."""
        if not self._source:
            raise ValueError("Öppna en ritning först.")
        self._view_page(sida)

    @property
    def kalibrering(self):
        """Mätverktygets referensmått och två relativa ritningspunkter."""
        return copy.deepcopy(self._calibration)

    @kalibrering.setter
    def kalibrering(self, value):
        self._calibration = _calibration(value, self.background)
        self._publish()

    def _document(self):
        return {
            "format": _FORMAT,
            "version": 23,
            "calculator_version": _CALCULATOR_VERSION,
            "title": self._title,
            "subtitle": self._subtitle,
            "label_size": self._label_size,
            "calibration": self.kalibrering,
            "sliding": copy.deepcopy(self._gliding),
            "colour_grouping": self.farggruppering,
            "table_view": self.tabellvy,
            "layout": self.visningsstorlekar,
            "insulation_widget": self.isoleringswidget,
            "comment_widget": self.kommentarwidget,
            "reference_widget": self.referens,
            "text_objects": self.textobjekt,
            "placement_locks": self.placeringslas,
            "canvas_bounds": self.ritningsram,
            "drawing_layout": self.ritningsunderlag,
            "object_layout": self.objektlayout,
            "drawing": {
                "name": self._filename,
                "data": base64.b64encode(self._source).decode("ascii"),
                "page": self.background.get("page", self._initial_page),
            },
            "tags": [
                {**{key: copy.deepcopy(tag[key]) for key in
                    ("id", "label", "x", "y", "page", "values", "footing_type")},
                 **({"imported_length": tag["imported_length"]} if "imported_length" in tag else {}),
                 **({"leader": copy.deepcopy(tag["leader"])} if "leader" in tag else {}),
                 **({"footing_type_inferred": True} if tag.get("footing_type_inferred") else {}),
                 "calculated": tag["status"] == "calculated"}
                for tag in self._tags
            ],
        }

    def spara(self, fil=None):
        """Spara till nyckelns lokala state-fil eller exportera till en angiven fil.

        Båda innehåller originalritningen. Namngivna projekt delar en state-fil
        utan att skriva över varandras nycklar. En explicit fil är alltid portabel.
        """
        document = self._document()
        if fil is None:
            if self._key is None:
                raise ValueError("Ange en fil eller skapa Grundplan med key för lokal lagring.")
            path = self._state_file
            state = self._read_state_file()
            state["projects"][self._key] = document
            document = state
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = Path(fil)
        return self._write_json(path, document)

    @staticmethod
    def _write_json(path, document):
        data = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
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
        return render_pdf(self._source, self.taggar, self._label_size, self._title, self._gliding,
                          page_number=self.background["page"], colour_grouping=self._colour,
                          insulation_widget=self._insulation_widget, comment_widget=self._comment_widget, reference_widget=self._reference_widget,
                          text_objects=self._text_objects, canvas_bounds=self._canvas_bounds,
                          drawing_layout=self._drawing_layout, object_layout=self._object_layout)

    def exportera_pdf(self, fil):
        """Exportera vyns enda ritningssida med fasta etiketter till en PDF.

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

        pages = [self._drawing_background(_render_source(self._source, self._filename, self.background["page"]), self._drawing_layout)]
        return render_html({
            "state": {"title": self._title, "subtitle": self._subtitle,
                      "label_size": self._label_size, "calibration": self.kalibrering, "tags": self.taggar,
                      "sliding": self.glidning, "sliding_result": self.glidningsresultat,
                      "colour_grouping": self.farggruppering, "table_view": self.tabellvy,
                      "layout": self.visningsstorlekar,
                      "insulation_widget": self.isoleringswidget,
                      "comment_widget": self.kommentarwidget,
                      "reference_widget": self.referens, "reference_data": self.referensgrupper,
                      "text_objects": self.textobjekt, "placement_locks": self.placeringslas,
                      "canvas_bounds": self.ritningsram, "drawing_layout": self.ritningsunderlag, "object_layout": self.objektlayout},
            "schema": {"fields": copy.deepcopy(_FIELDS), "load_groups": copy.deepcopy(LOAD_GROUPS)},
            "pages": pages,
            "page": self.background.get("page", 1),
            "pdf": {"filename": Path(self._filename).stem + "_med_etiketter.pdf",
                    "data": base64.b64encode(self._pdf_bytes()).decode("ascii")},
        })

    def exportera_html(self, fil):
        """Exportera en fristående resultatvy med öppningsbara etiketter.

        Vyns ritningssida och aktuella indata/resultat bäddas in. Filen fungerar
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
        if not isinstance(document, dict) or document.get("format") != _FORMAT or document.get("version") not in range(1, 24):
            raise ValueError("Filen är inte ett Grundplan-projekt av version 1–23.")
        canvas_bounds = validate_bounds(document.get("canvas_bounds", DEFAULT_BOUNDS))
        label_size = _label_size(document.get("label_size", 100))
        title = str(document.get("title", "Grundplan"))[:200]
        subtitle = _heading_text(document.get("subtitle", _DEFAULT_SUBTITLE), "Underrubrik", max_length=None)
        drawing = document["drawing"]
        if isinstance(drawing["page"], bool) or not isinstance(drawing["page"], int) or drawing["page"] < 1:
            raise ValueError("Sida måste vara ett positivt heltal.")
        source = base64.b64decode(drawing["data"], validate=True)
        rendered = _render_source(source, drawing["name"], drawing["page"]) if source else {}
        source_layout = drawing_layout(document.get("drawing_layout", {}) if document["version"] >= 23 else {}, rendered)
        rendered = self._drawing_background(rendered, source_layout)
        calibration = _calibration(document.get("calibration"), rendered)
        colour = validate_colour(document.get("colour_grouping", {}), coordinate_bounds=COORDINATE_BOUNDS)
        table_view = _table_view(document.get("table_view", {}))
        layout = _layout(document.get("layout", {}))
        insulation_widget = _insulation_widget(document.get("insulation_widget", {}), coordinate_bounds=COORDINATE_BOUNDS)
        comment_widget = _comment_widget(document.get("comment_widget", {}), coordinate_bounds=COORDINATE_BOUNDS)
        reference_widget = validate_reference(document.get("reference_widget", {}), coordinate_bounds=COORDINATE_BOUNDS)
        text_objects = validate_text_objects(document.get("text_objects", []), coordinate_bounds=COORDINATE_BOUNDS)
        gliding = validate_settings(document.get("sliding", {}), rendered.get("page_count", 0), coordinate_bounds=COORDINATE_BOUNDS)
        if any(int(page) != rendered.get("page") for page in gliding["placements"]):
            raise ValueError("Projektet har glidningssymboler på flera ritningssidor. Använd ett separat projekt per sida.")
        tags = document["tags"]
        if not isinstance(tags, list) or len(tags) > _MAX_TAGS:
            raise ValueError("Projektet har för många eller ogiltiga taggar.")
        valid_tags, details_by_id, ids = [], {}, set()
        for saved in tags:
            ident = saved["id"]
            if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in ids:
                raise ValueError("Projektet innehåller ogiltiga eller upprepade tagg-id.")
            ids.add(ident)
            page = _page_number(saved["page"], rendered.get("page_count", 0))
            if page != rendered.get("page"):
                raise ValueError("Projektet har sulor på flera ritningssidor. Använd ett separat projekt per sida.")
            for name in ("x", "y"):
                if not valid_coordinate(saved[name], name, COORDINATE_BOUNDS):
                    raise ValueError("Taggens position ligger utanför ritningen.")
            saved_values = saved["values"]
            if isinstance(saved_values, dict) and "lasttyp" not in saved_values and "imported_length" in saved:
                # Imported line supports remain line loads after a user-selected
                # pad model, including projects saved before separate load types.
                saved_values = {**saved_values, "lasttyp": 1}
            if document["version"] < 6 and isinstance(saved_values, dict):
                # Before v5, wall l was unused. In v5 it was an explicit override.
                saved_values = {**saved_values, "l_override": document["version"] == 5
                                and saved_values.get("lang") == 1 and saved_values.get("l") != 1}
                if document["version"] < 5 and saved_values.get("lang") == 1:
                    saved_values["l"] = 1.0
            tag = {
                "id": ident, "label": _label(saved["label"]), "page": page,
                "x": saved["x"], "y": saved["y"],
                "values": _values(saved_values, draft=True),
                "status": "stale", "summary": None, "error": "",
            }
            if "footing_type" in saved:
                typ = saved["footing_type"]
                inferred = saved.get("footing_type_inferred", False)
                if type(inferred) is not bool:
                    raise ValueError("Ogiltig markering för härledd sultyp.")
            elif document["version"] < 20:
                typ, inferred = infer_type({**saved, "values": tag["values"]})
            else:
                raise ValueError("Projektet saknar objektets sultyp.")
            validate_model(typ, tag["values"])
            tag["footing_type"] = typ
            if inferred:
                tag["footing_type_inferred"] = True
            if "leader" in saved:
                tag["leader"] = validate_leader(saved["leader"], coordinate_bounds=COORDINATE_BOUNDS)
            if "imported_length" in saved:
                length = _number(saved["imported_length"], "Importerad linjestödslängd")
                if length <= 0:
                    raise ValueError("Importerad linjestödslängd måste vara större än noll.")
                tag["imported_length"] = length
            try:
                details, summary = _inactive_result() if tag["values"]["inaktiv"] else _calculate(tag["values"])
                tag.update(status="inactive" if tag["values"]["inaktiv"] else "calculated", summary=summary)
                details_by_id[ident] = details
            except (ValueError, ArithmeticError) as exc:
                tag.update(status="error", error=str(exc))
            valid_tags.append(tag)
        locks = validate_objects(document.get("placement_locks", []), valid_tags, text_objects,
                                 drawing["page"], allow_empty=True)
        objects_layout = object_layout(document.get("object_layout", {}) if document["version"] >= 23 else {}, valid_tags, text_objects, drawing["page"] if source else None)
        # Replace the current project only after the entire input is validated.
        self._drawing_preview = None
        self._source = source
        self._filename = Path(drawing["name"]).name
        self._title = title
        self._subtitle = subtitle
        self._label_size = label_size
        self._canvas_bounds = canvas_bounds
        self._drawing_layout = source_layout
        self._object_layout = objects_layout
        self._calibration = calibration
        self._gliding = gliding
        self._colour = colour
        self._table_view = table_view
        self._layout = layout
        self._insulation_widget = insulation_widget
        self._comment_widget = comment_widget
        self._reference_widget = reference_widget
        self._text_objects = text_objects
        self._placement_locks = {object_key(item): item for item in locks}
        self._tags = valid_tags
        self._load_import = None
        self._details = details_by_id
        self.background = rendered
        self._initial_page = drawing["page"]
        self._publish()

    def _restore_history_calculations(self, before):
        for tag in self._tags:
            previous = before.get("tag:" + tag["id"])
            if previous is None or any(value != previous["values"].get(name)
                    for name, value in tag["values"].items() if name not in _TEXT_NAMES and name not in SLIDING_NAMES):
                self._refresh_tag(tag)
        self._drawing_preview = None
        if self._load_import:
            self._load_import["paused"] = True

    def angra(self):
        """Ångra senaste UI-handlingen i denna session; återställ beräkningar vid behov."""
        return self._history.apply(self)

    def gor_om(self):
        """Gör om den senast ångrade UI-handlingen."""
        return self._history.apply(self, redo=True)

    @history_command
    def _on_message(self, widget, content, buffers):
        """UI commands; imported files arrive as bytes, save paths are explicit input."""
        reply = {"request": content.get("request"), "view": content.get("view")}
        try:
            action = content["action"]
            if action == "undo":
                reply["description"] = self.angra()
            elif action == "redo":
                reply["description"] = self.gor_om()
            elif action == "add":
                reply["id"] = self.lagg_till(content["x"], content["y"], typ=content["kind"])
            elif action == "copy":
                reply["id"] = self.kopiera(
                    content["id"], content["x"], content["y"],
                    sida=content.get("page"), indata=content.get("values"),
                )
            elif action == "import_loads":
                reply["report"] = self._start_load_import(bytes(buffers[0]), content["name"])
            elif action == "place_import":
                if not isinstance(content["token"], str) or type(content["index"]) is not int:
                    raise ValueError("Ogiltig placeringsbegäran.")
                reply.update(self._place_load_import(content["x"], content["y"], sida=content["page"],
                                                     token=content["token"], index=content["index"]))
            elif action == "import_control":
                self._control_load_import(content["token"], content["operation"])
            elif action == "update":
                self.uppdatera(
                    content["id"], indata=content.get("values"), littera=content.get("label"),
                    x=content.get("x"), y=content.get("y"),
                )
            elif action == "move_tags":
                self.flytta_flera(content["positions"])
            elif action == "move_objects":
                self.flytta_objekt(content["objects"])
            elif action == "transform_objects":
                self.transformera_objekt(content["objects"])
            elif action == "object_order":
                self.lagerordning(content["objects"], content["operation"])
            elif action == "drawing_layout":
                self.ritningsunderlag = content["layout"]
            elif action == "drawing_commit":
                preview = self._drawing_preview
                if content.get("token") is not None and (not preview or content["token"] != preview["token"]):
                    raise ValueError("Ritningsunderlaget har ändrats. Öppna redigeringsläget igen.")
                base = preview["layout"] if content.get("token") else self._drawing_layout
                if not isinstance(content["layout"], dict) or set(content["layout"]) != {"x", "y", "scale"}:
                    raise ValueError("Ange underlagets position och skala.")
                layout = drawing_layout({**base, **content["layout"]}, preview["background"] if content.get("token") else self.background)
                if content.get("token"):
                    self._set_source(preview["source"], preview["name"], preview["page"])
                elif layout["scale"] != self._drawing_layout["scale"]:
                    self._calibration = None
                self._drawing_layout = layout
                self._publish()
            elif action == "drawing_cancel":
                if self._drawing_preview and self._drawing_preview["token"] == content.get("token"):
                    self._drawing_preview = None
            elif action == "canvas_bounds":
                self.ritningsram = content["bounds"]
            elif action == "placement_lock":
                self.las_placering(content["objects"], last=content["locked"])
            elif action == "leader":
                self.hanvisningslinje(content["id"], content["leader"])
            elif action == "calculate":
                self.uppdatera(content["id"], indata=content["values"], littera=content["label"])
                self.berakna(content["id"])
            elif action == "bulk_update":
                reply["report"] = self.uppdatera_flera(
                    content["ids"], indata=content["values"], berakna=True)
            elif action == "delete":
                self.ta_bort(content["id"])
            elif action == "delete_all":
                reply["deleted"] = self.ta_bort_samtliga()
            elif action == "page":
                self.visa_sida(content["page"])
            elif action == "label_size":
                self.etikettstorlek = content["value"]
            elif action == "calibration":
                self.kalibrering = content.get("calibration")
            elif action == "heading":
                self._set_heading(content["title"], content["subtitle"])
            elif action == "sliding":
                self.glidning = content["settings"]
            elif action == "colour_grouping":
                self.farggruppering = content["settings"]
            elif action == "table_view":
                self.tabellvy = content["settings"]
            elif action == "layout":
                self.visningsstorlekar = content["settings"]
            elif action == "insulation_widget":
                self.isoleringswidget = content["settings"]
            elif action == "comment_widget":
                self.kommentarwidget = content["settings"]
            elif action == "reference_widget":
                self.referens = content["settings"]
            elif action == "footing_type":
                self.bekrafta_sultyp(content["id"], content["kind"])
            elif action == "text_add":
                kind = content["kind"]
                if kind not in ("heading", "date"):
                    raise ValueError("Välj rubrik eller datum.")
                if kind == "heading":
                    reply["id"] = self.lagg_till_rubrik(content.get("text"), underrubrik=content.get("subtitle"),
                        x=content.get("x", .08), y=content.get("y", .08), bredd=content.get("width", 420),
                        storlek=content.get("size", 20))
                else:
                    reply["id"] = self.lagg_till_datum(x=content.get("x", .08), y=content.get("y", .18))
            elif action == "text_update":
                self.uppdatera_text(content["id"], **content["changes"])
            elif action == "text_delete":
                self.ta_bort_text(content["id"])
            elif action == "insulation_placement":
                self._view_page(content["page"])
                self.isoleringswidget = content["position"]
            elif action == "comment_placement":
                self._view_page(content["page"])
                self.kommentarwidget = content["position"]
            elif action == "reference_placement":
                self._view_page(content["page"])
                self.referens = content["position"]
            elif action == "colour_placement":
                self._view_page(content["page"])
                self.farggruppering = {"legend": content["position"]}
            elif action == "sliding_placement":
                page = self._view_page(content["page"])
                kind = content["kind"]
                if kind not in ("symbol", "legend"):
                    raise ValueError("Okänd glidningssymbol.")
                placements = copy.deepcopy(self._gliding["placements"])
                placements.setdefault(str(page), {})[kind] = content["position"]
                self.glidning = {"placements": placements}
            elif action == "drawing":
                updated = bool(self._source)
                if content.get("draft"):
                    source = bytes(buffers[0])
                    rendered = _render_source(source, content["name"], self._initial_page, fallback_page=bool(self.background))
                    layout = drawing_layout(self._drawing_layout if self.background else {}, rendered)
                    preview = {"token": uuid.uuid4().hex, "source": source, "name": content["name"],
                               "page": rendered["page"], "layout": layout,
                               "background": self._drawing_background(rendered, layout)}
                    self._drawing_preview = preview
                    reply["drawing_preview"] = {key: copy.deepcopy(preview[key]) for key in ("token", "background", "layout", "name")}
                else:
                    self._set_source(bytes(buffers[0]), content["name"])
                    self._publish()
                    reply.update(updated=updated, page=self.background["page"])
            elif action == "open":
                self._load_document(bytes(buffers[0]))
            elif action == "save_choices":
                reply["choices"] = self._save_choices()
            elif action == "save":
                if "key" in content or "state_file" in content:
                    if "key" not in content or content["key"] is None:
                        raise ValueError("Ange key för projektet.")
                    if not self._save_as(content["key"], content.get("state_file"), overwrite=content.get("overwrite") is True):
                        reply.update(ok=False, conflict=True,
                                     error="Det finns redan ett projekt med denna key i filen. Ersätt det sparade projektet?")
                        return reply
                    reply.update(saved_file=str(self._state_file), storage=self._storage())
                elif self._key is not None:
                    reply["saved_file"] = str(self.spara())
                else:
                    reply["download"] = json.dumps(self._document(), ensure_ascii=False, allow_nan=False)
            elif action == "export_json":
                reply["download"] = json.dumps(self._document(), ensure_ascii=False, allow_nan=False)
            elif action == "export_pdf":
                data = self._pdf_bytes()
                reply.update(ok=True, filename=Path(self._filename).stem + "_med_etiketter.pdf")
                self.send(reply, buffers=[data])
                return None
            elif action == "export_html":
                data = self._html_bytes()
                reply.update(ok=True, filename=Path(self._filename).stem + "_resultat.html")
                self.send(reply, buffers=[data])
                return None
            else:
                raise ValueError("Okänt kommando.")
            reply["ok"] = True
        except Exception as exc:
            # Exceptions in widget callbacks otherwise disappear in kernel logs.
            reply.update(ok=False, error=str(exc) or type(exc).__name__)
        return reply
