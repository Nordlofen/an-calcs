/* Shared plan view. All engineering calculations run in the Python kernel. */
const FOOTING_CATEGORIES = {wall: "Väggsula", wall_pad: "Väggsula m. beräkningsmodell pelarsula", pad: "Pelarsula"};
const physicalType = tag => tag.footing_type || (Number(tag.values.lang) === 1 || /^VS[.\s_-]?\d/i.test(tag.label || "")
  || tag.imported_length != null || Number(tag.values.lasttyp) === 1 ? "vaggsula" : "pelarsula");
const footingCategory = tag => physicalType(tag) === "pelarsula" ? "pad" : Number(tag.values.lang) === 1 ? "wall" : "wall_pad";
const REFERENCE_WIDGET_DEFAULTS = {enabled: false, x: .05, y: .3, size: 410};
const lineLoads = values => Number(values.lang) === 1 || Number(values.lasttyp ?? 0) === 1;
const COLOUR_DEFAULTS = {enabled: false, category: "t", secondary: null, categories: null, phase: "brott", edit_type: "pad", show_legend: true,
  include_only_h: false, bounds: {pad: [100, 200, 400], wall: [100, 200, 400]}, colors: {}, styles: {}, legend: {x: .65, y: .08, size: 300}};
const COLOUR_CATEGORIES = {sultyp: "Sultyp", t: "Tjocklek t", b: "Bredd bₓ", l: "Längd bᵧ", V: "Vertikallast V", isolering: "Isolering"};
const COLOUR_PHASES = {brott: "Brott", bruk: "Bruk", EQU: "EQU"};
const selectedColourCategories = settings => Object.keys(COLOUR_CATEGORIES)
  .filter(name => (settings.categories || [settings.category, settings.secondary]).includes(name));
const onlyHColourRestriction = settings => {
  const categories = selectedColourCategories(settings);
  const dimensions = categories.filter(category => ["t", "b", "l"].includes(category));
  if (dimensions.length) return "Endast H: avmarkera sulmått (" + dimensions.map(category => ({t: "t", b: "bₓ", l: "bᵧ"})[category]).join(", ")
    + ") för att kunna inkludera dessa sulor.";
  if (categories.includes("V") && settings.phase !== "EQU")
    return "Endast H: välj EQU för att gruppera dessa sulor efter vertikallast.";
  return "";
};
const INSULATION_WIDGET_DEFAULTS = {enabled: false, x: .65, y: .55, size: 300};
const COMMENT_WIDGET_DEFAULTS = {enabled: false, x: .08, y: .55, size: 410};
const CANVAS_DEFAULTS = {left: 0, top: 0, right: 1, bottom: 1};
export function validateCanvasBounds(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).length !== 4
      || Object.keys(value).some(key => !Object.hasOwn(CANVAS_DEFAULTS, key))
      || Object.values(value).some(v => typeof v !== "number" || !Number.isFinite(v) || v < -10 || v > 11)
      || [value.right - value.left, value.bottom - value.top].some(size => size < .05 - 1e-10 || size > 10 + 1e-10))
    throw new Error("Ritningsytans bredd och höjd ska vara 5–1000 % av originalet.");
  return {...value};
}
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
// ColorBrewer Set3, original 12-class colours.
const COLOUR_PALETTE = ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
  "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5", "#ffed6f"];
const COLOUR_PATTERNS = ["plain", "bands", "dots", "cross", "horizontal", "vertical"];
const COLOUR_INSULATION_GROUPS = [
  ["1", "Med isolering · inget bidrag"],
  ["0", "Utan isolering · inget bidrag"],
  ["x", "Utan isolering · bidrag i X_g"],
  ["y", "Utan isolering · bidrag i Y_g"],
  ["xy", "Utan isolering · bidrag i X_g och Y_g"],
];
const colourNumberKey = value => {const [m, e] = value.toExponential(12).split("e"); return m + "e" + Number(e);};
const colourPalette = index => COLOUR_PALETTE[index % COLOUR_PALETTE.length];
const colourBackground = color => {
  const channels = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16));
  const weight = COLOUR_PALETTE.includes(color.toLowerCase()) || Math.min(...channels) >= 150 ? 1 : .3;
  return "#" + channels.map(channel => Math.floor(channel * weight + 255 * (1 - weight) + .5).toString(16).padStart(2, "0")).join("");
};
const colourStyleScope = settings => selectedColourCategories(settings).join("+")
  + (selectedColourCategories(settings).includes("V") ? ":" + settings.phase : "");
