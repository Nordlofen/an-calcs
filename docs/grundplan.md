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
Sökvägar avser kernelns filsystem och arbetsmapp. PDF-sidor numreras från 1.
PNG, JPEG, WebP, TIFF (första bildrutan) och BMP stöds också.

## Arbeta i planvyn

1. Öppna en ritning och välj sida om den har flera PDF-sidor.
2. Välj **+ Väggsula** eller **+ Pelarsula** och klicka vid konstruktionen.
3. Ange littera. Öppna indataavsnitten och anpassa samtliga relevanta värden.
   Startvärdena kommer från beräkningens panel-schema och är exempel.
4. Tryck **Beräkna**. Dialogen visar utnyttjandegrad, dimensionerande last,
   bärförmåga och effektiv bredd.
5. Tryck **Minimera**. Taggen visar littera, utnyttjandegrad och bredd.
   Klicka på taggen igen för att öppna samma indata.

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

Gränssnittet anropar den befintliga beräkningsfunktionen utan att ändra dess
formler, koefficienter eller antaganden.

- **Väggsula:** `lang=1`. Funktionen använder en referenslängd på **1 m**.
  Krafter anges i kN/m och moment i kNm/m. Värdena förs till funktionen som
  kraft/moment på denna enmetersremsa. Fundamentlängden `l` används inte för
  att fördela laster. Ange inte hela väggens totallast i ett linjelastfält.
- **Pelarsula:** `lang=0`. Krafter anges i kN, moment i kNm och måtten
  `b` respektive `l` i m.
- Fundamentets egentyngd läggs till enligt den befintliga modellen:
  `F_v = F_vy + 1.5 * 25 * b * l_ref * t`.
- Utnyttjandegraden definieras här som `U = F_v / F_bd`. För väggsulor avser
  både täljare och nämnare en meter. `F_bd` är exakt den bärförmåga som
  ursprungsfunktionen returnerar: `q_bd * b` respektive `q_bd * b * l`.
  Gränssnittet inför ingen alternativ effektiv-area-modell.
- I den befintliga funktionens `details` står vissa lastposter i kN även
  för enmetersremsan. Planvyn visar dem med den uttryckliga per-meter-
  konventionen ovan. De returnerade `details` ändras inte.

Kontrollen avser jordens bärighet i brottgränstillstånd enligt repositoryts
befintliga Mathcad-baserade modell. Sättningar, betongdimensionering,
armering och pålbärförmåga ingår inte i taggens utnyttjandegrad.

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

En ritning får vara högst 40 MB och ett projekt högst 60 MB med upp till
1 000 taggar. Visningsbilden begränsas till 2 800 pixlar längs längsta sidan
för minnesanvändningens skull; originalfilen bevaras i projektet. Starta ett
nytt `Grundplan()` för att byta ritning när taggar redan finns.

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
Interaktionerna kan testas med `node tests/test_grundplan_ui.mjs`.
