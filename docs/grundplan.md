# Grundplan i JupyterLab

## Starta

Kräver Python 3.13 eller senare och notebook-tilläggen i notebookens
Pythonmiljö. Installera från GitHub genom att köra detta i terminalen,
från mappen där din `.venv` finns:

```sh
source .venv/bin/activate
uv pip install --upgrade --refresh "an-calcs[notebook] @ git+https://github.com/Nordlofen/an-calcs.git"
```

För lokal utveckling kan du i samma aktiverade miljö köra
`uv pip install -e ".[notebook]"` från an-calcs repositoryrot.

Spara projektet före uppdatering och starta sedan om kerneln. Ladda också
om hela webbläsarfliken om widgettillägget inte visas; enbart kernelomstart
laddar inte in ett nytt webbläsartillägg. Gränssnittet använder anywidget;
PDF renderas lokalt med pypdfium2 och rasterbilder med Pillow. Inga
ritningar skickas till en extern tjänst. I en fjärransluten Jupytermiljö
överförs de till den server där kerneln körs.

```python
from an_calcs.notebook import Grundplan

plan = Grundplan()  # Välj fil i gränssnittet.
plan
```

Alternativt `Grundplan("grundplan.pdf", sida=2, titel="Hus A")`.
Klicka direkt i rubriken eller underrubriken överst för att ändra texten.
Båda sparas i JSON-projektet och visas med samma innehåll i HTML-exporten.
Du kan också ange `underrubrik="Revision A"` när planen skapas eller ändra
texterna via `plan.titel` och `plan.underrubrik`. En tom underrubrik döljs
i HTML-exporten. Ändringarna påverkar inte sulornas beräkningar.

Sökvägar avser kernelns filsystem och arbetsmapp. PDF-sidor numreras från 1.
PNG, JPEG, WebP, TIFF (första bildrutan) och BMP stöds också.

## Arbeta i planvyn

1. Öppna en ritning och välj sida om den har flera PDF-sidor.
2. Välj **+ Väggsula** eller **+ Pelarsula** och klicka vid konstruktionen.
3. Ange littera. Öppna indataavsnitten och anpassa samtliga relevanta värden.
   Startvärdena kommer från beräkningens panel-schema och är exempel.
   Ange brottlasterna under **Laster – Brott**. Om sulan har isolering,
   kryssa i **Underliggande isolering** under **Isolering**, ange `f_d.brott`
   och `f_d.bruk` i kPa samt långtidslasterna under **Laster – Bruk**.
4. Tryck **Beräkna**. Dialogen visar utnyttjandegrad, dimensionerande last,
   bärförmåga och effektiv bredd. Med isolering visas tre separata kontroller:
   jord i brott, isolering i brott och isolering i bruk.
5. Tryck **Minimera**. Första raden visar littera, en symbol och texten
   **Med isolering** eller **Utan isolering**. Symbolen visar sulan över en
   skrafferad isoleringsremsa; bara remsan stryks över när isolering saknas.
   Andra raden visar högsta utnyttjandegrad och geometri, till exempel
   `U 34,6 % · b 1,8 m` för väggsula eller `U 68,3 % · 1,8 × 2,4 m`
   för pelarsula. Pelarsulans mått anges alltid som bredd × längd.
   För isolerade sulor visar en tredje rad styrande kontroll, till exempel
   `Styrande: Isolering · bruk`. Kontrollen finns också i dialogen och
   i etikettens hovringstext.
   Klicka på taggen igen för att öppna samma indata.

Vyn kommer ihåg vilka indata- och resultatavsnitt som är öppna för varje sula.
När du minimerar eller byter etikett och sedan återvänder återställs samma
utfällda och infällda avsnitt. Dessa visningsval gäller medan planvyn är öppen.

**Flytta:** dra etiketten till önskat läge och släpp. Ett kort klick öppnar
indata; en dragning flyttar etiketten utan att ändra indata eller resultat.
Positionen sparas i projektet. Dialogen kan flyttas genom att dra dess rubrik.

**Kopiera:** öppna en etikett, tryck **Kopiera sula** och klicka på ritningen
där den nya sulan ska placeras. Alla indata följer med, även ändringar som
ännu inte beräknats. Kopian får nästa lediga VS-/PS-littera och egna indata.
Anpassa last och geometri och tryck **Beräkna**; originalet påverkas inte.
**Avbryt kopiering** eller Escape avslutar kopieringen utan att skapa en sula.

