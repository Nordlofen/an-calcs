# an-calcs

Berakningsrepo for materialuppdelade ingenjorsfunktioner.

## Kontrakt

En berakningsfunktion i `an_calcs` ska vara oberoende av notebook- och
presentationskod. Grundkontraktet ar:

```python
details = funktion(px)
```

- `px` ar funktionens indata i dokumenterad ordning.
- returvardet ar en standardiserad `details`-dictionary.
- `details` ska kunna lasas av `an_print.CalcBlock`.

`details` innehaller normalt sektionerna:

- `metodbeskrivning`
- `indata`
- `delresultat`
- `slutresultat`
- `ekvationer`

Sektionerna `indata`, `delresultat` och `slutresultat` innehaller `items` med
poster enligt:

```python
{
    "namn": "...",
    "latex": "...",
    "value": ...,
    "unit": "...",
    "etikett": "...",
}
```

## Panel-schema

En berakningsfunktion kan dessutom ha ett frivilligt `panel_schema`-attribut.
Detta ar inte krav for att funktionen ska vara giltig, men gor funktionen
kompatibel med `an_print.Panel`.

`panel_schema` ska vara ren Python-data och far inte importera `ipywidgets`
eller annan UI-kod.

Minsta struktur:

```python
funktion.panel_schema = {
    "title": "Visningsnamn",
    "px": ["a", "b", "lasttyp"],
    "fields": [
        {"name": "a", "type": "float", "label": "A", "unit": "m", "default": 1.0},
        {"name": "b", "type": "float", "label": "B", "unit": "m", "default": 2.0},
        {
            "name": "lasttyp",
            "type": "choice",
            "label": "Lasttyp",
            "default": "PS",
            "options": [
                {"label": "Punktlast", "value": "PS"},
                {"label": "Linjelast", "value": "VS"},
            ],
        },
    ],
}
```

Stodda falttyper ar:

- `float`
- `int`
- `text`
- `bool`
- `choice`
- `table`

For `table` kan en tabell bygga flera parallella listor till `px`, till exempel
`dz_lista`, `Ek_lista` och `gamma_m_lista`.

For funktioner med flera befintliga `px`-format kan `panel_schema["px"]`
beskriva ett separat panelvanligt superset-format, sa lange funktionen sjalv
kan tolka detta format och fortfarande returnerar `details` enligt
grundkontraktet.

Foreslagen projektstruktur:

- `src/an_calcs/tra` for tra
- `src/an_calcs/stal` for stal
- `src/an_calcs/betong` for betong
- `src/an_calcs/geo` for geoteknik
- `src/an_calcs/common` for gemensamma hjalpmoduler
- `tests/` for tester
- `notebooks/` for exempel och utvecklingsnotebooks
- `docs/` for dokumentation

## Interaktiv grundplan i JupyterLab

`Grundplan` visar en PDF eller bild med klickbara taggar för väggsulor och
pelarsulor. Varje tagg har egna indata och använder
`an_calcs.geo.allmanna_barighetsekvationen` i Python-kerneln.

