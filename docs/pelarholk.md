# Pelarholk

## Modell och indata

Kraftmodell: SS-EN 1992-1-1:2005 (Sv), 10.9.6.3, figur 10.7b, släta fogytor.
Modellen kräver `l >= 1.2 h`, `0 <= mu <= 0.3` och icke-negativa kontaktkrafter.
Standardens högra delfigur är märkt (a) i användarens utgåva men hänvisas till
som (b) i texten. Originalbilden bevaras oförändrad.

Dictionary rekommenderas. Listformat följer `Pelarholk.panel_schema["px"]`:

`typ, fristaende, M, Fv, Fh, h, l, D, t_ig, bh, f_cd_ig, f_cd_c, c_nom, phi, f_yd, mu`.

| Indata | Definition / enhet |
|---|---|
| `typ` | `pelare` eller `vagg` (direktanropets förval: pelare) |
| `fristaende` | Bool, förval True. Styr böjarmering och val av tvärkraft |
| `M`, `Fv`, `Fh` | Dimensionerande laster vid holkens överkant; medurs, nedåt respektive åt höger positivt |
| `h`, `l` | Pelarmått/väggtjocklek i snittet och insticksdjup, mm |
| `D` | Verksamt kontaktdjup ut ur snittet, mm. Vägg låser D=1000 även i direktanrop |
| `t_ig` | Igjutningstjocklek, mm |
| `bh` | Från elementets högra yta till fundamentets högra ytterkant, inklusive igjutning, mm |
| `f_cd_ig`, `f_cd_c` | Dimensionerande tryckhållfasthet för igjutning och holkbetong, MPa |
| `c_nom`, `phi` | Täckskikt till aktuell dragstångs utsida och dragstångens diameter, mm |
| `f_yd` | Dimensionerande sträckgräns, MPa |
| `mu` | Friktionskoefficient, förval 0.3 |

Hållfastheter anges direkt; inga ytterligare partialkoefficienter tillämpas.
Panelens startvärden är exempel, inte en verifierad dimensionering.
Pelare använder kN, kNm och mm². Vägg använder kN/m, kNm/m och mm²/m, med
en meterstrimla. Lägesbyte behåller lastvärdena, användaren anpassar dem.

`bv`, `H` och `t_p` är enbart panelens skissmått och ingår inte i listformatet.
De får förekomma i dictionary men ignoreras av beräkningen. `B=bv+h+bh` visas
som härlett totalmått. `bh` används i böjberäkningen endast vid fristående holk.
Skissen reagerar direkt på fältändringar och återlästa fall. Samma skala används
i x/y; enbart igjutningens synliga tjocklek förstärks. Plattans längd och
pelarens visade höjd ovan holken är avbrutna, schematiska fortsättningar.
Fel i rena skissmått ger ett meddelande vid skissen, inte ett beräkningsstopp.

## Beräkningsgång

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
   eta_ig,i      = 100 sigma_ig,i,max / f_cd_ig
   eta_c,i       = 100 sigma_c,i,max / f_cd_c
   ```

   Spänningar redovisas i MPa, utnyttjanden i procent. Dessa antagna tryckzoner,
   spridningsvinkeln och jämförelsen direkt med f_cd är projektets modell,
   baserad på handberäkningen, och inte tryckformler föreskrivna i 10.9.6.3.
   Tillgänglig betonggeometri för spridningen förutsätts verifierad separat.
   Under pelarfoten visas endast medeltrycket `1000 F3/(D h)`; det ger ingen
   kontroll av maximalt bottentryck.
4. Vid fristående holk beräknas högra väggen som konsol:

   ```text
   a1 = 0.9 l
   d = bh - t_ig - c_nom - phi/2
   z = 0.9 d
   M_holk = F1 a1 / 1000
   Fs = 1000 M_holk / z
   As_req = 1000 Fs / f_yd
   ```

   Friktionen ingår i global jämvikt, men det gynnsamma lokala bidraget från
   mu F1 tas inte med i konsolens böjberäkning. Ingen kontroll av en inlagd
   armeringsmängd görs; resultatet är erforderlig area utan minimiarmering.
   Vid plattansluten holk visas **Ej beräknad**, utan nollvärde för Fs/As_req.
5. Redovisa oreducerad `V_Ed=max(F1,F2)` vid fristående holk, annars `V_Ed=F2`.
   F1, F2 och F3 redovisas alltid separat. `V_Ed` förs till `Tvärkraft()` med
   motsvarande beräkningsbredd och enheter. Ingen tvärkraftskapacitet beräknas
   inne i Pelarholk.

## Avgränsning och figurer

Modellen omfattar inte genomstansning, pålfördelning, minimiarmering, förankring,
överlapp eller fullständig detaljutformning. Plattanslutningens alternativa
lastöverföring förutsätts verifierad separat. B och H styr ingen bärförmåga.
Statusen för tryck avser endast de två sidokontaktzonerna i den valda modellen.

De två fasta PNG-figurerna ligger i `an_calcs.betong/figures`. Den interaktiva
måttskissen genereras av `_pelarholk_skiss.render`, via an-prints generella
figurkoppling. Beräkningsfunktionen importerar inte renderaren och läser inga
bildresurser. Figurerna uppdaterar inte beräkningsresultat automatiskt;
använd **Beräkna / uppdatera** för en ny redovisning.
