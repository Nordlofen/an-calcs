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
**Shift + Enter** lägger till en ny rad i underrubriken; fältet växer med texten.
Underrubriken har ingen separat teckengräns; hela texten sparas och följer med HTML-exporten.
**Enter** avslutar redigeringen.
Båda sparas i JSON-projektet och visas med samma innehåll i HTML-exporten.
Du kan också ange `underrubrik="Revision A"` när planen skapas eller ändra
texterna via `plan.titel` och `plan.underrubrik`. En tom underrubrik döljs
i HTML-exporten. Ändringarna påverkar inte sulornas beräkningar.

**Lägg till rubrik** och **Lägg till datum (åå/mm/dd)** skapar separata textobjekt
på ritningen. **Lägg till rubrik** kopierar direkt den befintliga rubriken och
hela underrubriken från interfacet, inklusive radbrytningar och textbredd.
Typsnitt och textstil är desamma. Du behöver inte skriva in texterna igen.
Båda flyttas och skalas tillsammans. Datumet börjar med dagens datum i Stockholm, exempelvis `26/10/08`,
och ändras inte när projektet öppnas igen. Dra texten för att flytta den och dra
hörnhandtaget för att förstora/förminska. Klicka på texten för att visa **Redigera**
och **×** (ta bort). Dubbelklick öppnar också textredigeringen; **Shift + Enter**
lägger till en rad. Rubrik, underrubrik och datum kan redigeras utan separat teckengräns,
exempelvis till ett revisionsdatum. Via Python kan en rubrik läggas till med
`plan.lagg_till_rubrik("Hus 1", underrubrik="Revision A")`.
Text, placering och storlek sparas i projektet och följer med PDF och HTML.
HTML visar fasta textobjekt. Flera rubriker/datum kan läggas till oberoende av varandra.
**Enter** avslutar redigeringen. Textobjekten påverkar inte sulornas beräkningar.

Varje `Grundplan` är låst till en ritningssida. En PDF med flera sidor används
med en separat cell och egen `key` för varje sida. Ange `sida=2` när den andra
vyn skapas; utan `sida` väljs sida 1. Detta gäller även om ritningen väljs via
**Öppna ritning**. En sparad key återställer sin tidigare valda sida.
Sidbyte i en befintlig vy stöds inte, och PDF/HTML-export innehåller endast
den valda sidan. Äldre projekt med sulor eller glidningssymboler på andra
sidor avvisas utan att den öppna vyn ändras eller projektfilen skrivs över.

```python
# Cell 1
plan_1 = Grundplan("grundplan.pdf", key="Hus A - sida 1", sida=1)
plan_1
```

```python
# Cell 2
plan_2 = Grundplan("grundplan.pdf", key="Hus A - sida 2", sida=2)
plan_2
```

Sökvägar avser kernelns filsystem och arbetsmapp. PDF-sidor numreras från 1.
PNG, JPEG, WebP, TIFF (första bildrutan) och BMP stöds också.

## Arbeta i planvyn

1. Öppna en ritning. Varje Grundplan gäller en enda ritningssida.
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
   `U 34,6 % · bₓ 1,8 m · t 0,3 m` för väggsula eller
   `U 68,3 % · bₓ 1,8 m · bᵧ 2,4 m · t 0,3 m` för pelarsula.
   Även väggsulor med ändrat bᵧ visar båda måtten med respektive beteckning.
   Alla beräknade sulor utom **Endast H-stabilitet** visar en tredje rad
   med styrande kontroll, till exempel `Styrande: Jord · brott` eller
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
med `schemaVersion: 1` eller `schemaVersion: 2` och listan `supports`. Hela filen kontrolleras innan
några sulor ändras eller placeringen startar. Filen får vara högst 5 MB.
Littera (`supportId`) måste vara unika i filen. För befintliga sulor matchas
support-ID mot littera i den aktuella vyn. Matchningen är skiftlägeskänslig.

Matchade sulor får nya vertikallaster för Brott, Bruk och EQU samt ny linjestödslängd L_vägg
för väggsulor. Vid första importen fyller längden även sulängden L_su. Vid uppdatering följer
L_su det importerade startvärdet om det inte ändrats; en manuellt ändrad sulängd behålls,
även efter sparning, återöppning och kopiering. Placering, littera, sultyp och övriga indata behålls. Ändrade
bärighetslaster räknar automatiskt om jord- och isoleringskontrollerna.
En oförändrad import behåller aktuella resultat. Glidmotståndet uppdateras
direkt från EQU-lasten och längden. Om ett littera matchar flera befintliga
sulor, eller filens lasttyp skiljer sig från den befintliga, avvisas hela importen.
Matchningen använder lasttypen, inte beräkningsmodellen. En importerad linjelast
kan därför uppdateras även efter byte till pelarsulemodellen; den valda modellen behålls.
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
| `type: "line"` / `"point"` | Lasttyp linjelast / total last; nya objekt får väggsulemodell / pelarsulemodell |
| `results[].category: "Brott"`, `V` | Vertikallast under Laster – Brott (`F_vy`) |
| `results[].category: "Bruk"`, `V` | Vertikallast under Laster – Bruk (`F_vy_bruk`) |
| `results[].category: "EQU"`, `V` | Färdig kontaktlast under Glidning (`V_Ed_EQU`) |
| `length.value`, `length.unit: "m"` | Hela L_vägg (`L_vagg`), automatisk inställning av Minst 1 m (`L_vagg_minst_1`) samt startvärde för L_su under Glidning (`glid_L`) |

Varje stöd ska ha exakt en last för Brott, Bruk och EQU. Väggsulor kräver
`distribution: "uniform"`, laster i `kN/m` och en positiv längd i `m`.
Pelarsulornas laster anges i `kN`. Värden och tecken behålls; linjelaster
behålls som inmatade linjelaster i kN/m. **Minst 1 m** kryssas automatiskt i
för importerad L_vägg ≥ 1 m. Jord- och isoleringskontrollen multiplicerar då
laster och moment med **1 m**. För kortare stöd är rutan avmarkerad och den
importerade längden visas som redigerbart värde. **bᵧ ändrar kontaktarean,
inte den yttre lastresultanten.** Hela importerade längden sparas även när
det numeriska fältet döljs. Samma importerade längd ger startvärdet för L_su,
som används separat för total EQU-last vid glidning och kan ändras oberoende.
Ingen ytterligare längdfaktor läggs på importerade punktlaster. Metadata som `model` och `source`
används inte som sökvägar eller beräkningsindata.
Version 2 kan beskriva flera lastkombinationer och `meanEnvelope` i `source`.
Importen använder det färdiga `V`-värdet för respektive lastkategori, utan att
räkna om enveloppen eller ändra tecknet utifrån `source.extremum`.
De båda filversionerna kan användas för att skapa och uppdatera sulor i samma projekt.

