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

## Böjstyvhet - Betongpålar

`an_calcs.betong.bojstyvhet_betongpalar` beräknar modifierad nominell böjstyvhet för en
kvadratisk betongpåle med fyra likadana huvudarmeringsjärn i hörnen.
Koefficienterna och summan av betongens och armeringens bidrag utgår från
avsnitt 5.6 i [underlaget, sida 11](https://kth.diva-portal.org/smash/get/diva2%3A1597682/FULLTEXT01.pdf).
Tryckzonen bestäms med modellen i det kompletterande bildunderlaget,
figur B7.14 (transformerat tröghetsmoment på sida B236). Betongens och
armeringens tröghetsmoment beräknas sedan separat kring den gemensamma
transformerade tyngdpunkten `x_tp`. `K_c` behålls som ytterligare reduktion.

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

Direkt anrop och redovisning med CalcBlock:

```python
from an_calcs.betong import bojstyvhet_betongpalar
from an_print import CalcBlock

px = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2, 30]
details = bojstyvhet_betongpalar(px)
cb = CalcBlock(details)
cb.SR(visa=True, etikett=True)
```

Exemplet ger `x = 184,300 mm`, `x_tp = 100,278 mm`, `EI_c = 66,615`,
`EI_s = 3242,440` och totalt `EI = 3309,056 kN·m²`.
Slutresultatet innehåller styvhetsbidragen, tryckzonens höjd `x` i mm och
kommentaren `Reducerad (x < b)` eller `Oreducerad (x = b)`.
Tryckzon, transformerade
snittkonstanter, tröghetsmoment, enhetsomvandlingar, koefficienter och
använda ekvationer redovisas i samma `details`-struktur via Panel eller CalcBlock.

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
lägre total styvhet. `K_c` använder effektivt kryptal som tidigare.
Kryptalet påverkar inte tryckzonslösningen. Detta är en modifierad modell,
inte den oförändrade nominella Eurokodmetoden.

`A_c`, armeringsinnehållet och slankheten baseras fortsatt på hela pålen.
Metoden kräver `A_s/A_c >= 0,002` och begränsar `k_2` till högst `0,20`.
Vid helt tryckt tvärsnitt används hela höjden `x=b` och `x_tp=b/2`.
Här betecknar `x` verksam betonghöjd, inte neutralaxelns läge utanför snittet.
`N_d = 0` tillåts: vid ren böjning löses tryckzonen utan division med normalkraft,
men `K_c=0` ger endast armeringens slutliga styvhetsbidrag enligt modellen.
Vid `N_d=M=0` används hela betonghöjden som beräkningskonvention.
Funktionen beräknar varken andra ordningens moment eller betongens sprickmoment.
Ogiltiga indata, överlappande järn och för lågt armeringsinnehåll ger `ValueError`,
som Panel visar vid beräkning.
