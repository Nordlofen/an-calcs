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

plan = Grundplan()  # Välj ritning och ange projektfil/key när du sparar.
plan
```

**Spara projekt** öppnar en ruta där **Projekt** och **Fall (key)** ska
anges. Välj **Nytt projekt…** och skriv exempelvis `26017 - Norrbodahöjden`,
eller välj en befintlig Grundplan-fil och dess sparade key. Tryck **Spara**.
Om filändelse saknas läggs `.json` till automatiskt, så filen blir
`26017 - Norrbodahöjden.json`. Mellanslag och svenska tecken behålls.
Samma normalisering används för `state_file=` i Python och i de kopierade argumenten.
Relativa sökvägar avser kernelns arbetsmapp, normalt mappen med notebooken.

**Kopiera projekt + key** kopierar Python-argumenten för den aktuella sparplatsen,
exempelvis `state_file='hus_a.grundplan_state.json', key='Hus A'`.
Klistra in dem i cellen för att återställa projektet automatiskt nästa gång:

```python
plan = Grundplan(state_file="hus_a.grundplan_state.json", key="Hus A")
plan
```

Ritningen ingår i JSON-filen; originalfilen behöver inte finnas kvar.

Alternativt kan en startritning anges:
`Grundplan("grundplan.pdf", key="Hus A", sida=2, titel="Hus A")`.
Om nyckeln redan är sparad återställs dess projekt i stället för startritningen.
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
4. Resultatet uppdateras automatiskt när indata ändras. Dialogen visar utnyttjandegrad, dimensionerande last,
   bärförmåga och effektiv area i en planskiss. Med isolering visas tre separata kontroller:
   jord i brott, isolering i brott och isolering i bruk.
5. Tryck **Minimera**. Första raden visar littera, en symbol och texten
   **Med isolering** eller **Utan isolering**. Symbolen visar sulan över en
   skrafferad isoleringsremsa; bara remsan stryks över när isolering saknas.
   Andra raden visar högsta utnyttjandegrad och geometri, till exempel
   `U 34,6 % · bₓ 1,8 m` för väggsula eller `U 68,3 % · 1,8 × 2,4 m`
   för pelarsula. Pelarsulans mått anges alltid som bₓ × bᵧ.
   För isolerade sulor visar en tredje rad styrande kontroll, till exempel
   `Styrande: Isolering · bruk`. Kontrollen finns också i dialogen och
   i etikettens hovringstext.
   Klicka på taggen igen för att öppna samma indata.

Panorering är grundläget och har ingen egen knapp. Efter en placering
avslutas sulverktyget automatiskt. Klicka på den valda sulknappen igen
eller tryck Escape för att avbryta en påbörjad placering.

Under resultatraderna visar etiketten ifyllda yttre laster som inte är noll,
grupperade i **Brott** och **Bruk**. Bruk visas när isolering är aktiverad.
Lastraderna avser inmatade värden **exklusive sulans egentyngd**; resultatskissen
använder däremot den beräknade vertikallasten inklusive egentyngd. Negativa
värden bevaras och mycket små laster visas med exponent för att inte avrundas
till noll. Tomma lastgrupper döljs. Detta gäller även PDF och HTML.

## Importera lasteffekter

Öppna först ritningen. Tryck **Importera/Uppdatera lasteffekt** och välj en JSON-fil
med `schemaVersion: 1` och listan `supports`. Hela filen kontrolleras innan
några sulor ändras eller placeringen startar. Filen får vara högst 5 MB.
Littera (`supportId`) måste vara unika i filen. För befintliga sulor matchas
support-ID mot littera på samtliga ritningssidor. Matchningen är skiftlägeskänslig.

Matchade sulor får nya vertikallaster för Brott, Bruk och EQU samt ny längd L
för väggsulor. Placering, littera, sultyp och övriga indata behålls. Ändrade
bärighetslaster räknar automatiskt om jord- och isoleringskontrollerna.
En oförändrad import behåller aktuella resultat. Glidmotståndet uppdateras
direkt från EQU-lasten och längden. Om ett littera matchar flera befintliga
sulor, eller filens sultyp skiljer sig från den befintliga, avvisas hela importen.
Sulor som saknas i filen behålls. Om filen bara innehåller befintliga littera
är uppdateringen klar direkt, utan en ny placeringsomgång.

Instruktionen visar exempelvis **Placera S.1 – väggsula (1 av 5)**, tillsammans
med stödets laster och eventuell längd. Klicka på ritningen där etiketten ska
placeras. Då skapas sulan och instruktionen visar nästa stöd, i filens ordning.
Ingen indatadialog öppnas mellan placeringarna. Endast nya littera behöver
placeras; befintliga sulor behåller sin position.
Dra på ritningen med vänster eller höger musknapp för att panorera under
placeringen; ett kort vänsterklick placerar nästa sula. Panorering förbrukar
inga stöd i kön och fungerar även medan en placering väntar på svar från
kerneln. **Shift + scroll** zoomar vid muspekaren utan att pausa placeringen. Shift + vänsterdrag
markerar befintliga etiketter för flerredigering och pausar placeringskön.

| JSON-fält | Indata i Grundplan |
| --- | --- |
| `supportId` | Littera |
| `type: "line"` / `"point"` | Väggsula / pelarsula |
| `results[].category: "Brott"`, `V` | Vertikallast under Laster – Brott (`F_vy`) |
| `results[].category: "Bruk"`, `V` | Vertikallast under Laster – Bruk (`F_vy_bruk`) |
| `results[].category: "EQU"`, `V` | Färdig kontaktlast under Glidning (`V_Ed_EQU`) |
| `length.value`, `length.unit: "m"` | Väggsulans hela längd L under Glidning (`glid_L`) |

Varje stöd ska ha exakt en last för Brott, Bruk och EQU. Väggsulor kräver
`distribution: "uniform"`, laster i `kN/m` och en positiv längd i `m`.
Pelarsulornas laster anges i `kN`. Värden och tecken behålls; linjelaster
multipliceras inte med längden och inga enheter omvandlas. Längden ändrar
inte bärighetskontrollens enmetersremsa. Metadata som `model` och `source`
används inte som sökvägar eller beräkningsindata.

Nya sulor får övriga startvärden från Grundplan och beräknas automatiskt vid placering.
Kontrollera geometri, jord, isolering och glidningsinställningar efter
placeringen, gärna med **Markera flera**. Bidragsriktningarna för glidning är
inte förvalda. EQU-lasten ska redan innehålla sulans egentyngd; vid beräkning
behandlas Brott och Bruk på samma sätt som manuellt inmatade yttre laster.
Importerade värden är vanliga redigerbara indata. Bruklasterna kan ändras även
utan isolering, och under Glidning kan EQU-lasten, friktionen och vägglängden
anges innan någon bidragsriktning väljs. Tomma, ännu oanvända värden krävs inte
för jordens bärighetskontroll.

**Pausa placering** eller Escape behåller kön så att du kan arbeta med
ritningen och befintliga sulor. Tryck **Fortsätt placera** för att fortsätta.
Du kan byta PDF-sida under placeringen. **Avbryt import** avslutar kön och
behåller redan placerade sulor. **Endast placerade sulor sparas i projektet**;
återstående kö försvinner vid kernelomstart eller när ett annat projekt öppnas.
Uppdaterade värden hos befintliga sulor behålls också när importkön avbryts.

**Radera samtliga sulor** tar bort alla sulor och deras beräkningsresultat på
samtliga ritningssidor efter en bekräftelse med antalet sulor. Eventuell
placeringskö avbryts. Ritningen, rubriker och projektets globala inställningar
behålls. Spara projektet för att skriva ändringen till JSON-filen. Från Python
kan samma åtgärd göras med `plan.ta_bort_samtliga()`.

Importen kan också startas från Python; placera sedan via planvyn:

```python
plan.importera_lasteffekt("Lasteffekt.json")
plan
```

`plan.lasteffekt_import` visar nästa stöd och aktuell placering. För
programmatisk placering används `plan.placera_lasteffekt(x, y, sida=1)`,
med relativa bildkoordinater mellan 0 och 1, där y ökar nedåt.

## Indatatabell och automatisk beräkning

Längst ned i planvyn finns **Sulor – indata**, med en rad per sula på samtliga
ritningssidor. Tabellen visar littera, ritningssida, status/utnyttjandegrad och
samtliga indatakategorier. Ändra mått, laster, jorddata, koefficienter,
isolering och glidning direkt i cellerna, utan en dialog. Decimaler kan anges
med komma eller punkt. Littera och kolumnrubriker hålls synliga när tabellen
rullas. Smala kolumner visar beteckning och enhet; håll pekaren över rubriken
för en fullständig förklaring. Enter går till samma kolumn på nästa rad; Shift + Enter går till
föregående rad.

Markeringar i ritningen och tabellen följs åt. Välj rader med kryssrutorna,
eller markera etiketter med Shift + klick/drag på ritningen. Kryssrutan i
tabellhuvudet väljer alla rader, även från andra sidor. Ändra en cell på en
markerad rad för att ersätta samma fält på **alla markerade rader**. Övriga
indata behålls per sula. På en omarkerad rad ändras endast den sulan.
Littera och fundamenttyp ändras alltid individuellt.

Blandade sultyper kan redigeras gemensamt för typoberoende fält, exempelvis
bₓ och isolering. Last- och längdfält kräver samma sultyp och är avstängda
vid blandat urval, eftersom laster anges per meter för väggsulor och totalt
för pelarsulor. bᵧ används endast för pelarsulor och glidlängden L endast för
väggsulor. Glidningsindata kan förberedas innan global glidningskontroll
aktiveras. Escape avmarkerar ritning och tabell; sidbyte rensar också urvalet.

Beräkning sker automatiskt vid placering, kopiering, ändring, lastuppdatering
och återöppning av projekt. Alla beräkningsknappar är borttagna. Ett fel
eller ofullständigt värde visas på den berörda sulan och ersätter dess gamla
resultat; övriga sulor beräknas ändå. Rätta cellen så uppdateras resultatet
igen. Ändringar följer med när projektet sparas eller exporteras.

Tabellen finns i notebookvyn. Resultat-HTML behåller sin läsvy med
expanderbara etiketter. Från Python beräknas sulor också automatiskt vid
`lagg_till()`, `uppdatera()` och som standard vid `uppdatera_flera()`.

## Lokala axlar och skisser

Indataraderna visar **beskrivning, beteckning, värde och enhet** i separata
kolumner, som i `Panel()`. Symbolerna har kursiv grundbokstav och nedsänkta
index, exempelvis bₓ, Mᵧ och γₘ. Även infotext och resultatrader visar
nedsänkta index, exempelvis f med index d,brott och q med index Ed.
Samma beteckningar visas i resultat-HTML.

Gränssnittet använder x tvärs en väggsula och y längs den; y-måttet i
beräkningen är 1 m. Pelarsulan visas med sina fulla mått bₓ × bᵧ. Axlarna
är lokala och kopplas inte automatiskt till ritningens riktningar.
**Visa definitionsskiss** öppnar planvy och två snitt med lastpilar.
På breda ytor ligger skissen bredvid dialogen, annars inne i den.

| Visad beteckning | Befintligt fältnamn i Python/JSON |
| --- | --- |
| bₓ / bᵧ | `b` / `l` |
| V | `F_vy` |
| Hₓ / Hᵧ | `F_hb` / `F_hl` |
| Mₓ / Mᵧ | `M_insp_b` / `M_insp_l` |
| eₓ,plac / eᵧ,plac | `e_b_plac` / `e_l_plac` |

Brukfälten har samma koppling med suffixet `_bruk`. Inga värden eller
momenttecken konverteras i tidigare projekt. Beräkningens befintliga
teckenkonvention behålls: positivt Mᵧ ger positivt bidrag i x och positivt
Mₓ ger positivt bidrag i y. Detta är programmets snittkonvention, **inte en
gemensam högerhandsregel för båda momentaxlarna**. Följ pilarna i skissen.

**Effektiv area – planvy** visar hela sulan i grått, effektiv area i grönt,
placeringen med en ring och resultanten R med en fylld punkt. Pilarna visar
Mᵧ/V i x-led och Mₓ/V i y-led. Under skissen redovisas bidragen med tecken:

```text
eₓ = eₓ,plac + Mᵧ/V      bₓ,eff = bₓ − 2|eₓ|
eᵧ = eᵧ,plac + Mₓ/V      bᵧ,eff = bᵧ − 2|eᵧ|
Aeff = bₓ,eff × bᵧ,eff
```

R ligger i den effektiva rektangelns centrum. Moment kan förstärka eller
motverka placeringsexcentriciteten. Måtten kommer från samma beräkning som
kontrollen; inga bärighetsberäkningar sker i webbläsaren. Skissen visar en
ekvivalent effektiv area, inte verklig kontakttrycksfördelning. Med isolering
kan **Brott** och **Bruk** väljas separat. Ändrade eller felaktiga indata
döljer skissen tills ett aktuellt resultat finns. Skissen och valet av
lastkombination finns även i resultat-HTML; PDF innehåller bara etiketterna.

## Visningsval

Vyn kommer ihåg vilka indata- och resultatavsnitt som är öppna för varje sula.
När du minimerar eller byter etikett och sedan återvänder återställs samma
utfällda och infällda avsnitt. Dessa visningsval gäller medan planvyn är öppen.
Ett enkelt klick utanför dialogrutan minimerar den, i både Jupyter och
resultat-HTML. Även ofärdiga inmatningar behålls. Klick i definitionsskissen
och dragningar för panorering lämnar dialogen öppen.

**Flytta:** dra etiketten till önskat läge och släpp. Ett kort klick öppnar
indata; en dragning flyttar etiketten utan att ändra indata eller resultat.
Positionen sparas i projektet. Dialogen kan flyttas genom att dra dess rubrik.

**Kopiera:** öppna en etikett, tryck **Kopiera sula** och klicka på ritningen
där den nya sulan ska placeras. Alla indata följer med, även ändringar som
ännu väntar på uppdatering. Kopian får nästa lediga VS-/PS-littera och egna indata.
Anpassa last och geometri; kopian beräknas automatiskt och originalet påverkas inte.
**Avbryt kopiering** eller Escape avslutar kopieringen utan att skapa en sula.

**Storlek:** reglaget **Etikettstorlek** ändrar etiketternas grundstorlek mellan
60 och 180 %, vid 100 % ritningszoom. Etiketterna förstoras och förminskas
tillsammans med ritningen när du zoomar. Grundstorleken sparas i projektet.
Dra på ritningen med vänster eller höger musknapp för att panorera fritt,
även när hela ritningen redan ryms i vyn. **Shift + scroll** över ritningen
zoomar in eller ut kring muspekaren. Scroll utan Shift behåller vanlig
scrollfunktion. Knapparna + och − styr också zoom;
**Anpassa** återställer zoom och centrering så att hela ritningen syns.
Taggarna behåller sina relativa lägen
vid zoom, panorering och sidbyte. Escape minimerar dialogen och avslutar
placeringsläget.

Grön tagg betyder U ≤ 100 %, röd betyder U > 100 % eller beräkningsfel.
Ändrade indata ger en streckad tagg och inga aktuella resultat förrän en
ny beräkning har körts. Att bara byta littera påverkar inte beräkningen.
Varje tagg har oberoende indata.

## Global glidningskontroll

Knappen **Glidningskontroll** aktiverar funktionen och markeras med färg.
Avstängning döljer kontrollerna och överlagringarna men behåller indata.
Kryssa i **Kontroll X_g** och/eller **Kontroll Y_g** för att ange globala
dimensionerande horisontallaster Hₓ,Ed och Hᵧ,Ed i kN, för lastkombination EQU.
X_g pekar åt höger på ritningen och Y_g uppåt. Koordinatsystemet är separat
från sulornas lokala x/y-axlar. Lokala horisontallaster från bärighetskontrollen
summeras inte automatiskt till dessa globala lasteffekter.

**X och Y kontrolleras var för sig, som separata lastfall.** Funktionen
kontrollerar inte samtidigt verkande horisontalkomponenter eller vridning.
Lastens absolutvärde jämförs med motståndet i vald riktning.

Under **Glidning** i respektive sulas indatadialog anges:

- **Bidrar i global X-led/Y-led:** de riktningar där sulans motstånd får räknas med.
  Inga riktningar är förvalda. Valen beskriver den antagna kraftöverföringen;
  parallella eller tvärgående sulor väljs manuellt. Funktionen kontrollerar
  inte att konstruktionen kan överföra krafterna till sulan.
- **V_Ed,EQU:** färdig dimensionerande vertikal kontaktlast i EQU, **inklusive
  sulans egentyngd**. Ange kN/m för väggsula och kN för pelarsula. Ingen
  egentyngd eller lastfaktor tillkommer i glidningsberäkningen.
- **μ_d:** färdig dimensionerande friktionskoefficient mellan sulan och
  underlaget. Ingen ytterligare partialkoefficient tillkommer.
- **L:** väggsulans hela bidragande längd i m. Detta är ett separat mått från
  bärighetskontrollens enmetersremsa. För pelarsulor används ingen längdfaktor.
  Längdfältet visas för väggsulor även innan en bidragsriktning har valts och
  även med isolering. Det kan lämnas tomt tills sulan ska bidra med glidmotstånd.

Motståndet för en vald riktning beräknas som
`H_Rd,i = V_Ed,EQU × L × μ_d` för väggsulor och
`H_Rd,i = V_Ed,EQU × μ_d` för pelarsulor. **Sulor med isolering bidrar alltid
med 0 kN**, oavsett tidigare glidningsindata. V och μ ska vara minst noll;
väggsulans L ska vara större än noll.

Motstånden summeras för varje riktning över **alla ritningssidor**. Den flyttbara
resultatrutan visar H_Ed, H_Rd, `U = |H_Ed| / H_Rd` och antal sulor med positivt
bidrag. Grönt betyder U ≤ 100 %, rött U > 100 %. Saknade eller ogiltiga indata
hos en vald sula gör kontrollen **Ofullständig**; ett delmotstånd redovisas då
inte som ett komplett resultat. En tom horisontallast tolkas inte som noll.
Resultaten uppdateras direkt när indata ändras, utan en separat beräkningsknapp.

På etiketten visas **Glidmotstånd – globalt** med V_Ed,EQU och L till vänster
och valda Hₓ,Rd,i/Hᵧ,Rd,i till höger. Glidningsblocket döljs på isolerade sulor
och sulor som inte bidrar i någon riktning. Etikettens färg och översta U avser
fortfarande jordens/isoleringens kontroll, medan resultatrutans färger avser
den globala glidningen. Ändring av glidningsindata gör inte jordresultatet inaktuellt.
När glidningsblocket är dolt visas en angiven positiv vägglängd i stället på
etikettens resultatrad, exempelvis `Kontrollera indata · L 6,2 m` eller
`U 78 % · bₓ 0,6 m · L 6,2 m`. Detta gäller också PDF och resultat-HTML.

Dra koordinatsymbolen för att flytta den. Klicka på den för att visa ramen
och dra hörnhandtaget för proportionell storleksändring. Piltangenter flyttar
symbolen; plus/minus ändrar storleken när hörnhandtaget har fokus. Dra
resultatrutans rubrik för att flytta rutan. Klicka på rutan och dra dess nedre
högra hörnhandtag för att förstora eller förminska hela rutan, inklusive texten.
Plus/minus fungerar också när hörnhandtaget har fokus. Symbol och ruta följer
ritningens zoom och får separata placeringar och storlekar på varje sida.

All glidningsindata samt placeringar och storlekar sparas med projektet. Äldre projekt
öppnas med glidningskontrollen avstängd. PDF-exporten innehåller fasta
överlagringar; HTML-exporten visar samma resultat och expanderbara indata,
utan möjlighet att ändra beräkningar.

Python kan också användas för att aktivera kontroller och läsa resultat:

```python
plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 180}
plan.uppdatera(tagg_id, indata={
    "glid_x": True, "V_Ed_EQU": 120, "glid_mu": 0.4, "glid_L": 3.0,
})
plan.glidningsresultat["x"]  # H_Rd = 144 kN för denna väggsula
```

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

Med `Grundplan("Hus A")` eller `Grundplan(key="Hus A")` fungerar lagringen
som i `Panel(..., key=...)`: nästa instans med samma fil och nyckel återställer
projektet automatiskt. **Spara projekt** visar sparinställningarna, förifyllda
för projekt som redan har en sparplats. Projektfil och key är obligatoriska.
Spara innan du stänger eller startar om kerneln; ändringar sparas inte
automatiskt. Från Python sparar `plan.spara()` direkt till den valda sparplatsen.

Standardfilen `.an_calcs_grundplan_state.json` finns i kernelns arbetsmapp.
Kontrollera den fullständiga sökvägen med `plan.state_file` eller håll musen
över sparfilens namn i gränssnittet. Varje nyckel har sitt eget projekt i
filen. En ny nyckel börjar tom och ersätter inte andra nycklar. JSON-filen
innehåller originalritningen, aktuellt sidnummer, rubriker, etikettstorlek,
alla taggpositioner, littera, indata och beräkningskodens versionsavtryck.

Spara-rutan listar giltiga Grundplan-state-filer i arbetsmappen och projektets
aktuella sparfil, även om den ligger någon annanstans. Varje fil visar sina
sparade keys. Valet byter sparplats för den aktuella planen; det öppnar inte
och ersätter inte vyn med innehållet i det sparade projektet. Om en annan
destination redan innehåller samma key måste ersättningen bekräftas.
Vid skrivfel behålls den tidigare sparplatsen och den gamla filen.

Knappen **Kopiera projekt + key** använder det faktiska Python-argumentet
`state_file=` trots fältnamnet **Projekt** i gränssnittet. Citattecken och
bakstreck i filnamn och keys hanteras som Python-text. Relativa sökvägar
behålls relativa, så notebook och JSON kan flyttas tillsammans. Om automatisk
kopiering inte tillåts visas argumenten i ett markerbart textfält.

En annan sparfil kan väljas för alla efterföljande instanser:

```python
Grundplan.configure_state_file("projekt.grundplan_state.json")
plan = Grundplan("Hus A")
plan
```

Eller för en enskild instans: `Grundplan(key="Hus A", state_file="projekt.json")`.
Ett explicit `state_file` går före den konfigurerade filen.
`Grundplan.configure_state_file(None)` återställer standardfilen. Relativa
sökvägar avser arbetsmappen när vyn skapas. Ange `key=` för nycklar som
innehåller punkt eller snedstreck; ett sådant första positionsargument
tolkas som en ritningssökväg. Ett `Path`-objekt tolkas alltid som en ritning.

För att börja använda ett befintligt nedladdat projekt, skapa exempelvis
`Grundplan("Hus A")`, välj **Öppna projekt** och därefter **Spara projekt**.
Projektet sparas då under den valda nyckeln.

**Exportera JSON** laddar ned en portabel kopia av det aktuella projektet.
Den kan öppnas med **Öppna projekt** eller från Python:

```python
plan.spara("hus_a.grundplan.json")
ateroppnad = Grundplan.oppna("hus_a.grundplan.json")
ateroppnad
```

Du kan börja med `Grundplan()` eller `Grundplan("grundplan.pdf")` och välja
projektfil/key i gränssnittet senare. Knappen **Spara projekt** skriver lokalt;
**Exportera JSON** laddar ned en portabel kopia. `plan.spara("kopia.json")`
behåller också funktionen för portabel export. En sparad notebook ersätter
inte projektfilen.

Vid återöppning beräknas alla sulor automatiskt från sparade indata med
aktuell beräkningskod. Sparade resultat behandlas aldrig som verifierade
numeriska data. Ofullständiga indata får sparas och visas som fel tills de
rättas.

Projekt sparas i formatversion 3. Äldre projekt i formatversion 1 och 2 kan
öppnas och beräknas också automatiskt. Deras angivna
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
kontroll, ifyllda laster och statusfärg följer med.
Etiketter nära sidkanten flyttas in så att hela etiketten ryms; mycket breda
etiketter förminskas vid behov. Etiketterna är fast sidinnehåll som följer
med vid utskrift, utan popup eller klickfunktion.

Exporten använder de automatiskt uppdaterade resultaten. Felaktiga eller
ofullständiga sulor visar sin status i stället för ett beräkningsresultat.
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
Dra i ritningen med vänster eller höger musknapp för att panorera,
använd **Shift + scroll** eller +/− för zoom och **Anpassa** för
att återställa vyn. Reglaget **Etikettstorlek** fungerar även i HTML-filen.
Visningsval gäller medan filen är öppen och ändrar inte det sparade projektet.

Beräkningsvärden och etikettpositioner är låsta i resultatvyn. Exporten
använder de automatiskt uppdaterade resultaten; felaktiga eller ofullständiga
sulor visar sin status i stället för ett aktuellt resultat. Använd JSON-projektet i Jupyter
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
taggar, ändra indata, spara och beräkna. Resultat-HTML fungerar utan kernel
och visar sparade indata och resultat utan möjlighet att räkna om.

## Ändra flera sulor samtidigt

Håll Shift och vänsterdra på en tom del av ritningen för att rita en
urvalsruta. Rutan träffar etiketter på den visade sidan även om de bara
ligger delvis i rutan. Dragningen växlar markeringen: omarkerade etiketter
i rutan läggs till, redan markerade avmarkeras och etiketter utanför rutan
behåller sin markering. Ctrl/Cmd fungerar på samma sätt.

Du kan också använda Shift-klick (eller Ctrl/Cmd-klick) på en enskild etikett
för att växla dess markering. **Markera flera** visar instruktionerna för
markering. Ett vanligt klick på en etikett öppnar alltid objektets redigering,
även efter ett urval eller när **Markera flera** är aktivt. Markerade etiketter
får en ram och en bock. Tryck **Ändra markerade** för gemensam indata.

Vanligt vänsterdrag eller högerdrag panorerar även med ett aktivt urval.
Det ändrar inga etikettpositioner. Tryck **Avmarkera** för att börja ett nytt urval.
Dra direkt i en etikett utan Shift för att flytta den, även när ett urval
eller **Markera flera** är aktivt.

Kryssa i de fält som ska ersättas, eller skriv direkt i dem så kryssas de i
automatiskt. **Olika värden** betyder att sulornas befintliga värden skiljer sig;
inget värde ersätts förrän du väljer fältet och trycker **Tillämpa**. Övriga parametrar, littera, sultyp och placering behålls.
Du kan exempelvis ändra isolering för ett helt urval, bredden för väggsulor eller
både bₓ och bᵧ för pelarsulor. Isolerprodukt och glidningsindata kan också ändras.

Vid blandat urval av vägg- och pelarsulor kan gemensamma mått som bₓ och
isoleringsinställningar ändras. Last- och längdfält kräver ett urval med samma
sultyp, eftersom laster anges per meter för väggsulor och totalt för pelarsulor.
Fundamenttypen ändras i varje sulas vanliga dialog.

**Tillämpa** uppdaterar och beräknar varje markerad sula automatiskt
med dess egna kvarvarande värden. I tabellen kan samma ändring göras direkt
i en cell på en markerad rad, utan dialog. Fel redovisas
med sulans littera; övriga sulor beräknas ändå. Saknade brukslaster och
isoleringsbärförmågor behöver fyllas i när isolering aktiveras.

Urval och ännu ej tillämpade gemensamma ändringar är tillfälliga. Tillämpade
värden sparas och exporteras med projektet på vanligt sätt. **Avmarkera**
rensar urvalet. Escape avslutar markeringsläget och rensar hela urvalet,
även under en pågående urvalsdragning. Urvalsrutan och markeringarna
försvinner direkt.
Sidbyte rensar också urvalet. Resultat-HTML har ingen
gemensam redigering.

Från Python kan motsvarande ändring göras med:

```python
ids = [tagg["id"] for tagg in plan.taggar if tagg["values"]["lang"] == 1]
rapport = plan.uppdatera_flera(ids, indata={"b": 0.9}, berakna=True)
rapport  # Antal uppdaterade/beräknade sulor och eventuella fel per sula.
```

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