**Storlek:** reglaget **Etikettstorlek** ändrar etiketternas grundstorlek mellan
60 och 180 %, vid 100 % ritningszoom. Etiketterna förstoras och förminskas
tillsammans med ritningen när du zoomar. Grundstorleken sparas i projektet.
Dra ritningen för att panorera fritt,
även när hela ritningen redan ryms i vyn. Knapparna + och − styr zoom;
**Anpassa** återställer zoom och centrering så att hela ritningen syns.
Taggarna behåller sina relativa lägen
vid zoom, panorering och sidbyte. Escape minimerar dialogen och avslutar
placeringsläget.

Grön tagg betyder U ≤ 100 %, röd betyder U > 100 % eller beräkningsfel.
Ändrade indata ger en streckad tagg och inga aktuella resultat förrän en
ny beräkning har körts. Att bara byta littera påverkar inte beräkningen.
Varje tagg har oberoende indata.

## Lastkonvention och resultat

Jordkontrollen anropar den befintliga beräkningsfunktionen med hävarmen satt
till noll. Därmed används de direkt angivna momenten utan bidrag från
horisontallast gånger hävarm. Isoleringen har en separat beräkning med samma
momentkonvention. De fristående beräkningsfunktionerna kan fortfarande
anropas med en hävarm.

- **Väggsula:** `lang=1`. Funktionen använder en referenslängd på **1 m**.
  Krafter anges i kN/m och moment i kNm/m. Värdena förs till funktionen som
  kraft/moment på denna enmetersremsa. Fundamentlängden `l` används inte för
  att fördela laster. Ange inte hela väggens totallast i ett linjelastfält.
- **Pelarsula:** `lang=0`. Krafter anges i kN, moment i kNm och måtten
  `b` respektive `l` i m.
- Ange moment direkt vid sulan kring l- respektive b-axeln, både i brott
  och bruk. Excentriciteten beräknas från dessa moment och eventuell
  placeringsexcentricitet. Horisontallaster i brott behålls för deras
  påverkan på jordens bärighet, men ger inget extra moment.
- Fundamentets egentyngd läggs till enligt den befintliga modellen:
  `F_v = F_vy + 1.5 * 25 * b * l_ref * t`.
- Jordens utnyttjandegrad definieras som `U = F_v / F_bd`. För väggsulor avser
  både täljare och nämnare en meter. `F_bd` är exakt den bärförmåga som
  ursprungsfunktionen returnerar: `q_bd * b` respektive `q_bd * b * l`.
  Denna jordkontroll är oförändrad när isoleringskontrollen aktiveras.
- I den befintliga funktionens `details` står vissa lastposter i kN även
  för enmetersremsan. Planvyn visar dem med den uttryckliga per-meter-
  konventionen ovan. Jordens poster i `details` ändras inte; med isolering
  tillkommer poster med namn som börjar med `isolering_`.

Jordkontrollen avser bärighet i brottgränstillstånd enligt repositoryts
befintliga Mathcad-baserade modell. Sättningar, betongdimensionering,
armering och pålbärförmåga ingår inte i taggens utnyttjandegrad.

## Isolering under sulan

Kryssrutan **Underliggande isolering** aktiverar kontrollen. När den är
avmarkerad används bara jordkontrollen, och fälten för isolering och brukslast
behöver inte fyllas i. Tidigare angivna värden behålls vid avmarkering.
Isoleringsval, bärförmågor och brukslaster följer med vid kopiering och sparning.

**Isolerprodukt** är ett valfritt textfält för kommentarer, exempelvis produkt
eller materialtyp. Texten sparas och kopieras med sulan. Den används inte i
beräkningen, och att ändra den gör inte ett befintligt resultat inaktuellt.

