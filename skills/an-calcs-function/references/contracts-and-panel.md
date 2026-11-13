# Paketkontrakt och panelmönster

Läs aktuell `an-calcs/README.md`, `an-print/README.md` och relevant kod innan
du bygger vidare. Nedanstående beskriver mönstret vid skillens tillkomst;
repoanvisningar och användarens uppdrag bestämmer vad som gäller nu.

## Beräkningskontrakt

```python
details = funktion(px)
```

- Placering: `src/an_calcs/<material>/<modul>.py`. Exportera önskat publikt
  namn via materialpaketets `__init__.py` enligt befintligt mönster.
- `px` har dokumenterad ordning. Namngivet dictionaryformat är lämpligt när
  metoder och frivilliga indata gör positionsformatet svårt att använda.
  Inför inte extra kort-/legacyformat för en ny funktion utan behov; bevara
  de format som redan finns när du ändrar en befintlig funktion.
- `details` innehåller normalt `metodbeskrivning`, `indata`, `delresultat`,
  `slutresultat` och `ekvationer`. Varje sektion har `title` och `items`.
- Numeriska poster i indata/delresultat/slutresultat använder detta mönster:

```python
{"namn": "R_d", "latex": r"R_d", "value": 125.0,
 "unit": "kN", "etikett": "Dimensionerande bärförmåga"}
```

Ekvationsposter använder `latex` och `etikett`; metodbeskrivning kan använda
`text`. Följ aktuella `CalcBlock`-exempel för text, status och precision.
Bevara unika postnamn och JSON-serialiserbara värden. `NaN` och oändliga
resultat ska inte hamna i en färdig redovisning.

`Panel` och `CalcBlock` finns i `an_print`. Panelen ska kunna köras med:

```python
from an_print import Panel
panel = Panel(funktion, key="Fall1")
```

## Schema och indatagrupper

`funktion.panel_schema` är ren Python-data utan import av UI-bibliotek.
`px` styr beräkningsordningen; `sections` styr visningsordningen. Varje fält
ska bara förekomma en gång i avsnitten, även när avsnitten är nästlade.

Exempel på struktur för en ny panel:

```python
funktion.panel_schema = {
    "title": "Beräkningens namn",
    "px": ["b", "d", "gamma_m"],
    "fields": [
        {"name": "b", "type": "float", "label": "Bredd",
         "symbol": "<i>b</i>", "unit": "mm", "default": 300.0},
        {"name": "d", "type": "float", "label": "Effektiv höjd",
         "symbol": "<i>d</i>", "unit": "mm", "default": 500.0},
        {"name": "gamma_m", "type": "float", "label": "Materialfaktor",
         "symbol": "γ<sub>M</sub>", "default": 1.5},
    ],
    "sections": [
        {"title": "Indata", "collapsible": True, "collapsed": False,
         "columns": 1, "sections": [
             {"title": "Geometri", "fields": ["b", "d"], "columns": 2},
         ]},
        {"title": "Beräkningsinställningar", "fields": ["gamma_m"],
         "collapsible": True, "collapsed": True},
    ],
}
```

Förvalen ovan illustrerar endast schemat och är inte en normerad modell.
Beräkningsfall, Redovisning och beräkningsknapp tillhandahålls av `Panel`;
duplicera inte dessa som egna indatafält eller avsnitt i funktionsschemat.

## Villkor, enheter och symboler

- `visible_if`: `{"field": "metod", "in": ["a", "b"]}`. Kombinera villkor
  med `{"all": [...]}`. Samma metodvillkor behöver hanteras i beräkningskärnan.
- `fixed_if`: låser ett värde under ett villkor och återställer föregående
  redigerbara värde när villkoret upphör. Använd i stället för att förstöra
  användarens tidigare inmatning vid lägesbyte.
- `presentation_if`: byter `label`, `unit` eller `symbol` vid exempelvis en
  avtalad meterstrimla. Säkerställ samma enheter i numeriskt resultat och
  ekvationernas förklaringar. En ändrad etikett skalar inte lasten automatiskt.