**Importera/Uppdatera lasteffekt** läser stödens Brott-, Bruk- och EQU-laster
från JSON. Befintliga littera får uppdaterade laster och vägglängd; nya sulor
placeras med ett klick per stöd. Anpassa övriga indata före beräkning.
**Radera samtliga sulor** rensar sulorna i vyn efter bekräftelse.
En redigerbar tabell längst ned visar alla sulors indata och delar markering
med ritningen. Ändra en cell på en markerad rad för att ge alla markerade
sulor samma värde i kolumnen. Resultaten uppdateras automatiskt vid varje
ändring; eventuella fel visas per sula.
Se [importformat och arbetsgång](docs/grundplan.md#importera-lasteffekter).

Installera från GitHub i samma Pythonmiljö som notebookens kernel.
Kör följande i terminalen, från mappen där din `.venv` finns:

```sh
source .venv/bin/activate
uv pip install --upgrade --refresh "an-calcs[notebook] @ git+https://github.com/Nordlofen/an-calcs.git"
```

Starta om notebookens kernel efter uppdatering. För lokal utveckling kan du
i stället köra `uv pip install -e ".[notebook]"` från repositoryts rot
med rätt virtuella miljö aktiverad.

```python
from an_calcs.notebook import Grundplan

plan = Grundplan()  # Välj PDF/bild och ange projektfil/key när du sparar.
plan
```

**Importera/Uppdatera ritning** ersätter PDF/bild även när sulor redan finns.
Indata, resultat och relativa placeringar behålls. Kalibrera mätverktyget på
nytt efter uppdatering; den nya ritningen sparas och följer med exporterna.

Eller ange sökväg och PDF-sida direkt:

```python
plan = Grundplan("grundplan.pdf", key="Hus A", sida=1, titel="Grundläggning")
plan
```

Välj **+ Väggsula** eller **+ Pelarsula** och klicka på ritningen. Ange
littera och indata och tryck **Minimera**. Klicka på taggen för att ändra
värden. Sulan beräknas automatiskt vid placering och när indata ändras.
Indata är grupperade i utfällbara avsnitt. Dra dialogens rubrik för att
flytta den; dra i ritningen för att panorera och använd **Shift + scroll**
eller zoomknapparna för att förstora. Shift + scroll zoomar kring muspekaren.
Shift + vänsterdrag ritar en urvalsruta för flerredigering. Shift + drag
eller Shift + klick lägger till omarkerade etiketter och avmarkerar markerade.
Varje Grundplan gäller en enda ritningssida. Öppna en annan PDF-sida i en ny
cell med egen `key` och exempelvis `sida=2`. Sparade projekt och exporter
hör till den valda sidan. Klicka på **Littera** eller **Status / U** i tabellen
för att sortera; ett nytt klick vänder ordningen.
Sulverktyget avslutas efter en placering;
klicka på den valda sulknappen igen eller tryck Escape för att avbryta.

**Mät** kalibreras genom två klick på ett känt mått och inmatning av avståndet
i meter. Därefter visar två klick en längd med en decimal, även efter zoom
och panorering. Kalibreringen följer med när projektet sparas och exporteras
till HTML. HTML-vyn har också **Exportera PDF** för att ladda ned ritningen
med etiketterna från exporttillfället, utan Jupyter eller internet.

Indata innehåller **Laster – Brott**, **Laster – Bruk** och **Isolering**.
Moment anges direkt vid sulan; inget momentbidrag från horisontallast
gånger hävarm läggs till. Horisontallaster i brott påverkar fortfarande
jordens bärighet.

bᵧ kan ändras även för väggsulor, i dialogen, tabellen och för flera markerade
sulor. Den lilla kryssrutan **Egen längd** låser upp måttet; avmarkerad
visar den ett grått, låst 1 m-fält. Laster anges fortfarande per meter vägg och
linjestödslängden **L_vägg** och sulängden **L_su** är separata. Importens
`length` fyller båda initialt; därefter behålls manuellt ändrad L_su vid uppdatering.
Den lilla kryssrutan **Minst 1 m** ställs in automatiskt vid import: aktiverad
för L_vägg ≥ 1 m, annars avmarkerad med kort stödslängd som redigerbart värde.
Lokal bärighets-/isoleringskontroll använder `V × 1 m` respektive `V × kort L_vägg`.
bᵧ ändrar kontaktarean utan att ändra den yttre lastresultanten. Hela L_vägg
behålls för total EQU-last och glidning. Se [lastkonventionen](docs/grundplan.md#lastkonvention-och-resultat). Det valda måttet används i skissen för effektiv area
och sparas med projektet. Tidigare sparade egna mått får kryssrutan aktiverad;
projekt från tiden före bᵧ-redigeringen behåller sin remslängd på 1 m.

Aktivera **Underliggande isolering** för att ange `f_d.brott` och `f_d.bruk`
i kPa samt separata långtidslaster. Isoleringens tryck beräknas som
`V / (bₓ,eff × bᵧ,eff)` för pelarsulor och
`V_total / (bₓ,eff × bᵧ,eff)` för väggsulor, för respektive
lastkombination. Resultatet visar
jordkontrollen och båda isoleringskontrollerna. Etiketten visar littera,
isoleringssymbol och **Med/utan isolering** på första raden. Andra raden
visar högsta utnyttjandegrad och bₓ, eller bₓ × bᵧ för pelarsulor och
väggsulor med ändrat bᵧ.
För isolerade sulor visas även en tredje rad med styrande kontroll.
Kontrollen visas också i dialogen och hovringstexten. Utseendet följer med
i HTML- och PDF-exporten. Se lastantagandena i
[användningsbeskrivningen](docs/grundplan.md#isolering-under-sulan).

Etiketten visar också ifyllda yttre laster som inte är noll, grupperade i
**Brott** och **Bruk** (med isolering). Vertikallast betecknas **V**.
**Visa definitionsskiss** förklarar sulans lokala x/y-axlar och anpassas till
väggsula eller pelarsula. Resultatets **Effektiv area – planvy** visar
lastresultanten, momentens bidrag till excentriciteten och den effektiva
rektangeln. Med isolering kan du växla mellan brott och bruk. Skisserna
följer med HTML-exporten. Befintliga momenttecken och beräkningar bevaras.

**Glidningskontroll** aktiverar separata globala kontroller i X-led och Y-led.
Välj riktningarna och ange motsvarande horisontallast i EQU. Under **Glidning**
i varje sulas dialog väljer du motståndsriktning och anger vertikallast i EQU
(inklusive egentyngd), dimensionerande friktionskoefficient och, för väggsulor,
hela väggsulans längd. Isolerade sulor bidrar alltid med noll.

**Färggruppering** färgar etiketternas bakgrund efter tjocklek, bₓ, bᵧ eller
vertikallast i Brott/Bruk/EQU. **Isolering** skiljer med isolering (inget bidrag)
från utan isolering med inget glidbidrag, bidrag i X_g, Y_g eller båda riktningarna.
Grupperna följer valda bidragsriktningar under **Glidning**.
Mått grupperas per unikt värde och laster med
egna intervall, separat för pelarsulor (kN) och väggsulor (kN/m). Klicka på
en färgruta för att välja färg. **Visa legend** visar en flyttbar och skalbar
färglegend. Prick och kant behåller kontrollstatusen. Senaste inställningen
återkommer efter av/på och sparas med projektet, inklusive legendens läge
och storlek. Färger och legend följer med PDF- och HTML-exporten. Sulor med
Endast H-stabilitet ingår inte när t, bₓ eller bᵧ finns bland valda kategorier.

**Lägg till kommentarer** visar en flyttbar och skalbar sammanställning med
littera och kommentar för endast sulor med ifylld kommentar. Rutan uppdateras
automatiskt, sparas med projektet och följer med PDF och resultat-HTML.

**Endast H-stabilitet** under **Geometri** undantar en sula från jordens
bärighetskontroll och isoleringskontrollen och sätter den till **Utan isolering**.
Kategorin **Isolering** döljs. Sulan bidrar fortfarande i sina
valda glidningsriktningar. Valet kan även ändras för markerade rader i tabellen;
övriga indatavärden behålls när läget växlas.
Sulmåtten bₓ/bᵧ döljs i detta läge; linjestödslängden L_vägg anges under Geometri och sulängden L_su anges fortfarande
under **Glidning**.

Koordinatsymbolen kan dras och förstoras med hörnhandtaget. Dra resultatrutans
rubrik för att flytta den och dra dess hörnhandtag för att ändra storlek på
hela rutan inklusive texten. Rutan visar last, summerat motstånd, utnyttjandegrad
och antal bidragande sulor i vyn. Etiketterna visar respektive
bidrag i två kompakta kolumner. Inställningar, placeringar och storlekar sparas med
projektet och visas i PDF- och HTML-exporterna. Se
[glidningsmodell och lastantaganden](docs/grundplan.md#global-glidningskontroll).

Dra en etikett för att flytta den. **Kopiera sula** i indatadialogen tar med
alla indata till en ny sula som placeras med ett klick på ritningen. Kopian
får eget littera och kan ändras oberoende av originalet. Reglaget
**Etikettstorlek** justerar etiketternas grundstorlek. Etiketterna förstoras
och förminskas tillsammans med ritningen när du zoomar. Positioner och
grundstorlek sparas i projektet.

**Shift + vänsterdrag** eller **Shift + klick** väljer ett urval av etiketter.
Ett vanligt klick på en etikett öppnar alltid objektets redigering.
**Ändra markerade** öppnar gemensamma indata: välj endast de fält som ska
ersättas, exempelvis isolering, väggbredd eller pelarsulornas bₓ/bᵧ.
Övriga värden behålls per sula. **Tillämpa** räknar automatiskt om urvalet
och redovisar eventuella fel per sula. Lastfält kräver samma sultyp i urvalet.
Se [gemensam redigering](docs/grundplan.md#ändra-flera-sulor-samtidigt).

**Spara projekt** öppnar en ruta med obligatoriska fält för **Projekt**
och **Fall (key)**. Välj en befintlig sparfil/key eller ange en ny, exempelvis
`26017 - Norrbodahöjden`. Filändelsen `.json` läggs till om den saknas.
Relativa sökvägar avser kernelns arbetsmapp.
**Kopiera projekt + key** kopierar argumenten att klistra in i notebookcellen:

```python
plan = Grundplan(state_file="hus_a.grundplan_state.json", key="Hus A")
plan
```

Nästa körning läser automatiskt in projektet, även efter kernelomstart.
Ritningen ingår; originalfilen behöver inte finnas kvar. Spara före omstart:
ändringar sparas först när du trycker Spara. Från Python används `plan.spara()`
när en sparplats är vald. Filen visas i `plan.state_file`.

**Exportera JSON** laddar ned en portabel kopia. **Öppna projekt** läser en
sådan kopia, som därefter kan sparas under den aktuella nyckeln.
En sparad notebook ersätter inte projektfilen. Portabla kopior från Python:

```python
plan.spara("grundplan.json")
plan = Grundplan.oppna("grundplan.json")
plan
```

**Exportera PDF** laddar ned vyns ritningssida med fasta etiketter.
Etiketternas positioner, storlek och aktuella status följer med. PDF-originalets
sidformat och vektorinnehåll bevaras. Exporten kan även göras från Python:

```python
plan.exportera_pdf("grundplan_med_etiketter.pdf")
```

**Exportera HTML** ger en fristående resultatvy med zoom, panorering och
klickbara etiketter. Indata och resultat visas i utfällbara avsnitt;
tabellen följer också med som en låst och sorterbar vy. Markera flera etiketter
med Shift + klick/drag för att framhäva deras tabellrader. Beräkningsvärdena
kan inte ändras. Den valda ritningssidan bäddas in, så filen
kan öppnas utan internet eller Jupyter:

```python
plan.exportera_html("grundplan_resultat.html")
```

Se [exempelnotebooken](notebooks/Sulgrundlaggning.ipynb) och
[användning, lastkonventioner och begränsningar](docs/grundplan.md).

Notebookvyn ligger separat i `an_calcs.notebook`. Tilläggsbiblioteken
importeras inte när vanliga beräkningsfunktioner används. Detta är
Jupyterversionen; export till en fristående beräkningsbar HTML-fil ingår
ännu inte.

## Böjstyvhet - Betongpålar

`an_calcs.betong.bojstyvhet_betongpalar` beräknar modifierad nominell böjstyvhet för en
kvadratisk betongpåle med fyra likadana huvudarmeringsjärn i hörnen.
Koefficienterna och summan av betongens och armeringens bidrag utgår från
avsnitt 5.6 i [underlaget, sida 11](https://kth.diva-portal.org/smash/get/diva2%3A1597682/FULLTEXT01.pdf).
Tryckzonen bestäms med modellen i det kompletterande bildunderlaget,
figur B7.14 (transformerat tröghetsmoment på sida B236). Betongens och
armeringens tröghetsmoment beräknas sedan separat kring den gemensamma
transformerade tyngdpunkten `x_tp`. `K_c` används som ytterligare reduktion.
`K_c` och `K_s` kan även ersättas var för sig med manuella värden.

Användning i notebook med Panel:

```python
from an_calcs.betong import bojstyvhet_betongpalar
from an_print import Panel

panel = Panel(bojstyvhet_betongpalar)
panel
```

Materialvärdena och det effektiva kryptalet anges direkt i Panel.
Startvärdena är ett beräkningsexempel och ska anpassas till aktuellt fall.
Antalet huvudarmeringsjärn är alltid fyra och behöver inte matas in.
I standardläget beräknas `K_c = k_1*k_2/(1+phi_eff)` och `K_s = 1`.
Markera **Ange Kc manuellt** eller **Ange Ks manuellt** i Panel för att visa
respektive värdefält. Ett manuellt värde ersätter faktorn direkt i `EI`.
Tillåtna värden är ändliga tal från noll och uppåt, utan övre gräns.
Avmarkera valet för att återgå till automatläget; ett dolt manuellt värde ignoreras.

| Ordning i `px` | Storhet | Enhet |
| --- | --- | --- |
| 1 | `b` – pålsida | mm |
| 2 | `c_nom` – täckskikt till bygelns utsida | mm |
| 3 | `phi_b` – bygeldiameter | mm |
| 4 | `phi_h` – huvudarmeringsdiameter | mm |
| 5 | `l_0` – knäckningslängd | m |
| 6 | `N_d` – dimensionerande normalkraft, positiv i tryck | kN |
| 7 | `f_ck` – karakteristisk cylindertryckhållfasthet | MPa |
| 8 | `f_cd` – dimensionerande betongtryckhållfasthet | MPa |
| 9 | `E_cd` – dimensionerande elasticitetsmodul för betong | MPa |
| 10 | `E_s` – elasticitetsmodul för armering | MPa |
| 11 | `phi_eff` – effektivt kryptal | – |
| 12 | `M` – böjande moment kring hela pålens geometriska mittaxel | kN·m |

`M` ska avse samma lastkombination som `N_d`. Positiva och negativa moment
ger samma styvhet för det symmetriska tvärsnittet; koordinaterna räknas från
mest tryckt kant. I Panel visas momentfältet intill normalkraften.
Äldre direkta anrop med elva värden behöver kompletteras med `M` sist i `px`.
Anrop med tolv värden fortsätter att använda automatläget. För manuella faktorer
läggs fyra värden till (Panel använder alltid detta utökade format):

| Ordning i `px` | Storhet | Typ |
| --- | --- | --- |
| 13 | `K_c_override` – aktivera manuellt Kc | `True`/`False` |
| 14 | `K_c_manuell` – manuell betongfaktor | tal ≥ 0 |
| 15 | `K_s_override` – aktivera manuellt Ks | `True`/`False` |
| 16 | `K_s_manuell` – manuell armeringsfaktor | tal ≥ 0 |

Direkt anrop och redovisning med CalcBlock:

```python
from an_calcs.betong import bojstyvhet_betongpalar
from an_print import CalcBlock

px = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2, 30]
details = bojstyvhet_betongpalar(px)
cb = CalcBlock(details)
cb.SR(visa=True, etikett=True)
```

Exempel på manuella faktorer:

```python
# Ersätt Kc med 0.25 och Ks med 0.75.
details = bojstyvhet_betongpalar(px + [True, 0.25, True, 0.75])
# Ersätt endast Ks; det inaktiva värdet för Kc ignoreras.
details = bojstyvhet_betongpalar(px + [False, None, True, 0.75])
```

Exemplet med automatiska faktorer ger `x = 184,300 mm`, `x_tp = 100,278 mm`, `EI_c = 66,615`,
`EI_s = 3242,440` och totalt `EI = 3309,056 kN·m²`.
Slutresultatet innehåller styvhetsbidragen och tryckzonens höjd `x` i mm.
På samma rad anges `reducerad (x < b)` eller `oreducerad (x = b)` i etiketten
efter `tryckzonens höjd`. Visa etiketter för SR för att se kommentaren.
Tryckzon, transformerade snittkonstanter, tröghetsmoment, enhetsomvandlingar, koefficienter och
använda ekvationer redovisas i samma `details`-struktur via Panel eller CalcBlock.
Aktiva manuella faktorer visas under Indata. Delresultat visar både grundmodellens
`K_c_auto`/`K_s_auto` och de använda `K_c`/`K_s`. Metodbeskrivningen och ekvationerna
anger om respektive faktor är automatisk eller manuellt vald.
Delresultat visar även `sigma_min_b` i MPa, märkt `sigma_min(x=b)`:
minsta kantspänning beräknad med hela tvärsnittets transformerade snittkonstanter
före eventuell reduktion av tryckzonen. Positivt värde betyder tryck och negativt
värde drag. Värdet sparas före iterationen även när slutligt `x` blir mindre än `b`.

Tryckzonsberäkningen använder linjärelastiska material, dragfri betong och
modulkvoten `alpha = E_s/E_cd`. Två järn finns i vardera armeringsraden.
Vid lösning av `x` behandlas järnen som koncentrerade areor, enligt bilden.
Armering inne i tryckzonen får faktorn `alpha-1` och armering utanför den får
faktorn `alpha`. Därmed hanteras även fall där båda raderna är tryckta eller dragna.
Momentet flyttas till `x_tp` och tryckzonens höjd bestäms genom bisektion:

```text
M_tp = abs(M)*10^6 + N_d*1000*(x_tp - b/2)
N_d*1000/A_II - M_tp/I_II*(x - x_tp) = 0
```

Det transformerade `I_II` används endast för tryckzonsberäkningen.
De slutliga tröghetsmomenten beräknas enligt:

```text
I_c = b*x^3/12 + b*x*(x/2 - x_tp)^2
I_s = 4*I_phi + (A_s/2)*((d' - x_tp)^2 + (d - x_tp)^2)
EI  = (K_c*E_cd*I_c + K_s*E_s*I_s)/10^9  [kN·m²]
```

Slutligt `I_c` beräknas utan armeringsavdrag och slutligt `I_s` inkluderar
järnens egna tröghetsmoment. Förskjutningen av beräkningsaxeln kan öka
armeringens bidrag; lägre betongbidrag innebär därför inte nödvändigtvis
lägre total styvhet. Automatiskt `K_c` använder effektivt kryptal som tidigare.
Manuellt `K_c` ersätter hela denna faktor, utan ytterligare krypreduktion eller
begränsning. Tryckzonslösningen påverkas varken av kryptalet eller K-faktorerna.
Detta är en modifierad modell,
inte den oförändrade nominella Eurokodmetoden.

`A_c`, armeringsinnehållet och slankheten baseras fortsatt på hela pålen.
Metoden kräver `A_s/A_c >= 0,002` även vid manuella faktorer.
`k_2` begränsas till högst `0,20` vid beräkning av grundmodellens `K_c_auto`.
Vid helt tryckt tvärsnitt används hela höjden `x=b` och `x_tp=b/2`.
Här betecknar `x` verksam betonghöjd, inte neutralaxelns läge utanför snittet.
`N_d = 0` tillåts: vid ren böjning löses tryckzonen utan division med normalkraft,
men automatiskt `K_c=0` ger endast armeringens slutliga styvhetsbidrag.
Ett manuellt `K_c` används även i detta fall.
Vid `N_d=M=0` används hela betonghöjden som beräkningskonvention.
Funktionen beräknar varken andra ordningens moment eller betongens sprickmoment.
Ogiltiga indata, överlappande järn och för lågt armeringsinnehåll ger `ValueError`,
som Panel visar vid beräkning.