Nya sulor får övriga startvärden från Grundplan och beräknas automatiskt vid placering.
Kontrollera geometri, jord, isolering och glidningsinställningar efter
placeringen, gärna med flerredigering. Bidragsriktningarna för glidning är
inte förvalda. EQU-lasten ska redan innehålla sulans egentyngd; vid beräkning
behandlas Brott och Bruk på samma sätt som manuellt inmatade yttre laster.
Importerade värden är vanliga redigerbara indata. Bruklasterna kan ändras även
utan isolering, och under Glidning kan EQU-lasten, friktionen och vägglängden
anges innan någon bidragsriktning väljs. Tomma, ännu oanvända värden krävs inte
för jordens bärighetskontroll.

**Pausa placering** eller Escape behåller kön så att du kan arbeta med
ritningen och befintliga sulor. Tryck **Fortsätt placera** för att fortsätta.
**Avbryt import** avslutar kön och
behåller redan placerade sulor. **Endast placerade sulor sparas i projektet**;
återstående kö försvinner vid kernelomstart eller när ett annat projekt öppnas.
Uppdaterade värden hos befintliga sulor behålls också när importkön avbryts.

**Radera samtliga sulor** tar bort alla sulor och deras beräkningsresultat på
den aktuella vyn efter en bekräftelse med antalet sulor. Eventuell
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

Längst ned i planvyn finns **Sulor – indata**, med en rad per sula i
vyn. Tabellen visar littera, status/utnyttjandegrad och
samtliga indatakategorier. Ändra mått, laster, jorddata, koefficienter,
isolering och glidning direkt i cellerna, utan en dialog. Decimaler kan anges
med komma eller punkt. Littera och kolumnrubriker hålls synliga när tabellen
rullas. Smala kolumner visar beteckning och enhet; håll pekaren över rubriken
för en fullständig förklaring. Enter går till samma kolumn på nästa rad; Shift + Enter går till
föregående rad i den visade ordningen. Kommentarens textfält tillåter flera rader.

Klicka på valfri kolumnrubrik för sortering. Tal sorteras numeriskt, text alfabetiskt och saknade/ej tillämpliga indatavärden sist i båda riktningarna. Vid lika värden sorteras raderna efter **Littera**, naturligt, exempelvis S.2 före S.10.
**Status / U** visar fel i indata först, därefter pågående uppdateringar och
sedan beräknade sulor med högst utnyttjandegrad först. Ett nytt klick på samma
rubrik vänder ordningen; pilen visar riktningen. Sorteringen ändrar endast
tabellens visning. Markeringar och indata hör fortfarande till samma sulor.
Rader flyttas först när fokus lämnar tabellraderna efter cellredigering.

Om sulor är markerade när du klickar på en sorteringsrubrik sorteras **bara de markerade raderna** och samlas överst. Övriga rader ligger under och behåller sin inbördes ordning. Själva markeringen flyttar inga rader; nästa rubrikklick använder den då aktuella markeringen. Utan markering sorteras hela tabellen. Detta gäller även i HTML-resultatvyn.

Klicka på en huvudkategori, exempelvis **Geometri** eller **Laster – Brott**, för att fälla ihop dess kolumner. Den smala gruppfliken finns kvar för att visa dem igen. Littera och Status / U är alltid synliga. Fällning och sortering sparas med projektet och används vid HTML-export.

Markeringar i ritningen och tabellen följs åt. Välj rader med kryssrutorna,
eller markera etiketter med Shift + klick/drag på ritningen. Kryssrutan i
tabellhuvudet väljer alla rader. Ändra en cell på en
markerad rad för att ersätta samma fält på **alla markerade rader**. Övriga
indata behålls per sula. På en omarkerad rad ändras endast den sulan.
Littera och fundamenttyp ändras alltid individuellt.

Klicka på en radkryssruta för att sätta en startpunkt. Shift + klick på en
annan rad markerar eller avmarkerar hela intervallet i tabellens visade
ordning, beroende på slutradens nya kryssvärde. Fler Shift + klick använder
samma startpunkt; ett vanligt klick sätter en ny. Rader utanför intervallet
behåller sin markering. Escape och **Avmarkera** rensar både markering och
startpunkt.

Blandade sultyper kan redigeras gemensamt för typoberoende fält, exempelvis
bₓ och isolering. Last- och längdfält kräver samma sultyp och är avstängda
vid blandat urval, eftersom laster anges per meter för väggsulor och totalt
för pelarsulor. bᵧ är redigerbart även för väggsulor, i dialogen, tabellen
och vid flerredigering. Aktivera den lilla kryssrutan **Egen längd** vid bᵧ
för att låsa upp inmatningen. När den är av visas ett grått, låst **1 m**.
Avmarkering återställer måttet till 1 m och räknar om sulan direkt.
Inställningen sparas och kopieras med sulan. Pelarsulors bᵧ är alltid
redigerbart. Standardvärdet för väggsulor är 1 m och lasterna anges fortfarande
per meter vägg. Det valda måttet sparas och används i skissen för effektiv
area. När bᵧ avviker från 1 m visar även väggsuletiketten bₓ × bᵧ.
Tidigare sparade egna väggsulemått aktiverar kryssrutan vid återöppning.
Projekt från tiden före bᵧ-redigeringen återställs med 1 m, eftersom deras
sparade längdvärde tidigare inte användes för väggsulor. Från Python aktiverar
`indata={"l": 2.4}` egen längd automatiskt; `indata={"l_override": False}`
återställer 1 m. Sulängden L_su används endast för
väggsulor. Glidningsindata kan förberedas innan global glidningskontroll
aktiveras. Escape avmarkerar ritning och tabell.

Beräkning sker automatiskt vid placering, kopiering, ändring, lastuppdatering
och återöppning av projekt. Alla beräkningsknappar är borttagna. Ett fel
eller ofullständigt värde visas på den berörda sulan och ersätter dess gamla
resultat; övriga sulor beräknas ändå. Rätta cellen så uppdateras resultatet
igen. Ändringar följer med när projektet sparas eller exporteras.

Tabellen finns både i notebookvyn och som låst läsvy i resultat-HTML. Från Python beräknas sulor också automatiskt vid
`lagg_till()`, `uppdatera()` och som standard vid `uppdatera_flera()`.

## Lokala axlar och skisser

