# Betongtvärsnitt

```python
from an_calcs.betong import betongtvarsnitt
from an_print import Panel

Panel(betongtvarsnitt, key="Snitt 1")
```

Välj **Påle**, **Balk** eller **Plattremsa** och **Stadium II** eller **Stadium III**.
Måttskissen uppdateras när geometri eller armering ändras. Panel använder
`an-print` med stöd för dynamiska figurer och indatagrupper. Spara indata och
redovisningsval under **Beräkningsfall**.

Spänningsfiguren visar de yttre lasterna och ett schematiskt tvärsnitt med
två järn per sida. Påle och balk visas med bygel. Plattremsan visas bredare.
Stadium II visar profilen vid angiven last. Stadium III visar profilen vid
momentkapacitet för angiven normalkraft. För delvis tryckta snitt ritas
neutralaxeln vid halva höjden i stadium II och något högre i stadium III.
Tryckzonens numeriska höjd redovisas i resultatet.

| Geometri | Mått och armering |
|---|---|
| Påle | Kvadratiskt snitt, fyra identiska hörnjärn, täckskikt till bygelns utsida, bygel- och stångdiameter |
| Balk | Bredd, höjd, obligatorisk bygeldiameter och täckskikt till bygelns utsida i ÖK och UK. Antal och stångdiameter per sida |
| Plattremsa | Fast beräkningsbredd 1 000 mm i Panel. Plattjocklek och täckskikt till längsarmeringens utsida i ÖK och UK. C/c-avstånd och stångdiameter per sida |

Stångcentrum beräknas geometriskt från täckskiktet, en halv stångdiameter
och för balk även bygeldiametern. I underkant mäts motsvarande avstånd från
underkanten. Ange noll som antal eller c/c-avstånd för att utelämna raden.
För plattremsa beräknas armeringsarean med \(b/s\) gånger en stångs area.
Måttskissen visar ett avrundat antal järn med angivet c/c. Ett tomt c/c-fält
använder det motsvarande avståndet från antalet i det sparade fallet eller
från förvalt antal i ett nytt fall.

Längder anges i mm och laster i kN och kNm för **hela snittbredden**. För en
1000 mm bred remsa sammanfaller lastvärdena numeriskt med kN/m och kNm/m.
Tryckkraft är positiv. Positivt böjmoment kring hela snittets geometriska mitt
har trycksidan i ÖK. Armeringen avser den studerade böjriktningen.

## Resultat

- **Stadium II** löser elastisk snittjämvikt vid angivna \(N_d\) och \(M\) med
  dragfri betong. Vid helt tryckt snitt används hela betonghöjden. \(EI_{II}\)
  beräknas från det transformerade tröghetsmomentet och angiven \(E_{cd}\).
  Stålraderna behandlas som koncentrerade areor och deras egna
  tröghetsmoment försummas. Slutresultatet visar valt stadium, tryckzonens
  höjd, maximal betongtryckspänning, stålspänning per rad, betongens tryckkraft,
  armeringens dragkraft, hävarm där den finns och \(EI_{II}\). Töjningarna
  finns i delresultatet. Under Ekvationer visas det transformerade snittets
  area, tyngdpunkt och tröghetsmoment samt hur man bestämmer tryckzonens
  höjd från normalkraft och moment. Elastiska stålspänningar redovisas även
  över flytgränsen.
- **Stadium III** löser tryck- och momentkapacitet vid given normalkraft och
  visar valt stadium, tryckzonens höjd, stålspänningar, betongens tryckkraft,
  armeringens dragkraft och hävarm där den finns. \(M_{Ed}\) och \(M_{Rd}\)
  i lastens riktning visas efter varandra. Töjningarna finns i delresultatet.
  Spänningar och töjningar avser snittet vid momentkapacitet. Panel använder
  rektangulärt tryckblock med \(\lambda=0,8\) och \(\eta=1\) för \(f_{ck}\leq50\) MPa.
  Stålet har horisontell flytplatå vid \(f_{yd}=f_{yk}/\gamma_s\). Vid helt
  tryckt snitt används blockmodellens pivotvillkor med 1,75 ‰ som gräns
  vid jämn tryckning. Även tidigare sparade Panel-fall räknas om med
  rektangulärt tryckblock. Resultaten avser
  tvärsnittskapacitet och omfattar ingen sekant- eller tangentstyvhet.