- `help`: kort vanlig text under fältet. `span` kan ge ett viktigt fält större
  utrymme utan att alla fält behöver bli breda.
- `symbol` kan använda HTML-index. Booleska widgetetiketter måste kontrolleras
  särskilt: ToggleButton renderar vanlig text, medan Checkbox kan använda
  `description_allow_html`. I Tvärkrafts widgetversion filtrerades `<sub>`
  bort. `label_html` använde därför exempelvis
  `<i>b</i><span style='vertical-align:sub;font-size:smaller'>w</span>`.
  Kontrollera aktuell rendering; en godkänd Python-sträng bevisar inte att
  indexet visas rätt. Återanvänd befintligt stöd i `an-print` först.

Varken ett stängt avsnitt eller en dold ruta ska radera dess inmatade värde.
Validering av den aktiva metoden avgör vilka värden som används. Kontrollera
även metodbyte efter återläsning av ett sparat fall.

## Frivilliga figurer

Ett avsnitt kan ange följande metadata utöver `title`, `fields` och `columns`:

```python
{
    "figure": {
        "package": "an_calcs.betong",
        "resource": "figures/ec2-figure-6-5.png",
        "caption": "Figur 6.5 · Fackverksmodell",
        "alt": "Fackverksmodell med vinklar och mått för tvärkraftsarmering.",
        "source": "SS-EN 1992-1-1:2005 (Sv), s. 85",
        "visible_if": {"field": "metod", "in": ["bada", "6.2.3"]},
    },
}
```

`an-print` läser resursen via `importlib.resources` och bäddar in bilden.
Bilden visas till vänster om fälten på bred yta och ovanför på smal yta.
Frånvaro av `figure` ska inte kräva en resursmapp, bildläsning eller ny bredd.
Använd filformat som den aktuella panelversionen stöder.

Lägg färdiga bilder under funktionens paket, exempelvis `figures/`, och
dokumentera ursprung, figur, tryckt sida och PDF-sida där det behövs. Kontrollera
att beskärningen innehåller alla nödvändiga mått, pilar och förklaringar.
Verifiera att bildfilerna finns även i byggd wheel och kan läsas därifrån.
Lägg inte original-PDF, Excelunderlag eller gamla mockuper i skillen.

## Befintliga förebilder och riktade testkommandon

I `an-calcs` är `src/an_calcs/betong/tvarkraft.py` och
`tests/test_tvarkraft_panel.py` förebilder för metoder, alternativ inmatning,
enheter, figurer och sparade fall. `tests/test_tvarkraft.py` har numeriska fall.
Använd dem som API- och testmönster, inte som formler för andra beräkningar.

Exempel för ett arbete som faktiskt gäller Tvärkraft:

```bash
.venv/bin/python -m unittest tests.test_tvarkraft tests.test_tvarkraft_panel
.venv/bin/python -m unittest discover -s ../an-print/tests -p test_panel.py
```

Byt till nästa funktions exakta testmoduler. Kör panelberoendets tester när
panelstöd berörs. Undvik `test_tvarkraft*.py`: det träffar också träberäkningen
för dymlingsförband. Kör en isolerad visualisering med temporär state-fil för
UI-kontroll och visa aldrig en statisk mockup som bevis på widgetfunktion.

## Uppdateringskommando vid ändringar i båda paketen

Om remoter och paketnamn fortfarande är dessa och båda paketen ska uppdateras:

```bash
uv pip install --upgrade --reinstall-package an-calcs --reinstall-package an-print \
  "an-calcs @ git+https://github.com/Nordlofen/an-calcs.git@main" \
  "an-print @ git+https://github.com/Nordlofen/an-print.git@main"
```

Starta om notebookens kernel efter installation. Kontrollera `pyproject.toml`
innan ett extra används; `an-calcs[betong]` är inget definierat extra vid
skillens tillkomst. Anpassa kommandot om bara ett paket ändrats eller om
användaren använder en annan pakethanterare eller Git-ref.