Indataraderna visar **beskrivning, beteckning, värde och enhet** i separata
kolumner, som i `Panel()`. Symbolerna har kursiv grundbokstav och nedsänkta
index, exempelvis bₓ, Mᵧ och γₘ. Även infotext och resultatrader visar
nedsänkta index, exempelvis f med index d,brott och q med index Ed.
Samma beteckningar visas i resultat-HTML.

Gränssnittet använder x tvärs en väggsula och y längs den; bᵧ har
standardvärdet 1 m och kan ändras. Pelarsulan visas med sina fulla mått
bₓ × bᵧ. Axlarna är lokala och kopplas inte automatiskt till ritningens riktningar.
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

**Flytta flera:** markera etiketter med Shift + klick, urvalsruta eller
tabellens kryssrutor. Dra sedan en av de markerade etiketterna med vanligt
vänsterdrag. Alla markerade etiketter flyttas lika långt och behåller sina
inbördes avstånd. Vid ritningskanten begränsas hela gruppens förflyttning.
Markeringen behålls efter flytten; en omarkerad etikett flyttas individuellt.
Escape avbryter dragningen och återställer alla placeringar. Hänvisningslinjer
följer etiketternas ramar, medan spetsar och mellannoder ligger kvar.
Gruppflyttning är tillgänglig i redigeringsvyn; resultat-HTML behåller låsta placeringar.

**Hänvisningslinje (spline):** öppna sulans redigeringspanel och fäll ut
**Etikett**. Markera **Hänvisningslinje** och dra en bana från etikettens ram
till önskad pilspets. Banan jämnas ut och får automatiskt så få noder som behövs
för att återge formen. Långa raka sträckor får färre noder; böjar och avsiktliga
öglor behålls. Ett klick på ritningen skapar i stället en enkel spline.
Den andra änden sitter fast i etikettens ram och följer med vid flytt
eller ändrad etikettstorlek. Avmarkering döljer linjen; när den aktiveras igen
återkommer samma placering, anslutningspunkt och kurvform.

**Rita om spline** låter dig börja om med en ny bana från samma anslutningspunkt.
Den gamla linjen visas svagt medan du ritar och ersätts först när du släpper en
giltig ny bana. Alla gamla noder ersätts. Escape avbryter och behåller den tidigare
formen. En avbruten eller alltför kort dragning sparar ingen ändring.

Klicka på linjen eller **Redigera linje** för att visa noder och kontrollhandtag.
Dra anslutningsnoden längs ramen för att välja sida och läge. Dra spetsen eller
mellannoder för att flytta dem; de små blå handtagen ändrar böjningen.
Dubbelklick på kurvan lägger till en mellannod utan att ändra kurvformen.
Markera en mellannod och tryck Delete eller Backsteg för att ta bort den.
Ändpunkterna behålls. Escape avslutar redigeringen och avbryter en pågående
dragning eller placering. En linje kan ha upp till 64 ritningsnoder.

Linjetjocklek och pilhuvud följer etikettstorleken: vid 100 % är de 1 px
respektive 7 px, vid 150 % 1,5 px respektive 10,5 px. Ritningszoom skalar hela
presentationen på skärmen och ändrar inte exportens grundstorlek. Spets och
mellannoder behåller sina relativa ritningspositioner när etiketten skalas.
Pilhuvudet följer splinens verkliga riktning vid spetsen. Ingen extra rak del
eller övergångskurva ändrar den ritade formen. Smala skyddsområden längs
pilhuvudets armar håller förbipasserande kurvdelar fria från pilens sidor.
Även dessa områden följer etikettstorleken.
PDF och resultat-HTML visar linje och pil som vektorer utan redigeringshandtag.
Linjen lagras separat från beräkningsindata och ändrar inga beräkningsresultat.

**Kopiera:** öppna en etikett, tryck **Kopiera sula** och klicka på ritningen
där den nya sulan ska placeras. Alla indata följer med, även ändringar som
ännu väntar på uppdatering. Kopian får nästa lediga VS-/PS-littera och egna indata.
Anpassa last och geometri; kopian beräknas automatiskt och originalet påverkas inte.
**Avbryt kopiering** eller Escape avslutar kopieringen utan att skapa en sula.

**Storlek:** reglaget **Etikettstorlek** ändrar etiketternas grundstorlek mellan
20 och 180 %, vid 100 % ritningszoom. Etiketterna förstoras och förminskas
tillsammans med ritningen när du zoomar. Grundstorleken sparas i projektet.
Dra på ritningen med vänster eller höger musknapp för att panorera fritt,
även när hela ritningen redan ryms i vyn. **Shift + scroll** över ritningen
zoomar in eller ut kring muspekaren. Scroll utan Shift behåller vanlig
scrollfunktion. Knapparna + och − styr också zoom;
**Anpassa** återställer zoom och centrering så att hela ritningen syns.
Taggarna behåller sina relativa lägen
vid zoom och panorering. Escape minimerar dialogen och avslutar
placeringsläget.

Grön tagg betyder U ≤ 100 %, röd betyder U > 100 % eller beräkningsfel.
Ändrade indata ger en streckad tagg och inga aktuella resultat förrän en
ny beräkning har körts. Att bara byta littera påverkar inte beräkningen.
Varje tagg har oberoende indata.

Jorddata, grundvatten, grundläggningsdjup **d** och samtliga koefficienter samlas under
**Jord - Allm. Bärighets.** i dialogen, flerredigeringen och tabellen.
Samma indelning används i resultat-HTML.

## Arbetsytans och tabellens storlek

Arbetsytans och tabellens bredd och höjd kan justeras oberoende med handtagen
i respektive nedre högra hörn. Dra diagonalt eller i en riktning; ritningens zoom,
etikettplaceringar, markeringar och indata behålls. Bredden ryms inom notebookens
eller webbläsarens tillgängliga utrymme. Tabellen får egen rullning när alla rader
eller kolumner inte ryms. Dubbelklick återställer både standardbredd och standardhöjd.
När handtaget har fokus ändrar vänster/höger bredden och upp/ned höjden
(20 px, eller 100 px med Shift). Home/End väljer minsta/största storlek;
Enter återställer standardstorleken. Escape avbryter pågående dragning.

Valda storlekar sparas med projektet och följer med till resultat-HTML. Där kan
storlekarna också ändras lokalt utan att låsa upp indatavärden. PDF-exporten
påverkas inte av arbetsytans eller tabellens visningsstorlek. Äldre projekt med
enbart höjdinställningar använder automatiskt full tillgänglig bredd.

