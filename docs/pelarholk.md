# Pelarholk

## Modell och indata

Kraftmodell: SS-EN 1992-1-1:2005 (Sv), 10.9.6.3, figur 10.7b, släta fogytor.
Modellen kräver `l >= 1.2 h`, `0 <= mu <= 0.3` och icke-negativa kontaktkrafter.
Standardens högra delfigur är märkt (a) i användarens utgåva men hänvisas till
som (b) i texten. Originalbilden bevaras oförändrad.

Dictionary rekommenderas. Listformat följer `Pelarholk.panel_schema["px"]`:

`typ, fristaende, M, Fv, Fh, h, l, D, t_ig, bh, c_nom, phi, f_yd, mu, t_ig_b`.

| Indata | Definition / enhet |
|---|---|
| `typ` | `pelare` eller `vagg` (direktanropets förval: pelare) |
| `fristaende` | Bool, förval True. Styr böjarmering och val av tvärkraft |
| `M`, `Fv`, `Fh` | Dimensionerande laster vid holkens överkant; medurs, nedåt respektive åt höger positivt |
| `h`, `l` | Pelarmått/väggtjocklek i snittet och insticksdjup, mm |
| `D` | Verksamt kontaktdjup ut ur snittet, mm. Vägg låser D=1000 även i direktanrop |
| `t_ig` | Igjutningstjocklek vid sidorna, mm |
| `t_ig_b` | Igjutningstjocklek under pelarfoten, mm, > 0. Förval 20 mm |
| `b1` (även `bh`) | Från elementets högra yta till fundamentets högra ytterkant, inklusive igjutning, mm |
| `c_nom`, `phi` | Täckskikt till aktuell dragstångs utsida och dragstångens diameter, mm |
| `f_yd` | Dimensionerande sträckgräns, MPa |
| `mu` | Friktionskoefficient, förval 0.3 |

Stålets dimensionerande sträckgräns anges direkt. Äldre dictionary-indata och
de äldre 14- och 16-värdesformaten accepteras. `f_cd_ig`/`f_cd_c` från
16-värdesformatet ignoreras och visas inte. Äldre sparade materialvärden bevaras vid sparande.
Sidindex 1 avser höger och 2 vänster. Dictionary-formatet accepterar både
`b1`/`b2` och de äldre `bh`/`bv`; motstridiga värden för samma sida avvisas.
Panelens lagrade fältnycklar och motsvarande positionsfält är fortsatt `bh`/`bv`
så att befintliga fall återläses utan förlust. Synliga symboler är b₁ och b₂.
Saknat `t_ig_b` i äldre anrop eller sparade fall får förvalet 20 mm; ange
bottenigjutningens faktiska tjocklek för aktuellt fall.
Panelens startvärden är exempel, inte en verifierad dimensionering.
Pelare använder kN, kNm och mm². Vägg använder kN/m, kNm/m och mm²/m, med
en meterstrimla. Lägesbyte behåller lastvärdena, användaren anpassar dem.

`b2` (även `bv`), `H` och `t_p` är enbart panelens skissmått och ingår inte i listformatet.
De får förekomma i dictionary men ignoreras av beräkningen. `B=b2+h+b1` visas
som härlett totalmått. `b1` används i böjberäkningen endast vid fristående holk.
Skissen reagerar direkt på fältändringar och återlästa fall. Samma skala används
i x/y; enbart igjutningens synliga tjocklek förstärks. Bottenigjutningen styrs
separat av `t_ig_b`. Lastavståndet `a_v_2` och bottenmåttet måttsätts
i en separat principfigur för vänstra holkväggen.
Geometrin förutsätter `H > l + t_ig_b` för betong under igjutningen. Plattans längd och
pelarens visade höjd ovan holken är avbrutna, schematiska fortsättningar.
Fel i rena skissmått ger ett meddelande vid skissen, inte ett beräkningsstopp.

## Beräkningsgång

Ekvationsredovisningen använder korta vänsterled för jämvikten (summor av
krafter och moment) och en storhet per rad. Formlerna visas utan
enhetsomräkningsfaktorer och förutsätter konsekventa enheter; den numeriska
beräkningen behåller omräkningarna enligt nedan. Endast
enhetsförklaringen ligger som separat not under ekvationerna. Insticksdjup
redovisas som en kompakt kontroll i resultatet. Hjälptexten under `l` blir
röd direkt om `l < 1,2h`, även när `h` ändras eller ett sparat fall återläses.
Vid otillräckligt insticksdjup visas endast indata och kontrollen **Ej uppfyllt**,
utan kraft-, tryck- eller armeringsresultat. Detta kräver an-print med stöd
för `ekvationer["notes"]`.

1. Validera aktiva indata och modellgränser. Böjarmeringsindata behöver inte
   anges vid plattansluten holk och inaktiva värden valideras inte.
2. Lös de tre jämviktsekvationerna (mm, kN, kNm; per meter för vägg):

   ```text
   F1 - F2 - mu F3 = Fh
   mu F1 - mu F2 + F3 = Fv
   (0.9 l + mu h/2) F1 + (mu h/2 - 0.1 l) F2 = 1000 M + Fh l
   ```

   F3 angriper centriskt under elementet. Negativ kontaktkraft betyder att
   detta kraftspel inte är giltigt; funktionen avvisar fallet utan klippning.
