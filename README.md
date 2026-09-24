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

`an_calcs.betong.bojstyvhet_betongpalar` beräknar nominell böjstyvhet för en
kvadratisk betongpåle med fyra likadana huvudarmeringsjärn i hörnen.
Beräkningen följer avsnitt 5.6, ekvationerna (5.22)-(5.27) och (5.29), i
[underlaget, sida 11](https://kth.diva-portal.org/smash/get/diva2%3A1597682/FULLTEXT01.pdf).

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

Direkt anrop och redovisning med CalcBlock:

```python
from an_calcs.betong import bojstyvhet_betongpalar
from an_print import CalcBlock

px = [300, 30, 8, 20, 3, 300, 30, 20, 30000, 200000, 2]
details = bojstyvhet_betongpalar(px)
cb = CalcBlock(details)
cb.SR(visa=True, etikett=True)
```

Exemplet ger `EI_c = 280,763`, `EI_s = 2621,094` och totalt
`EI = 2901,857 kN·m²`. Alla tre resultat finns i `details["slutresultat"]`.
Mellanresultat, enhetsomvandlingar, koefficienter och använda ekvationer
redovisas i samma `details`-struktur och kan visas genom Panel eller CalcBlock.

`A_c` och `I_c` avser hela tvärsnittets geometri utan avdrag för armeringen.
Metoden kräver `A_s/A_c >= 0,002` och begränsar `k_2` till högst `0,20`.
Ogiltiga indata, överlappande järn och för lågt armeringsinnehåll ger `ValueError`,
som Panel visar vid beräkning. `N_d = 0` tillåts som gränsfall och ger endast
armeringens styvhetsbidrag enligt modellen.