```python
plan.visningsstorlekar = {"board_width": 1100, "board_height": 850,
                         "table_width": 900, "table_height": 350}  # px
plan.visningsstorlekar = {"board_width": None, "board_height": None}  # Standardstorlek.
```

`plan.visningshojder` fungerar fortfarande för att läsa och ändra enbart höjderna.

## Kommentarer och sammanställningswidgetar

**Kommentar** är en egen huvudkategori sist i dialogen och längst till höger i tabellen. Fältet tillåter flera rader och kan redigeras gemensamt för markerade sulor, även vid blandade sultyper. Texten sparas med sulan och påverkar inga beräkningsresultat.

En ifylld kommentar markeras med en liten pratbubbla längst till höger på etikettens första rad. Håll pekaren över bubblan för att läsa texten; klicka för att öppna och visa kommentarsavsnittet. Tom text eller enbart blanksteg ger ingen symbol. Resultat-HTML visar kommentaren som låst text, medan PDF visar symbolen på etiketten.

**Lägg till kommentarer** visar en flyttbar och skalbar ruta med **Littera** och **Kommentar** för endast sulor med ifylld kommentar. Rutan uppdateras direkt när kommentarer eller sulor ändras och har ingen fottext. Placering, storlek och på/av sparas med projektet; den följer med PDF och låst resultat-HTML. Knappen visar eller döljer samma ruta och behåller dess placering och storlek.

Vid aktiv **Färggruppering** får litteran i kommentarsrutan en kompakt ram med samma bakgrundsfärg som sulans färggrupp. Färgen följer vald kategori, kombination, lastintervall och egna färgval, även när färglegenden är dold. När färggrupperingen är avstängd eller sulan saknar tillämplig färggrupp visas litteran utan färgram. Utseendet följer med PDF och resultat-HTML.
Eventuellt gruppmönster visas även i litterans färgram.

**Widget: Isolering** aktiverar en fristående ruta på ritningen med antal sulor **Med isolering** och **Utan isolering** samt littera för alla **Föreskrivna utan isolering**. Sulor med **Endast H-stabilitet** utesluts från både antalen och litteralistan, även i PDF och resultat-HTML. Antal och littera uppdateras när sulor ändras, läggs till eller tas bort.

Dra widgetens rubrik för att flytta rutan. Klicka på den och dra hörnhandtaget för att skala hela rutan. Piltangenter flyttar och plus/minus på hörnhandtaget ändrar storlek. På/av, placering och storlek sparas med projektet och behålls när widgeten stängs av. PDF och resultat-HTML visar den sparade rutan; HTML:s PDF-knapp hämtar samma inbäddade PDF.

```python
plan.farggruppering = {"enabled": True, "categories": ["t", "b"]}
plan.kommentarwidget = {"enabled": True, "x": .08, "y": .55, "size": 410}
plan.isoleringswidget = {"enabled": True, "x": .65, "y": .55, "size": 300}
plan.tabellvy = {"collapsed": ["F_vy", "F_vy_bruk"],
                 "sort": {"key": "b", "direction": "ascending"}}
```

## Färggruppering

**Färggruppering** öppnar en kompakt inställningsrad under verktygsfältet.
Välj valfritt antal av **Tjocklek t**, **Bredd bₓ**, **Längd bᵧ**, **Vertikallast V** och **Isolering**, från en till alla fem.
Varje unik kombination får en färg. Vid exempelvis bₓ + t + V · brott måste både bredd, tjocklek och lastintervall vara samma för att sulorna ska dela färg. Bara upptagna kombinationer visas i legend och färgval. Klicka på en vald kategori för att avmarkera den; minst en kategori är alltid vald. Lastintervallets inställningar visas när V ingår bland valen. Egna färger behålls oavsett i vilken ordning samma kategorier väljs.
Kombinationer med V visar mått och övriga val på första raden i legenden och lastintervall med kN eller kN/m på andra raden. Kombinerade mått utan V behåller en gemensam rad och bryts vid behov.
Checkboxen **Endast H** är avmarkerad som standard. Sulor med **Endast H-stabilitet**
får då helt vit bakgrund utan gruppmönster och räknas inte i färglegenden.
Statusprick, ram och glidmotståndsinformation behålls. Markera rutan för att ta med
dem vid **Isolering**, **V · EQU** eller kombinationen av dessa.
De utesluts alltid när t, bₓ, bᵧ eller V · Brott/Bruk ingår bland valen,
även vid kombinerad gruppering. Ingen grupp **Ej tillämpligt** skapas.
Rutan är då inaktiv och avmarkerad, med en förklaring som visar vilka val
som behöver ändras. Det sparade valet behålls och gäller igen när du återgår
till Isolering eller V · EQU. Vid dessa val uppdateras etikettfärger och
legend direkt när rutan markeras eller avmarkeras.
Inställningen sparas i projektet; äldre projekt får rutan avmarkerad.
Sulmått och tjocklek får en färg per unikt indatavärde. Klicka på färgrutorna
för att välja egna färger. Mörka färger visas med ljusare bakgrund på
etiketten så att texten förblir läsbar. Prick och kant visar fortfarande
kontrollstatus; färggrupperingen ändrar inga laster eller beräkningar.