3. Projektets kontaktmodell har triangulära tryckzoner `a_c=0.3l` med
   maxtryck vid överkant för F1 och underkant för F2. Tryckspridning genom
   igjutningen ges av `delta_a=t_ig/tan(26.6°)`, vinkel mot vertikalen,
   och `a_c_spr=a_c+delta_a`. D är konstant genom igjutningen.

   ```text
   sigma_ig,i,max = 2000 Fi / (D a_c)
   sigma_c,i,max  = 2000 Fi / (D a_c_spr), i=1,2
   ```

   Spänningar redovisas i MPa, utan utnyttjandegrader eller hållfasthetsjämförelse.
   De antagna tryckzonerna och spridningsvinkeln är projektets modell,
   baserad på handberäkningen, och inte tryckformler föreskrivna i 10.9.6.3.
   Tillgänglig betonggeometri för spridningen förutsätts verifierad separat.
   Under pelarfoten visas endast medeltrycket `1000 F3/(D h)`; det ger ingen
   kontroll av maximalt bottentryck.

   Slutresultat visar `sigma_ig_max` och `sigma_c_max`: största trycket för
   respektive material från F1/F2. Kontaktkraften anges i etiketten.
   Alla fyra enskilda kontakttryck finns under delresultat.
4. Vid fristående holk beräknas högra väggen som konsol:

   ```text
   a1 = 0.9 l
   d = b1 - t_ig - c_nom - phi/2
   z = 0.9 d
   M_holk = F1 a1 / 1000
   Fs = 1000 M_holk / z
   As_req = 1000 Fs / f_yd
   ```

   Friktionen ingår i global jämvikt, men det gynnsamma lokala bidraget från
   mu F1 tas inte med i konsolens böjberäkning. Ingen kontroll av en inlagd
   armeringsmängd görs; resultatet är erforderlig area utan minimiarmering.
   Vid plattansluten holk utgår böjarmeringsresultaten helt, utan statusrad
   eller nollvärden för Fs/As_req.
5. Redovisa oreducerade `V_Ed_1=F1` (höger) och `V_Ed_2=F2` (vänster) vid
   fristående holk. Vid plattansluten holk redovisas endast `V_Ed_2`.
   Det tidigare gemensamma `V_Ed` och raden Styrande ersätts av dessa resultat.
   F1, F2 och F3 redovisas alltid separat.
6. Beräkna `a_v_2 = 0.1*l + t_ig_b` i mm, från F2:s angreppspunkt till
   underkant bottenigjutning. Den första termen är höjden över pelarfoten.
   `V_Ed_2` och `a_v_2` kan användas tillsammans som `V_Ed` och `a_v` i
   `Tvärkraft()` med motsvarande beräkningsbredd och enheter. Lastavståndet
   avser endast vänstra väggen och hör inte ihop med `V_Ed_1`.
   Kraftreduktion, dess tillämpningsvillkor och tvärkraftskapacitet hanteras
   i `Tvärkraft()`. Ingen reduktion görs i Pelarholk. Bottenmåttet ändrar
   inte global jämvikt, kontakttryck eller den avtalade böjmodellen.

## Avgränsning och figurer

Modellen omfattar inte genomstansning, pålfördelning, minimiarmering, förankring,
överlapp eller fullständig detaljutformning. Plattanslutningens alternativa
lastöverföring förutsätts verifierad separat. B och H styr ingen bärförmåga.
Kontakttrycken avser de två sidokontaktzonerna i den valda modellen;
tryckhållfastheten kontrolleras separat.

Panelen återanvänder den detaljerade kontaktzonsfiguren med oförändrad
utformning och sidobeteckningarna b₁/b₂. Visningsbredden begränsas till 780 px.
Friläggningen använder en kompakt SVG och EC2:s originalfigur en PNG, båda
begränsade till 560 px. Alla bilder är lagrade i `an_calcs.betong/figures`.
Friläggningen visar högra holkväggen med F1, snittets tvärkraft och det inre
kraftparet Fs/Fc samt måtten a1, d och z, endast vid fristående holk.
En separat principfigur visar F₂ på vänstra holkväggen, `a_v_2`, höjden
`0.1l` över pelarfoten och bottenigjutningen `t_ig_b`, högst 560 px bred.
Den är tillgänglig för båda holktyperna. Friläggningen och lastavståndsfiguren
ligger under samma ihopfällbara flik **Holkväggar – böjarmering och lastavstånd**,
med underrubriker utan egna öppningsreglage. Vid plattansluten holk visas
endast lastavståndsfiguren i fliken.
Måttskissen genereras av `_pelarholk_skiss.render`, begränsad till 460 px.
Index i hjälptexter och bildtexter formateras som index, även på smal yta.
Beräkningsfunktionen importerar inte renderaren och läser inga bildresurser.
Figurerna uppdaterar inte beräkningsresultat automatiskt;
använd **Beräkna / uppdatera** för en ny redovisning.