function decorateColourGroups(groups, settings) {
  const saved = settings.styles?.[colourStyleScope(settings)] || {};
  let active = groups.filter(group => group.count && !["special", "omitted"].includes(group.kind));
  const mapping = {};
  let start = 0;
  while (active.length) {
    const end = start + COLOUR_PALETTE.length;
    const retained = Object.fromEntries(active.filter(group => saved[group.key] != null && saved[group.key] >= start && saved[group.key] < end)
      .map(group => [group.key, saved[group.key]]));
    Object.assign(mapping, retained);
    const used = new Set(Object.values(retained));
    const pending = active.filter(group => mapping[group.key] == null);
    let nextIndex = start;
    for (const group of pending.slice(0, Math.min(active.length, COLOUR_PALETTE.length) - used.size)) {
      while (used.has(nextIndex)) nextIndex++;
      mapping[group.key] = nextIndex; used.add(nextIndex);
    }
    active = pending.filter(group => mapping[group.key] == null);
    start = end;
  }
  for (const group of groups) {
    let index = null, color;
    if (group.kind === "omitted") color = "#ffffff";
    else if (group.kind === "special") color = settings.colors[group.key] || "#d5dde1";
    else {
      index = mapping[group.key] ?? null;
      color = settings.colors[group.key] || (index === null ? "#d5dde1" : colourPalette(index));
    }
    const batch = Math.floor((index ?? 0) / COLOUR_PALETTE.length);
    Object.assign(group, {color, background: colourBackground(color), style_index: index,
      pattern: batch ? COLOUR_PATTERNS[1 + (batch - 1) % (COLOUR_PATTERNS.length - 1)] : "plain",
      pattern_variant: batch ? Math.floor((batch - 1) / (COLOUR_PATTERNS.length - 1)) : 0});
  }
}
export function colourGroups(tags, settings = COLOUR_DEFAULTS) {
  const categories = selectedColourCategories(settings);
  const includeH = settings.include_only_h === true && !onlyHColourRestriction(settings);
  tags = tags.filter(tag => !tag.values.inaktiv && (includeH || !tag.values.endast_h_stabilitet));
  if (categories.length > 1) {
    const parts = categories.map(category => colourGroups(tags, {...settings, categories: [category]}));
    const order = parts.map(part => new Map(part.groups.map((group, index) => [group.key, index])));
    const pairs = new Map(), groups = [], assignments = new Map();
    for (const tag of tags) {
      const pair = parts.map(part => part.assignments.get(tag.id).key), key = "combo:" + JSON.stringify(pair);
      if (!pairs.has(key)) pairs.set(key, {pair, ids: []});
      pairs.get(key).ids.push(tag.id);
    }
    for (const [key, {ids}] of [...pairs].sort(([, a], [, b]) => a.pair.reduce((difference, key, index) =>
      difference || order[index].get(key) - order[index].get(b.pair[index]), 0))) {
      const group = {key, count: ids.length, kind: "combination", unit: "",
        categories, parts: parts.map(part => part.assignments.get(ids[0]))};
      groups.push(group); for (const id of ids) assignments.set(id, group);
    }
    decorateColourGroups(groups, settings);
    return {groups, assignments};
  }
  const category = categories[0], {phase} = settings, groups = [], assignments = new Map(), byKey = new Map(), special = new Map();
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const make = (key, data) => {
    const group = {key, count: 0, ...data};
    groups.push(group); return group;
  };
  if (category === "sultyp") {
    for (const [kind, label] of Object.entries(FOOTING_CATEGORIES)) {
      byKey.set(kind, make("sultyp:" + kind, {label, kind: "footing_type", unit: "", category: kind}));
    }
  } else if (category === "isolering") {
    for (const [suffix, label] of COLOUR_INSULATION_GROUPS) {
      byKey.set(suffix, make("isolering:" + suffix, {label, kind: "insulation", unit: ""}));
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
    if (category === "l" && tags.some(tag => footingCategory(tag) === "wall"))
      byKey.set("omitted", make("l:wall", {label: "", kind: "omitted", unit: ""}));
    const values = [...new Set(tags.filter(tag => !tag.values.endast_h_stabilitet && finite(tag.values[category])
      && (category !== "l" || footingCategory(tag) !== "wall"))
      .map(tag => tag.values[category]))].sort((a, b) => a - b);
    for (const value of values) {
      const key = category + ":" + colourNumberKey(value);
      if (!byKey.has(key)) byKey.set(key, make(key, {value, unit: "m", kind: "geometry"}));
    }
  }
  for (const tag of tags) {
    const values = tag.values;
    if (category === "sultyp") {
      const group = byKey.get(footingCategory(tag));
      group.count++; assignments.set(tag.id, group); continue;
    }
    if (category === "isolering") {
      const insulated = !values.endast_h_stabilitet && values.isolering === true;
      const direction = (values.glid_x ? "x" : "") + (values.glid_y ? "y" : "");
      const group = byKey.get(insulated ? "1" : direction || "0");
      group.count++; assignments.set(tag.id, group); continue;
    }
    if (category === "l" && footingCategory(tag) === "wall") {
      const group = byKey.get("omitted");
      group.count++; assignments.set(tag.id, group); continue;
    }
    const value = values[category === "V" ? {brott: "F_vy", bruk: "F_vy_bruk", EQU: "V_Ed_EQU"}[phase] : category];
    let group;
    if (!finite(value)) {
      const key = "missing";
      if (!special.has(key)) {
        const item = make(key, {label: "Saknar värde", kind: "special", unit: ""});
        special.set(key, item);
      }
      group = special.get(key);
    } else if (category === "V") {
      const kind = lineLoads(values) ? "wall" : "pad";
      const index = settings.bounds[kind].filter(bound => value >= bound).length;
      group = byKey.get(kind + ":" + index);
    } else group = byKey.get(category + ":" + colourNumberKey(value));
    group.count++; assignments.set(tag.id, group);
  }
  decorateColourGroups(groups, settings);
  return {groups, assignments};
}

// Explicit SVG shapes keep patterns vector based in Chromium PDF output. The
// minimum screen spacing makes the whole-label marks readable when zoomed out.
export function colourPatternGeometry(pattern, width, height, scale = 1, compact = false, variant = 0) {
  scale = Math.max(.01, scale);
  const pitch = compact ? 14 : Math.max(52 / (1 + Math.min(variant, 3) * .15), 22 / scale);
  const band = compact ? 4 : Math.max(pitch * .32, 7 / scale);
  const radius = compact ? 2.2 : Math.max(pitch * .14, 3 / scale);
  const shapes = [];
  const path = (x1, y1, x2, y2) => shapes.push({tag: "path", d: `M ${x1} ${y1} L ${x2} ${y2}`, "stroke-width": band});
  if (pattern === "bands" || pattern === "cross") {
    for (let x = -height; x <= width + pitch; x += pitch) {
      path(x, 0, x + height, height);
      if (pattern === "cross") path(x + height, 0, x, height);
    }
  } else if (pattern === "dots") {
    for (let y = Math.min(pitch / 2, height / 2); y < height + radius; y += pitch)
      for (let x = Math.min(pitch / 2, width / 2); x < width + radius; x += pitch)
        shapes.push({tag: "circle", cx: x, cy: y, r: radius});
  } else if (pattern === "horizontal") {
    for (let y = pitch / 2; y < height + band; y += pitch) path(0, y, width, y);
  } else if (pattern === "vertical") {
    for (let x = pitch / 2; x < width + band; x += pitch) path(x, 0, x, height);
  }
  return {pitch, band, radius, shapes};
}

const drawingDistance = (start, end, background) => Math.hypot(
  (end.x - start.x) * background.width, (end.y - start.y) * background.height);
export function validateCalibration(value, background) {
  if (value == null) return null;
  if (!background?.url) throw new Error("Öppna en ritning före kalibrering.");
  const validPoint = point => point && [point.x, point.y].every(n => typeof n === "number" && Number.isFinite(n) && n >= -10 && n <= 11);
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

// Nodes and handles use relative drawing coordinates. Only the final endpoint
// is computed from the label's actual frame, so it follows dragging and sizing.
export function leaderEndpoint(attachment, box) {
  const {side, offset} = attachment;
  return {x: box.x + (side === "left" ? 0 : side === "right" ? box.width : box.width * offset),
    y: box.y + (side === "top" ? 0 : side === "bottom" ? box.height : box.height * offset)};
}
export function leaderAttachment(point, box) {
  const clamp = value => Math.max(0, Math.min(1, value));
  const candidates = [
    {side: "left", offset: clamp((point.y - box.y) / box.height)},
    {side: "right", offset: clamp((point.y - box.y) / box.height)},
    {side: "top", offset: clamp((point.x - box.x) / box.width)},
    {side: "bottom", offset: clamp((point.x - box.x) / box.width)},
  ];
  return candidates.sort((a, b) => {
    const distance = candidate => {const p = leaderEndpoint(candidate, box);
      return ((p.x - point.x) / box.width) ** 2 + ((p.y - point.y) / box.height) ** 2;};
    return distance(a) - distance(b);
  })[0];
}
const leaderAdd = (a, b) => ({x: a.x + b.x, y: a.y + b.y});
const leaderSub = (a, b) => ({x: a.x - b.x, y: a.y - b.y});
const leaderLerp = (a, b, t) => ({x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t});
export function leaderVertices(leader, endpoint) {
  return [...leader.nodes, {...endpoint, in: leader.end_handle, out: {x: 0, y: 0}}];
}
export function leaderCurvePoint(a, b, t) {
  const p = leaderLerp(a, leaderAdd(a, a.out), t), q = leaderLerp(leaderAdd(a, a.out), leaderAdd(b, b.in), t),
    r = leaderLerp(leaderAdd(b, b.in), b, t);
  return leaderLerp(leaderLerp(p, q, t), leaderLerp(q, r, t), t);
}
export function leaderTip(vertices, width, height, size) {
  const pixel = point => ({x: point.x * width, y: point.y * height});
  const anchor = pixel(vertices[0]);
  const curves = vertices.slice(1).map((b, i) => {
    const a = vertices[i];
    return [pixel(a), pixel(leaderAdd(a, a.out)), pixel(leaderAdd(b, b.in)), pixel(b)];
  });
  const tangent = curves.flat().map(p => leaderSub(p, anchor)).find(v => Math.hypot(v.x, v.y) > 1e-8) || {x: 1, y: 0};
  const direction = Math.atan2(tangent.y, tangent.x);
  const points = curves.flat(), margin = 10 * size;
  const left = Math.min(anchor.x, ...points.map(p => p.x)) - margin,
    top = Math.min(anchor.y, ...points.map(p => p.y)) - margin,
    right = Math.max(anchor.x, ...points.map(p => p.x)) + margin,
    bottom = Math.max(anchor.y, ...points.map(p => p.y)) + margin;
  let clip = `M ${left} ${top} H ${right} V ${bottom} H ${left} Z`;
  // Clear narrow bands along the arrow arms, leaving the original spline and
  // its true endpoint tangent intact. The two disjoint holes remain vectors.
  for (const angle of [direction - .45, direction + .45]) {
    const u = {x: Math.cos(angle), y: Math.sin(angle)}, n = {x: -u.y, y: u.x};
    const p = (distance, offset) => ({x: anchor.x + (u.x * distance + n.x * offset) * size,
      y: anchor.y + (u.y * distance + n.y * offset) * size});
    const polygon = [p(3, -.8), p(9, -1.5), p(9, 1.5), p(3, .8)];
    clip += ` M ${polygon[0].x} ${polygon[0].y}` + polygon.slice(1).map(p => ` L ${p.x} ${p.y}`).join("") + " Z";
  }
  return {anchor, direction, clip, curves};
}
export function splitLeader(leader, endpoint, segment, t) {
  const result = JSON.parse(JSON.stringify(leader)), vertices = leaderVertices(result, endpoint);
  const a = vertices[segment], b = vertices[segment + 1];
  const p = leaderLerp(a, leaderAdd(a, a.out), t), q = leaderLerp(leaderAdd(a, a.out), leaderAdd(b, b.in), t),
    r = leaderLerp(leaderAdd(b, b.in), b, t);
  const s = leaderLerp(p, q, t), u = leaderLerp(q, r, t), v = leaderLerp(s, u, t);
  a.out = leaderSub(p, a);
  if (segment + 1 === result.nodes.length) result.end_handle = leaderSub(r, b);
  else b.in = leaderSub(r, b);
  result.nodes.splice(segment + 1, 0, {...v, in: leaderSub(s, v), out: leaderSub(u, v)});
  return result;
}

const leaderSegmentDistance = (p, a, b) => {
  const v = leaderSub(b, a), length = v.x ** 2 + v.y ** 2;
  const t = length ? Math.max(0, Math.min(1, ((p.x - a.x) * v.x + (p.y - a.y) * v.y) / length)) : 0;
  const q = leaderLerp(a, b, t);
  return Math.hypot(p.x - q.x, p.y - q.y);
};
export function leaderFromStroke(stroke, attachment, width, height, zoom = 1) {
  if (!stroke.length) return null;
  // Distances use drawing pixels; screen zoom only sets the fitting tolerance.
  const points = [], spacing = 2 / zoom, tolerance = 3 / zoom;
  for (const p of stroke) {
    const q = {x: p.x * width, y: p.y * height}, previous = points.at(-1);
    if (!previous || Math.hypot(q.x - previous.x, q.y - previous.y) >= spacing) points.push(q);
  }
  const last = stroke.at(-1), end = {x: last.x * width, y: last.y * height};
  if (points.length && Math.hypot(end.x - points.at(-1).x, end.y - points.at(-1).y) > .01) points.push(end);
  if (points.length < 2) return null;
  let length = 0;
  for (let i = 1; i < points.length; i++) length += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
  if (length * zoom < 12) return null;
  // Average small hand tremors, keeping both endpoints and intentional loops.
  const smooth = points.map((p, i) => i && i < points.length - 1
    ? {x: (points[i - 1].x + 2 * p.x + points[i + 1].x) / 4, y: (points[i - 1].y + 2 * p.y + points[i + 1].y) / 4} : p);
  let indices;
  for (let error = tolerance; ; error *= 1.35) {
    const kept = new Set([0, smooth.length - 1]), ranges = [[0, smooth.length - 1]];
    while (ranges.length) {
      const [a, b] = ranges.pop(); let farthest = error, index = null;
      for (let i = a + 1; i < b; i++) {
        const d = leaderSegmentDistance(smooth[i], smooth[a], smooth[b]);
        if (d > farthest) {farthest = d; index = i;}
      }
      if (index !== null) {kept.add(index); ranges.push([a, index], [index, b]);}
    }
    indices = [...kept].sort((a, b) => a - b);
    if (indices.length <= 65) break;
  }
  const build = () => {
    const vertices = indices.map(i => ({...smooth[i], in: {x: 0, y: 0}, out: {x: 0, y: 0}}));
    const times = vertices.slice(1).map((p, i) => Math.sqrt(Math.hypot(p.x - vertices[i].x, p.y - vertices[i].y)));
    const tangent = (i) => {
      if (!i) return leaderSub(vertices[1], vertices[0]);
      if (i === vertices.length - 1) return leaderSub(vertices[i], vertices[i - 1]);
      const before = leaderSub(vertices[i], vertices[i - 1]), after = leaderSub(vertices[i + 1], vertices[i]),
        a = Math.max(times[i - 1], .0001), b = Math.max(times[i], .0001);
      return {x: before.x / a - (before.x + after.x) / (a + b) + after.x / b,
        y: before.y / a - (before.y + after.y) / (a + b) + after.y / b};
    };
    for (let i = 0; i < vertices.length - 1; i++) {
      const a = tangent(i), b = tangent(i + 1), h = times[i];
      vertices[i].out = {x: a.x * (i ? h : 1) / 3, y: a.y * (i ? h : 1) / 3};
      vertices[i + 1].in = {x: -b.x * (i + 1 < vertices.length - 1 ? h : 1) / 3,
        y: -b.y * (i + 1 < vertices.length - 1 ? h : 1) / 3};
    }
    return vertices;
  };
  // Refine only bends where the fitted curve loses the drawn shape. Straight
  // stretches need no extra nodes, regardless of how many pointer samples arrive.
  let vertices;
  for (;;) {
    vertices = build(); let worst = tolerance * 1.5, extra = null;
    for (let s = 0; s < vertices.length - 1; s++) {
      const samples = Array.from({length: 25}, (_, i) => leaderCurvePoint(vertices[s], vertices[s + 1], i / 24));
      for (let i = indices[s] + 1; i < indices[s + 1]; i++) {
        const d = Math.min(...samples.slice(1).map((p, j) => leaderSegmentDistance(smooth[i], samples[j], p)));
        if (d > worst) {worst = d; extra = i;}
      }
    }
    if (extra === null || indices.length >= 65) break;
    indices.push(extra); indices.sort((a, b) => a - b);
  }
  // A cubic can follow a bend with fewer anchors than its polyline needs.
  // Remove redundant anchors only when both the drawn and fitted paths stay
  // close over the corresponding interval, preserving crossings and loops.
  const fits = candidate => {
    for (let s = 0; s < candidate.length - 1; s++) {
      const samples = Array.from({length: 25}, (_, i) => leaderCurvePoint(candidate[s], candidate[s + 1], i / 24));
      const trace = smooth.slice(indices[s], indices[s + 1] + 1);
      for (const [path, target] of [[trace, samples], [samples, trace]]) for (const p of path) {
        let distance = Infinity;
        for (let i = 1; i < target.length; i++) distance = Math.min(distance, leaderSegmentDistance(p, target[i - 1], target[i]));
        if (distance > tolerance * 1.5) return false;
      }
    }
    return true;
  };
  for (let i = 1; i < indices.length - 1;) {
    const previous = indices, next = indices.filter((_, j) => j !== i);
    indices = next; const candidate = build();
    if (fits(candidate)) vertices = candidate;
    else {indices = previous; i++;}
  }
  const normalized = p => ({x: p.x / width, y: p.y / height});
  // Stored leaders run from the arrow tip to the label, opposite to drawing.
  const reversed = vertices.reverse().map(p => ({...normalized(p), in: normalized(p.out), out: normalized(p.in)}));
  return {enabled: true, attachment: {...attachment}, nodes: reversed.slice(0, -1), end_handle: reversed.at(-1).in};
}

function render({ model, el, readOnly = false, pdfMode = false }) {
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
  root.classList.toggle("gp-pdf", pdfMode);
  // Keep JupyterLab's cell shortcuts from consuming keys intended for the widget.
  root.setAttribute("data-lm-suppress-shortcuts", "true");
  const view = Math.random().toString(36).slice(2);
  let sequence = 0, active = null, mode = "pan", zoom = 1, panX = 24, panY = 24, disposed = false;
  let lastBackground = "", formId = null, copySource = null, sizeDraft = null, dialogAnchor = null;
  let headingDraft = null;
  let historyBusy = false, historyEditGroup = null, historyGroupSequence = 0;
  let cropDraft = null, canvasPending = null;
  let drawingDraft = null, drawingPreview = null, drawingPending = false, objectsBusy = false;
  const scaleDrafts = new Map();
  const canvasBounds = () => cropDraft || canvasPending || state().canvas_bounds || CANVAS_DEFAULTS;
  let leaderEdit = null, leaderNode = null, leaderPlacement = null;
  const leaderDrafts = new Map();
  const leaderElements = new Map();
  let leaderClipSequence = 0;
  let slidingDraft = null, overlaySelected = null;
  const selectedOverlays = new Set(), lockDrafts = new Map();
  let overlayClickHandled = null;
  let colourDraft = null, colourEditType = null;
  let insulationWidgetDraft = null;
  let commentWidgetDraft = null, referenceWidgetDraft = null;
  let textAddBusy = false;
  const textElements = new Map(), textDrafts = new Map(), textDeleting = new Set();
  let layoutDraft = null, panelDrag = null;
  const layout = () => ({...LAYOUT_DEFAULTS, ...(layoutDraft || state().layout)});
  const overlayPositions = new Map(), pendingOverlayPositions = new Map(), slidingDirty = new Set();
  const slidingNames = new Set(["glid_x", "glid_y", "V_Ed_EQU", "glid_mu", "glid_L"]);
  const bearingOnlyNames = new Set(["b", "l", "l_override", "L_vagg_minst_1", "L_vagg", "t", "d", "e_b_plac", "e_l_plac", "F_vy", "F_hb", "F_hl", "M_insp_b", "M_insp_l",
    "F_vy_bruk", "M_insp_b_bruk", "M_insp_l_bruk", "c_prime", "c_uk", "gamma", "gamma_prime", "phi_k",
    "delta_h", "beta", "alpha", "eta", "gamma_m", "gamma_m0", "gamma_Rd", "f_d_brott", "f_d_bruk"]);
  const insulationNames = new Set(["isolering", "isolerprodukt", "f_d_brott", "f_d_bruk"]);
  const sliding = () => slidingDraft || state().sliding || {enabled: false, check_x: false, check_y: false, placements: {}};
  const colour = () => colourDraft || state().colour_grouping || COLOUR_DEFAULTS;
  const insulationWidget = () => insulationWidgetDraft || state().insulation_widget || INSULATION_WIDGET_DEFAULTS;
  const commentWidget = () => commentWidgetDraft || state().comment_widget || COMMENT_WIDGET_DEFAULTS;
  const referenceWidget = () => referenceWidgetDraft || state().reference_widget || REFERENCE_WIDGET_DEFAULTS;
  const positions = new Map(), pendingPositions = new Map();
  const pending = new Map(), dirty = new Set(), inputs = new Map(), edits = new Map(), drafts = new Map();
  const groupingTags = () => state().tags.filter(tag => !(drafts.get(tag.id)?.values.inaktiv ?? tag.values.inaktiv));
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
  const background = () => drawingPreview?.background || model.get("background") || {};
  const drawingLayout = () => drawingDraft || state().drawing_layout || {x: 0, y: 0, scale: 1};
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
    if (historyBusy && !["undo", "redo"].includes(action)) return;
    const request = ++sequence;
    const field = document.activeElement;
    const typing = field?.closest?.(".an-grundplan") === root && (field.tagName?.toLowerCase() === "textarea"
      || field.tagName?.toLowerCase() === "input" && !["checkbox", "radio", "range", "file", "button"].includes(field.type));
    const coalesce = typing && (["heading", "sliding", "colour_grouping"].includes(action)
      || action === "update" && !("x" in payload || "y" in payload)
      || action === "text_update" && !["x", "y", "size", "width"].some(key => key in payload.changes)
      || action === "bulk_update" && field.closest(".gp-table-section"));
    if (coalesce) {
      const key = action + ":" + (payload.id || payload.ids?.join(",") || "");
      if (!historyEditGroup || historyEditGroup.field !== field || historyEditGroup.key !== key)
        historyEditGroup = {field, key, token: view + ":" + ++historyGroupSequence};
    } else historyEditGroup = null;
    pending.set(request, onDone);
    showHistory();
    model.send({ action, ...payload, ...(coalesce ? {history_group: historyEditGroup.token} : {}), request, view }, undefined, buffers);
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
      if (input === title) { input.type = "text"; input.maxLength = 200; }
      else input.rows = 1;
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
  const historyControls = node("span", "gp-history-controls");
  const historyTooltip = node("span", "gp-history-tooltip");
  historyTooltip.id = "gp-history-tooltip-" + view;
  historyTooltip.setAttribute("role", "tooltip"); historyTooltip.hidden = true;
  let historyTooltipTimer = null, historyHover = null;
  const macKeys = /mac|iphone|ipad/i.test(globalThis.navigator?.platform || "");
  const historyButtons = new Map();
  function hideHistoryTooltip() {
    clearTimeout(historyTooltipTimer); historyTooltipTimer = null;
    historyTooltip.hidden = true;
    for (const b of historyButtons.values()) b.removeAttribute("aria-describedby");
  }
  function historyCaption(action) {
    const label = action === "undo" ? "Ångra" : "Gör om", description = state().history?.[action];
    const shortcut = macKeys ? action === "undo" ? "⌘Z" : "⇧⌘Z" : action === "undo" ? "Ctrl+Z" : "Ctrl+Shift+Z / Ctrl+Y";
    return (description ? label + ": " + description : action === "undo" ? "Inget att ångra" : "Inget att göra om") + " · " + shortcut;
  }
  function showHistory() {
    for (const [action, b] of historyButtons) {
      b.disabled = !state().history?.[action] || historyBusy || !!pending.size || !!drawingDraft || !!cropDraft
        || !!canvasPending || !!leaderPlacement || !!panelDrag;
      b.setAttribute("aria-description", historyCaption(action));
    }
    if (historyHover && !historyTooltip.hidden) historyTooltip.textContent = historyCaption(historyHover);
  }
  function scheduleHistoryTooltip(action, control) {
    hideHistoryTooltip(); historyHover = action;
    historyTooltipTimer = setTimeout(() => {
      if (disposed || historyHover !== action) return;
      const rect = control.getBoundingClientRect();
      historyTooltip.textContent = historyCaption(action);
      historyTooltip.style.left = Math.max(8, rect.left) + "px";
      historyTooltip.style.top = rect.top + rect.height + 7 + "px";
      historyTooltip.hidden = false;
      historyButtons.get(action).setAttribute("aria-describedby", historyTooltip.id);
    }, 600);
  }
  function runHistory(action) {
    if (readOnly || historyBusy || pending.size || drawingDraft || cropDraft || canvasPending || leaderPlacement) return;
    if (drag || panelDrag) {cancelDrag(); endPanelDrag(); showHistory(); return;}
    if (!state().history?.[action]) return;
    hideHistoryTooltip(); historyEditGroup = null; historyBusy = true;
    cancelDrag(); closeDialog(); closeBulk(); setMode("pan"); copySource = null;
    for (const values of [dirty, drafts, edits, slidingDirty, positions, pendingPositions, overlayPositions,
      pendingOverlayPositions, leaderDrafts, lockDrafts, scaleDrafts, textDrafts]) values.clear();
    leaderEdit = leaderNode = null;
    headingDraft = sizeDraft = slidingDraft = colourDraft = colourEditType = layoutDraft = calibrationDraft = null;
    insulationWidgetDraft = commentWidgetDraft = referenceWidgetDraft = null;
    formId = null; bulkSignature = "";
    command(action, {}, [], reply => {
      historyBusy = false;
      update(); viewport.focus({preventScroll: true});
      showMessage(reply.ok ? (action === "undo" ? "Ångrat: " : "Gjort om: ") + reply.description : reply.error, !reply.ok);
    });
  }
  for (const [action, label] of [["undo", "Ångra"], ["redo", "Gör om"]]) {
    const control = node("span", "gp-history-control"), b = button("", () => runHistory(action), "gp-history-button gp-" + action);
    b.setAttribute("aria-label", label);
    b.setAttribute("aria-keyshortcuts", action === "undo" ? "Meta+Z Control+Z" : "Meta+Shift+Z Control+Shift+Z Control+Y");
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M9 4 4 9 9 14 M4 9h10a6 6 0 0 1 0 12h-3");
    if (action === "redo") path.setAttribute("transform", "translate(24 0) scale(-1 1)");
    icon.append(path); b.append(icon); control.append(b); historyControls.append(control); historyButtons.set(action, b);
    for (const event of ["pointerenter", "pointermove", "focusin"])
      control.addEventListener(event, () => scheduleHistoryTooltip(action, control));
    for (const event of ["pointerleave", "focusout", "pointerdown"])
      control.addEventListener(event, () => {historyHover = null; hideHistoryTooltip();});
  }
  if (!readOnly) {toolbar.append(historyControls, node("span", "gp-separator")); root.append(historyTooltip);}
  root.addEventListener("focusin", () => {historyEditGroup = null;});
  root.addEventListener("focusout", () => {historyEditGroup = null;});
  root.addEventListener("pointerdown", hideHistoryTooltip, true);
  root.addEventListener("wheel", hideHistoryTooltip, true);
  document.addEventListener("scroll", hideHistoryTooltip, true);
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
  const loadDrawing = button("Redigera ritningsunderlag", beginDrawingEdit);
  const drawingBar = node("section", "gp-drawing-bar"); drawingBar.hidden = true;
  drawingBar.setAttribute("aria-label", "Redigera ritningsunderlag");
  const drawingUpdate = button("Uppdatera ritningsunderlag", () => fileInput.click());
  const drawingScaleLabel = node("label", "gp-drawing-scale", "Skala ");
  const drawingScaleInput = node("input"); drawingScaleInput.type = "number";
  drawingScaleInput.min = "10"; drawingScaleInput.max = "1000"; drawingScaleInput.step = "any";
  drawingScaleInput.required = true;
  drawingScaleInput.setAttribute("aria-label", "Ritningsunderlagets skala i procent");
  drawingScaleInput.addEventListener("input", () => {
    const scale = Number(drawingScaleInput.value) / 100;
    const valid = drawingScaleInput.value !== "" && Number.isFinite(scale) && scale >= .1 && scale <= 10;
    drawingScaleInput.setCustomValidity(valid ? "" : "Ange 10–1000 procent.");
    if (drawingDraft && valid) {drawingDraft = {...drawingDraft, scale}; showCanvas();}
    else drawingApply.disabled = true;
  });
  drawingScaleLabel.append(drawingScaleInput, node("span", "", "%"));
  const drawingApply = button("Klar", () => finishDrawingEdit(true), "gp-primary");
  const drawingCancel = button("Avbryt", () => finishDrawingEdit(false));
  drawingBar.append(drawingUpdate, drawingScaleLabel, drawingApply, drawingCancel,
    node("span", "gp-field-note", "Dra underlaget eller dess hörn. Skalning och uppdatering kräver ny måttkalibrering."));
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
    selected.clear(); selectedOverlays.clear(); overlaySelected = null;
    tableAnchor = null; bulkSignature = ""; closeBulk(); renderMarkers(); renderSlidingGeometry(); showSelection();
  });
  const lockMany = button("Lås placering", () => setPlacementLock(true));
  const unlockMany = button("Lås upp", () => setPlacementLock(false));
  selectionBar.append(selectionCount);
  const objectScaleLabel = node("label", "gp-object-scale", "Skala urval ");
  const objectScaleInput = node("input"); objectScaleInput.type = "number";
  objectScaleInput.value = "100"; objectScaleInput.min = "10"; objectScaleInput.max = "1000";
  objectScaleInput.setAttribute("aria-label", "Skala markerade objekt i procent");
  objectScaleInput.title = "Relativt urvalets nuvarande storlek. Låsta objekt behåller sin storlek och placering.";
  const objectScaleApply = button("Skala", () => {
    const factor = Number(objectScaleInput.value) / 100;
    if (!Number.isFinite(factor) || factor < .1 || factor > 10) {showMessage("Ange 10–1000 procent.", true); return;}
    const starts = selectedTransformStarts(), frame = objectSelectionFrame(starts);
    if (!frame) return;
    scaleObjects(starts, frame, factor); saveObjectTransforms(starts);
  });
  objectScaleLabel.append(objectScaleInput, node("span", "", "%"));
  const orderButtons = [ ["Flytta fram", "forward"], ["Flytta bak", "backward"], ["Längst fram", "front"], ["Längst bak", "back"] ]
    .map(([label, operation]) => button(label, () => changeOrder(operation)));
  if (!readOnly) selectionBar.append(editMany, lockMany, unlockMany, objectScaleLabel, objectScaleApply, ...orderButtons);
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
  const commentWidgetToggle = button("Lägg till kommentarer", () => {
    const patch = {enabled: !commentWidget().enabled};
    if (!patch.enabled) {cancelDrag(); overlaySelected = null;}
    const draft = {...commentWidget(), ...patch}; commentWidgetDraft = draft; update();
    command("comment_widget", {settings: patch}, [], reply => {
      if (commentWidgetDraft === draft) {commentWidgetDraft = null; update();}
      if (!reply.ok) showMessage(reply.error, true);
    });
  });
  commentWidgetToggle.title = "Visa objektkommentarer i en flyttbar och skalbar ruta. Senaste placering och storlek behålls.";
  if (!readOnly) toolbar.append(commentWidgetToggle);
  const referenceToggle = button("Referens", () => {
    const patch = {enabled: !referenceWidget().enabled};
    if (!patch.enabled) {cancelDrag(); overlaySelected = null;}
    const draft = {...referenceWidget(), ...patch}; referenceWidgetDraft = draft; update();
    command("reference_widget", {settings: patch}, [], reply => {
      if (referenceWidgetDraft === draft) {referenceWidgetDraft = null; update();}
      if (!reply.ok) showMessage(reply.error, true);
    });
  });
  referenceToggle.title = "Automatiska referensgrupper med mått och laster för vidare dimensionering i Foundation.";
  if (!readOnly) toolbar.append(referenceToggle);
  const textAddButtons = [];
  for (const [kind, caption] of [["heading", "Lägg till rubrik"], ["date", "Lägg till datum (åå/mm/dd)"]]) {
    const add = button(caption, () => {
      if (textAddBusy || !background().url) return;
      cancelDrag(); closeDialog(); closeBulk(); setMode("pan");
      textAddBusy = true; showTextObjects();
      // Place each object in the visible part of the drawing, then let it be dragged.
      const rect = sheet.getBoundingClientRect(), bounds = viewport.getBoundingClientRect();
      const x = Math.max(canvasBounds().left, Math.min(canvasBounds().right - .05, (Math.max(bounds.left, rect.left + canvasBounds().left * rect.width) + 35 - rect.left) / rect.width));
      const y = Math.max(canvasBounds().top, Math.min(canvasBounds().bottom - .05, (Math.max(bounds.top, rect.top + canvasBounds().top * rect.height) + (kind === "heading" ? 35 : 85) - rect.top) / rect.height));
      // Copy the visible heading, including any typing awaiting a kernel reply.
      const contents = kind === "heading" ? {text: title.value, subtitle: subtitle.value,
        width: Math.max(80, Math.min(10000, subtitle.clientWidth + 8)), size: overlaySize("text:", 20 / zoom)} : {};
      command("text_add", {kind, x, y, ...contents}, [], reply => {
        textAddBusy = false;
        if (reply.ok) overlaySelected = "text:" + reply.id;
        showTextObjects();
        if (reply.ok) chooseOverlay("text:" + reply.id);
        if (reply.ok) showMessage((kind === "heading" ? "Rubrik och underrubrik kopierade till ritningen." : "Datum tillagt.")
          + " Dra texten för att flytta, dra hörnet för att skala och klicka på Redigera för att ändra texten.");
      });
    });
    add.title = kind === "heading" ? "Kopiera befintlig rubrik och underrubrik till ritningen." : "Lägg till ett flyttbart och skalbart datum på ritningen.";
    textAddButtons.push(add);
    if (!readOnly) toolbar.append(add);
  }
  const colourControls = node("section", "gp-colour-controls");
  colourControls.hidden = true;
  colourControls.setAttribute("aria-label", "Inställningar för färggruppering");
  const colourCategories = node("div", "gp-colour-row");
  const colourCategoryButtons = new Map(), colourPhaseButtons = new Map(), colourTypeButtons = new Map();
  colourCategories.append(node("span", "gp-colour-caption", "Gruppera efter"));
  const categoryChoices = node("div", "gp-colour-choices");
  for (const [category, caption] of Object.entries(COLOUR_CATEGORIES)) {
    const choice = button(caption, () => {
      const current = selectedColourCategories(colour());
      const categories = Object.keys(COLOUR_CATEGORIES).filter(name =>
        name === category ? !current.includes(name) : current.includes(name));
      if (categories.length) setColour({categories});
    });
    colourCategoryButtons.set(category, choice); categoryChoices.append(choice);
  }
  const colourLegendChoice = node("label", "gp-colour-legend-choice");
  const colourLegendCheck = node("input"); colourLegendCheck.type = "checkbox";
  colourLegendCheck.setAttribute("aria-label", "Visa färglegend");
  colourLegendCheck.addEventListener("change", () => setColour({show_legend: colourLegendCheck.checked}));
  colourLegendChoice.append(colourLegendCheck, node("span", "", "Visa legend"));
  const colourOnlyHChoice = node("label", "gp-colour-inclusion-choice");
  const colourOnlyHCheck = node("input"); colourOnlyHCheck.type = "checkbox";
  colourOnlyHCheck.setAttribute("aria-label", "Inkludera sulor med endast H-stabilitet i färggrupperingen");
  const colourOnlyHNote = node("p", "gp-colour-hint gp-colour-inclusion-note");
  colourOnlyHNote.id = "gp-colour-only-h-" + view;
  colourOnlyHCheck.setAttribute("aria-describedby", colourOnlyHNote.id);
  colourOnlyHCheck.addEventListener("change", () => {
    if (!colourOnlyHCheck.disabled) setColour({include_only_h: colourOnlyHCheck.checked});
  });
  colourOnlyHChoice.append(colourOnlyHCheck, node("span", "", "Endast H"));
  colourCategories.append(categoryChoices, colourOnlyHChoice, colourLegendChoice);
  const colourLoadOptions = node("div", "gp-colour-row");
  colourLoadOptions.append(node("span", "gp-colour-caption", "Lastfall"));
  const phaseChoices = node("div", "gp-colour-choices");
  for (const [phase, caption] of Object.entries(COLOUR_PHASES)) {
    const choice = button(caption, () => setColour({phase}));
    colourPhaseButtons.set(phase, choice); phaseChoices.append(choice);
  }
  const typeChoices = node("div", "gp-colour-choices");
  for (const [kind, caption] of [["pad", "Punktlaster [kN]"], ["wall", "Linjelaster [kN/m]"]]) {
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
  colourControls.append(colourCategories, colourLoadOptions, colourBoundsRow, colourOnlyHNote, colourHint, colourSwatches);
  const cancelCopy = button("Avbryt kopiering", () => {
    setMode("pan");
    showMessage("Kopieringen avbröts.");
  });
  cancelCopy.hidden = true;
  const sizeLabel = node("label", "gp-size-label", "Etikettstorlek ");
  sizeLabel.title = "Grundstorlek vid 100 % ritningszoom. Etiketterna följer ritningens zoom.";
  const sizeInput = node("input");
  sizeInput.type = "range";
  sizeInput.min = "20";
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
  const cropTool = button("Beskär", () => {
    if (readOnly || cropDraft || canvasPending || !background().url) return;
    cancelDrag(); closeDialog(); closeBulk(); setMode("pan");
    selected.clear(); selectedOverlays.clear(); overlaySelected = null;
    cropDraft = {...canvasBounds()}; showSelection(); renderMarkers(); renderSlidingGeometry();
    update(); fit(); viewport.focus({preventScroll: true});
    showMessage("Dra de fyra kanterna eller hörnen. Utåt ger mer marginal, inåt beskär. Klar sparar ramen; Escape avbryter.");
  });
  cropTool.title = "Justera ritningsytans fyra kanter och marginaler.";
  if (!readOnly) toolbar.append(cropTool);
  const cropBar = node("section", "gp-crop-bar"); cropBar.hidden = true;
  cropBar.setAttribute("aria-label", "Beskär ritningsyta");
  const cropHint = node("span", "gp-crop-hint", "Dra kanter eller hörn för att ändra marginalerna.");
  const cropSize = node("output", "gp-crop-size");
  const cropApply = button("Klar", () => finishCrop(true), "gp-primary");
  const cropCancel = button("Avbryt", () => finishCrop(false));
  const cropReset = button("Återställ till original", () => {
    cancelDrag(); cropDraft = {...CANVAS_DEFAULTS}; showCanvas(); fit();
  });
  cropBar.append(cropHint, cropSize, cropApply, cropCancel, cropReset);
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
  const paper = node("div", "gp-paper");
  const cropFrame = node("div", "gp-crop-frame"); cropFrame.hidden = true;
  for (const edge of ["left", "top", "right", "bottom"]) {
    const hit = node("div", "gp-crop-edge gp-crop-edge-" + edge);
    hit.dataset.edge = edge; cropFrame.append(hit);
  }
  for (const edge of ["left", "top", "right", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"]) {
    const handle = button("", () => {}, "gp-crop-handle gp-crop-" + edge);
    handle.dataset.edge = edge;
    handle.setAttribute("aria-label", "Justera " + ({left: "vänster kant", right: "höger kant", top: "övre kant", bottom: "nedre kant",
      "top-left": "övre vänstra hörnet", "top-right": "övre högra hörnet", "bottom-left": "nedre vänstra hörnet", "bottom-right": "nedre högra hörnet"}[edge]));
    handle.addEventListener("keydown", event => {
      if (!cropDraft || !event.key.startsWith("Arrow")) return;
      event.preventDefault(); event.stopPropagation();
      adjustCrop(edge, {...cropDraft}, (event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0) * (event.shiftKey ? .02 : .002),
        (event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0) * (event.shiftKey ? .02 : .002));
    });
    cropFrame.append(handle);
  }
  const drawingFrame = node("div", "gp-drawing-frame"); drawingFrame.hidden = true;
  for (const corner of ["top-left", "top-right", "bottom-left", "bottom-right"]) {
    const handle = button("", () => {}, "gp-drawing-handle gp-crop-" + corner);
    handle.dataset.corner = corner;
    handle.setAttribute("aria-label", "Skala ritningsunderlag från " + corner);
    drawingFrame.append(handle);
  }
  const objectFrame = node("div", "gp-object-frame"); objectFrame.hidden = true;
  const objectHandle = button("", () => {}, "gp-object-handle");
  objectHandle.setAttribute("aria-label", "Skala markerade objekt"); objectFrame.append(objectHandle);
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
  const axesButton = button("", event => selectOverlayClick("symbol", event), "gp-axis-symbol gp-sliding-handle");
  axesButton.setAttribute("aria-label", "Globalt koordinatsystem: X_g åt höger, Y_g uppåt." + (readOnly ? "" : " Dra för att flytta."));
  const svgNode = (name, attributes, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const measurementOverlay = node("div", "gp-measurement-overlay");
  const leaderSvg = svgNode("svg", {class: "gp-leaders", "aria-label": "Etiketternas hänvisningslinjer"});
  const leaderHandles = svgNode("svg", {class: "gp-leader-handles", "aria-label": "Redigera hänvisningslinje"});
  const leaderResizeObserver = new ResizeObserver(() => renderLeaders());
  const patternHosts = new Map();
  const patternObserver = new ResizeObserver(entries => {
    for (const {target} of entries) drawGroupPattern(target);
  });
  function drawGroupPattern(host) {
    const entry = patternHosts.get(host);
    if (!entry) return;
    const {svg, group, compact} = entry, width = host.clientWidth, height = host.clientHeight;
    const scale = compact ? 1 : (sizeDraft ?? state().label_size ?? 100) / 100 * zoom;
    const geometry = colourPatternGeometry(group.pattern, width, height, scale, compact, group.pattern_variant);
    // Darker marks on light colours, lighter marks on the deeper Set3 colours.
    const channels = [1, 3, 5].map(i => parseInt(group.background.slice(i, i + 2), 16));
    const light = channels.map(c => {const n = c / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4;});
    const bright = light[0] * .2126 + light[1] * .7152 + light[2] * .0722 > .55;
    const target = bright ? [25, 52, 61] : [255, 255, 255], weight = bright ? .23 : .48;
    const ink = "#" + channels.map((c, i) => Math.round(c * (1 - weight) + target[i] * weight).toString(16).padStart(2, "0")).join("");
    svg.setAttribute("viewBox", `0 0 ${width || 1} ${height || 1}`);
    svg.dataset.pitch = String(geometry.pitch);
    svg.replaceChildren(...geometry.shapes.map(({tag, ...attributes}) => svgNode(tag,
      {...attributes, fill: tag === "circle" ? ink : "none", stroke: tag === "path" ? ink : "none"})));
  }
  function paintGroupPattern(host, group, compact = false) {
    host.dataset.pattern = group.pattern;
    if (group.pattern === "plain") return;
    const svg = svgNode("svg", {class: "gp-group-pattern", "aria-hidden": "true", focusable: "false", preserveAspectRatio: "none"});
    host.append(svg);
    patternHosts.set(host, {svg, group, compact});
  }
  function refreshGroupPatterns(observe = false) {
    if (observe) patternObserver.disconnect();
    for (const host of patternHosts.keys()) {
      if (host.closest(".an-grundplan") !== root) {patternHosts.delete(host); continue;}
      drawGroupPattern(host);
      if (observe) patternObserver.observe(host);
    }
  }
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
  const slidingHeader = button("Glidningskontroll", event => {
    selectOverlayClick("legend", event);
  }, "gp-sliding-header gp-sliding-handle");
  slidingHeader.title = readOnly ? "Globala glidningsresultat" : "Dra rubriken för att flytta resultatrutan";
  slidingHeader.setAttribute("aria-label", "Glidningskontroll." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const slidingBody = node("div", "gp-sliding-body");
  slidingBody.setAttribute("aria-live", "polite");
  const legendResize = button("", () => {}, "gp-overlay-resize gp-legend-resize");
  legendResize.setAttribute("aria-label", "Ändra glidningsrutans storlek. Dra hörnet eller använd plus och minus.");
  legendResize.title = "Dra hörnet för att förstora eller förminska hela rutan proportionellt";
  slidingLegend.addEventListener("click", event => selectOverlayBody("legend", event));
  slidingLegend.append(slidingHeader, node("p", "gp-sliding-note", "X och Y kontrolleras var för sig"), slidingBody, legendResize);
  const colourLegend = node("section", "gp-sliding-overlay gp-colour-legend");
  colourLegend.dataset.kind = "colour";
  colourLegend.setAttribute("aria-label", "Legend för färggruppering");
  const colourHeader = button("Färggruppering", event => {
    selectOverlayClick("colour", event);
  }, "gp-sliding-header gp-sliding-handle");
  colourHeader.setAttribute("aria-label", "Färggruppering." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const colourLegendBody = node("div", "gp-colour-legend-body");
  const colourResize = button("", () => {}, "gp-overlay-resize gp-colour-resize");
  colourResize.setAttribute("aria-label", "Ändra färglegendens storlek. Dra hörnet eller använd plus och minus.");
  colourResize.title = "Dra hörnet för att förstora eller förminska proportionellt";
  colourLegend.addEventListener("click", event => selectOverlayBody("colour", event));
  colourLegend.append(colourHeader, colourLegendBody, colourResize);
  const insulationLegend = node("section", "gp-sliding-overlay gp-insulation-widget");
  insulationLegend.dataset.kind = "insulation"; insulationLegend.setAttribute("aria-label", "Isolering – sammanställning av sulor");
  const insulationHeader = button("Isolering", event => {
    selectOverlayClick("insulation", event);
  }, "gp-sliding-header gp-sliding-handle");
  insulationHeader.setAttribute("aria-label", "Isolering." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const insulationBody = node("div", "gp-insulation-widget-body");
  const insulationResize = button("", () => {}, "gp-overlay-resize gp-insulation-resize");
  insulationResize.setAttribute("aria-label", "Ändra isoleringswidgetens storlek. Dra hörnet eller använd plus och minus.");
  insulationResize.title = "Dra hörnet för att förstora eller förminska proportionellt";
  insulationLegend.addEventListener("click", event => selectOverlayBody("insulation", event));
  insulationLegend.append(insulationHeader, insulationBody, insulationResize);
  const commentLegend = node("section", "gp-sliding-overlay gp-sliding-legend gp-comment-widget");
  commentLegend.dataset.kind = "comments"; commentLegend.setAttribute("aria-label", "Kommentarer – sammanställning av sulor");
  const commentHeader = button("Kommentarer", event => {
    selectOverlayClick("comments", event);
  }, "gp-sliding-header gp-sliding-handle");
  commentHeader.setAttribute("aria-label", "Kommentarer." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const commentBody = node("div", "gp-comment-widget-body");
  const commentResize = button("", () => {}, "gp-overlay-resize gp-comment-resize");
  commentResize.setAttribute("aria-label", "Ändra kommentarwidgetens storlek. Dra hörnet eller använd plus och minus.");
  commentResize.title = "Dra hörnet för att förstora eller förminska proportionellt";
  commentLegend.addEventListener("click", event => selectOverlayBody("comments", event));
  commentLegend.append(commentHeader, commentBody, commentResize);
  const referenceLegend = node("section", "gp-sliding-overlay gp-sliding-legend gp-reference-widget");
  referenceLegend.dataset.kind = "reference";
  referenceLegend.setAttribute("aria-label", "Referens – automatiska grupper för Foundation");
  const referenceHeader = button("Referens", event => {
    selectOverlayClick("reference", event);
  }, "gp-sliding-header gp-sliding-handle");
  referenceHeader.setAttribute("aria-label", "Referens." + (readOnly ? "" : " Dra för att flytta eller använd piltangenterna."));
  const referenceBody = node("div", "gp-reference-body");
  const referenceResize = button("", () => {}, "gp-overlay-resize");
  referenceResize.setAttribute("aria-label", "Ändra Referensens storlek. Dra hörnet eller använd plus och minus.");
  referenceLegend.addEventListener("click", event => selectOverlayBody("reference", event));
  referenceLegend.append(referenceHeader, referenceBody, referenceResize);
  overlays.append(axesOverlay, slidingLegend, colourLegend, insulationLegend, commentLegend, referenceLegend);
  sheet.append(picture, leaderSvg, markers, overlays, leaderHandles);
  paper.append(sheet);
  viewport.append(paper, selectionBox, measurementOverlay, cropFrame, drawingFrame, objectFrame);
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
  const leaderSection = node("details", "gp-leader-section");
  leaderSection.append(node("summary", "", "Etikett"));
  const leaderChoice = node("label", "gp-leader-choice");
  const leaderCheck = node("input"); leaderCheck.type = "checkbox";
  leaderCheck.setAttribute("aria-label", "Hänvisningslinje");
  leaderChoice.append(leaderCheck, node("span", "", "Hänvisningslinje"));
  const leaderEditButton = button("Redigera linje", () => {
    const id = active; if (!id) return;
    beginLeaderEdit(id);
  });
  const leaderRedrawButton = button("Rita om spline", () => {if (active) beginLeaderDraw(active);});
  leaderRedrawButton.title = "Rita en ny bana från etikettens anslutning. Escape behåller den gamla linjen.";
  leaderCheck.addEventListener("change", () => {
    const tag = current(); if (!tag) return;
    const saved = leaderFor(tag);
    if (leaderCheck.checked && !saved) {
      beginLeaderDraw(tag.id);
    } else if (saved) {
      if (!leaderCheck.checked) {leaderEdit = leaderNode = null;}
      saveLeader(tag.id, {...saved, enabled: leaderCheck.checked});
    }
  });
  leaderSection.append(leaderChoice, leaderEditButton, leaderRedrawButton);
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
  else form.append(labelRow, leaderSection, basis, sketchToggle, sketchSlot, fieldsBox, results, footer);
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
    ["over", "U > 100 %"], ["horizontal", "Endast H-stabilitet"], ["inactive", "Inaktiv"], ["stale", "Uppdaterar"]]) {
    const item = node("span", "gp-legend-item gp-tag-" + state, label);
    item.setAttribute("role", "listitem");
    legend.append(item);
  }
  const help = node("p", "gp-help",
    "Dra i ritningen med vänster eller höger musknapp för att panorera. Shift + scroll zoomar vid muspekaren. Klick markerar ett objekt; Shift + klick eller Shift + vänsterdrag markerar flera etiketter och widgets. Dra en markerad etikett eller widgetrubrik för gemensam förflyttning. Urvalet kan skalas, låsas och flyttas fram eller bak. Lås placering skyddar position och storlek; dragning på låsta objekt panorerar utan att ändra markeringen. Klicka på en etikett för indata och Kopiera sula. Redigera ritningsunderlag används för att flytta, skala eller uppdatera underlaget.");
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
  workspace.append(measurementBar, cropBar, drawingBar);
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
      command(action, { name: file.name, ...(action === "drawing" && drawingDraft ? {draft: true} : {}) }, [buffer], (reply) => {
        if (action === "drawing") {
          drawingBusy = false;
          if (reply.ok && reply.drawing_preview && drawingDraft) {
            drawingPreview = reply.drawing_preview;
            drawingDraft = {...drawingPreview.layout, x: drawingDraft.x, y: drawingDraft.y, scale: drawingDraft.scale};
            update(); showMessage(file.name + " förhandsvisas. Klar sparar; Avbryt behåller det tidigare underlaget.");
            return;
          }
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
            + (reply.report.skipped_inactive ? reply.report.skipped_inactive + " inaktiva sulor överhoppade. " : "")
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
          headingDraft = null; cropDraft = canvasPending = null;
          drawingDraft = drawingPreview = null; scaleDrafts.clear();
          slidingDraft = null; overlaySelected = null; selectedOverlays.clear(); lockDrafts.clear();
          colourDraft = null; colourEditType = null; colourError.textContent = "";
          tableViewDraft = null; tableSortScope = null; insulationWidgetDraft = null; commentWidgetDraft = null; referenceWidgetDraft = null;
          textDrafts.clear(); textDeleting.clear(); textAddBusy = false;
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
    if (cropDraft) finishCrop(false);
    if (drawingDraft) finishDrawingEdit(false);
    leaderPlacement = null; leaderEdit = leaderNode = null;
    viewport.classList.remove("gp-placing-leader");
    renderLeaders();
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
    const rect = sheet.getBoundingClientRect();
    const point = {x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height};
    const bounds = canvasBounds();
    return Number.isFinite(point.x) && Number.isFinite(point.y) && point.x >= bounds.left && point.x <= bounds.right
      && point.y >= bounds.top && point.y <= bounds.bottom ? point : null;
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
    measureTool.disabled = !background().url || !!drawingDraft || drawingPending || !!cropDraft || !!canvasPending || calibrationBusy || bulkBusy || importBusy || drawingBusy || deleteBusy;
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
      ? measurePoints.length === 2 ? "Ange det kända avståndet mellan punkterna." : "Kalibrering krävs: klicka på " + (measurePoints.length ? "slutpunkten" : "startpunkten") + " för ett känt mått."
      : measurePoints.length === 2 ? "Klicka för att börja en ny mätning."
        : "Mätning: klicka på " + (measurePoints.length ? "slutpunkten" : "startpunkten") + ".";
    if (measuring()) showMessage(measurementHint.textContent + " Dra för att panorera. Shift + scroll zoomar. Escape avslutar.");
    renderMeasurement();
  }
  function renderMeasurement() {
    measurementOverlay.hidden = !measuring() || !measurePoints.length;
    measurementSvg.replaceChildren();
    if (measurementOverlay.hidden) return;
    const viewRect = viewport.getBoundingClientRect(), rect = sheet.getBoundingClientRect();
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
    for (const marker of markers.children) marker.style.setProperty("--gp-tag-scale", String(labelScale(marker.dataset.tagId, value) * zoom));
    refreshGroupPatterns();
    renderLeaders();
  }
  function leaderFor(tag) {return leaderDrafts.get(tag.id) || tag.leader;}
  function leaderBox(id) {
    const marker = [...markers.children].find(element => element.dataset.tagId === id);
    if (!marker) return null;
    const image = sheet.getBoundingClientRect(), box = marker.getBoundingClientRect();
    if (!image.width || !image.height) return null;
    return {x: (box.left - image.left) / image.width, y: (box.top - image.top) / image.height,
      width: box.width / image.width, height: box.height / image.height};
  }
  function saveLeader(id, value) {
    if (readOnly || placementLocked({type: "tag", id}) || state().tags.find(tag => tag.id === id)?.values.inaktiv) return;
    leaderDrafts.set(id, value); renderLeaders(); showLeaderChoice();
    command("leader", {id, leader: value}, [], reply => {
      if (leaderDrafts.get(id) === value) leaderDrafts.delete(id);
      renderLeaders(); showLeaderChoice();
      if (!reply.ok) showMessage(reply.error, true);
    });
  }
  function showLeaderChoice() {
    const tag = current(), value = tag && leaderFor(tag);
    leaderSection.hidden = !!(drafts.get(tag?.id)?.values.inaktiv ?? tag?.values.inaktiv);
    leaderCheck.checked = !!value?.enabled;
    leaderEditButton.hidden = !value?.enabled;
    leaderRedrawButton.hidden = !value?.enabled;
  }
  function beginLeaderDraw(id) {
    if (readOnly || drawingBusy || importBusy || deleteBusy || bulkBusy) return;
    const tag = state().tags.find(tag => tag.id === id); if (!tag || tag.values.inaktiv) return;
    const saved = leaderFor(tag);
    cancelDrag(); setMode("pan"); closeDialog(); closeBulk();
    leaderPlacement = {id, attachment: saved ? {...saved.attachment} : null, stroke: null};
    viewport.classList.add("gp-placing-leader");
    viewport.focus({preventScroll: true}); renderLeaders();
    showMessage(saved ? "Rita om från den blå anslutningspunkten till önskad pilspets. Escape behåller den gamla linjen."
      : "Dra från etikettens ram till önskad pilspets för att rita banan. Ett klick på ritningen skapar en enkel spline. Escape avbryter.");
  }
  function beginLeaderEdit(id) {
    if (readOnly || placementLocked({type: "tag", id}) || state().tags.find(tag => tag.id === id)?.values.inaktiv) return;
    setMode("pan"); closeDialog(); closeBulk();
    leaderEdit = id; leaderNode = null; renderLeaders();
    viewport.focus({preventScroll: true});
    showMessage("Dra noder och blå handtag för att forma kurvan. Dra anslutningen längs etikettens ram. Dubbelklick lägger till en nod; Delete tar bort vald mellannod. Escape avslutar.");
  }
  function createLeader(id, anchor) {
    const box = leaderBox(id); if (!box) return;
    const attachment = leaderAttachment(anchor, box), endpoint = leaderEndpoint(attachment, box);
    const handle = Math.min(.12, Math.hypot(endpoint.x - anchor.x, endpoint.y - anchor.y) / 2);
    const normal = {left: {x: -handle, y: 0}, right: {x: handle, y: 0},
      top: {x: 0, y: -handle}, bottom: {x: 0, y: handle}}[attachment.side];
    const delta = leaderSub(endpoint, anchor);
    const length = Math.hypot(delta.x, delta.y) || 1;
    saveLeader(id, {enabled: true, attachment, nodes: [{...anchor, in: {x: 0, y: 0},
      out: {x: delta.x / length * handle, y: delta.y / length * handle}}], end_handle: normal});
    leaderPlacement = null; viewport.classList.remove("gp-placing-leader"); beginLeaderEdit(id);
  }
  function renderLeaders() {
    // Keep each hit path alive while entering edit mode. Replacing it between
    // the two clicks prevents browsers from dispatching a native dblclick.
    leaderHandles.replaceChildren();
    const bg = background(); if (!bg.width || !bg.height) return;
    const painted = new Set();
    for (const svg of [leaderSvg, leaderHandles]) svg.setAttribute("viewBox", `0 0 ${bg.width} ${bg.height}`);
    const pixel = point => ({x: point.x * bg.width, y: point.y * bg.height});
    for (const tag of state().tags.filter(tag => tag.page === bg.page)) {
      const value = leaderFor(tag), box = leaderBox(tag.id);
      if (!value?.enabled || !box) continue;
      painted.add(tag.id);
      const size = labelScale(tag.id);
      let elements = leaderElements.get(tag.id);
      if (!elements) {
        const group = svgNode("g", {}), clipId = "gp-leader-tip-" + view + "-" + ++leaderClipSequence,
          clip = svgNode("clipPath", {id: clipId, clipPathUnits: "userSpaceOnUse"}),
          clearance = svgNode("path", {"clip-rule": "evenodd"}),
          path = svgNode("path", {class: "gp-leader-path", fill: "none", stroke: "#26343a", "clip-path": `url(#${clipId})`,
          "stroke-linecap": "round", "stroke-linejoin": "round"}),
          arrow = svgNode("path", {class: "gp-leader-arrow", fill: "none", stroke: "#26343a",
            "stroke-linecap": "round", "stroke-linejoin": "round"});
        clip.append(clearance);
        path.dataset.tagId = tag.id; group.append(clip, path, arrow);
        const hit = readOnly ? null : svgNode("path", {class: "gp-leader-hit", fill: "none", stroke: "transparent",
          role: "button", tabindex: 0});
        if (hit) {
          hit.dataset.tagId = tag.id;
          hit.addEventListener("keydown", event => {
            if (["Enter", " "].includes(event.key)) {event.preventDefault(); beginLeaderEdit(tag.id);}
          });
          group.append(hit);
        }
        const layer = svgNode("svg", {class: "gp-object-leader", viewBox: `0 0 ${bg.width} ${bg.height}`});
        layer.append(group); sheet.append(layer);
        elements = {layer, group, path, arrow, hit, clearance}; leaderElements.set(tag.id, elements);
      }
      elements.layer.setAttribute("viewBox", `0 0 ${bg.width} ${bg.height}`);
      elements.layer.style.zIndex = String(objectZ({type: "tag", id: tag.id}));
      const vertices = leaderVertices(value, leaderEndpoint(value.attachment, box));
      const {anchor, direction, clip, curves} = leaderTip(vertices, bg.width, bg.height, size);
      let d = `M ${anchor.x} ${anchor.y}`;
      for (const [, a, b, end] of curves) {
        d += ` C ${a.x} ${a.y} ${b.x} ${b.y} ${end.x} ${end.y}`;
      }
      elements.path.setAttribute("d", d); elements.path.setAttribute("stroke-width", size);
      elements.group.setAttribute("opacity", leaderPlacement?.id === tag.id ? ".25" : "1");
      elements.clearance.setAttribute("d", clip);
      const arm = angle => ({x: anchor.x + Math.cos(angle) * 7 * size, y: anchor.y + Math.sin(angle) * 7 * size});
      const left = arm(direction - .45), right = arm(direction + .45);
      elements.arrow.setAttribute("d", `M ${left.x} ${left.y} L ${anchor.x} ${anchor.y} L ${right.x} ${right.y}`);
      elements.arrow.setAttribute("stroke-width", size);
      const inactive = drafts.get(tag.id)?.values.inaktiv ?? tag.values.inaktiv;
      if (elements.hit) elements.hit.style.display = inactive || placementLocked({type: "tag", id: tag.id}) ? "none" : "";
      if (readOnly || inactive || placementLocked({type: "tag", id: tag.id})) continue;
      elements.hit.setAttribute("d", d);
      elements.hit.setAttribute("stroke-width", Math.max(10 / zoom, size));
      elements.hit.setAttribute("aria-label", "Redigera hänvisningslinje för " + tag.label);
      if (leaderEdit !== tag.id) continue;
      const handle = (point, index, kind) => {
        const p = pixel(point), circle = svgNode("circle", {cx: p.x, cy: p.y,
          r: (kind === "node" ? 5 : 3.5) / zoom, class: "gp-leader-handle",
          fill: kind === "node" ? leaderNode === index ? "#1688e5" : "white" : "#1688e5",
          stroke: kind === "node" ? "#1688e5" : "white", "stroke-width": 1.5 / zoom,
          tabindex: 0, role: "button", "aria-label": kind === "node"
            ? index === 0 ? "Spets på ritningen" : index === vertices.length - 1 ? "Anslutning på etikettens ram" : "Nod " + index
            : "Kontrollhandtag " + kind + " för nod " + index});
        circle.dataset.tagId = tag.id; circle.dataset.index = String(index); circle.dataset.handle = kind;
        circle.addEventListener("focus", () => {leaderNode = kind === "node" ? index : null;});
        leaderHandles.append(circle);
      };
      vertices.forEach((vertex, index) => {
        for (const kind of ["in", "out"]) {
          if ((index === 0 && kind === "in") || (index === vertices.length - 1 && kind === "out")) continue;
          const p = pixel(vertex), q = pixel(leaderAdd(vertex, vertex[kind]));
          leaderHandles.append(svgNode("path", {d: `M ${p.x} ${p.y} L ${q.x} ${q.y}`, fill: "none",
            stroke: "#1688e5", "stroke-width": 1 / zoom, "stroke-dasharray": `${3 / zoom} ${3 / zoom}`}));
          handle(leaderAdd(vertex, vertex[kind]), index, kind);
        }
      });
      vertices.forEach((vertex, index) => handle(vertex, index, "node"));
    }
    for (const [id, elements] of leaderElements) if (!painted.has(id)) {
      elements.layer.remove(); leaderElements.delete(id);
    }
    if (leaderPlacement && !readOnly) {
      const box = leaderBox(leaderPlacement.id);
      if (box) {
        const attachment = leaderPlacement.drawingAttachment || leaderPlacement.attachment || {side: "right", offset: .5};
        const start = pixel(leaderEndpoint(attachment, box));
        leaderHandles.append(svgNode("circle", {class: "gp-leader-draw-start", cx: start.x, cy: start.y,
          r: 6 / zoom, fill: "white", stroke: "#1688e5", "stroke-width": 2 / zoom,
          "aria-label": "Rita från etikettens anslutning"}));
        if (leaderPlacement.stroke?.length) {
          const d = leaderPlacement.stroke.map((p, i) => {const q = pixel(p); return `${i ? "L" : "M"} ${q.x} ${q.y}`;}).join(" ");
          leaderHandles.append(svgNode("path", {class: "gp-leader-preview", d, fill: "none", stroke: "#14695e",
            "stroke-width": labelScale(leaderPlacement.id), "stroke-linecap": "round", "stroke-linejoin": "round"}));
        }
      }
    }
  }
  function addLeaderNode(event) {
    if (readOnly || measuring() || drawingBusy || importBusy || deleteBusy || leaderPlacement) return;
    const hit = event.target.closest(".gp-leader-hit"); if (!hit) return;
    const tag = state().tags.find(tag => tag.id === hit.dataset.tagId), point = measurementPoint(event), box = leaderBox(tag.id);
    if (!point || !box) return;
    const value = leaderFor(tag); if (value.nodes.length >= 64) {showMessage("Linjen har redan 64 noder.", true); return;}
    const endpoint = leaderEndpoint(value.attachment, box), vertices = leaderVertices(value, endpoint), bg = background();
    let closest = {distance: Infinity, segment: 0, t: .5};
    for (let i = 0; i < vertices.length - 1; i++) for (let step = 1; step < 100; step++) {
      const t = step / 100, p = leaderCurvePoint(vertices[i], vertices[i + 1], t);
      const distance = Math.hypot((point.x - p.x) * bg.width, (point.y - p.y) * bg.height);
      if (distance < closest.distance) closest = {distance, segment: i, t};
    }
    leaderEdit = tag.id; leaderNode = closest.segment + 1;
    saveLeader(tag.id, splitLeader(value, endpoint, closest.segment, closest.t));
    viewport.focus({preventScroll: true});
  }
  viewport.addEventListener("dblclick", addLeaderNode);
  sheet.addEventListener("gp:layout", renderLeaders);
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
    if (patch.categories) {
      draft.category = patch.categories[0]; draft.secondary = patch.categories[1] || null;
    }
    for (const name of ["bounds", "colors", "styles", "legend"]) {
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
    if (group.kind === "omitted") return "";
    if (group.kind === "combination") return group.parts.map((part, index) => colourPartCaption(group, index)).filter(Boolean).join(" · ");
    if (group.label) return group.label;
    if (group.kind === "geometry") return precise(group.value) + " m";
    return group.low == null ? "V < " + precise(group.high) : group.high == null ? "V ≥ " + precise(group.low)
      : precise(group.low) + " ≤ V < " + precise(group.high);
  }
  function colourPartCaption(group, index) {
    const part = group.parts[index], category = group.categories[index];
    if (part.kind === "omitted") return "";
    const prefix = {t: "t ", b: "b_x ", l: "b_y "}[category] || (category === "V" && part.kind === "special" ? "V " : "");
    return prefix + colourGroupCaption(part) + (["pad", "wall"].includes(part.kind) ? " " + part.unit : "");
  }
  function showColour() {
    const settings = colour(), data = colourGroups(groupingTags(), settings);
    colourToggle.classList.toggle("gp-selected", settings.enabled);
    colourToggle.setAttribute("aria-pressed", String(settings.enabled));
    colourToggle.disabled = !background().url || drawingBusy;
    colourControls.hidden = !settings.enabled;
    const kind = colourEditType || settings.edit_type;
    const categories = selectedColourCategories(settings), hasV = categories.includes("V");
    for (const [value, choice] of colourCategoryButtons) {
      const checked = categories.includes(value);
      choice.classList.toggle("gp-selected", checked); choice.setAttribute("aria-pressed", String(checked));
      choice.disabled = false;
      choice.title = "Välj en eller flera kategorier. Minst en kategori ska vara vald.";
    }
    for (const [buttons, selectedValue] of [[colourPhaseButtons, settings.phase], [colourTypeButtons, kind]]) {
      for (const [value, choice] of buttons) {
        choice.classList.toggle("gp-selected", value === selectedValue);
        choice.setAttribute("aria-pressed", String(value === selectedValue));
      }
    }
    colourLegendCheck.checked = settings.show_legend;
    const onlyHRestriction = onlyHColourRestriction(settings);
    colourOnlyHCheck.disabled = !!onlyHRestriction;
    colourOnlyHCheck.checked = !onlyHRestriction && settings.include_only_h === true;
    colourOnlyHChoice.classList.toggle("gp-disabled", !!onlyHRestriction);
    colourOnlyHChoice.title = onlyHRestriction || "Inkludera sulor med endast H-stabilitet i färggrupperingen. Gäller Sultyp, Isolering och V · EQU.";
    colourOnlyHNote.textContent = onlyHRestriction;
    colourOnlyHNote.hidden = !onlyHRestriction;
    colourLoadOptions.hidden = colourBoundsRow.hidden = !hasV;
    colourBoundsCaption.textContent = "Intervallgränser [" + (kind === "wall" ? "kN/m" : "kN") + "]";
    if (document.activeElement !== colourBounds && !colourBounds.validityMessage) {
      colourBounds.value = settings.bounds[kind].map(value => String(value).replace(".", ",")).join("; ");
    }
    colourHint.textContent = categories.length > 1 ? categories.length + " valda parametrar. Samma kombination ger samma färg. " + (hasV ? "Linjelaster och punktlaster har separata intervall. " : "") + "Klicka på en färgruta för att välja färg."
      : categories[0] === "V"
      ? "Linjelaster och punktlaster har separata intervall. V är angiven last utan tillägg; EQU innehåller redan egentyngd. Klicka på en färgruta för att välja färg."
      : categories[0] === "isolering" ? "Fem grupper efter isolering och valda bidragsriktningar under Glidning. Isolerade sulor bidrar inte. Klicka på en färgruta för att välja färg."
        : "En färg per unikt värde. Klicka på en färgruta för att välja färg.";
    colourSwatches.replaceChildren();
    for (const group of data.groups.filter(group => group.kind !== "omitted").filter(group => !hasV || (group.parts?.find(part => ["pad", "wall"].includes(part.kind))?.kind ?? group.kind) === kind || group.kind === "special" || group.parts?.some(part => part.kind === "special"))) {
      const row = node("label", "gp-colour-chip");
      const input = node("input"); input.type = "color"; input.value = group.color;
      input.setAttribute("aria-label", "Färg för " + colourGroupCaption(group) + (group.unit ? " [" + group.unit + "]" : ""));
      input.addEventListener("change", () => setColour({colors: {[group.key]: input.value}}));
      row.append(input);
      if (group.pattern !== "plain") {
        const sample = node("span", "gp-colour-swatch gp-colour-pattern-sample"); sample.style.background = group.background;
        paintGroupPattern(sample, group, true); row.append(sample);
      }
      row.append(mathText("span", "", colourGroupCaption(group))); colourSwatches.append(row);
    }
    colourLegendBody.replaceChildren(node("p", "gp-colour-legend-title",
      categories.length > 1 ? categories.map(category => category === "V" ? "V" : COLOUR_CATEGORIES[category]).join(" + ") + (hasV ? " · " + (settings.phase === "EQU" ? "EQU" : settings.phase) : "")
        : categories[0] === "isolering" ? "Isolering och glidmotstånd"
        : COLOUR_CATEGORIES[categories[0]] + (categories[0] === "V" ? " · " + COLOUR_PHASES[settings.phase] : categories[0] === "sultyp" ? "" : " [m]")));
    let previousKind = null, previousFooting = null;
    for (const group of data.groups.filter(group => group.count > 0 && group.kind !== "omitted")) {
      const typePart = group.parts?.find(part => part.kind === "footing_type") || (group.kind === "footing_type" ? group : null);
      if (typePart && typePart.category !== previousFooting) {
        previousFooting = typePart.category;
        colourLegendBody.append(node("strong", "gp-colour-legend-section", typePart.label));
      }
      if (categories.length === 1 && hasV && group.kind !== previousKind && ["pad", "wall"].includes(group.kind)) {
        colourLegendBody.append(node("strong", "gp-colour-legend-section",
          group.kind === "wall" ? "Linjelaster [kN/m]" : "Punktlaster [kN]"));
      }
      previousKind = group.kind;
      const row = node("div", "gp-colour-legend-row");
      const swatch = node("span", "gp-colour-swatch"); swatch.style.background = group.background;
      paintGroupPattern(swatch, group, true);
      let caption = mathText("span", "", group.kind === "combination" && typePart
        ? group.parts.flatMap((part, i) => group.categories[i] === "sultyp" ? [] : [colourPartCaption(group, i)]).filter(Boolean).join(" · ")
        : colourGroupCaption(group));
      if (group.kind === "combination" && hasV) {
        const index = group.categories.indexOf("V");
        caption = node("span", "gp-colour-legend-label"); row.dataset.multiline = "true";
        caption.append(mathText("span", "gp-colour-legend-details", group.parts.flatMap((part, i) =>
          i === index || group.categories[i] === "sultyp" ? [] : [colourPartCaption(group, i)]).filter(Boolean).join(" · ")),
        mathText("span", "gp-colour-legend-load", colourPartCaption(group, index)));
      }
      row.append(swatch, caption, node("span", "gp-colour-group-count", String(group.count)));
      colourLegendBody.append(row);
    }
    colourLegendBody.append(node("p", "gp-sliding-note", "Antal sulor visas till höger."));
    showInsulationWidget();
    showCommentWidget(settings.enabled ? data.assignments : null);
    showReferenceWidget(settings.enabled ? data.assignments : null);
    renderSlidingGeometry();
    refreshGroupPatterns(true);
  }
  function showInsulationWidget() {
    const settings = insulationWidget();
    insulationWidgetToggle.classList.toggle("gp-selected", settings.enabled);
    insulationWidgetToggle.setAttribute("aria-pressed", String(settings.enabled));
    insulationWidgetToggle.disabled = !background().url || drawingBusy;
    const tags = groupingTags().filter(tag => !(drafts.get(tag.id)?.values || tag.values).endast_h_stabilitet),
      uninsulated = tags.filter(tag => !(drafts.get(tag.id)?.values || tag.values).isolering);
    insulationBody.replaceChildren();
    for (const [caption, count] of [["Med isolering", tags.length - uninsulated.length], ["Utan isolering", uninsulated.length]]) {
      const row = node("div", "gp-insulation-count"); row.append(node("span", "", caption), node("strong", "", String(count)));
      insulationBody.append(row);
    }
    insulationBody.append(node("p", "gp-insulation-list-heading", "Föreskrivna utan isolering"),
      node("p", "gp-insulation-list", uninsulated.map(tag => drafts.get(tag.id)?.label.trim() || tag.label)
        .sort(tableCollator.compare).join(", ") || "Inga sulor"));
  }
  function showCommentWidget(groups) {
    const settings = commentWidget();
    commentWidgetToggle.classList.toggle("gp-selected", settings.enabled);
    commentWidgetToggle.setAttribute("aria-pressed", String(settings.enabled));
    commentWidgetToggle.disabled = !background().url || drawingBusy;
    const rows = state().tags.map(tag => ({id: tag.id, label: drafts.get(tag.id)?.label.trim() || tag.label,
      comment: (drafts.get(tag.id)?.values || tag.values).kommentar?.trim() || ""}))
      .filter(row => row.comment).sort((a, b) => tableCollator.compare(a.label, b.label));
    commentBody.replaceChildren(node("p", "gp-sliding-note", rows.length
      ? rows.length + (rows.length === 1 ? " sula med kommentar" : " sulor med kommentarer") : "Inga sulor med kommentarer"));
    if (!rows.length) return;
    const table = node("table", "gp-comment-table"), head = node("thead"), heading = node("tr"), body = node("tbody");
    heading.append(node("th", "", "Littera"), node("th", "", "Kommentar")); head.append(heading);
    for (const row of rows) {
      const tr = node("tr"), label = node("th"), group = groups?.get(row.id);
      if (group) {
        const badge = node("span", "gp-comment-label"); badge.append(node("span", "", row.label));
        badge.style.background = group.background;
        paintGroupPattern(badge, group, true);
        label.append(badge);
      } else label.textContent = row.label;
      tr.append(label, node("td", "", row.comment)); body.append(tr);
    }
    table.append(head, body); commentBody.append(table);
  }
  function showReferenceWidget(assignments) {
    const settings = referenceWidget(), data = state().reference_data || {groups: [], excluded: []};
    referenceToggle.classList.toggle("gp-selected", settings.enabled);
    referenceToggle.setAttribute("aria-pressed", String(settings.enabled));
    referenceToggle.disabled = !background().url || drawingBusy;
    referenceBody.replaceChildren(node("p", "gp-sliding-note", "Underlag för vidare dimensionering i Foundation."),
      node("p", "gp-sliding-note", "Referens väljs efter högst aktuell U. Varje sula beräknas individuellt."));
    let category = null;
    for (const group of data.groups) {
      if (group.category !== category) {
        category = group.category;
        referenceBody.append(node("strong", "gp-reference-section", FOOTING_CATEGORIES[category]));
      }
      const row = node("div", "gp-reference-row"), ident = node("div", "gp-reference-ident");
      const badge = node("span", "gp-comment-label"); badge.append(node("span", "", group.label));
      const style = assignments?.get(group.reference_id);
      badge.style.background = style?.background || "#ffffff";
      if (style) paintGroupPattern(badge, style, true);
      const utilization = node("strong", group.utilization > 1 ? "gp-reference-over" : "gp-reference-ok",
        "U " + compactNumber(group.utilization * 100, 1) + " %");
      const range = group.utilization_range || {min: group.utilization, max: group.utilization};
      const interval = node("span", "gp-reference-range " + (range.max > 1 ? "gp-reference-over" : "gp-reference-ok"),
        "(" + compactNumber(range.min * 100, 1) + "–" + compactNumber(range.max * 100, 1) + " %)");
      interval.title = "Gruppens lägsta–högsta utnyttjandegrad";
      ident.append(badge, utilization, interval);
      const info = node("div", "gp-reference-info");
      info.append(mathText("p", "gp-reference-geometry", Object.entries(group.geometry).map(([name, value]) =>
        ({t: "t", b: "b_x", l: "b_y", L_vagg: "L_vägg"}[name] || name) + " " + precise(value) + " m").join(" · ")));
      info.append(node("p", "gp-reference-caption", group.unit === "kN/m" ? "Linjelast" : "Punktlast"));
      for (const phase of ["brott", "bruk"]) {
        const line = node("p", "gp-reference-load"), value = group.loads[phase];
        let caption = value == null ? "—" : compactNumber(value, 2) + " " + group.unit;
        if (category === "wall_pad" && group.unit === "kN/m" && group.resultants[phase] != null)
          caption += " → " + compactNumber(group.resultants[phase], 2) + " kN";
        line.append(symbolNode({base: "V", subscript: phase}), node("span", "", caption));
        info.append(line);
      }
      info.append(node("p", "gp-reference-caption", "Gäller för"),
        node("p", "gp-reference-members", group.members.map(member => member.label).join(", ") + " (" + group.members.length + " st)"));
      row.append(ident, info); referenceBody.append(row);
    }
    if (!data.groups.length) referenceBody.append(node("p", "gp-sliding-note", "Inga beräknade sulor att referera till."));
    const unresolved = data.excluded.filter(item => !["Inaktiv", "Endast H-stabilitet"].includes(item.reason));
    if (unresolved.length) referenceBody.append(node("p", "gp-reference-warning", "Utanför referensgrupper: "
      + unresolved.map(item => item.label + " (" + item.reason + ")").join(", ")));
  }
  function textObject(kind) {
    return kind?.startsWith("text:") ? state().text_objects?.find(item => item.id === kind.slice(5)) : null;
  }
  function overlayPosition(kind) {
    const key = background().page + ":" + kind;
    const text = textObject(kind);
    if (text) return overlayPositions.get(key) || {x: text.x, y: text.y, size: text.size};
    if (kind === "colour") return {...COLOUR_DEFAULTS.legend, ...(overlayPositions.get(key) || colour().legend)};
    if (["insulation", "comments", "reference"].includes(kind)) {
      const {x, y, size} = overlayPositions.get(key) || (kind === "reference" ? referenceWidget() : kind === "comments" ? commentWidget() : insulationWidget()); return {x, y, size};
    }
    const defaults = kind === "symbol" ? {x: .06, y: .55, size: 160} : {x: .50, y: .04, size: 410};
    return {...defaults, ...(overlayPositions.get(key) || sliding().placements?.[background().page]?.[kind])};
  }
  function overlaySize(kind, value) {
    const [low, high] = kind.startsWith("text:") ? [10, 144] : kind === "symbol" ? [50, 600] : ["colour", "insulation"].includes(kind) ? [150, 900] : [205, 1230];
    return Math.max(low, Math.min(high, value));
  }
  function saveOverlayPosition(kind, page, position) {
    const key = page + ":" + kind;
    overlayPositions.set(key, position);
    pendingOverlayPositions.set(key, position);
    const text = textObject(kind);
    command(text ? "text_update" : kind === "colour" ? "colour_placement" : kind === "insulation" ? "insulation_placement"
      : kind === "comments" ? "comment_placement" : kind === "reference" ? "reference_placement" : "sliding_placement",
      text ? {id: text.id, changes: position} : {kind, page, position}, [], () => {
      if (pendingOverlayPositions.get(key) === position) pendingOverlayPositions.delete(key);
      if (overlayPositions.get(key) === position) overlayPositions.delete(key);
      renderSlidingGeometry();
    });
  }
  function bindOverlayKeys(element, kind, resize) {
    element.addEventListener("keydown", event => {
      if (readOnly || placementLocked(overlayObject(kind))) return;
      const p = {...overlayPosition(kind)}, step = event.shiftKey ? 20 : 5;
      if (resize && ["+", "=", "-"].includes(event.key)) {
        p.size = overlaySize(kind, p.size + (event.key === "-" ? -step : step));
      } else if (!resize && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        const starts = movementStarts(overlayObject(kind));
        moveObjects(starts, (event.key === "ArrowRight" ? step : event.key === "ArrowLeft" ? -step : 0) / background().width,
          (event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0) / background().height);
        saveObjectPositions(starts); return;
      } else return;
      event.preventDefault();
      saveOverlayPosition(kind, background().page, p);
      renderSlidingGeometry();
    });
  }
  for (const [element, kind, resize] of [[axesButton, "symbol", false], [axesResize, "symbol", true],
      [slidingHeader, "legend", false], [legendResize, "legend", true], [colourHeader, "colour", false], [colourResize, "colour", true],
      [insulationHeader, "insulation", false], [insulationResize, "insulation", true],
      [commentHeader, "comments", false], [commentResize, "comments", true],
      [referenceHeader, "reference", false], [referenceResize, "reference", true]]) bindOverlayKeys(element, kind, resize);
  function showTextObjects() {
    for (const add of textAddButtons) add.disabled = !background().url || textAddBusy || drawingBusy || !!drawingDraft || drawingPending || importBusy || deleteBusy;
    const objects = state().text_objects || [];
    for (const [id, entry] of textElements) if (!objects.some(item => item.id === id)) {
      entry.element.remove(); textElements.delete(id); textDrafts.delete(id);
      if (overlaySelected === "text:" + id) overlaySelected = null;
    }
    for (const item of objects) {
      let entry = textElements.get(item.id);
      if (!entry) {
        const kind = "text:" + item.id;
        const element = node("div", "gp-sliding-overlay gp-text-annotation");
        element.dataset.kind = kind; element.dataset.textId = item.id;
        const text = node(readOnly ? "span" : "button", "gp-annotation-text gp-sliding-handle");
        const title = node("span", "gp-annotation-title"), subtitle = node("span", "gp-annotation-subtitle");
        text.append(title, subtitle);
        if (!readOnly) text.type = "button";
        const resize = button("", () => {}, "gp-overlay-resize gp-text-resize");
        resize.setAttribute("aria-label", "Ändra textens storlek. Dra hörnet eller använd plus och minus.");
        element.append(text);
        entry = {element, text, title, subtitle, resize, editing: false};
        if (!readOnly) {
          const editor = node("textarea", "gp-annotation-editor"); editor.rows = 1;
          editor.setAttribute("aria-label", item.kind === "date" ? "Datumtext (åå/mm/dd)" : "Rubriktext på ritningen");
          const subtitleEditor = item.kind === "heading" ? node("textarea", "gp-annotation-editor gp-annotation-subtitle-editor") : null;
          if (subtitleEditor) {
            subtitleEditor.rows = 1; subtitleEditor.placeholder = "Underrubrik (valfri)";
            subtitleEditor.setAttribute("aria-label", "Underrubrik på ritningen");
          }
          const tools = node("div", "gp-annotation-tools");
          const edit = button("Redigera", () => {
            entry.editing = true; overlaySelected = kind; showTextObjects(); editor.focus({preventScroll:true});
          });
          const lock = button("Lås placering", () => {
            const object = overlayObject(kind);
            setPlacementLock(!placementLocked(object), [object]);
          }, "gp-text-lock");
          const remove = button("×", () => {
            if (textDeleting.has(item.id)) return;
            textDeleting.add(item.id); remove.disabled = true;
            command("text_delete", {id: item.id}, [], () => {textDeleting.delete(item.id); showTextObjects();});
          });
          remove.setAttribute("aria-label", "Ta bort textobjekt"); remove.title = "Ta bort textobjekt";
          tools.append(edit, lock, remove); element.append(editor);
          if (subtitleEditor) element.append(subtitleEditor);
          element.append(tools, resize);
          Object.assign(entry, {editor, subtitleEditor, tools, remove, lock, lockLabel: item.kind === "date" ? "datum" : "rubrik"});
          text.addEventListener("click", event => selectOverlayClick(kind, event));
          text.addEventListener("dblclick", () => edit.click());
          for (const field of [editor, subtitleEditor].filter(Boolean)) {
            field.addEventListener("input", () => {
              const draft = {text: editor.value, subtitle: subtitleEditor?.value || ""};
              textDrafts.set(item.id, draft); showTextObjects();
              command("text_update", {id: item.id, changes: draft}, [], () => {
                if (textDrafts.get(item.id) === draft) textDrafts.delete(item.id);
                showTextObjects();
              });
            });
            field.addEventListener("keydown", event => {
              if (event.key === "Escape" || event.key === "Enter" && !event.shiftKey) {
                event.preventDefault(); event.stopPropagation(); entry.editing = false; showTextObjects(); text.focus({preventScroll:true});
              }
            });
          }
          bindOverlayKeys(text, kind, false); bindOverlayKeys(resize, kind, true);
        }
        textElements.set(item.id, entry); overlays.append(element);
      }
      const value = textDrafts.get(item.id)?.text ?? item.text;
      const subtitleValue = textDrafts.get(item.id)?.subtitle ?? item.subtitle ?? "";
      entry.element.classList.toggle("gp-annotation-heading", item.kind === "heading");
      if (item.kind === "heading") entry.element.style.width = (item.width ?? 420) + "px";
      entry.title.textContent = value || (readOnly ? "" : item.kind === "heading" ? "Rubrik" : "Datum");
      entry.title.hidden = !value && readOnly;
      entry.subtitle.textContent = subtitleValue; entry.subtitle.hidden = !subtitleValue;
      if (!readOnly) {
        if (document.activeElement !== entry.editor) entry.editor.value = value;
        if (entry.subtitleEditor && document.activeElement !== entry.subtitleEditor) entry.subtitleEditor.value = subtitleValue;
        entry.remove.disabled = textDeleting.has(item.id);
      }
    }
    renderSlidingGeometry();
  }
  function renderSlidingGeometry() {
    for (const [element, kind] of [[axesOverlay, "symbol"], [slidingLegend, "legend"], [colourLegend, "colour"], [insulationLegend, "insulation"], [commentLegend, "comments"], [referenceLegend, "reference"]]) {
      const p = overlayPosition(kind);
      element.hidden = (kind === "colour" ? !colour().enabled || !colour().show_legend
        : kind === "insulation" ? !insulationWidget().enabled : kind === "comments" ? !commentWidget().enabled : kind === "reference" ? !referenceWidget().enabled : !sliding().enabled) || !background().url;
      element.style.zIndex = String(objectZ(overlayObject(kind)) + 1);
      const visualScale = objectScale(overlayObject(kind));
      element.style.left = p.x * 100 + "%";
      element.style.top = p.y * 100 + "%";
      element.classList.toggle("gp-overlay-selected", !readOnly && (selectedOverlays.has(kind) || overlaySelected === kind));
      element.classList.toggle("gp-placement-locked", !readOnly && placementLocked(overlayObject(kind)));
      if (kind === "symbol") {
        element.style.width = element.style.height = p.size * zoom * visualScale + "px";
        axesResize.hidden = readOnly || placementLocked(overlayObject(kind)) || overlaySelected !== "symbol";
      } else {
        const scale = zoom * visualScale * p.size / (["colour", "insulation"].includes(kind) ? 300 : 410);
        element.style.transform = "scale(" + scale + ")";
        const resize = kind === "colour" ? colourResize : kind === "insulation" ? insulationResize : kind === "comments" ? commentResize : kind === "reference" ? referenceResize : legendResize;
        resize.hidden = readOnly || placementLocked(overlayObject(kind)) || overlaySelected !== kind;
        // Keep the corner target usable even when the whole legend is small.
        resize.style.transform = "scale(" + 1 / scale + ")";
      }
    }
    for (const [id, entry] of textElements) {
      const kind = "text:" + id, p = overlayPosition(kind), selected = !readOnly && overlaySelected === kind;
      const scale = zoom * p.size / 20 * objectScale(overlayObject(kind));
      entry.element.hidden = !background().url;
      entry.element.style.left = p.x * 100 + "%"; entry.element.style.top = p.y * 100 + "%";
      entry.element.style.zIndex = String(objectZ(overlayObject(kind)) + 1);
      entry.element.style.transform = "scale(" + scale + ")";
      entry.element.classList.toggle("gp-overlay-selected", !readOnly && (selectedOverlays.has(kind) || overlaySelected === kind));
      entry.element.classList.toggle("gp-placement-locked", !readOnly && placementLocked(overlayObject(kind)));
      if (!selected) entry.editing = false;
      entry.text.hidden = entry.editing;
      entry.resize.hidden = !selected || entry.editing || placementLocked(overlayObject(kind));
      entry.resize.style.transform = "scale(" + 1 / scale + ")";
      if (!readOnly) {
        const locked = placementLocked(overlayObject(kind));
        entry.lock.textContent = locked ? "Lås upp" : "Lås placering";
        entry.lock.setAttribute("aria-label", (locked ? "Lås upp " : "Lås ") + entry.lockLabel);
        entry.lock.setAttribute("aria-pressed", String(locked));
        entry.lock.title = locked ? "Lås upp position och storlek" : "Lås position och storlek";
        entry.text.title = (locked ? "Position och storlek är låsta. Dra för att panorera." : "Dra för att flytta.")
          + " Dubbelklicka eller välj Redigera för att ändra texten.";
        for (const field of [entry.editor, entry.subtitleEditor].filter(Boolean)) {
          field.hidden = !entry.editing;
          if (entry.editing) {
            field.style.height = "auto";
            field.style.height = Math.max(field === entry.editor ? 33 : 25, (field.scrollHeight || 0) + 2) + "px";
          }
        }
        entry.tools.hidden = !selected || entry.editing;
        entry.tools.style.transform = "scale(" + 1 / scale + ")";
        entry.tools.style.top = -29 / scale + "px";
      }
    }
    showObjectFrame();
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
      const contributors = (r.contributors || []).map(tag => tag.label).join(", ");
      const count = node("td", "gp-sliding-footings");
      count.append(node("span", "gp-sliding-count", waiting ? "—" : (r.count ?? 0) + " st"));
      if (!waiting && contributors) count.append(node("div", "gp-sliding-contributors", contributors));
      count.title = waiting ? "Uppdaterar glidningskontrollen" : contributors || "Inga sulor med positivt bidrag";
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
  function showCanvas() {
    const bg = background(), bounds = canvasBounds(), w = (bg.width || 0) * zoom, h = (bg.height || 0) * zoom;
    for (const element of [paper, cropFrame]) {
      element.style.left = panX + bounds.left * w + "px";
      element.style.top = panY + bounds.top * h + "px";
      element.style.width = (bounds.right - bounds.left) * w + "px";
      element.style.height = (bounds.bottom - bounds.top) * h + "px";
    }
    sheet.style.left = -bounds.left * w + "px";
    sheet.style.top = -bounds.top * h + "px";
    const ru = drawingLayout();
    picture.style.position = "absolute"; picture.style.zIndex = "0";
    picture.style.left = (ru.x || 0) * w + "px"; picture.style.top = (ru.y || 0) * h + "px";
    picture.style.width = (bg.source_width || bg.width || 0) * (ru.scale || 1) * zoom + "px";
    picture.style.height = (bg.source_height || bg.height || 0) * (ru.scale || 1) * zoom + "px";
    drawingFrame.hidden = drawingBar.hidden = !drawingDraft;
    root.classList.toggle("gp-editing-drawing", !!drawingDraft);
    if (drawingDraft) {
      drawingFrame.style.left = panX + (ru.x || 0) * w + "px";
      drawingFrame.style.top = panY + (ru.y || 0) * h + "px";
      drawingFrame.style.width = picture.style.width; drawingFrame.style.height = picture.style.height;
      drawingScaleInput.value = String(Math.round(ru.scale * 10000) / 100);
    }
    drawingApply.disabled = drawingBusy || drawingPending || !bg.url || !drawingScaleInput.validity.valid; drawingCancel.disabled = drawingBusy || drawingPending;
    drawingUpdate.disabled = drawingBusy || drawingPending;
    paper.hidden = !bg.url;
    root.classList.toggle("gp-cropping", !!cropDraft);
    cropBar.hidden = cropFrame.hidden = !cropDraft;
    cropTool.disabled = readOnly || !!drawingDraft || drawingPending || !bg.url || !!cropDraft || !!canvasPending || drawingBusy || importBusy || bulkBusy || calibrationBusy;
    measureTool.disabled = !!cropDraft || !!canvasPending || !!drawingDraft || drawingPending;
    if (cropDraft) cropSize.textContent = "Bredd " + number((bounds.right - bounds.left) * 100, 1) + " % · Höjd " + number((bounds.bottom - bounds.top) * 100, 1) + " %";
  }
  function adjustCrop(edge, before, dx, dy) {
    const next = {...before};
    const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
    if (edge.includes("left")) next.left = clamp(before.left + dx, Math.max(-10, before.right - 10), before.right - .05);
    if (edge.includes("right")) next.right = clamp(before.right + dx, before.left + .05, Math.min(11, before.left + 10));
    if (edge.includes("top")) next.top = clamp(before.top + dy, Math.max(-10, before.bottom - 10), before.bottom - .05);
    if (edge.includes("bottom")) next.bottom = clamp(before.bottom + dy, before.top + .05, Math.min(11, before.top + 10));
    cropDraft = next; showCanvas();
  }
  function finishCrop(apply) {
    if (!cropDraft) return;
    cancelDrag();
    const bounds = validateCanvasBounds(cropDraft); cropDraft = null;
    if (apply) {
      canvasPending = bounds; showCanvas();
      command("canvas_bounds", {bounds}, [], reply => {
        if (canvasPending !== bounds) return;
        canvasPending = null; update(); fit();
        showMessage(reply.ok ? "Ritningsytans ram sparad." : reply.error, !reply.ok);
      });
    }
    update(); fit();
    if (!apply) showMessage("Beskärningen avbröts. Den sparade ramen behålls.");
  }
  function placeSheet() {
    showCanvas();
    renderMeasurement();
    renderLeaders();
    showObjectFrame();
  }
  function fit() {
    const bg = background();
    if (!bg.width) return;
    if (pdfMode) {
      setZoom(1);
      panX = -canvasBounds().left * bg.width;
      panY = -canvasBounds().top * bg.height;
      placeSheet();
      return;
    }
    const bounds = canvasBounds(), margin = cropDraft ? 80 : 48;
    setZoom(Math.min((viewport.clientWidth - margin) / (bg.width * (bounds.right - bounds.left)),
      (viewport.clientHeight - margin) / (bg.height * (bounds.bottom - bounds.top))));
    panX = viewport.clientWidth / 2 - bg.width * zoom * (bounds.left + bounds.right) / 2;
    panY = viewport.clientHeight / 2 - bg.height * zoom * (bounds.top + bounds.bottom) / 2;
    placeSheet();
  }
  function closeDialog() {
    rememberSections(inputSections);
    rememberSections(resultSections);
    active = null;
    dialogAnchor = null;
    formId = null;
    dialog.hidden = true;
    sketch.hidden = true;
    renderMarkers();
  }
  function openDialog(tag) {
    if (bulkBusy || deleteBusy) return;
    closeBulk();
    leaderEdit = leaderNode = null;
    if (!readOnly) { selected.clear(); selected.add(tag.id); selectedOverlays.clear(); overlaySelected = null;
      tableAnchor = null; bulkSignature = ""; renderSlidingGeometry(); showSelection(); }
    active = tag.id;
    dialogAnchor = tag.id;
    formId = null;
    update();
    const rect = board.getBoundingClientRect();
    const imageRect = sheet.getBoundingClientRect();
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
    bubble.addEventListener("click", event => {event.stopPropagation(); if (!event.detail || pickedTarget(event).closest(".gp-tag-comment") === bubble) openComment(tag);});
    bubble.addEventListener("keydown", event => {
      event.stopPropagation();
      if (["Enter", " "].includes(event.key)) {event.preventDefault(); openComment(tag);}
    });
    return bubble;
  }
  function placeDialog(x, y) {
    const margin = 8, gap = 12;
    const boardRect = board.getBoundingClientRect();
    const labelRect = dialogAnchor && objectElement({type: "tag", id: dialogAnchor})?.getBoundingClientRect();
    const anchor = labelRect && {left: labelRect.left - boardRect.left, top: labelRect.top - boardRect.top,
      right: labelRect.left - boardRect.left + labelRect.width, bottom: labelRect.top - boardRect.top + labelRect.height};
    const clampX = (value, width) => Math.max(margin, Math.min(board.clientWidth - width - margin, value));
    const clampY = value => Math.max(margin, Math.min(board.clientHeight - dialog.offsetHeight - margin, value));
    const besideLabel = width => {
      // Prefer a side, then above/below. On small boards use the least overlap.
      const candidates = [[anchor.right + gap, anchor.top - 20], [anchor.left - gap - width, anchor.top - 20],
        [anchor.left, anchor.bottom + gap], [anchor.left, anchor.top - gap - dialog.offsetHeight]]
        .map(([left, top]) => ({left: clampX(left, width), top: clampY(top)}));
      const overlap = p => Math.max(0, Math.min(p.left + width, anchor.right + gap) - Math.max(p.left, anchor.left - gap))
        * Math.max(0, Math.min(p.top + dialog.offsetHeight, anchor.bottom + gap) - Math.max(p.top, anchor.top - gap));
      const clear = candidates.find(p => overlap(p) === 0);
      return {position: clear || candidates.reduce((best, p) => overlap(p) < overlap(best) ? p : best), clear: !!clear};
    };
    let inline = board.clientWidth < dialog.offsetWidth + 430 + 28;
    if (anchor && !sketch.hidden && !inline && !besideLabel(dialog.offsetWidth + 442).clear
        && besideLabel(dialog.offsetWidth).clear) inline = true;
    if (inline !== sketchInline) {
      sketchInline = inline;
      (inline ? sketchSlot : board).append(sketch);
      sketch.classList.toggle("gp-sketch-inline", inline);
    }
    const extra = !sketch.hidden && !inline ? 442 : 0;
    const {left, top} = anchor ? besideLabel(dialog.offsetWidth + extra).position
      : {left: clampX(x, dialog.offsetWidth + extra), top: clampY(y)};
    dialog.style.left = left + "px";
    dialog.style.top = top + "px";
    if (!inline) {
      sketch.style.left = left + dialog.offsetWidth + 12 + "px";
      sketch.style.top = Math.max(8, Math.min(board.clientHeight - sketch.offsetHeight - 8, top)) + "px";
    }
  }
  function showSketch() {
    const tag = current();
    const onlyH = tag?.values.inaktiv || inputs.get("inaktiv")?.input.checked
      || (readOnly ? tag?.values.endast_h_stabilitet : inputs.get("endast_h_stabilitet")?.input.checked);
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
    leaderResizeObserver.disconnect();
    markers.replaceChildren();
    const grouped = colour().enabled ? colourGroups(groupingTags(), colour()).assignments : null;
    for (const tag of state().tags.filter((t) => t.page === background().page)) {
      const summary = dirty.has(tag.id) ? null : tag.summary;
      const tagState = dirty.has(tag.id) ? "stale" : tag.status;
      const draft = drafts.get(tag.id);
      const values = draft?.values || tag.values;
      const inactive = values.inaktiv === true;
      const onlyH = values.endast_h_stabilitet === true;
      const color = inactive ? "inactive" : summary ? (onlyH ? "horizontal" : summary.utnyttjandegrad <= 1 ? "ok" : "over") : tagState;
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
      const object = {type: "tag", id: tag.id};
      marker.style.zIndex = String(objectZ(object) + 1);
      marker.style.setProperty("--gp-tag-scale", String(labelScale(tag.id) * zoom));
      const group = grouped?.get(tag.id);
      if (group) {
        marker.style.setProperty("--gp-tag-bg", group.background);
        marker.dataset.colourGroup = group.key;
      } else if (colour().enabled) marker.style.setProperty("--gp-tag-bg", "#ffffff");
      marker.title = readOnly ? "Klicka för indata och resultat · Shift + klick markerar raden i tabellen"
        : placementLocked({type: "tag", id: tag.id}) ? "Placering låst · dra för att panorera · klicka för indata"
        : selected.has(tag.id) && selected.size + selectedOverlays.size > 1 ? "Dra för att flytta urvalets upplåsta etiketter och widgets tillsammans"
        : "Dra för att flytta · klicka för indata och kopiering";
      const position = positions.get(tag.id) || tag;
      marker.style.left = position.x * 100 + "%";
      marker.style.top = position.y * 100 + "%";
      marker.classList.toggle("gp-active", active === tag.id);
      marker.classList.toggle("gp-multi-selected", selected.has(tag.id));
      marker.classList.toggle("gp-placement-locked", !readOnly && placementLocked({type: "tag", id: tag.id}));
      marker.setAttribute("aria-pressed", String(selected.has(tag.id)));
      if (inactive) {
        const heading = node("span", "gp-tag-heading");
        heading.append(node("strong", "", draft?.label.trim() || tag.label));
        const comment = typeof values.kommentar === "string" ? values.kommentar.trim() : "";
        if (comment) heading.append(commentBubble(tag, comment));
        marker.style.setProperty("--gp-tag-bg", "#ffffff");
        marker.setAttribute("aria-label", tag.label + ", Inaktiv");
        marker.append(heading, node("span", "gp-tag-result", "Inaktiv"));
        markers.append(marker);
        if (leaderFor(tag)?.enabled) leaderResizeObserver.observe(marker);
        continue;
      }
      const insulated = !onlyH && values.isolering === true;
      const insulationText = insulated ? "Med isolering" : "Utan isolering";
      const label = draft?.label.trim() || tag.label;
      const heading = node("span", "gp-tag-heading");
      const insulation = node("span", "gp-tag-insulation");
      insulation.append(insulationIcon(insulated), node("span", "", insulationText));
      heading.append(node("strong", "", label), insulation);
      const comment = typeof values.kommentar === "string" ? values.kommentar.trim() : "";
      if (comment) heading.append(commentBubble(tag, comment));
      const dimensions = [];
      if (!onlyH && summary && Number.isFinite(summary.b) && Number.isFinite(tag.values.l)) {
        dimensions.push("bₓ " + number(summary.b) + " m");
        if (tag.values.lang === 0 || tag.values.l !== 1) dimensions.push("bᵧ " + number(tag.values.l) + " m");
        if (Number.isFinite(tag.values.t)) dimensions.push("t " + precise(tag.values.t) + " m");
      }
      const geometry = dimensions.join(" · ");
      const showSlidingBlock = !insulated && (values.glid_x || values.glid_y);
      const text = summary
        ? onlyH ? "Endast H-stabilitet" + (geometry ? " · " + geometry : "")
          : "U " + number(summary.utnyttjandegrad * 100, 1) + " % · " + geometry
        : ({ new: "Kontrollera indata", stale: "Uppdaterar…", error: "Kontrollera indata" }[tagState] || "Kontrollera indata");
      const accessibleGeometry = !onlyH && summary && (tag.values.lang === 0 || tag.values.l !== 1) ? ", mått i ordningen bₓ × bᵧ" : "";
      const governingLabel = !onlyH && summary?.styrande;
      const governing = governingLabel ? ", styrande: " + governingLabel : "";
      marker.setAttribute("aria-label", label + ", " + insulationText + ", " + text + accessibleGeometry + governing);
      marker.title += accessibleGeometry + governing;
      if (group) marker.title += " · Färggrupp: " + colourGroupCaption(group) + (group.unit ? " [" + group.unit + "]" : "");
      marker.append(heading, mathText("span", "gp-tag-result", text));
      if (governingLabel) marker.append(node("span", "gp-governing", "Styrande: " + governingLabel));
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
        if (lineLoads(values)) {
          add(data, "L", "su", value("glid_L", "m"));
        }
        for (const axis of ["x", "y"]) if (values["glid_" + axis]) {
          const capacity = slidingDirty.has(tag.id) ? null : tag.sliding?.[axis];
          add(capacities, "H", axis + ",Rd,i", capacity == null ? "—" : compactNumber(capacity, 1) + " kN", true);
        }
        grid.append(data, capacities); section.append(grid); marker.append(section);
      }
      markers.append(marker);
      if (group) paintGroupPattern(marker, group);
      if (leaderFor(tag)?.enabled) leaderResizeObserver.observe(marker);
    }
    refreshGroupPatterns(true);
    renderLeaders();
    syncTableSelection();
  }
  const groups = [
    ["Geometri", ["lang", "inaktiv", "lasttyp", "endast_h_stabilitet", "b", "l", "l_override", "L_vagg_minst_1", "L_vagg", "t", "e_b_plac", "e_l_plac"]],
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
    if (tag.values.inaktiv && !["label", "inaktiv", "kommentar"].includes(name)) return "—";
    if (resultantFields.has(name)) {
      const total = dirty.has(tag.id) ? null : tag.load_resultants?.[resultantFields.get(name).phase];
      return Number.isFinite(total) ? precise(total) : "—";
    }
    if (tag.values.endast_h_stabilitet && name === "isolering") return "Nej";
    if (tag.values.endast_h_stabilitet && insulationNames.has(name)) return "—";
    if (tag.values.endast_h_stabilitet && bearingOnlyNames.has(name)) return "—";
    if (["L_vagg_minst_1", "l_override"].includes(name) && tag.values.lang === 0) return "—";
    if (name === "glid_L" && !lineLoads(tag.values)) return "—";
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
    if (readOnly || control.disabled || resultantFields.has(name) || importBusy || bulkBusy || deleteBusy) return;
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
    const selectedInactive = selectionTags().some(tag => drafts.get(tag.id)?.values.inaktiv ?? tag.values.inaktiv);
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
        const inactiveField = (values.inaktiv || selected.has(tag.id) && selectedInactive)
          && !["inaktiv", "kommentar"].includes(name);
        const blocked = selected.has(tag.id) && (mixed && sameTypeFields.has(name) || mixedLoads && loadTypeFields.has(name));
        const ownLength = drafts.get(tag.id)?.values.l_override ?? tag.values.l_override;
        const atLeastOne = drafts.get(tag.id)?.values.L_vagg_minst_1 ?? tag.values.L_vagg_minst_1;
        const ignored = (drafts.get(tag.id)?.values.endast_h_stabilitet ?? tag.values.endast_h_stabilitet)
          && (bearingOnlyNames.has(name) || insulationNames.has(name));
        control.hidden = name === "lasttyp" && Number(values.lang) === 1;
        control.disabled = inactiveField || busy || blocked || (name === "lang" && physicalType(tag) === "pelarsula") || (["L_vagg_minst_1", "l_override"].includes(name) && Number(values.lang) === 0)
          || (name === "glid_L" && !lineLoads(values))
          || (name === "lasttyp" && Number(values.lang) === 1) || (name === "L_vagg" && !lineLoads(values))
          || ignored || (name === "l" && tag.values.lang === 1 && !ownLength)
          || (name === "L_vagg" && Number(values.lang) === 1 && atLeastOne && !(drafts.get(tag.id)?.values.endast_h_stabilitet ?? tag.values.endast_h_stabilitet));
        control.title = inactiveField ? "Inaktiv sula: endast kommentaren kan ändras. Avmarkera Inaktiv för att ändra indata."
          : ignored ? name === "isolering" ? "Endast H-stabilitet använder alltid Utan isolering."
          : "Används inte vid Endast H-stabilitet. Det sparade värdet behålls."
          : blocked ? "Välj samma beräkningsmodell och lasttyp för att ändra detta fält gemensamt."
          : name === "label" || name === "lang" ? "Ändras endast för denna sula."
          : selected.has(tag.id) && selected.size > 1 ? "Ändrar denna kolumn för alla " + selected.size + " markerade sulor."
          : name === "L_vagg" && Number(values.lang) === 1 && atLeastOne ? "Minst 1 m: lokal kontroll använder 1 m. Avmarkera för att ange ett kortare linjestöd. Glidning använder L_su."
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
      const inactive = draft?.values.inaktiv ?? tag.values.inaktiv;
      result.textContent = inactive ? "Inaktiv" : summary ? summary.endast_h_stabilitet ? "Endast H" : "U " + number(summary.utnyttjandegrad * 100, 1) + "%"
        : stale || tag.status === "stale" ? "Uppdaterar…" : tag.status === "error" ? "Fel i indata" : "Kontrollera indata";
      result.className = "gp-table-status " + (inactive ? "gp-inactive" : summary ? summary.endast_h_stabilitet ? "gp-horizontal"
        : summary.utnyttjandegrad <= 1 ? "gp-pass" : "gp-fail" : "");
      result.title = inactive ? "Ingår inte i beräkningar eller sammanställningar. Kommentaren kan redigeras."
        : tag.error || (summary?.endast_h_stabilitet ? "Jordens bärighet och isolering kontrolleras inte." : summary?.styrande) || "";
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
  const loadTypeFields = new Set(["L_vagg", "glid_L", "V_Ed_EQU", ...groups[1][1], ...groups[2][1]]);
  function beginDrawingEdit() {
    if (readOnly || drawingBusy || drawingPending || importBusy || bulkBusy || calibrationBusy) return;
    cancelDrag(); setMode("pan"); closeDialog(); closeBulk();
    selected.clear(); selectedOverlays.clear(); overlaySelected = null;
    drawingDraft = {...(state().drawing_layout || {x: 0, y: 0, scale: 1})};
    drawingScaleInput.setCustomValidity("");
    drawingPreview = null; update();
    showMessage("Redigera ritningsunderlag: dra för att flytta, använd hörnen eller Skala. Klar sparar; Avbryt återställer.");
  }
  function finishDrawingEdit(apply) {
    if (!drawingDraft || drawingBusy || drawingPending) return;
    if (apply && !drawingScaleInput.reportValidity()) return;
    cancelDrag();
    const layout = {x: drawingDraft.x, y: drawingDraft.y, scale: drawingDraft.scale}, preview = drawingPreview;
    if (apply && !background().url) return;
    if (!apply) {
      if (preview) command("drawing_cancel", {token: preview.token});
      drawingDraft = drawingPreview = null; update(); fit();
      showMessage("Redigeringen avbröts. Underlag och måttkalibrering behålls."); return;
    }
    const recalibrate = !!preview || layout.scale !== (state().drawing_layout?.scale ?? 1);
    drawingPending = true; update();
    command("drawing_commit", {layout, ...(preview ? {token: preview.token} : {})}, [], reply => {
      drawingPending = false;
      if (reply.ok) {
        drawingDraft = drawingPreview = null;
        if (recalibrate) {measurePoints = []; measureCursor = null; calibrationDraft = null;}
        update();
        showMessage(recalibrate ? "Ritningsunderlaget sparat. Ny måttkalibrering krävs." : "Ritningsunderlagets placering sparad. Måttkalibreringen behålls.");
      } else {update(); showMessage(reply.error, true);}
    });
  }
  function objectScale(object) {return scaleDrafts.get(placementKey(object)) ?? state().object_layout?.scales?.[placementKey(object)] ?? 1;}
  function labelScale(id, value = sizeDraft ?? state().label_size ?? 100) {
    const object = {type: "tag", id};
    return (placementLocked(object) ? state().label_size ?? 100 : value) / 100 * objectScale(object);
  }
  function allObjectKeys() {
    return [...state().tags.filter(t => t.page === background().page).map(t => "tag:" + t.id),
      ...["symbol", "legend", "colour", "insulation", "comments", "reference", ...state().text_objects?.map(t => "text:" + t.id) || []].map(kind => placementKey(overlayObject(kind)))];
  }
  function objectOrder() {
    const keys = allObjectKeys(), order = state().object_layout?.order || [];
    return [...order.filter(k => keys.includes(k)), ...keys.filter(k => !order.includes(k))];
  }
  function objectZ(object) {return 10 + Math.max(0, objectOrder().indexOf(placementKey(object))) * 2;}
  function changeOrder(operation) {
    const objects = selectionObjects(); if (!objects.length || objectsBusy) return;
    objectsBusy = true; showSelection();
    command("object_order", {objects, operation}, [], reply => {
      objectsBusy = false; renderMarkers(); renderSlidingGeometry(); showSelection();
      if (reply.ok) showMessage("Lagerordningen uppdaterad."); else showMessage(reply.error, true);
    });
  }
  function objectElement(object) {
    return object.type === "tag" ? [...markers.children].find(e => e.dataset.tagId === object.id)
      : visibleOverlays().find(e => e.dataset.kind === object.kind);
  }
  function selectedTransformStarts() {
    return new Map(selectionObjects().filter(o => !placementLocked(o)).map(object => {
      const position = object.type === "tag" ? positions.get(object.id) || state().tags.find(t => t.id === object.id) : overlayPosition(object.kind);
      return [placementKey(object), {object, position: {x: position.x, y: position.y}, scale: objectScale(object)}];
    }));
  }
  function objectSelectionFrame(starts) {
    const rect = sheet.getBoundingClientRect(), boxes = [...starts.values()].map(({object}) => objectElement(object)?.getBoundingClientRect()).filter(Boolean);
    if (!boxes.length || !rect.width) return null;
    const left = Math.min(...boxes.map(b => b.left)), top = Math.min(...boxes.map(b => b.top)),
      right = Math.max(...boxes.map(b => b.left + b.width)), bottom = Math.max(...boxes.map(b => b.top + b.height));
    return {x: (left - rect.left) / rect.width, y: (top - rect.top) / rect.height,
      left, top, width: right - left, height: bottom - top};
  }
  function showObjectFrame() {
    const starts = selectedTransformStarts(), frame = objectSelectionFrame(starts);
    objectFrame.hidden = readOnly || !!drawingDraft || !!cropDraft || measuring() || objectsBusy || !frame;
    if (objectFrame.hidden) return;
    const rect = viewport.getBoundingClientRect();
    objectFrame.style.left = frame.left - rect.left + "px"; objectFrame.style.top = frame.top - rect.top + "px";
    objectFrame.style.width = frame.width + "px"; objectFrame.style.height = frame.height + "px";
  }
  function scaleObjects(starts, frame, factor) {
    if (!starts.size || !frame) return;
    const values = [...starts.values()], bounds = canvasBounds();
    let low = Math.max(...values.map(v => .1 / v.scale)), high = Math.min(...values.map(v => 10 / v.scale));
    // Keep every anchor inside the existing canvas envelope, preserving group geometry.
    for (const {position} of values) for (const [axis, a, b] of [["x", bounds.left, bounds.right], ["y", bounds.top, bounds.bottom]]) {
      const delta = position[axis] - frame[axis];
      if (delta > 0) {
        low = Math.max(low, (Math.min(a, position[axis]) - frame[axis]) / delta);
        high = Math.min(high, (Math.max(b, position[axis]) - frame[axis]) / delta);
      }
    }
    const f = Math.max(low, Math.min(high, factor));
    for (const {object, position, scale} of values) {
      const p = {x: frame.x + (position.x - frame.x) * f, y: frame.y + (position.y - frame.y) * f};
      scaleDrafts.set(placementKey(object), scale * f);
      if (object.type === "tag") positions.set(object.id, p);
      else overlayPositions.set(object.page + ":" + object.kind, {...overlayPosition(object.kind), ...p});
    }
    renderMarkers(); renderSlidingGeometry(); showObjectFrame();
  }
  function saveObjectTransforms(starts) {
    if (!starts.size || objectsBusy) return;
    const objects = [...starts.values()].map(({object}) => {
      const p = object.type === "tag" ? positions.get(object.id) : overlayPositions.get(object.page + ":" + object.kind);
      return {...object, x: p.x, y: p.y, scale: objectScale(object)};
    });
    objectsBusy = true; showSelection();
    command("transform_objects", {objects}, [], reply => {
      for (const {object} of starts.values()) {
        scaleDrafts.delete(placementKey(object));
        if (object.type === "tag") positions.delete(object.id);
        else overlayPositions.delete(object.page + ":" + object.kind);
      }
      objectsBusy = false; renderMarkers(); renderSlidingGeometry(); showSelection();
      if (reply.ok) showMessage(objects.length + " objekt skalade."); else showMessage(reply.error, true);
    });
  }
  function pickedTarget(event) {
    // Native hit testing respects clipping and each object's stacking order.
    if (event.target.closest(".gp-leader-handle") || event.target.closest(".gp-leader-hit")) return event.target;
    if (!document.elementsFromPoint) return event.target;
    const candidates = [], seen = new Set();
    for (const element of document.elementsFromPoint(event.clientX, event.clientY)) {
      const target = element.closest(".gp-tag") || element.closest(".gp-sliding-overlay");
      if (!target || target.closest(".an-grundplan") !== root || target.hidden || seen.has(target)) continue;
      seen.add(target);
      const object = target.dataset.tagId ? {type: "tag", id: target.dataset.tagId} : overlayObject(target.dataset.kind);
      candidates.push({target, element, object});
    }
    candidates.sort((a, b) => Number(placementLocked(a.object)) - Number(placementLocked(b.object)) || objectZ(b.object) - objectZ(a.object));
    if (!candidates.length) return event.target;
    const winner = candidates[0];
    return event.target.closest(".gp-tag") === winner.target || event.target.closest(".gp-sliding-overlay") === winner.target ? event.target : winner.element;
  }
  function selectionTags() { return state().tags.filter(tag => selected.has(tag.id)); }
  function overlayObject(kind) { return {type: "overlay", kind, page: background().page}; }
  function placementKey(object) {
    return object.type === "tag" ? "tag:" + object.id : "overlay:" + object.page + ":" + object.kind;
  }
  function placementLocked(object) {
    const key = placementKey(object);
    return lockDrafts.get(key)?.locked ?? (state().placement_locks || []).some(item => placementKey(item) === key);
  }
  function visibleOverlays() { return [...overlays.children].filter(element => !element.hidden); }
  function selectionObjects() {
    const kinds = new Set(visibleOverlays().map(element => element.dataset.kind));
    return [...selectionTags().filter(tag => tag.page === background().page).map(tag => ({type: "tag", id: tag.id})),
      ...[...selectedOverlays].filter(kind => kinds.has(kind)).map(overlayObject)];
  }
  function chooseOverlay(kind, toggle = false) {
    if (readOnly || bulkBusy) return;
    if (toggle && active) selected.add(active);
    closeDialog(); closeBulk();
    if (toggle) {
      if (selectedOverlays.has(kind)) selectedOverlays.delete(kind); else selectedOverlays.add(kind);
    } else if (!selectedOverlays.has(kind)) {
      selected.clear(); selectedOverlays.clear(); selectedOverlays.add(kind);
    }
    overlaySelected = selectedOverlays.has(kind) ? kind : null;
    bulkSignature = ""; tableAnchor = null;
    renderMarkers(); renderSlidingGeometry(); showSelection();
  }
  function selectOverlayClick(kind, event) {
    if (readOnly) return;
    // A pointer gesture already handled selection on pointerup. Keyboard clicks
    // still select here; body clicks are handled by their enclosing widget.
    if (event?.detail && overlayClickHandled) {overlayClickHandled = null; return;}
    chooseOverlay(kind, !!(event?.shiftKey || event?.ctrlKey || event?.metaKey));
  }
  function selectOverlayBody(kind, event) {
    if (event.target.closest(".gp-sliding-handle") || event.target.closest(".gp-overlay-resize")) return;
    selectOverlayClick(kind, event);
  }
  function setPlacementLock(locked, objects = selectionObjects()) {
    if (readOnly || bulkBusy || !objects.length) return;
    cancelDrag();
    const draft = {locked};
    for (const object of objects) lockDrafts.set(placementKey(object), draft);
    renderMarkers(); renderSlidingGeometry(); showSelection();
    command("placement_lock", {objects, locked}, [], reply => {
      for (const object of objects) if (lockDrafts.get(placementKey(object)) === draft) lockDrafts.delete(placementKey(object));
      renderMarkers(); renderSlidingGeometry(); showSelection();
      if (reply.ok) showMessage(objects.length + (locked ? " objekt har låst placering." : " objekt har upplåst placering."));
    });
  }
  function movementStarts(object) {
    const selectedObject = object.type === "tag" ? selected.has(object.id) : selectedOverlays.has(object.kind);
    const objects = placementLocked(object) ? [] : selectedObject ? selectionObjects() : [object];
    return new Map(objects.filter(item => !placementLocked(item)).map(item => {
      const p = item.type === "tag" ? positions.get(item.id) || state().tags.find(tag => tag.id === item.id) : overlayPosition(item.kind);
      return [placementKey(item), {object: item, position: {x: p.x, y: p.y}}];
    }));
  }
  function moveObjects(starts, dx, dy) {
    if (!starts.size) return;
    const points = [...starts.values()].map(item => item.position);
    const bounds = canvasBounds();
    const mx = Math.max(Math.min(0, bounds.left - Math.min(...points.map(p => p.x))), Math.min(Math.max(0, bounds.right - Math.max(...points.map(p => p.x))), dx));
    const my = Math.max(Math.min(0, bounds.top - Math.min(...points.map(p => p.y))), Math.min(Math.max(0, bounds.bottom - Math.max(...points.map(p => p.y))), dy));
    for (const {object, position} of starts.values()) {
      const p = {x: position.x + mx, y: position.y + my};
      if (object.type === "tag") positions.set(object.id, p);
      else overlayPositions.set(object.page + ":" + object.kind, {...overlayPosition(object.kind), ...p});
    }
    renderMarkers(); renderSlidingGeometry();
  }
  function saveObjectPositions(starts) {
    const objects = [...starts.values()].map(({object}) => {
      const p = object.type === "tag" ? positions.get(object.id) : overlayPositions.get(object.page + ":" + object.kind);
      return {object, position: p};
    });
    if (!objects.length) return;
    if (objects.length === 1 && objects[0].object.type === "overlay") {
      const {object, position} = objects[0]; saveOverlayPosition(object.kind, object.page, position); return;
    }
    for (const {object, position} of objects) {
      if (object.type === "tag") pendingPositions.set(object.id, position);
      else pendingOverlayPositions.set(object.page + ":" + object.kind, position);
    }
    const tagsOnly = objects.every(item => item.object.type === "tag");
    const payload = tagsOnly ? objects.map(({object, position}) => ({id: object.id, ...position}))
      : objects.map(({object, position}) => ({...object, x: position.x, y: position.y}));
    command(tagsOnly ? objects.length > 1 ? "move_tags" : "update" : "move_objects",
      tagsOnly ? objects.length > 1 ? {positions: payload} : payload[0] : {objects: payload}, [], reply => {
      for (const {object, position} of objects) {
        const key = object.type === "tag" ? object.id : object.page + ":" + object.kind;
        const local = object.type === "tag" ? positions : overlayPositions;
        const pending = object.type === "tag" ? pendingPositions : pendingOverlayPositions;
        if (pending.get(key) === position) pending.delete(key);
        if (local.get(key) === position) local.delete(key);
      }
      renderMarkers(); renderSlidingGeometry();
      if (reply.ok) showMessage(objects.length + " markerade objekt flyttade.");
    });
  }
  function showSelection() {
    // Keep the canvas at the same screen position while the selection box is drawn.
    if (drag?.box) return;
    const objects = selectionObjects(), locked = objects.filter(placementLocked).length;
    selectionBar.hidden = !objects.length;
    selectionCount.textContent = objects.length + " markerade" + (locked ? " · " + locked + " låsta" : "");
    const titles = [...selectionTags().map(tag => tag.label), ...selectedOverlays].join(", ");
    selectionCount.title = titles;
    selectionBar.setAttribute("aria-label", "Markerade objekt: " + titles);
    editMany.disabled = bulkBusy || !selected.size; clearMany.disabled = bulkBusy;
    lockMany.disabled = bulkBusy || locked === objects.length;
    unlockMany.disabled = bulkBusy || !locked;
    objectScaleInput.disabled = objectScaleApply.disabled = bulkBusy || objectsBusy || locked === objects.length;
    for (const b of orderButtons) b.disabled = bulkBusy || objectsBusy || drawingPending;
    showObjectFrame();
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
    const hasInactive = tags.some(tag => tag.values.inaktiv);
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
        const footingLength = bulkInputs.get("glid_L");
        if (footingLength) {
          footingLength.blocked = !common;
          footingLength.choose.disabled = footingLength.input.disabled = !common;
          if (!common) footingLength.choose.checked = false;
          footingLength.row.hidden = !common;
        }
        for (const [name, entry] of bulkInputs) if (loadTypeFields.has(name) && !["L_vagg", "glid_L"].includes(name)) {
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
      + (hasInactive ? "Urvalet innehåller inaktiva sulor. Endast Inaktiv och Kommentar kan ändras. "
        : mixed ? "Blandade sultyper: last- och längdfält kräver att du väljer enbart väggsulor eller enbart pelarsulor. "
        : strip ? "Väggsulor: laster anges per meter. " : "Pelarsulemodell: lasttypen avgör om lasten anges per meter eller som punktlast. ")
      + "Urval: " + tags.map(tag => tag.label).join(", ");
    for (const [index, [label, names, note]] of groups.entries()) {
      if (label === "Glidning" && !sliding().enabled && !tags.some(tag => tag.values.endast_h_stabilitet)) continue;
      const available = names.filter(name => fieldSchema.has(name) && name !== "lang"
        && (!hasInactive || ["inaktiv", "kommentar"].includes(name))
        && !(onlyH && (bearingOnlyNames.has(name) || insulationNames.has(name)))
        && !(strip && name === "lasttyp")
        && !(!mixed && !strip && ["L_vagg_minst_1", "l_override"].includes(name)));
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
        const message = report.calculated + " av " + report.updated + " sulor beräknade automatiskt."
          + (report.inactive ? " " + report.inactive + " inaktiva sulor undantagna." : "");
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
    const typeNote = node("p", "gp-field-note gp-footing-type", "Sultyp: " + FOOTING_CATEGORIES[footingCategory(tag)]);
    fieldsBox.append(typeNote);
    if (tag.footing_type_inferred) {
      const note = node("div", "gp-type-confirmation");
      note.append(node("p", "gp-field-note", "Äldre objekt: ursprunglig sultyp saknas. Bekräfta för att använda Referens."));
      if (!readOnly && !tag.values.inaktiv) {
        const choice = node("select"); choice.setAttribute("aria-label", "Bekräfta ursprunglig sultyp");
        for (const [kind, caption] of [["vaggsula", "Väggsula"], ["pelarsula", "Pelarsula"]]) {
          const option = node("option", "", caption); option.value = kind; choice.append(option);
        }
        choice.value = physicalType(tag);
        const confirm = button("Bekräfta sultyp", () => {
          confirm.disabled = true;
          command("footing_type", {id: tag.id, kind: choice.value}, [], reply => {
            confirm.disabled = false;
            if (reply.ok) buildFields(current()); else showMessage(reply.error, true);
          });
        });
        note.append(choice, confirm);
      }
      fieldsBox.append(note);
    }
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
            control.title = "Lokal bärighets- och isoleringskontroll använder 1 m. Global glidning använder L_su.";
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
    if (inputs.get("inaktiv")?.input.checked) return {inaktiv: true, kommentar: inputs.get("kommentar")?.input.value ?? current().values.kommentar};
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
    const inactive = readOnly ? current()?.values.inaktiv : inputs.get("inaktiv")?.input.checked;
    if (!readOnly) labelInput.disabled = !!inactive;
    if (inactive) {
      basis.textContent = "Inaktiv sula: ingår inte i beräkningar, färggruppering eller isoleringswidgeten. Kommentaren kan redigeras. Sparade indata behålls.";
      for (const [name, entry] of inputs) {
        const editable = ["inaktiv", "kommentar"].includes(name);
        entry.row.hidden = !editable;
        if (!readOnly) {entry.input.disabled = !editable; entry.input.required = false; entry.input.setCustomValidity("");}
      }
      for (const group of new Set([...inputs.values()].map(entry => entry.group)))
        group.hidden = ![...inputs.values()].some(entry => entry.group === group && !entry.row.hidden);
      showSketch(); showLeaderChoice();
      return;
    }
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
        : "Pelarsula: ange punktlaster och moment. Egentyngd tillkommer i beräkningen.";
    if (strip) {
      basis.replaceChildren(mathText("span", "", "Väggsula: laster och moment anges per meter linjestöd. Yttre lastresultant = angivet värde × "
        + (atLeastOne ? "1 m (Minst 1 m)." : "kort L_vägg.")
        + " Sulmåttet b_y anger fördelningslängden under sulan och ändrar inte den yttre lastresultanten. Egentyngd tillkommer."));
    }
    if (!strip && line) basis.replaceChildren(mathText("span", "", "Pelarsulemodell med linjelast: laster och moment anges per meter linjestöd och multipliceras med hela L_vägg. b_x och b_y anger kontaktmåtten. Egentyngd tillkommer i beräkningen."));
    if (onlyH) basis.replaceChildren(mathText("span", "", "Endast H-stabilitet: jordens bärighet och isolering kontrolleras inte. V_Ed,EQU ska redan innehålla sulans egentyngd."));
    for (const [name, entry] of inputs) {
      if (name === "lang") {
        const pad = physicalType(current()) === "pelarsula";
        entry.row.hidden = pad;
        if (!readOnly) {entry.input.disabled = pad; entry.input.required = !pad;}
        continue;
      }
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
        entry.row.hidden = !line || onlyH;
        entry.unit.textContent = "m";
        entry.row.title = strip ? "Bärighet/isolering: Minst 1 m använder 1 m, annars angiven kort längd. Glidning använder L_su."
          : "Hela linjestödslängden används för att omräkna linjelasten till total kraft. Sulmåtten ändrar inte resultanten.";
        if (readOnly) entry.input.textContent = strip && atLeastOne && !onlyH ? "1" : current()?.values.L_vagg == null ? "—" : number(current().values.L_vagg, 10);
        else {
          entry.input.hidden = strip && atLeastOne && !onlyH;
          entry.fixed.hidden = !entry.input.hidden;
          entry.input.disabled = !line || onlyH || (strip && atLeastOne);
          entry.input.required = line && !(strip && atLeastOne) && !onlyH;
          entry.input.placeholder = onlyH || !strip ? "Hela linjestödslängden" : "Kortare än 1 m";
          if (entry.input.disabled) entry.input.setCustomValidity("");
        }
        continue;
      }
      if (slidingNames.has(name)) {
        const numeric = !["glid_x", "glid_y"].includes(name);
        const length = name === "glid_L";
        const disabled = (!sliding().enabled && !onlyH) || (length ? !line : insulated);
        entry.row.hidden = (!sliding().enabled && !onlyH) || (length ? !line : numeric && insulated);
        entry.unit.textContent = name === "V_Ed_EQU" ? (line ? "kN/m" : "kN") : fieldSchema.get(name).unit;
        if (!readOnly) { entry.input.disabled = disabled; entry.input.required = numeric && !disabled && selected && !insulated;
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
    if (drafts.get(tag.id)?.values.inaktiv ?? tag.values.inaktiv) {
      results.append(node("strong", "gp-inactive", "Inaktiv"),
        node("p", "gp-result-note", "Sulan ingår inte i bärighets-, isolerings- eller glidningsberäkningar."));
      return;
    }
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
      ["Lasteffekt q_Ed", number(r.q_Ed) + " kPa"],
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
    if (leaderPlacement && (bg.url !== lastBackground
      || !data.tags.some(tag => tag.id === leaderPlacement.id && tag.page === bg.page && !tag.values.inaktiv))) {
      cancelDrag(); leaderPlacement = null;
      viewport.classList.remove("gp-placing-leader");
    }
    if (leaderEdit && !data.tags.some(tag => tag.id === leaderEdit && !tag.values.inaktiv && leaderFor(tag)?.enabled)) leaderEdit = leaderNode = null;
    for (const id of selected) {
      if (!data.tags.some(tag => tag.id === id)) selected.delete(id);
    }
    if (!bulkDialog.hidden && bulkIds.some(id => !selected.has(id))) {
      closeBulk(); bulkSignature = "";
    }
    showLayout();
    showHeading();
    showCanvas();
    showLabelSize(sizeDraft ?? data.label_size ?? 100);
    const storage = data.storage;
    showStorage(storage);
    total.textContent = data.tags.length + (data.tags.length === 1 ? " sula" : " sulor");
    loadDrawing.disabled = drawingBusy || drawingPending || !!drawingDraft || !!cropDraft || !!canvasPending || importBusy || bulkBusy || calibrationBusy || deleteBusy;
    loadDrawing.title = "Flytta, skala eller uppdatera ritningsunderlaget i ett separat redigeringsläge.";
    const editingDrawing = !!drawingDraft || drawingPending || drawingBusy;
    loadProject.disabled = editingDrawing;
    sizeInput.disabled = editingDrawing;
    saveProject.disabled = saving || !!cropDraft || !!canvasPending || !!drawingDraft || drawingPending;
    exportJson.disabled = !bg.url || editingDrawing;
    for (const entry of exports) entry.button.disabled = entry.busy || !bg.url || !!cropDraft || !!canvasPending || !!drawingDraft || drawingPending;
    empty.hidden = !!bg.url;
    sheet.hidden = !bg.url;
    zoomBar.hidden = !bg.url;
    for (const b of modes.values()) b.disabled = !bg.url || drawingBusy || !!cropDraft || !!canvasPending || !!drawingDraft || drawingPending;
    showSelection();
    showLoadImport();
    if (mode === "measure" && !calibration()) {
      measurePoints = []; measureCursor = null; mode = "calibrate";
    }
    if (bg.url !== lastBackground) {
      cancelDrag();
      cropDraft = canvasPending = null; showCanvas();
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
      showLeaderChoice();
      showResult();
    } else sketch.hidden = true;
    renderMarkers();
    showSliding();
    showColour();
    showTable();
    showLayout();
    showMeasurement();
    showTextObjects();
    const visibleKinds = new Set(visibleOverlays().map(element => element.dataset.kind));
    for (const kind of selectedOverlays) if (!visibleKinds.has(kind)) selectedOverlays.delete(kind);
    if (overlaySelected && !visibleKinds.has(overlaySelected)) overlaySelected = null;
    showSelection();
    if (editingDrawing) for (const b of [loadEffects, deleteAll, slidingToggle, colourToggle,
      insulationWidgetToggle, commentWidgetToggle, referenceToggle]) b.disabled = true;
    showHistory();
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
    const pageBox = paper.getBoundingClientRect();
    const intersects = bounds => Math.max(bounds.left, rect.left, pageBox.left)
      < Math.min(bounds.left + bounds.width, rect.right, pageBox.left + pageBox.width)
      && Math.max(bounds.top, rect.top, pageBox.top)
      < Math.min(bounds.top + bounds.height, rect.bottom, pageBox.top + pageBox.height);
    selectionBox.hidden = false;
    selectionBox.style.left = rect.localLeft + "px";
    selectionBox.style.top = rect.localTop + "px";
    selectionBox.style.width = rect.width + "px";
    selectionBox.style.height = rect.height + "px";
    // Always toggle against the selection at pointerdown, so repeated moves do not toggle again.
    const ids = new Set(drag.beforeSelection);
    if (rect.width > 0 && rect.height > 0) for (const marker of markers.children) {
      const bounds = marker.getBoundingClientRect();
      if (intersects(bounds)) {
        const id = marker.dataset.tagId;
        if (ids.has(id)) ids.delete(id); else ids.add(id);
      }
    }
    selected.clear();
    for (const id of ids) selected.add(id);
    const kinds = new Set(drag.beforeOverlays);
    if (!readOnly && rect.width > 0 && rect.height > 0) for (const element of visibleOverlays()) {
      const bounds = element.getBoundingClientRect();
      if (intersects(bounds)) {
        const kind = element.dataset.kind;
        if (kinds.has(kind)) kinds.delete(kind); else kinds.add(kind);
      }
    }
    selectedOverlays.clear(); for (const kind of kinds) selectedOverlays.add(kind);
    overlaySelected = null; renderSlidingGeometry();
    renderMarkers();
  }
  function cancelDrag() {
    const previous = drag;
    drag = null;
    selectionBox.hidden = true;
    if (previous?.drawing && drawingDraft) {drawingDraft = previous.beforeDrawing; showCanvas();}
    if (previous?.objectScaling) for (const {object} of previous.objectPositions.values()) scaleDrafts.delete(placementKey(object));
    if (previous?.crop && cropDraft) {cropDraft = previous.beforeCrop; showCanvas();}
    if (previous?.box) {
      selected.clear();
      for (const id of previous.beforeSelection) {
        if (state().tags.some(tag => tag.id === id && tag.page === background().page)) selected.add(id);
      }
      selectedOverlays.clear(); for (const kind of previous.beforeOverlays) selectedOverlays.add(kind);
      renderSlidingGeometry();
      renderMarkers(); showSelection();
    }
    if (previous?.leader) {
      if (previous.hadLeaderDraft) leaderDrafts.set(previous.leader, previous.beforeLeader);
      else leaderDrafts.delete(previous.leader);
      renderLeaders();
    }
    if (previous?.stroke && leaderPlacement) {
      leaderPlacement.stroke = null; leaderPlacement.drawingAttachment = null; renderLeaders();
    }
    if (previous?.overlay) {
      const key = previous.page + ":" + previous.overlay;
      if (pendingOverlayPositions.has(key)) overlayPositions.set(key, pendingOverlayPositions.get(key));
      else overlayPositions.delete(key);
      renderSlidingGeometry();
    }
    if (previous?.objectPositions) for (const {object} of previous.objectPositions.values()) {
      const key = object.type === "tag" ? object.id : object.page + ":" + object.kind;
      const local = object.type === "tag" ? positions : overlayPositions;
      const pending = object.type === "tag" ? pendingPositions : pendingOverlayPositions;
      if (pending.has(key)) local.set(key, pending.get(key)); else local.delete(key);
    }
    if (previous?.objectPositions) {renderMarkers(); renderSlidingGeometry();}
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    viewport.classList.remove("gp-selecting");
    if (previous && viewport.hasPointerCapture(previous.pointerId)) viewport.releasePointerCapture(previous.pointerId);
    if (previous?.id) renderMarkers();
  }
  viewport.addEventListener("pointerdown", (event) => {
    if (![0, 2].includes(event.button) || drag || drawingBusy || drawingPending || objectsBusy || deleteBusy || !background().url) return;
    if (event.button === 2) {
      event.preventDefault();
      viewport.focus({preventScroll: true});
      drag = {pan: true, x: event.clientX, y: event.clientY, left: panX, top: panY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    if (drawingDraft) {
      event.preventDefault(); viewport.focus({preventScroll: true});
      drawingScaleInput.setCustomValidity("");
      const corner = event.target.closest(".gp-drawing-handle")?.dataset.corner;
      const inside = !!event.target.closest(".gp-drawing-frame");
      const rect = picture.getBoundingClientRect();
      drag = {drawing: inside, drawingCorner: corner, beforeDrawing: {...drawingDraft},
        width: rect.width, height: rect.height, pan: !inside,
        x: event.clientX, y: event.clientY, left: panX, top: panY, moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId); return;
    }
    if (event.target.closest(".gp-object-handle") && !readOnly) {
      const starts = selectedTransformStarts(), frame = objectSelectionFrame(starts); if (!frame) return;
      event.preventDefault(); viewport.focus({preventScroll: true});
      drag = {objectScaling: true, objectPositions: starts, frame, x: event.clientX, y: event.clientY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId); return;
    }
    if (cropDraft || canvasPending) {
      event.preventDefault(); viewport.focus({preventScroll: true});
      const edge = cropDraft && (event.target.closest(".gp-crop-handle") || event.target.closest(".gp-crop-edge"))?.dataset.edge;
      drag = {crop: edge, beforeCrop: cropDraft && {...cropDraft}, pan: !edge,
        x: event.clientX, y: event.clientY, left: panX, top: panY, moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId); return;
    }
    if (leaderPlacement && !readOnly && !importBusy && !bulkBusy) {
      const box = leaderBox(leaderPlacement.id), point = measurementPoint(event); if (!box || !point) return;
      const marker = event.target.closest(".gp-tag"), ownFrame = marker?.dataset.tagId === leaderPlacement.id;
      const attachment = leaderPlacement.attachment || leaderAttachment(point, box);
      const endpoint = leaderEndpoint(attachment, box), bg = background();
      const nearStart = Math.hypot((point.x - endpoint.x) * bg.width, (point.y - endpoint.y) * bg.height) * zoom < 16;
      event.preventDefault(); viewport.focus({preventScroll: true});
      if (!ownFrame && !nearStart && leaderPlacement.attachment) {
        showMessage("Börja vid den blå anslutningspunkten på etiketten. Escape behåller den gamla linjen."); return;
      }
      const drawing = ownFrame || nearStart;
      drag = {stroke: drawing, leaderClick: drawing ? null : leaderPlacement.id, attachment,
        x: event.clientX, y: event.clientY, moved: false, pointerId: event.pointerId};
      if (drawing) {leaderPlacement.stroke = [endpoint]; leaderPlacement.drawingAttachment = attachment;}
      viewport.setPointerCapture(event.pointerId); renderLeaders(); return;
    }
    const hitTarget = pickedTarget(event);
    // The original DOM target can be a locked widget above the winning label.
    // Its later native click must not override selection handled on pointerup.
    if (event.target.closest(".gp-sliding-overlay")) overlayClickHandled = true;
    if (hitTarget.closest(".gp-tag-comment")) return;
    if (hitTarget.closest(".gp-annotation-editor") || hitTarget.closest(".gp-annotation-tools")) return;
    if (bulkBusy) return;
    if (!readOnly && !measuring() && !importBusy) {
      const handle = hitTarget.closest(".gp-leader-handle"), hit = hitTarget.closest(".gp-leader-hit");
      if (handle || hit) {
        event.preventDefault(); viewport.focus({preventScroll: true});
        const id = (handle || hit).dataset.tagId, tag = state().tags.find(tag => tag.id === id);
        if (!tag) return;
        if (!handle) {beginLeaderEdit(id); return;}
        leaderNode = handle.dataset.handle === "node" ? Number(handle.dataset.index) : null;
        drag = {leader: id, index: Number(handle.dataset.index), handle: handle.dataset.handle,
          beforeLeader: leaderFor(tag), hadLeaderDraft: leaderDrafts.has(id),
          x: event.clientX, y: event.clientY, moved: false, pointerId: event.pointerId};
        viewport.setPointerCapture(event.pointerId); renderLeaders(); return;
      }
    }
    if (measuring() && !(event.shiftKey || event.ctrlKey || event.metaKey)) {
      if (calibrationBusy || importBusy) return;
      event.preventDefault(); viewport.focus({preventScroll: true});
      drag = {measurement: true, x: event.clientX, y: event.clientY, left: panX, top: panY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    const overlay = hitTarget.closest(".gp-sliding-overlay");
    if (importBusy && (overlay || hitTarget.closest(".gp-tag"))) return;
    if (overlay) {
      const resize = !!hitTarget.closest(".gp-overlay-resize") || hitTarget === axesResize;
      const select = !!(event.shiftKey || event.ctrlKey || event.metaKey), kind = overlay.dataset.kind;
      if (readOnly) return;
      event.preventDefault();
      setMode("pan");
      overlayClickHandled = kind;
      const rect = overlay.getBoundingClientRect();
      const objectPositions = resize || select || !hitTarget.closest(".gp-sliding-handle") ? new Map() : movementStarts(overlayObject(kind));
      drag = {overlay: kind, page: background().page, resize: resize && !placementLocked(overlayObject(kind)), select,
        box: select, beforeSelection: new Set(selected), beforeOverlays: new Set(selectedOverlays),
        objectPositions, placementPan: !resize && !select && !objectPositions.size,
        left: panX, top: panY,
        width: rect.width, height: rect.height,
        position: {...overlayPosition(kind)}, x: event.clientX, y: event.clientY,
        moved: false, pointerId: event.pointerId};
      viewport.setPointerCapture(event.pointerId);
      return;
    }
    const marker = hitTarget.closest(".gp-tag");
    const tag = marker && state().tags.find((t) => t.id === marker.dataset.tagId);
    if (!tag && hitTarget.closest("button")) return;
    event.preventDefault();
    viewport.focus({preventScroll: true});
    if (!marker && !leaderPlacement && leaderEdit) {leaderEdit = leaderNode = null; renderLeaders();}
    const select = !!tag && (event.shiftKey || event.ctrlKey || event.metaKey);
    const objectPositions = tag && !select && !readOnly ? movementStarts({type: "tag", id: tag.id}) : new Map();
    drag = { x: event.clientX, y: event.clientY, left: panX, top: panY,
      moved: false, pointerId: event.pointerId, id: tag?.id,
      objectPositions, placementPan: !!tag && !select && !readOnly && !objectPositions.size,
      placementBlocked: importBusy,
      box: !!(event.shiftKey || event.ctrlKey || event.metaKey),
      beforeSelection: new Set(selected),
      beforeOverlays: new Set(selectedOverlays),
      select };
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!drag && measuring() && measurePoints.length === 1) {
      measureCursor = measurementPoint(event); showMeasurement(); return;
    }
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 5) drag.moved = true;
    if (drag.drawing) {
      if (!drag.moved) return;
      const before = drag.beforeDrawing;
      if (drag.drawingCorner) {
        const sx = drag.drawingCorner.includes("left") ? -1 : 1, sy = drag.drawingCorner.includes("top") ? -1 : 1;
        const ratio = Math.max(.1 / before.scale, Math.min(10 / before.scale,
          1 + (sx * dx * drag.width + sy * dy * drag.height) / (drag.width ** 2 + drag.height ** 2)));
        const scale = before.scale * ratio;
        drawingDraft = {...before, scale,
          x: Math.max(-10, Math.min(11, before.x + (sx < 0 ? drag.width * (1 - ratio) / (background().width * zoom) : 0))),
          y: Math.max(-10, Math.min(11, before.y + (sy < 0 ? drag.height * (1 - ratio) / (background().height * zoom) : 0)))};
      } else drawingDraft = {...before,
        x: Math.max(-10, Math.min(11, before.x + dx / (background().width * zoom))),
        y: Math.max(-10, Math.min(11, before.y + dy / (background().height * zoom)))};
      showCanvas(); return;
    }
    if (drag.objectScaling) {
      if (drag.moved) scaleObjects(drag.objectPositions, drag.frame,
        1 + (dx * drag.frame.width + dy * drag.frame.height) / (drag.frame.width ** 2 + drag.frame.height ** 2));
      return;
    }
    if (drag.crop) {
      adjustCrop(drag.crop, drag.beforeCrop, dx / (background().width * zoom), dy / (background().height * zoom)); return;
    }
    if (drag.stroke) {
      const point = measurementPoint(event); if (!point || !leaderPlacement) return;
      const previous = leaderPlacement.stroke.at(-1), bg = background();
      if (Math.hypot((point.x - previous.x) * bg.width, (point.y - previous.y) * bg.height) * zoom >= 2) {
        // Bound memory during a long gesture without losing the whole trace.
        if (leaderPlacement.stroke.length >= 4096) leaderPlacement.stroke = leaderPlacement.stroke.filter((_, i) => !i || i % 2);
        leaderPlacement.stroke.push(point); renderLeaders();
      }
      return;
    }
    if (drag.leaderClick) return;
    if (drag.leader) {
      if (!drag.moved) return;
      const point = measurementPoint(event), box = leaderBox(drag.leader); if (!point || !box) return;
      const value = JSON.parse(JSON.stringify(drag.beforeLeader)), index = drag.index;
      const endpoint = leaderEndpoint(value.attachment, box);
      if (drag.handle === "node") {
        if (index === value.nodes.length) value.attachment = leaderAttachment(point, box);
        else Object.assign(value.nodes[index], point);
      } else {
        const offset = leaderSub(point, index === value.nodes.length ? endpoint : value.nodes[index]);
        if (index === value.nodes.length) value.end_handle = offset;
        else value.nodes[index][drag.handle] = offset;
      }
      leaderDrafts.set(drag.leader, value); renderLeaders(); return;
    }
    if (drag.measurement) {
      if (drag.moved) {
        panX = drag.left + dx; panY = drag.top + dy; placeSheet();
        viewport.classList.add("gp-panning");
      }
      return;
    }
    if (drag.select && !drag.box) return;
    if (drag.moved) {
      if (drag.box) {
        viewport.classList.add("gp-selecting");
        if (active) closeDialog();
        if (!bulkDialog.hidden) closeBulk();
        previewSelection(event);
      } else if (drag.placementPan) {
        panX = drag.left + dx; panY = drag.top + dy; placeSheet();
        viewport.classList.add("gp-panning");
      } else if (!drag.resize && drag.objectPositions?.size) {
        const rect = sheet.getBoundingClientRect();
        moveObjects(drag.objectPositions, dx / rect.width, dy / rect.height);
        viewport.classList.add("gp-dragging-tag"); closeDialog();
      } else if (drag.overlay) {
        const p = {...drag.position};
        if (drag.resize) {
          const delta = drag.overlay === "symbol" ? (dx + dy) / (2 * zoom)
            : p.size * (dx * drag.width + dy * drag.height) / (drag.width ** 2 + drag.height ** 2);
          p.size = overlaySize(drag.overlay, p.size + delta);
        }
        else {
          const rect = sheet.getBoundingClientRect();
          p.x = Math.max(0, Math.min(1, p.x + dx / rect.width));
          p.y = Math.max(0, Math.min(1, p.y + dy / rect.height));
        }
        overlayPositions.set(drag.page + ":" + drag.overlay, p);
        renderSlidingGeometry();
        closeDialog();
      } else if (drag.id) {
        return; // Result views allow selecting labels but cannot move them.
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
    const { moved, id, overlay, page, select, placementBlocked, pan, box, beforeSelection, measurement, leader,
      objectPositions, placementPan, resize, crop, drawing, objectScaling,
      stroke, leaderClick, attachment } = drag;
    drag = null;
    selectionBox.hidden = true;
    viewport.classList.remove("gp-dragging-tag");
    viewport.classList.remove("gp-panning");
    viewport.classList.remove("gp-selecting");
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    if (pan || crop || drawing) return;
    if (objectScaling) {if (moved) saveObjectTransforms(objectPositions); return;}
    if (stroke && leaderPlacement) {
      const point = measurementPoint(event); if (point) leaderPlacement.stroke.push(point);
      const bg = background(), value = point && moved && leaderFromStroke(leaderPlacement.stroke, attachment, bg.width, bg.height, zoom);
      if (value) {
        const id = leaderPlacement.id;
        leaderPlacement = null; viewport.classList.remove("gp-placing-leader");
        saveLeader(id, value); beginLeaderEdit(id);
      } else {
        leaderPlacement.stroke = null; renderLeaders();
        showMessage("Dra en bana från anslutningspunkten till pilspetsen. Escape behåller den gamla linjen.");
      }
      return;
    }
    if (leaderClick) {
      if (!moved && leaderPlacement) {const point = measurementPoint(event); if (point) createLeader(leaderClick, point);}
      return;
    }
    if (leader) {if (moved) saveLeader(leader, leaderDrafts.get(leader)); return;}
    if (measurement) {if (!moved) chooseMeasurementPoint(event); return;}
    if (box) {
      if (moved) {
        if (selected.size !== beforeSelection.size || [...selected].some(id => !beforeSelection.has(id))) bulkSignature = "";
        setMode("pan"); showSelection(); renderMarkers();
        return;
      }
      if (!id && !overlay) return;
    }
    if (overlay) {
      if (select) {if (!moved) chooseOverlay(overlay, true); return;}
      if (moved && !placementPan) {
        if (resize) saveOverlayPosition(overlay, page, overlayPositions.get(page + ":" + overlay));
        else saveObjectPositions(objectPositions);
      } else if (!moved) chooseOverlay(overlay);
      return;
    }
    if (id) {
      const tag = state().tags.find((t) => t.id === id);
      if (select) { if (!moved && tag) toggleTag(tag); return; }
      if (!moved) { if (tag) openDialog(tag); return; }
      if (readOnly || placementPan) return;
      saveObjectPositions(objectPositions);
      return;
    }
    if (readOnly || moved || placementBlocked || mode === "pan") return;
    const rect = sheet.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    const bounds = canvasBounds();
    if (x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom) return;
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
      if (panel === dialog) dialogAnchor = null;
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
    hideHistoryTooltip();
    const key = String(event.key).toLowerCase();
    if (!readOnly && (event.metaKey || event.ctrlKey) && !event.altKey
        && (key === "z" || key === "y" && event.ctrlKey && !event.metaKey)) {
      const field = event.target.closest("input") || event.target.closest("textarea");
      if (event.target.isContentEditable || field && !["checkbox", "radio", "range", "file", "button"].includes(field.type)) return;
      event.preventDefault();
      runHistory(key === "y" || event.shiftKey ? "redo" : "undo");
      return;
    }
    if (!readOnly && leaderEdit && ["Delete", "Backspace"].includes(event.key)
        && !["input", "textarea", "select"].some(selector => event.target.closest(selector))) {
      event.preventDefault();
      const tag = state().tags.find(tag => tag.id === leaderEdit), value = tag && leaderFor(tag);
      if (value && leaderNode > 0 && leaderNode < value.nodes.length) {
        const next = JSON.parse(JSON.stringify(value)); next.nodes.splice(leaderNode, 1);
        leaderNode = null; saveLeader(tag.id, next); viewport.focus({preventScroll: true});
      }
      return;
    }
    if (event.key === "Escape" && drawingDraft) {
      event.preventDefault(); if (!drawingBusy) finishDrawingEdit(false); return;
    }
    if (event.key === "Escape" && cropDraft) {
      event.preventDefault(); finishCrop(false); return;
    }
    if (event.key === "Escape" && !savePanel.hidden) {
      if (!saving) { savePanel.hidden = true; saveProject.focus(); }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      const selecting = !!drag?.box || selected.size > 0 || selectedOverlays.size > 0;
      const wasMeasuring = measuring();
      const wasDrawingLeader = !!leaderPlacement;
      cancelDrag(); selectedOverlays.clear(); overlaySelected = null; renderSlidingGeometry(); closeDialog(); closeBulk();
      if (!bulkBusy) { selected.clear(); tableAnchor = null; bulkSignature = ""; showSelection(); renderMarkers(); }
      setMode("pan"); showMessage(wasDrawingLeader ? "Ritningen av splinen avbröts. Den tidigare linjen behålls."
        : wasMeasuring ? "Mätningen avslutades. Kalibreringen behålls." : selecting && !bulkBusy ? "Markeringen avbröts."
        : readOnly ? "Klicka på en etikett för indata och resultat." : "Klicka på en etikett för indata eller dra den för att flytta.");
    }
  });
  function receive(reply, buffers = []) {
    if (reply.view !== view) return;
    if (!reply.ok) showMessage(reply.error, true);
    const onDone = pending.get(reply.request);
    pending.delete(reply.request);
    onDone?.(reply, buffers);
    showHistory();
  }
  const resizeObserver = new ResizeObserver(() => {
    hideHistoryTooltip();
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
  picture.addEventListener("load", renderLeaders);
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
    historyHover = null; hideHistoryTooltip();
    endPanelDrag();
    document.removeEventListener("pointerdown", outsideDown, true);
    document.removeEventListener("pointermove", outsideMove, true);
    document.removeEventListener("pointerup", outsideUp, true);
    document.removeEventListener("pointercancel", outsideCancel, true);
    document.removeEventListener("scroll", hideHistoryTooltip, true);
    resizeObserver.disconnect();
    leaderResizeObserver.disconnect();
    patternObserver.disconnect();
    patternHosts.clear();
    model.off("change:state", update);
    model.off("change:background", update);
    model.off("msg:custom", receive);
    pending.clear();
    root.remove();
  };
}

export default { render };