Grundpaletten är [ColorBrewer Set3 med tolv färger](https://colorbrewer2.org/#type=qualitative&scheme=Set3&n=12),
med originalfärgerna bevarade. De första tolv upptagna grupperna får varsin färg.
Grupper 13–24 återanvänder färgerna med breda diagonala band över hela etiketten;
25–36 får stora prickar. Därefter används kryssband, horisontella och vertikala band.
Mönstren ligger bakom texten och får grövre avstånd och markeringar vid utzoomning,
så att de kan urskiljas i översiktsläget. Legendens färgrutor och kommentarsrutans littera
visar samma färg och mönstertyp. PDF-exporten behåller dem som vektorer.

Tomma intervall och den neutrala gruppen **Saknar värde** tar inga färgplatser.
Automatiska markeringar sparas separat för varje kategorikombination och lastfall.
Aktuella gruppers färger behålls där det går vid redigering, byte av gruppering och återöppning.
Grupper som försvunnit eller blivit tomma reserverar inga färgplatser. Nya grupper
använder lediga grundfärger först. Finns högst tolv upptagna grupper används inga
mönster, även om sparade tilldelningar tidigare hade skraffering. Vid fler grupper
används alla tolv grundfärger innan nästa uppsättning får mönster.
Tomma grupper som ännu inte tilldelats en färg visas neutralt bland färgvalen.
Egna sparade färgval behålls och kan fortfarande ändras med färgväljaren.

**Isolering** visar fem grupper i legenden **Isolering och glidmotstånd**:

- **Med isolering · inget bidrag**
- **Utan isolering · inget bidrag**
- **Utan isolering · bidrag i X_g**
- **Utan isolering · bidrag i Y_g**
- **Utan isolering · bidrag i X_g och Y_g**

Grupperna följer sulans valda bidragsriktningar under **Glidning**, även när
den globala glidningskontrollen är avstängd. De anger valda riktningar,
inte att bärförmågan är färdigberäknad eller större än noll. Isolerade sulor
hör alltid till första gruppen, oavsett sparade riktningsval. Både vägg- och
pelarsulor ingår. Sulor med **Endast H-stabilitet** ingår när **Endast H** är
markerad och grupperas som utan isolering med sina valda riktningar.
X_g och Y_g kontrolleras som separata lastfall.
Legenden visar endast grupper med minst en sula och uppdateras när indata
eller sulor ändras. Tomma grupper döljs även i HTML och PDF. Egna färgval
behålls i inställningarna, så att en grupp som åter får sulor visas med
samma manuellt valda färg.
Färgvalen sparas och exporteras på samma sätt som övriga färgkategorier.
Äldre färgval för med isolering och utan isolering behålls för första
respektive andra gruppen. Utan isolering visas valda H_Rd-bidrag, V_Ed,EQU
och väggsulans L_su i etikettens glidmotståndsblock, även när den globala
glidningskontrollen är avstängd. Isolerade sulor får inget extra glidblock.
H_Rd visas med högst en decimal i etiketter, glidningslegend och export;
beräkningar och sparade resultat behåller full precision.

För **Vertikallast V** väljer du **Brott**, **Bruk** eller **EQU**.
Grupperingen använder angiven last: F_vy, F_vy_bruk respektive V_Ed_EQU,
utan något tillägg för egentyngd. EQU-lasten ska redan innehålla egentyngd.
Pelarsulor och väggsulor har separata intervall i **kN** respektive **kN/m**.
Valet **Intervall för** styr vilka gränser och färger du redigerar;
båda typerna färggrupperas samtidigt på ritningen.

Ange gränser i stigande ordning, exempelvis `100; 200; 400`.
Det ger grupperna V < 100, 100 ≤ V < 200, 200 ≤ V < 400 och V ≥ 400.
Även kommaseparerade heltal, som `100, 200, 400`, fungerar.
Använd semikolon mellan gränser om du skriver decimaler med komma:
`100,5; 200,5; 400`. Undre gränsen ingår, övre gränsen ingår inte.
Tomma, upprepade eller osorterade gränser avvisas och tidigare gränser behålls.

**Visa legend** styr färglegenden på ritningen. Dra rubriken för att flytta
den, klicka på den och dra hörnhandtaget för att skala rutan inklusive texten.
Piltangenter flyttar den och plus/minus på hörnhandtaget ändrar storleken.
Legenden följer ritningens zoom och visar färgernas betydelse samt antal
sulor per grupp. Vid lastgruppering visas separata enheter för de två typerna.
Sulor som uteslutits ur grupperingen visas vita och utelämnas ur legenden.
Saknad indata hos sulor som omfattas av grupperingen får **Saknar värde**.

När **Färggruppering** stängs av döljs färger och legend. Alla valda kategorier, lastfall,
intervall, färger, legendens visningsval, placering och storlek behålls och
återkommer när knappen aktiveras igen. Inställningarna sparas i projektet.
PDF och låst resultat-HTML visar den sparade färggrupperingen och legenden;
HTML:s PDF-knapp exporterar samma inbäddade PDF med dessa färger.

Python kan också ändra inställningarna utan att ändra sulornas indata:

```python
plan.farggruppering = {"enabled": True, "categories": ["b", "t", "V"],
                       "phase": "brott", "bounds": {"wall": [100, 200, 400, 600]}}
plan.farggruppering = {"enabled": True, "category": "V", "phase": "EQU",
                       "bounds": {"wall": [100, 300, 600]}, "show_legend": True,
                       "include_only_h": True}  # Ta även med sulor med endast H-stabilitet.
plan.farggruppering = {"legend": {"x": 0.6, "y": 0.15, "size": 360}}
plan.farggruppering = {"enabled": False}  # Inställningarna behålls.
```

Äldre projekt och Python-anrop med `category` och `secondary` fungerar fortfarande och behåller sina färgval. `categories` är listan för nya kombinationer. Ett anrop med `category` eller `secondary` utan `categories` ersätter listan med det äldre kategori-/parvalet.

## Linjestödslängd och sulgeometri

**Beräkningsmodell** och **lasttyp** är separata inställningar. Väggsulemodellen
använder alltid linjelaster. För **Pelarsula** visas **Last anges som** med
alternativen **Linjelast [kN/m]** och **Total last [kN]**. Nya manuella pelarsulor
har total last som standard. Vid byte från väggsulemodell behålls linjelasten.

En pelarsulemodell med linjelast visar **L_vägg** och använder hela den positiva
längden, även över 1 m. Krafter i brott, bruk och EQU samt yttre moment
omräknas från per meter till totalsiffror. **Minst 1 m** döljs i denna modell.
bₓ/bᵧ anger kontaktmåtten och ändrar inte den yttre lastresultanten. Originalindatan
behålls vid modellbyte, sparning och importuppdatering; ingen dubbel omräkning sker.
Äldre importerade linjestöd känns igen på sparad importinformation även om deras
beräkningsmodell ändrats till pelarsula. Äldre manuella pelarsulor behåller total last.

Tabellen visar den skrivskyddade kolumnen **V_res [kN]** direkt efter V i både
**Laster – Brott** och **Laster – Bruk**. V_res är den yttre lastresultanten,
exklusive sulans egentyngd: V × använd stödslängd för linjelast, annars V.
Kolumnerna uppdateras automatiskt, kan sorteras med littera som skiljekriterium
och följer med gruppens visningsval och den låsta HTML-exporten. Saknad/ogiltig
last eller stödslängd visas som ett streck; andra indatafel hindrar inte att en
giltig resultant visas. Endast H-stabilitet visar inga brott-/brukresultanter.
På pelarsuleetiketter med linjelast visas exempelvis **V 200 kN/m → 120 kN**.

Python-fältet `lasttyp` är 1 för linjelast och 0 för total last; `lang` väljer
fortfarande beräkningsmodell. Exempel för ett linjestöd som kontrolleras som pelarsula:

```python
plan.uppdatera(tagg_id, indata={"lang": 0, "lasttyp": 1, "L_vagg": 0.6,
                              "b": 1.2, "l": 1.3, "F_vy": 200, "F_vy_bruk": 100})
# Yttre lastresultanter: 120 kN i brott, 60 kN i bruk.
```

**L_vägg** ligger under **Geometri** och betyder "Längd linjestöd alt. längd ovanliggande vägg".
Fältet gäller linjelaster. För väggsulemodellen finns **Minst 1 m**, som automatiskt väljs
för importerad längd ≥ 1 m. Då används 1 m lokalt och det numeriska fältet döljs;
hela importerade längden sparas som L_vägg och ger startvärdet för L_su.
För kortare stöd är valet av och längden redigerbar i dialogen, tabellen och
för flera markerade sulor.
Importformatet ändras inte: befintliga `length.value` fyller fältet.
**bᵧ** beskriver fördelningslängden under sulan och **L_su** dess totala längd.
Måtten kan ändras oberoende; bᵧ ändrar inte den yttre lastresultanten.

Exempel: V = 200 kN/m och L_vägg = 0,6 m ger 120 kN yttre last oavsett bᵧ.
Med **Minst 1 m** blir den lokala yttre lasten 200 kN även om hela väggen är 5 m.
Brott- och brukmoment samt brottets horisontallaster omräknas med samma längdfaktor.
Sulans egentyngd beräknas från bₓ, bᵧ och t, med befintliga faktorer 1,5 i brott och 1,0 i bruk.
Resultatsammanfattningen visar total last och bärförmåga i kN, och areaskissen visar totala krafter och moment.
Trycket för isoleringen är total kraft / effektiv area. Den gemensamma väggsulemotorn och dess
rapport använder ekvivalenta laster per meter sula; dess modell och formfaktorer ändras inte.
Resultatdialogen visar **Lasteffekt q_Ed [kPa]** direkt ovanför **Bärförmåga q_bd**.
q_Ed är vertikallastresultanten i brott, inklusive sulans egentyngd, delad med
den effektiva kontaktarean `A_eff = b_x,eff × b_y,eff`. Samma värde visas i
den låsta resultat-HTML:en, även när isolering inte används.

Äldre projekt med angiven L_vägg får kryssrutan inställd efter längden och räknas om.
Projekt utan känd linjestödslängd och nya manuella sulor använder **Minst 1 m**
som standard; för glidning används alltid L_su vid linjelast. Avmarkera och ange
L_vägg eller importera lasteffekten på nytt för att använda en kort stödslängd.
Ett redan ifyllt L_su i ett äldre projekt bevaras vid första uppdateringen.

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
  sulans egentyngd**. Ange kN/m vid linjelast och kN vid total last, även när
  beräkningsmodellen är pelarsula. Linjelasten avser kontaktlast per meter sula. Ingen
  egentyngd eller lastfaktor tillkommer i glidningsberäkningen.
- **μ_d:** färdig dimensionerande friktionskoefficient mellan sulan och
  underlaget. Ingen ytterligare partialkoefficient tillkommer.
- **L_su:** väggsulans totala längd i m, separat från bᵧ och L_vägg.
  Det interna Python-fältnamnet `glid_L` behålls för kompatibilitet.
  Längdfältet visas vid linjelast, även med pelarsulemodell, innan en bidragsriktning
  har valts och även med isolering. L_su krävs för aktiva oisolerade linjelastbidrag.
  L_vägg och valet Minst 1 m påverkar inte glidmotståndet; de hör till den lokala
  lastomräkningen i brott och bruk. Importen fyller initialt båda längderna med
  linjestödslängden; en manuellt ändrad L_su bevaras vid senare lastimport.

Markera **Endast H-stabilitet** under **Geometri** om sulan endast ska ingå
i glidningskontrollen. Jordens bärighetskontroll och isoleringskontrollen
utförs då inte, och deras indata döljs i dialogen och inaktiveras i tabellen.
Sulan sätts automatiskt till **Utan isolering** och kategorin **Isolering**
döljs. Sparade material- och bärförmågevärden behålls; isolering kan aktiveras
igen efter att **Endast H-stabilitet** avmarkerats. Glidningsindata
visas även innan den globala kontrollen har aktiverats; bidragsriktningarna
väljs fortfarande manuellt. Vanliga sulor med isolering bidrar med 0 kN.
Sulmåtten bₓ/bᵧ och **Egen längd** döljs i dialogen och kan inte redigeras i
tabellen i detta läge. Tidigare mått behålls när läget växlas, men redovisas
inte på etiketten. **L_vägg** och den lokala kryssrutan **Minst 1 m** döljs
eftersom bärighet inte kontrolleras. Sulängden **L_su** under **Glidning**
är redigerbar vid linjelast och bestämmer det globala bidraget.
Etiketten och tabellens status visar **Endast H-stabilitet** i neutral blå färg
utan någon utnyttjandegrad för bärighet. Valet sparas, följer med kopierade
sulor och visas i PDF- och HTML-exporterna.

Motståndet för en vald riktning beräknas som
`H_Rd,i = V_Ed,EQU × L_su × μ_d` för linjelaster, oavsett beräkningsmodell, och
`H_Rd,i = V_Ed,EQU × μ_d` för total last. **Sulor med isolering bidrar alltid
med 0 kN**, oavsett tidigare glidningsindata. V och μ ska vara minst noll;
sulängden L_su ska vara större än noll. EQU ska redan innehålla
sulans egentyngd; varken bᵧ eller L_vägg multipliceras in.

Motstånden summeras för varje riktning över **vyns sulor**. Den flyttbara
resultatrutan visar H_Ed, H_Rd, `U = |H_Ed| / H_Rd` och antal sulor med positivt
bidrag. Grönt betyder U ≤ 100 %, rött U > 100 %. Saknade eller ogiltiga indata
hos en vald sula gör kontrollen **Ofullständig**; ett delmotstånd redovisas då
inte som ett komplett resultat. En tom horisontallast tolkas inte som noll.
Resultaten uppdateras direkt när indata ändras, utan en separat beräkningsknapp.

På etiketten visas **Glidmotstånd – globalt** med V_Ed,EQU och L_su till vänster
och valda Hₓ,Rd,i/Hᵧ,Rd,i till höger, i samma format för vanliga sulor och
**Endast H-stabilitet**. Blocket visas oberoende av den globala knappens läge.
Glidningsblocket döljs på isolerade sulor
och sulor som inte bidrar i någon riktning. Etikettens färg och översta U avser
fortfarande jordens/isoleringens kontroll, medan resultatrutans färger avser
den globala glidningen. Ändring av glidningsindata gör inte jordresultatet inaktuellt.
L_su visas endast i glidmotståndsblocket för oisolerade linjelastsulor med en vald
bidragsriktning. Den upprepas inte på den övre måttraden. Detta gäller också
PDF och resultat-HTML. L_vägg redovisas inte i glidmotståndsblocket.

Dra koordinatsymbolen för att flytta den. Klicka på den för att visa ramen
och dra hörnhandtaget för proportionell storleksändring. Piltangenter flyttar
symbolen; plus/minus ändrar storleken när hörnhandtaget har fokus. Dra
resultatrutans rubrik för att flytta rutan. Klicka på rutan och dra dess nedre
högra hörnhandtag för att förstora eller förminska hela rutan, inklusive texten.
Plus/minus fungerar också när hörnhandtaget har fokus. Symbol och ruta följer
ritningens zoom. Placeringar och storlekar hör till den aktuella vyn.

All glidningsindata samt placeringar och storlekar sparas med projektet. Äldre projekt
öppnas med glidningskontrollen avstängd. PDF-exporten innehåller fasta
överlagringar; HTML-exporten visar samma resultat och expanderbara indata,
utan möjlighet att ändra beräkningar.

Python kan också användas för att aktivera kontroller och läsa resultat:

```python
plan.glidning = {"enabled": True, "check_x": True, "H_x_Ed": 180}
plan.uppdatera(tagg_id, indata={
    "glid_x": True, "V_Ed_EQU": 120, "glid_mu": 0.4, "glid_L": 3.0, "L_vagg": 3.0,
})
plan.glidningsresultat["x"]  # H_Rd = 144 kN för denna väggsula
```

## Lastkonvention och resultat

Jordkontrollen anropar den befintliga beräkningsfunktionen med hävarmen satt
till noll. Därmed används de direkt angivna momenten utan bidrag från
horisontallast gånger hävarm. Isoleringen har en separat beräkning med samma
momentkonvention. De fristående beräkningsfunktionerna kan fortfarande
anropas med en hävarm.

- **Väggsula:** `lang=1`. Grundplan använder bᵧ (`l`) som beräkningsremsans
  referenslängd, med **1 m** som standardvärde. Krafter anges alltid i kN/m
  och moment i kNm/m. Under **Geometri** sitter den lilla kryssrutan **Minst 1 m**
  vid L_vägg. Markerad använder den lokala kontrollen 1 m; avmarkerad används
  angiven positiv L_vägg ≤ 1 m. Den yttre lastresultanten är `V × lokal L_vägg`.
  Vald bᵧ är fördelningslängden under sulan och ändrar inte denna resultant.
  Resultantlasterna normaliseras med bᵧ för den gemensamma väggsulemotorns API.
  Grundplans resultat redovisar då total last, egentyngd och bärförmåga.
  Excentriciteten är `e_y = e_y,plac + M_x / N` med samma lastgrund för
  moment och normalkraft; effektiv längd är `b_y − 2 × abs(e_y)`.
  Jordmodellens specialfaktorer för långsträckt fundament behålls.
  Linjestödslängden `L_vägg` och sulängden `L_su` är separata. Ange inte hela väggens totallast i ett linjelastfält.
- **Pelarsula:** `lang=0`. Med `lasttyp=0` anges krafter i kN och moment i kNm.
  Med `lasttyp=1` anges kN/m respektive kNm/m, och hela L_vägg används för
  omräkning till total last. Måtten `b` respektive `l` anges i m.
- Ange moment direkt vid sulan kring l- respektive b-axeln, både i brott
  och bruk. Excentriciteten beräknas från dessa moment och eventuell
  placeringsexcentricitet. Horisontallaster i brott behålls för deras
  påverkan på jordens bärighet, men ger inget extra moment.
- Fundamentets egentyngd läggs till enligt den befintliga modellen:
  `F_v = F_vy × lokal L_vägg + 1.5 * 25 * b * b_y * t` totalt för väggsulor,
  respektive `F_v = V_res + 1.5 * 25 * b * l * t` totalt för pelarsulemodellen.
- Jordens utnyttjandegrad definieras som `U = F_v / F_bd`. Väggsulemotorn använder
  ekvivalenta värden per meter. För väggsulor multipliceras både last och
  bärförmåga med bᵧ i Grundplans sammanfattning; kvoten är densamma.
  Motorns `F_bd` är `q_bd * b` respektive `q_bd * b * l`.
  Denna jordkontroll är oförändrad när isoleringskontrollen aktiveras.
- I den befintliga funktionens `details` står vissa lastposter i kN även
  för enmetersremsan. Planvyn visar total kraft för den lokala kontrollen.
  Jordens poster i `details` ändras inte; med isolering
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

Varje kombination använder sin egen vertikallast och sina egna moment.
Uttrycken ovan gäller pelarsulor. För väggsulor multipliceras yttre laster
och moment först med lokal L_vägg: 1 m med **Minst 1 m**, annars angiven kort
längd. `l_ref = b_y`, total `EG_k = 25 × b × b_y × t` och
`q_Ed = N_total / (b_eff × l_eff)`. Ett större bᵧ fördelar samma yttre resultant
över större area; egentyngden ändras med sulans geometri. Till exempel ger
200 kN/m över 0,6 m alltid 120 kN yttre last, oavsett bᵧ.
I den gemensamma motorns rapport används ekvivalenta värden per meter.
Egentyngdsfaktorn 1,5 i brott följer
den befintliga jordmodellen; i bruk används 1,0. Ingen lastkombination
genereras från karakteristiska laster. Effektiva mått, total last och
bärförmågor måste vara positiva; annars visas ett fel utan aktuell utnyttjandegrad.

Valet **Minst 1 m** sparas med sulan och stöds i tabellen, flerredigering och
resultat-HTML. Äldre projekt med angiven L_vägg får valet automatiskt utifrån
längden vid öppning; tidigare långväggars lokala kontroll rättas till 1 m.
Saknad L_vägg använder Minst 1 m som standard. Glidningen använder alltid
L_su vid linjelast, oberoende av L_vägg och den lokala längdfaktorn.
Glidningsblocket visar L_su; L_vägg hör till den lokala brott-/brukberäkningen.

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

Projekt sparas i formatversion 18. Äldre projekt i formatversion 1–17 kan
öppnas och beräknas också automatiskt; färggruppering är avstängd om den saknas.
Deras angivna
momentvärden bevaras; tidigare hävarmar och horisontallaster i bruk tas bort
utan att räknas om till moment. Dessa borttagna fält ignoreras även om de
skickas som `indata` från Python. Projekt i formatversion 1 får isoleringen
avstängd.

En ritning får vara högst 40 MB och ett projekt högst 60 MB med upp till
1 000 taggar. Visningsbilden begränsas till 2 800 pixlar längs längsta sidan
för minnesanvändningens skull; originalfilen bevaras i projektet.

**Importera/Uppdatera ritning** väljer en ny PDF eller bild även när sulor
redan finns. Sulor, indata, resultat, rubriker och placeringar behålls;
etiketter och glidningssymboler ligger kvar på samma relativa bildkoordinater.
Kontrollera placeringen om den nya ritningens utsnitt eller marginaler ändrats.
Mätverktygets kalibrering återställs och behöver anges på nytt. Den tidigare
PDF-sidan används om den finns i den nya filen, annars sida 1. En ogiltig fil
lämnar projektet orört. Den nya ritningen följer med sparning och export.
Från Python: `plan.importera_ritning("grundplan_rev_B.pdf")`.

## Exportera ritning med etiketter som PDF

Tryck **Exportera PDF** för att ladda ned vyns ritningssida med sulornas
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

Etiketter, widgetar, symboler och placerade texter använder samma HTML/CSS,
typsnitt, radbrytningar och proportioner som interfacet. Även de mjuka skuggorna
består av vektorer. Typsnitten bäddas in och texten är sökbar. Originalritningen
läggs aldrig in som en skärmbild när källan är en PDF. Draghandtag,
markeringsramar och redigeringskontroller ingår inte.

PDF-export kräver `reportlab`, `pypdf` och `playwright`, som ingår i
`an-calcs[notebook]`, samt en lokal Chromium, Google Chrome eller Microsoft Edge.
Webbläsaren körs isolerat utan nätverksåtkomst eller användarprofil. Om Chrome
eller Edge redan finns installerad behövs ingen separat webbläsarinstallation.
Annars kör du i samma Pythonmiljö som din notebook:

```sh
python -m playwright install chromium
```

Uppdatera med installationskommandot ovan om du har en äldre installation.
Resultat-HTML innehåller den färdiga vektor-PDF:en; dess PDF-knapp kräver ingen
webbläsarrenderare, Python eller nätverksanslutning hos mottagaren.

## Mäta avstånd på ritningen

1. Tryck **Mät** och klicka på start- och slutpunkten för ett känt referensmått.
2. Ange det verkliga avståndet i meter och tryck **Spara kalibrering**. Både
   decimalpunkt och decimalkomma fungerar.
3. Klicka på två nya punkter. Avståndet visas vid mätlinjen och ovanför ritningen
   i meter med en decimal. Ett tredje klick påbörjar nästa mätning.

Mätningen följer ritningen vid zoom och panorering. Dra med vänster eller
höger musknapp för att panorera; **Shift + scroll** zoomar även under mätning.
**Rensa mått** tar bort den aktuella mätlinjen. **Kalibrera om** väljer ett
nytt referensmått och Escape avslutar verktyget utan att radera kalibreringen.
Under mätning används vanliga klick på ritningen och etiketterna som mätpunkter.

Kalibreringen hör till vyns ritningssida och sparas med **Spara projekt**.
Den återställs vid öppning av projektet och följer med HTML-exporten.
En ny ritning behöver kalibreras på nytt. Mätlinjerna är tillfälliga och ingår
inte i PDF-exporten. Kalibreringen förutsätter en ritning med samma skala i
båda riktningarna.

## Exportera en interaktiv resultatvy som HTML

Tryck **Exportera HTML** för att ladda ned en enda fil med ritningen och
öppningsbara etiketter. Filen får originalritningens namn med tillägget
`_resultat.html`. Du kan också exportera från Python:

```python
plan.exportera_html("grundplan_resultat.html")
```

Öppna filen i en vanlig webbläsare. Den fungerar utan Jupyter, Python eller
internet; ritningsbilder, indata, resultat och gränssnitt finns i filen.
Endast vyns valda PDF-sida följer med. Ritningsbilden har samma
upplösning som i Jupyter-vyn (högst 2 800 pixlar längs längsta sidan).

**Exportera PDF** i HTML-vyn laddar ned ritningen med fasta etiketter och
eventuell glidningslegend. PDF-filen bäddas in när HTML-filen skapas och har
samma innehåll som PDF-export från Jupyter, inklusive originalets vektorgrafik
när ritningen är en PDF. Knappen fungerar även utan internet. Zoom, markeringar,
öppna dialoger och tillfälliga mätlinjer ändrar inte PDF-innehållet.

Klicka på en etikett för resultat och utfällbara indatakategorier. **Minimera**
stänger dialogen, och samma avsnitt är utfällda när etiketten öppnas igen.
Dra i ritningen med vänster eller höger musknapp för att panorera,
använd **Shift + scroll** eller +/− för zoom och **Anpassa** för
att återställa vyn. Etiketterna använder storleken från exporten och följer
ritningens zoom; HTML-filen har inget reglage för etikettstorlek.
Visningsval gäller medan filen är öppen och ändrar inte det sparade projektet.
**Mät** fungerar också i HTML-vyn. En eventuell omkalibrering där gäller bara
den öppna vyn och skriver inte om HTML-filen eller det sparade projektet.

Tabellen **Sulor – indata och resultat** följer med under ritningen. Alla
indata och statusvärden visas som låst text. Shift + klick på etiketter eller
Shift + vänsterdrag framhäver motsvarande tabellrader. Ett nytt Shift + klick
växlar markeringen; ett nytt urvalsdrag växlar etiketter inom rutan.
Tabellens kryssrutor, inklusive Shift + klick för radintervall, markerar även
motsvarande etiketter. Klicka på valfri kolumnrubrik för att sortera och på huvudkategorier för att fälla ihop eller visa kolumner. **Avmarkera** eller Escape rensar urvalet. Markering används endast
för att framhäva sulor och påverkar inga beräkningsvärden.

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
för att växla dess markering. Ett vanligt klick på en etikett öppnar alltid
objektets redigering, även efter ett urval. Markerade etiketter
får en ram och en bock. Tryck **Ändra markerade** för gemensam indata.

Vanligt vänsterdrag eller högerdrag panorerar även med ett aktivt urval.
Det ändrar inga etikettpositioner. Tryck **Avmarkera** för att börja ett nytt urval.
Dra direkt i en etikett utan Shift för att flytta den, även när ett urval är aktivt.

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
ogiltiga eller ändrade indata, projektets återöppning och separata vyer för PDF-sidor.
Isoleringstesterna omfattar olika effektiva areor i brott/bruk, egentyngd,
styrande kontroll, saknade värden och import av äldre projekt.
Interaktionerna kan testas med `node tests/test_grundplan_ui.mjs`.