Stålspänning visas med drag positivt och tryck negativt i slutresultatet.
Positiva spänningar och krafter visas utan plustecken. Jämviktsekvationerna
och stålspänningarna från `berakna_betongtvarsnitt` har tryck positivt.

Stadium II varnar vid överskriden elastisk töjningsgräns eller flytgräns i
stålet och ger en kritisk varning vid överskriden stuktöjning i betongen.
Stadium III ger kritiska varningar om beräkningen saknar jämvikt för angiven
normalkraft eller om momentet ligger utanför den beräknade kapaciteten.
Varningstexterna visas i metodbeskrivningen och slutresultatet.

Modellgränsen för elastisk betongtrycktöjning är som standard
\(0,4(f_{ck}+8)/E_{cd}\). Med \(f_{ck}=30\) MPa och \(E_{cd}=33\,000\) MPa
blir gränsen 0,4606 ‰. Den kan anges manuellt i ‰ i Panel eller dimensionslöst
som `epsilon_c_lim` i en dictionary.

Modellerna omfattar rektangulära snitt, enaxlig böjning, normalkraft i tryck
eller noll och \(f_{ck}\leq50\) MPa. Stadium III använder betongens tryckblock
enligt EN 1992-1-1:2004 3.1.7(3), stålets flytplatå enligt 3.2.7(2) och
antagandena för böjning med normalkraft enligt 6.1. Ekvationerna visar
kraft- och momentjämvikt samt specialfallet ren böjning med ett draglager.
Modellen söker jämvikt numeriskt för tillåtna töjningar i brottgränstillstånd.
Förankring, skjuvning, torsion, sprickbredd, fria stångavstånd, rotationsförmåga,
instabilitet och andra ordningens effekter kontrolleras separat.

## Anrop från Python

Dictionary-formatet kan använda samma två lager som Panel. För balk är
`phi_b` bygeldiametern i mm. `c_nom_ok`, `c_nom_uk`, `phi_ok` och `phi_uk`
anges i mm. För balk anges `n_ok`, `n_uk` i antal stänger. För plattremsa
kan `s_ok`, `s_uk` anges i mm och beräkningsbredden `b` ändras. Äldre
plattremsor med `n_ok`, `n_uk` stöds fortfarande. Påle använder `b`, `c_nom`,
`phi_b` och `phi_h` för den kvadratiska geometrin.

```python
from an_calcs.betong import berakna_betongtvarsnitt, betongtvarsnitt

indata = dict(geometri="balk", stadium="II", b=300, h=600,
              c_nom_ok=35, c_nom_uk=40, phi_b=8,
              n_ok=2, phi_ok=16, n_uk=4, phi_uk=20,
              N_d=200, M=100)
details = betongtvarsnitt(indata)
raw = berakna_betongtvarsnitt(indata)
EI_II = raw["stadium_II"]["EI_II"]  # kNm²
```

För balk och plattremsa kan Python-anrop även ange en lista med
`armeringsrader` med valfritt antal poster. Varje post har `y` från ÖK till
stångcentrum, `phi`, valfritt `namn` och exakt ett av `antal`, `s` (c/c i mm)
eller `A_s` (mm² för hela bredden). Tidigare Python-anrop med
`tryckblock="parabel"` stöds fortfarande.

Den tidigare `bojstyvhet_betongpalar()` och dess Panel är kvar för modifierad
nominell pålstyvhet och tidigare sparade fall. `betongtvarsnitt(px)` känner
även igen det tidigare listformatet med 12 eller 16 värden och anropar
den tidigare funktionen direkt.
