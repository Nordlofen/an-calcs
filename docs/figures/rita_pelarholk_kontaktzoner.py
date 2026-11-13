from pathlib import Path
from math import sin, cos, radians, tan
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
import pypdfium2 as pdfium

import sys

# Ange en separat utdatakatalog; PNG kopieras till paketets figures efter granskning.
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/pelarholk-kontaktzoner")
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1600, 1220
for name, file in [('Arial','Arial.ttf'),('Arial-Bold','Arial Bold.ttf'),('Arial-Italic','Arial Italic.ttf'),('Arial-BoldItalic','Arial Bold Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name, '/System/Library/Fonts/Supplemental/' + file))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial-Italic', boldItalic='Arial-BoldItalic')
c = canvas.Canvas(str(OUT/'pelarholk-kontaktzoner.pdf'), pagesize=(W,H))
c.setTitle('Pelarholk – kontaktzoner och tryckspridning')
c.setAuthor('Beräkningsunderlag för Pelarholk()')
INK='#173342'; MUTED='#59707A'; LINE='#9EADB3'; BORDER='#D6DFE3'; BLUE='#176B8A'
ORANGE='#B8601B'; ORANGE_FILL='#F9E5D3'; GROUT='#FBF1D8'; CONCRETE='#E9EEF0'

def line(x1,y1,x2,y2,color=INK,width=1.4,dash=None):
    c.saveState(); c.setStrokeColor(HexColor(color)); c.setLineWidth(width)
    if dash: c.setDash(*dash)
    c.line(x1,H-y1,x2,H-y2); c.restoreState()

def poly(points, fill=None, stroke=INK, width=1.5, close=True):
    c.saveState(); p=c.beginPath(); p.moveTo(points[0][0],H-points[0][1])
    for x,y in points[1:]: p.lineTo(x,H-y)
    if close: p.close()
    c.setLineWidth(width)
    if stroke: c.setStrokeColor(HexColor(stroke))
    if fill: c.setFillColor(HexColor(fill))
    c.drawPath(p, stroke=bool(stroke), fill=bool(fill)); c.restoreState()

def rect(x,y,w,h,fill=None,stroke=None,r=0):
    c.saveState()
    if fill: c.setFillColor(HexColor(fill))
    if stroke: c.setStrokeColor(HexColor(stroke))
    c.setLineWidth(1)
    c.roundRect(x,H-y-h,w,h,r,stroke=bool(stroke),fill=bool(fill)); c.restoreState()

def text(t,x,y,size=17,color=INK,bold=False,align='left',angle=0):
    c.saveState(); c.setFillColor(HexColor(color)); c.setFont('Arial-Bold' if bold else 'Arial',size)
    c.translate(x,H-y); c.rotate(angle)
    {'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align](0,0,t)
    c.restoreState()

def rich(t,x,y,w=300,size=17,color=INK,align=0):
    st=ParagraphStyle('p',fontName='Arial',fontSize=size,leading=size*1.32,textColor=HexColor(color),alignment=align)
    p=Paragraph(t,st); pw,ph=p.wrap(w,1000); p.drawOn(c,x,H-y-ph)
    return ph

def arrow(x1,y1,x2,y2,color=BLUE,width=2.5,head=9):
    line(x1,y1,x2,y2,color,width)
    dx,dy=x2-x1,y2-y1; norm=(dx*dx+dy*dy)**.5; ux,uy=dx/norm,dy/norm
    poly([(x2,y2),(x2-head*ux+head*.38*uy,y2-head*uy-head*.38*ux),(x2-head*ux-head*.38*uy,y2-head*uy+head*.38*ux)],color,color)

def tick(x,y): line(x-4,y+4,x+4,y-4,MUTED,1.2)

def rotated_rich(t,x,y,size=17):
    st=ParagraphStyle('rot',fontName='Arial',fontSize=size,leading=size*1.25,textColor=HexColor(MUTED),alignment=1)
    p=Paragraph(t,st); pw,ph=p.wrap(420,60)
    c.saveState();c.translate(x,H-y);c.rotate(90)
    p.drawOn(c,-pw/2,-ph/2);c.restoreState()

def dim_v(x,y1,y2,label,rot=True,offset=-10,size=16):
    line(x,y1,x,y2,MUTED,1)
    tick(x,y1);tick(x,y2)
    if rot:
        label=label.replace('a_c,spr','<i>a</i><sub>c,spr</sub>').replace('a_c','<i>a</i><sub>c</sub>')
        label=label.replace('l','<i>l</i>')
        rotated_rich(label,x+offset,(y1+y2)/2,size)
    else: rich(label.replace('l','<i>l</i>'),x+offset,(y1+y2)/2-10,90,size,MUTED)

def dim_h(x1,x2,y,label,size=17):
    line(x1,y,x2,y,MUTED,1);tick(x1,y);tick(x2,y)
    rich(label,x1-30,y-30,x2-x1+60,size,MUTED,1)

def guide(x1,y,x2):line(x1,y,x2,y,LINE,.9,(3,4))

def triangle(axis,top,bottom,peak,direction=1):
    poly([(axis,top),(axis+direction*peak,top),(axis,bottom)],ORANGE_FILL,ORANGE,1.5)
    for yy in range(int(top+14),int(bottom),16):
        xx=axis+direction*peak*(bottom-yy)/(bottom-top)
        line(axis,yy,xx,yy,ORANGE,.7)

# Header
rect(0,0,W,H,'#FFFFFF')
text('Pelarholk – kontaktzoner och tryckspridning',52,61,32,bold=True)
text('Principskiss • ej skalenlig • släta ytor',54,94,17,MUTED)
rect(1343,39,205,45,'#EAF3F6',r=8)
text('MODELLUNDERLAG',1445,67,14,BLUE,True,'center')

# Panel outlines
rect(44,125,710,806,'#FFFFFF',BORDER,10)
rect(780,125,776,806,'#FFFFFF',BORDER,10)
text('A   Kontaktzoner och kraftlägen',69,165,21,bold=True)
text('Krafter på pelaren/väggen enligt figur 10.7b',69,194,15,MUTED)
text('B   Tryckspridning genom igjutningen',804,165,21,bold=True)
text('Detalj av den övre kontaktzonen – principiell spänningsmodell',804,194,15,MUTED)

# A – cross section: l = 420 drawing units, ac=.3l
yt,yb=305,725
ac=.3*(yb-yt)
xl,xr=330,460
# Structural concrete U and grout.
poly([(225,yt),(312,yt),(312,743),(478,743),(478,yt),(565,yt),(565,810),(225,810)],CONCRETE)
poly([(312,yt),(xl,yt),(xl,yb),(xr,yb),(xr,yt),(478,yt),(478,743),(312,743)],GROUT)
rect(xl,270,xr-xl,yb-270,'#FFFFFF')
line(xl,270,xl,yb);line(xr,270,xr,yb);line(xl,yb,xr,yb)
line(xl,270,xl+45,270);poly([(xl+45,270),(xl+51,264),(xl+57,276),(xl+63,270)],stroke=INK,close=False);line(xl+63,270,xr,270)
line((xl+xr)/2,263,(xl+xr)/2,809,LINE,.8,(8,4))
# Updated horizontal dimension chain: b2 + h + b1 = B.
for x,yy in ((225,yt),(xl,270),(xr,270),(565,yt)):
    line(x,yy-5,x,233,LINE,.9,(3,4))
dim_h(225,xl,240,'<i>b</i><sub>2</sub>',19)
dim_h(xl,xr,240,'<i>h</i>',20)
dim_h(xr,565,240,'<i>b</i><sub>1</sub>',19)
# Pressure triangles – top right and bottom left
triangle(xr,yt,yt+ac,86)
poly([(xl,yb-ac),(xl,yb),(xl-86,yb)],ORANGE_FILL,ORANGE,1.5)
for yy in range(int(yb-ac+14),yb,16):
    xx=xl-86*(yy-(yb-ac))/ac
    line(xl,yy,xx,yy,ORANGE,.7)
# Explicit contact lengths marked on the material faces
line(xr,yt,xr,yt+ac,ORANGE,3)
line(xl,yb-ac,xl,yb,ORANGE,3)
arrow(553,yt+.1*(yb-yt),xr+3,yt+.1*(yb-yt))
rich('<i>F</i><sub>1</sub>',520,314,55,21,BLUE)
arrow(237,yb-.1*(yb-yt),xl-3,yb-.1*(yb-yt))
rich('<i>F</i><sub>2</sub>',239,648,55,21,BLUE)
arrow(395,803,395,yb+6)
rich('<i>F</i><sub>3</sub>',412,769,55,21,BLUE)
# Dimension chains.
for yy in (yt,yb):guide(119,yy,225)
dim_v(128,yt,yb,'l',True,-12,20)
for yy in (yt,810):guide(77,yy,225)
dim_v(86,yt,810,'H',True,-12,20)
for yy in (yt,yt+ac,yb-ac,yb):guide(181,yy,225)
dim_v(190,yt,yt+ac,'a_c = 0,3l',True,-10,16)
dim_v(190,yt+ac,yb-ac,'0,4l',True,-10,16)
dim_v(190,yb-ac,yb,'a_c = 0,3l',True,-10,16)
for yy in (yt,yt+.1*(yb-yt),yb-.1*(yb-yt),yb):guide(568,yy,666)
dim_v(623,yt,yt+.1*(yb-yt),'0,1l',False,12,16)
dim_v(623,yt+.1*(yb-yt),yb-.1*(yb-yt),'0,8l',True,21,17)
dim_v(623,yb-.1*(yb-yt),yb,'0,1l',False,12,16)
for x in (225,565):line(x,815,x,856,LINE,.9,(3,4))
dim_h(225,565,850,'<i>B</i>',20)
rich('<i>D</i> = beräkningsdjup · <i>D</i> = 1 000 mm för vägg<br/><font size="15"><i>B</i> och <i>H</i> är skissmått.</font>',68,879,655,17,INK,1)

# B – geometry of stress spread. 26.6 degrees measured from vertical.
g0,g1=1010,1110
top=305
aci=170
delta=(g1-g0)/tan(radians(26.6))
end=top+aci+delta
rect(g0,284,g1-g0,440,GROUT)
rect(g1,284,335,440,CONCRETE)
line(g0,284,g0,724,INK,1.6)
line(g1,284,g1,724,INK,1.6)
text('Igjutning',1060,235,16,INK,True,'center')
text('Holkbetong',1280,235,16,INK,True,'center')
line(g0,280,g0,258,LINE,.9);line(g1,280,g1,258,LINE,.9)
dim_h(g0,g1,265,'<i>t</i><sub>ig</sub>',18)
# Stress diagrams have equal area; diagram width is stress, not geometry.
triangle(g0,top,top+aci,100,-1)
triangle(g1,top,end,100*aci/(aci+delta),1)
rich('σ<sub>ig,max</sub>',879,270,125,19,ORANGE)
rich('σ<sub>c,max</sub>',1191,291,145,19,ORANGE)
line(1187,311,g1+100*aci/(aci+delta),top,ORANGE,1)
# Boundaries of proposed spread.
line(g0,top,g1,top,BLUE,2)
line(g0,top+aci,g1,end,BLUE,2.4)
line(g0,top+aci,g0,end,LINE,1,(4,4))
for yy in (top,top+aci):guide(856,yy,g0-106)
dim_v(868,top,top+aci,'a_c',True,-11,19)
for yy in (top,top+aci,end):guide(1195,yy,1468)
dim_v(1335,top+aci,end,'Δa',True,-16,19)
dim_v(1450,top,end,'a_c,spr = a_c + Δa',True,28,18)
# Angle arc.
origin=(g0,top+aci)
arc=[]
for j in range(25):
    theta=radians(90-26.6*j/24)
    arc.append((origin[0]+66*cos(theta),origin[1]+66*sin(theta)))
poly(arc,stroke=BLUE,width=1.7,close=False)
line(1032,534,1170,562,BLUE,1)
rich('α = 26,6°<br/><font size="14">mot vertikalen</font>',1177,546,155,18,BLUE)
# Material key.
rect(821,754,21,17,GROUT,BORDER);text('Igjutning',852,769,15,MUTED)
rect(1036,754,21,17,CONCRETE,BORDER);text('Holkbetong',1067,769,15,MUTED)
rect(1266,754,21,17,ORANGE_FILL,ORANGE);text('Tryckdiagram',1297,769,15,MUTED)
rich('Tryckdiagrammens horisontella bredd visar spänning.<br/>Endast spalten <i>t</i><sub>ig</sub> är ett horisontellt geometrimått här.',816,801,703,16,MUTED)
rich('Detaljen visar övre zonen. Motsvarande spegling för den undre zonen behöver bedömas mot tillgänglig betonggeometri.',816,865,703,15,MUTED)

# Equations and limitations – dedicated bottom strip.
rect(44,951,1512,207,'#F4F8FA',BORDER,10)
text('Samband i det illustrerade modellförslaget',68,984,20,bold=True)
rich('<i>a</i><sub>c</sub> / 3 = 0,1<i>l</i>  ger  <b><i>a</i><sub>c</sub> = 0,3<i>l</i></b>',69,1002,640,21)
rich('σ<sub>ig,i,max</sub> = 2<i>F</i><sub>i</sub> / (<i>D a</i><sub>c</sub>),  <i>i</i> = 1, 2',69,1041,640,21)
rich('Δ<i>a</i> = <i>t</i><sub>ig</sub> / tan α',807,1002,700,21)
rich('σ<sub>c,i,max</sub> = 2<i>F</i><sub>i</sub> / (<i>D a</i><sub>c,spr</sub>)<br/>= (<i>a</i><sub>c</sub> / <i>a</i><sub>c,spr</sub>) σ<sub>ig,i,max</sub>',807,1040,700,21)
rich('Kraft och area används med konsekventa enheter: N och mm² ger MPa.',69,1112,1395,15,MUTED)
rich('Kraftlägen: SS-EN 1992-1-1:2005, figur 10.7b. Tryckzoner och spridning: föreslagen modell baserad på handberäkningen.<br/>Principskiss, ej skalenlig. Friktionskrafter visas inte. F<sub>3</sub>: endast kraftläge; bottenkontaktens tryckmodell visas inte.',53,1171,1494,12,MUTED)
c.showPage();c.save()

doc=pdfium.PdfDocument(OUT/'pelarholk-kontaktzoner.pdf')
page=doc[0]; bitmap=page.render(scale=1.5)
bitmap.to_pil().save(OUT/'pelarholk-kontaktzoner.png')
bitmap.close();page.close();doc.close()
print(OUT/'pelarholk-kontaktzoner.png')
print(OUT/'pelarholk-kontaktzoner.pdf')
