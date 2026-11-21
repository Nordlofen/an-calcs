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

En separat spänningsfigur under last- och materialfälten visar samma snitt
tillsammans med töjning, betongspänning, betongens tryckkraft, armeringens
dragkraft och hävarmen när den finns. Diagrammen delar höjdskala. Deras
bredd är schematisk. Stadium II visar profilen vid angiven last och
stadium III den ultimata profilen vid angiven normalkraft.

| Geometri | Mått och armering |
|---|---|
| Påle | Kvadratiskt snitt, fyra identiska hörnjärn, täckskikt till bygelns utsida, bygel- och stångdiameter |
| Balk | Bredd, höjd, obligatorisk bygeldiameter och täckskikt till bygelns utsida i ÖK och UK. Antal och stångdiameter per sida |
| Plattremsa | Fast beräkningsbredd 1 000 mm i Panel. Plattjocklek och täckskikt till längsarmeringens utsida i ÖK och UK. Antal och stångdiameter per sida |

Stångcentrum beräknas geometriskt från täckskiktet, en halv stångdiameter
och för balk även bygeldiametern. I underkant mäts motsvarande avstånd från
underkanten. Antal noll utelämnar den armeringsraden. Skissen visar
placeringen i breddled schematiskt.

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
  finns i delresultatet. Elastiska stålspänningar redovisas även över flytgränsen.
- **Stadium III** löser tryck- och momentkapacitet vid given normalkraft och
  visar valt stadium, tryckzonens höjd, stålspänningar, betongens tryckkraft,
  armeringens dragkraft och hävarm där den finns. \(M_{Ed}\) och \(M_{Rd}\)
  i lastens riktning visas efter varandra. Töjningarna finns i delresultatet.
  Snittresultaten avser den ultimata profilen. Panel använder rektangulärt
  tryckblock med \(\lambda=0,8\) och \(\eta=1\) för \(f_{ck}\leq50\) MPa.
  Stålet har horisontell flytplatå vid \(f_{yd}=f_{yk}/\gamma_s\). Vid helt
  tryckt snitt används blockmodellens pivotvillkor med 1,75 ‰ som gräns
  vid jämn tryckning. Även tidigare sparade Panel-fall räknas om med
  rektangulärt tryckblock. Resultaten avser
  tvärsnittskapacitet och omfattar ingen sekant- eller tangentstyvhet.

Modellgränsen för elastisk betongtrycktöjning är som standard
\(0,4(f_{ck}+8)/E_{cd}\). Med \(f_{ck}=30\) MPa och \(E_{cd}=33\,000\) MPa
blir gränsen 0,4606 ‰. Den kan anges manuellt i ‰ i Panel eller dimensionslöst
som `epsilon_c_lim` i en dictionary. Det är ett varningskriterium för den
elastiska modellen. Brottöjningskontrollen använder ett separat villkor.
Varningstexterna visas både i metodbeskrivningen och i slutresultatet.

Modellerna omfattar rektangulära snitt, enaxlig böjning, normalkraft i tryck
eller noll och \(f_{ck}\leq50\) MPa. Stadium III bygger på materialmodellerna
från EN 1992-1-1:2004, 3.1.7 och 6.1, med inmatade designvärden. Modellen
söker jämvikt numeriskt längs tillåtna ultimata töjningsprofiler. Förankring,
skjuvning, torsion, sprickbredd, fria stångavstånd, rotationsförmåga,
instabilitet och andra ordningens effekter kontrolleras separat.

## Anrop från Python

Dictionary-formatet kan använda samma två lager som Panel. För balk är
`phi_b` bygeldiametern i mm. `c_nom_ok`, `c_nom_uk`, `phi_ok` och `phi_uk`
anges i mm och `n_ok`, `n_uk` i antal stänger. Påle använder `b`, `c_nom`,
`phi_b` och `phi_h` för den kvadratiska geometrin.
Python-anrop med dictionary kan ange en annan beräkningsbredd för plattremsa.

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