Ange färdiga dimensionerande bärförmågor `f_d.brott` och `f_d.bruk` i kPa,
där bruksvärdet gäller långtidsbelastning. Programmet tillämpar ingen extra
materialfaktor och väljer inte materialvärden automatiskt. Korttidsvärden
och långtidsvärden i produktdata avser olika provningsvillkor; se exempelvis
[BEWI:s tekniska EPS-tabell](https://www.bewi.com/wp-content/uploads/2023/09/Teknisk-tabell-EPS-SE-11-2023.pdf).
Produktklassens tryckhållfasthet omvandlas inte automatiskt till `f_d`.

**Laster – Bruk** har egna fält för vertikallast och två direkt angivna
moment. Ange den färdiga långtidslastkombinationen,
exklusive sulans egentyngd, med samma teckenkonvention som brottlasterna.
Vertikal brukslast och båda bärförmågorna saknar startvärden och måste anges
för att kontrollen ska kunna genomföras.

Beräkningen använder följande uttryck separat i brott och bruk:

```text
EG_k = 25 × b × l_ref × t
N_brott = F_vy + 1,5 × EG_k
N_bruk  = F_vy_bruk + 1,0 × EG_k

e_b = abs(e_b_plac + M_insp_l / N)
e_l = abs(e_l_plac + M_insp_b / N)
b_eff = b − 2 × e_b
l_eff = l_ref − 2 × e_l
q_Ed = N / (b_eff × l_eff)
U_isolering = q_Ed / f_d
```

Varje kombination använder sin egen vertikallast och sina egna moment. `l_ref` är
1 m för väggsula och `l` för pelarsula. Egentyngdsfaktorn 1,5 i brott följer
den befintliga jordmodellen; i bruk används 1,0. Ingen lastkombination
genereras från karakteristiska laster. Effektiva mått, total last och
bärförmågor måste vara positiva; annars visas ett fel utan aktuell utnyttjandegrad.

Isoleringen förutsätts täcka hela den effektiva arean. Kontrollen gäller
trycket över effektiv area, inte maximalt kanttryck. Den beräknar inte
krypdeformation eller sättning. Resultatavsnitten **Isolering – Brott** och
**Isolering – Bruk** visar last, effektiva mått och area, lasteffekt och bärförmåga.

## Spara och återöppna

**Spara projekt** laddar ned en JSON-fil. Den innehåller originalritningen,
aktuellt sidnummer, alla taggpositioner, littera, indata och beräkningskodens
versionsavtryck. Filen kan öppnas med **Öppna projekt** eller från Python:

```python
plan.spara("hus_a.grundplan.json")
ateroppnad = Grundplan.oppna("hus_a.grundplan.json")
ateroppnad
```

Vid återöppning beräknas tidigare beräknade taggar på nytt från sparade
indata. Sparade resultat behandlas aldrig som verifierade numeriska data.
Om beräkningskodens versionsavtryck har ändrats markeras taggarna som
inaktuella och måste beräknas igen. Ofullständiga indata får sparas som
utkast.

Projekt sparas i formatversion 3. Äldre projekt i formatversion 1 och 2 kan
öppnas, men sulorna måste beräknas igen med **Beräkna**. Deras angivna
momentvärden bevaras; tidigare hävarmar och horisontallaster i bruk tas bort
utan att räknas om till moment. Dessa borttagna fält ignoreras även om de
skickas som `indata` från Python. Projekt i formatversion 1 får isoleringen
avstängd.

En ritning får vara högst 40 MB och ett projekt högst 60 MB med upp till
1 000 taggar. Visningsbilden begränsas till 2 800 pixlar längs längsta sidan
för minnesanvändningens skull; originalfilen bevaras i projektet. Starta ett
nytt `Grundplan()` för att byta ritning när taggar redan finns.

## Exportera ritning med etiketter som PDF

Tryck **Exportera PDF** för att ladda ned alla ritningssidor med sulornas
minimerade etiketter ovanpå. Filen får originalritningens namn med tillägget
`_med_etiketter.pdf`. Från Python:

```python
plan.exportera_pdf("grundplan_med_etiketter.pdf")
```

PDF-originalets sidformat, beskärning och rotation bevaras, liksom dess
vektorritning och text. För en importerad bild skapas en PDF-sida i samma
proportioner, med bildens fulla upplösning och 96 dpi som grund för sidstorleken.
Export från ett återöppnat JSON-projekt använder den inbäddade ritningen;
originalfilen behöver inte finnas kvar.

Etiketterna använder sina sparade positioner och reglaget **Etikettstorlek**.
Zoom, panorering och öppna dialogrutor påverkar inte exporten. Littera,
isoleringssymbol och text, utnyttjandegrad, geometrimått, eventuell styrande
kontroll och statusfärg följer med.
Etiketter nära sidkanten flyttas in så att hela etiketten ryms; mycket breda
etiketter förminskas vid behov. Etiketterna är fast sidinnehåll som följer
med vid utskrift, utan popup eller klickfunktion.

Exporten räknar inte om sulorna. Ändrade, ännu inte beräknade eller felaktiga
sulor visas med sin status i stället för ett aktuellt beräkningsresultat.
Indatadialoger och fullständiga beräkningsrapporter ingår inte. Fortsätt spara
JSON-projektet separat för att kunna redigera sulorna senare.

PDF-export kräver `reportlab` och `pypdf`, som ingår i `an-calcs[notebook]`.
Uppdatera med installationskommandot ovan om du har en äldre installation.

## Exportera en interaktiv resultatvy som HTML

Tryck **Exportera HTML** för att ladda ned en enda fil med ritningen och
öppningsbara etiketter. Filen får originalritningens namn med tillägget
`_resultat.html`. Du kan också exportera från Python:

```python
plan.exportera_html("grundplan_resultat.html")
```

Öppna filen i en vanlig webbläsare. Den fungerar utan Jupyter, Python eller
internet; ritningsbilder, indata, resultat och gränssnitt finns i filen.
Alla PDF-sidor följer med och väljs med **Sida**. Ritningsbilderna har samma
upplösning som i Jupyter-vyn (högst 2 800 pixlar längs längsta sidan).

Klicka på en etikett för resultat och utfällbara indatakategorier. **Minimera**
stänger dialogen, och samma avsnitt är utfällda när etiketten öppnas igen.
Dra i ritningen för att panorera, använd +/− för zoom och **Anpassa** för
att återställa vyn. Reglaget **Etikettstorlek** fungerar även i HTML-filen.
Visningsval gäller medan filen är öppen och ändrar inte det sparade projektet.

Beräkningsvärden och etikettpositioner är låsta i resultatvyn. Exporten
räknar inte om sulor: ändrade, ej beräknade eller felaktiga sulor visar sin
status i stället för ett aktuellt resultat. Använd JSON-projektet i Jupyter
för fortsatt redigering. Export från ett återöppnat JSON-projekt kräver
inte att originalritningen finns kvar.

## Använd resultat och taggar från Python

```python
tagg_id = plan.lagg_till(
    0.35, 0.4, littera="VS2", typ="vaggsula",
    indata={"b": 0.8, "F_vy": 100.0},
)
details = plan.berakna(tagg_id)
plan.uppdatera(tagg_id, indata={"b": 1.0})
details = plan.berakna(tagg_id)

plan.uppdatera(tagg_id, x=0.45, y=0.3)  # Flytta utan att ändra resultat.
kopia_id = plan.kopiera(tagg_id, 0.6, 0.4, indata={"F_vy": 150.0})
plan.berakna(kopia_id)
plan.etikettstorlek = 120  # Grundstorlek i procent, vid 100 % ritningszoom.

# Exempelvärden: anpassa bärförmågor och långtidslast för aktuellt projekt.
plan.uppdatera(tagg_id, indata={
    "isolering": True, "f_d_brott": 200.0, "f_d_bruk": 80.0,
    "F_vy_bruk": 60.0,
})
details = plan.berakna(tagg_id)

from an_print import CalcBlock
CalcBlock(details).SR(visa=True, etikett=True)

plan.taggar       # Kopior av taggar, indata och sammanfattningar.
plan.resultat     # Aktuella details per tagg-id.
```

Positionerna `x` och `y` ligger mellan 0 och 1 med origo i bildens övre vänstra
hörn. De är relativa bildkoordinater, inte meter eller projektkoordinater.
Sulans mått och lastfördelning hämtas inte automatiskt från ritningen.
Denna första version placerar punktmarkeringar vid sulorna; linjemarkering,
skalinställning och automatisk identifiering av stomlinjer ingår inte.

Widgeten måste vara ansluten till en aktiv Pythonkernel för att skapa
taggar, ändra indata, spara och beräkna. Export till en fristående HTML-app
är en senare del.

## Kontrollera installationen

```sh
python -m unittest discover -s tests
```

Notebooktesterna hoppas över om tilläggen saknas. Med tilläggen installerade
kontrollerar de bland annat per-meter-laster, oberoende taggar,
ogiltiga eller ändrade indata, projektets återöppning och PDF med flera sidor.
Isoleringstesterna omfattar olika effektiva areor i brott/bruk, egentyngd,
styrande kontroll, saknade värden och import av äldre projekt.
Interaktionerna kan testas med `node tests/test_grundplan_ui.mjs`.
