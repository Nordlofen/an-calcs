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

Foreslagen projektstruktur:

- `src/an_calcs/tra` for tra
- `src/an_calcs/stal` for stal
- `src/an_calcs/betong` for betong
- `src/an_calcs/geo` for geoteknik
- `src/an_calcs/common` for gemensamma hjalpmoduler
- `tests/` for tester
- `notebooks/` for exempel och utvecklingsnotebooks
- `docs/` for dokumentation
