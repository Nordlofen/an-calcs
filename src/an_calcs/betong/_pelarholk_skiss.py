"""Måttskiss för panelen. Ingen beräkning av lasteffekter eller bärförmåga."""

from html import escape
import math


def render(values):
    """Returnera SVG som uppdateras av Panel när angivna geometrifält ändras."""
    free = bool(values.get("fristaende", True))
    wall = values.get("typ") == "vagg"
    names = ["h", "l", "bv", "bh", "H", "t_ig"]
    names += ([] if wall else ["D"]) + ([] if free else ["t_p"])
    try:
        v = {k: float(values[k]) for k in names}
        if any(not math.isfinite(x) or x <= 0 for x in v.values()):
            raise ValueError("Ange positiva, ändliga skissmått.")
        if v["H"] <= v["l"] + v["t_ig"]:
            raise ValueError("Skissen kräver H > l + t_ig för betong under igjutningen.")
        if v["t_ig"] >= min(v["bv"], v["bh"]):
            raise ValueError("Igjutningen måste rymmas inom båda sidomåtten.")
        if not free and v["t_p"] > v["H"]:
            raise ValueError("Plattjockleken får inte överstiga H i skissen.")
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Komplettera skissmåtten."
        return f'<p role="status">Skissen kan inte visas: {escape(message)} Beräkningsvillkoren kontrolleras separat.</p>'
    D = 1000.0 if wall else v["D"]
    h, l, bv, bh, H, tig = (v[k] for k in ("h", "l", "bv", "bh", "H", "t_ig"))
    B = bv+h+bh
    extension = 0 if free else max(h, B*.35)
    stub = max(h, H*.30)
    scale = min(550/(B+extension), 360/(H+stub))
    if not math.isfinite(B) or scale <= 0:
        return '<p role="status">Skissmåtten ligger utanför visningsområdet.</p>'
    x0 = 65+(550-(B+extension)*scale)/2
    xr, xe, xc = x0+B*scale, x0+(B+extension)*scale, x0+bv*scale
    xcr = xc+h*scale
    yc, yt = 90, 90+stub*scale
    yb, yl = yt+H*scale, yt+l*scale
    yp = yt+v.get("t_p", 0)*scale
    grout = min(max(5, tig*scale), 12, min(bv,bh,H-l)*scale*.4)
    fmt = lambda x: f"{x:,.1f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
    mode = "Fristående holk" if free else "Holk med anslutande platta"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 {yb+112:.3f}" role="img" aria-label="Måttsatt tvärsnitt: {mode}" '
             f'data-B="{B:g}" data-scale-x="{scale}" data-scale-y="{scale}" data-standalone="{str(free).lower()}" '
             'style="display:block;width:100%;height:auto;font:19px sans-serif;color:var(--anp-fg,#202327)">',
             f'<title>{mode} · mått i mm</title>',
             '<desc>Samma skala i höjd och bredd. Igjutningen visas schematiskt förstärkt. B och H används endast för skissen.</desc>']
    def line(x1,y1,x2,y2,extension=False):
        dash = ' stroke-dasharray="4 5" opacity=".5"' if extension else ''
        parts.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="currentColor" stroke-width="1"{dash}/>')
    def tick(x,y):
        line(x-3,y+3,x+3,y-3)
    def text(x,y,label,extra=""):
        parts.append(f'<text x="{x:.3f}" y="{y:.3f}" fill="currentColor" text-anchor="middle" {extra}>{label}</text>')
    def symbol(name):
        main, _, sub = name.partition("_")
        return f'<tspan font-style="italic">{main}</tspan>' + (f'<tspan baseline-shift="sub" font-size="14">{sub}</tspan>' if sub else '')
    outer = f'M {x0} {yt} H {xr} V {yb} H {x0} Z' if free else f'M {x0} {yt} H {xe} V {yp} H {xr} V {yb} H {x0} Z'
    parts += [f'<path data-part="fundament" d="{outer}" fill="var(--anp-soft,#f4f6f8)" stroke="currentColor" stroke-width="1.6"/>',
              f'<rect data-part="igjutning" x="{xc-grout}" y="{yt}" width="{xcr-xc+2*grout}" height="{yl-yt+grout}" fill="#f5c478" stroke="#c47b12"/>']
    center = (xc+xcr)/2
    brk = min(12, (xcr-xc)*.22)
    amplitude = min(5, brk*.5)
    parts.append(f'<path data-part="pelare-vagg" d="M {xc} {yc} H {center-brk} l {brk*.65} {-amplitude} l {brk*.7} {2*amplitude} l {brk*.65} {-amplitude} H {xcr} V {yl} H {xc} Z" fill="var(--anp-bg,#fff)" stroke="currentColor" stroke-width="1.6"/>')
    if not free:
        cut = xe-10
        for yy in (yt,yp):
            parts.append(f'<path d="M {cut-3} {yy-4} l 7 8 m -1 -8 l 7 8" fill="none" stroke="currentColor" stroke-width="1.6"/>')
    chain = 49
    for x,y in ((x0,yt),(xc,yc),(xcr,yc),(xr,yt)):
        line(x,chain-6,x,y-7,True)
        tick(x,chain)
    line(x0,chain,xr,chain)
    # Fasta symboler undviker överlapp för smala mått; talvärden finns i fälten.
    previous = -math.inf
    for start,end,name in ((x0,xc,"b_v"),(xc,xcr,"h"),(xcr,xr,"b_h")):
        mid = (start+end)/2
        yy = 15 if mid-previous < 36 else 34
        text(mid,yy,symbol(name))
        if yy == 15:
            line(mid,yy+8,mid,chain-6,True)
        previous = mid
    yB = yb+36
    for x in (x0,xr):
        line(x,yb+5,x,yB+6,True)
        tick(x,yB)
    line(x0,yB,xr,yB)
    text((x0+xr)/2,yB+25,f'B = {fmt(B)} mm', 'data-dimension="B"')
    xH = x0-26
    for yy in (yt,yb):
        line(xH-5,yy,x0-6,yy,True)
        tick(xH,yy)
    line(xH,yt,xH,yb)
    tx,ty = xH-10,(yt+yb)/2
    text(tx,ty,f'H = {fmt(H)}' if yb-yt>115 else 'H', f'transform="rotate(-90 {tx} {ty})"')
    xl = xcr+min(28,(xr-xcr)*.4)
    line(xcr+3,yl,xl+6,yl,True)
    line(xl,yt,xl,yl)
    tick(xl,yt)
    tick(xl,yl)
    tx,ty = xl+14,(yt+yl)/2
    if yl-yt>108 and xr-xcr>70:
        text(tx,ty,f'l = {fmt(l)}', f'transform="rotate(-90 {tx} {ty})"')
    else:
        text(tx,ty+5,symbol("l"))
    if not free:
        xp = xe+21
        for yy in (yt,yp):
            line(xe+5,yy,xp+5,yy,True)
            tick(xp,yy)
        line(xp,yt,xp,yp)
        text(xp+12,(yt+yp)/2,symbol("t_p"),f'transform="rotate(-90 {xp+12} {(yt+yp)/2})"')
    text(340,yb+98,f'D = {fmt(D)} mm · ut ur snittplanet', 'font-size="15"')
    parts.append('</svg>')
    return ''.join(parts)
