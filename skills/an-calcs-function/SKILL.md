---
name: an-calcs-function
description: Skapa eller vidareutveckla ingenjörsberäkningar i an-calcs från standarder, PDF och Excel, med ren beräkningsfunktion, an-print-panel, redovisning och riktad verifiering. Använd för nya beräkningssnurror och ändringar i befintliga funktioner i AN Suite.
---

# Beräkningsfunktioner i an-calcs

För en beräkningsidé till en spårbar funktion som passar `an_calcs` och
`an_print`. Arbetsflödet bygger på utvecklingen av `Tvärkraft()`; återanvänd
arkitekturen och arbetssättet, men bestäm formler och tillämpningsområde för
varje ny uppgift.

## Välj rätt arbetssteg

- Utgå från senaste beställningen och beslut som redan fattats i chatten.
  Vid ”läs in”, ”sammanställ indata”, ”visa ett exempel” eller ”implementera
  inte än”: leverera just det steget utan att ändra beräknings- eller panelkod.
  När implementation beställs, genomför det överenskomna arbetet utan nya
  rutinmässiga bekräftelsefrågor.
- Identifiera aktiv projektmapp, lokala instruktioner och Git-status. Hitta
  `an-print` bland projektets anslutna mappar eller som syskonrepo när det
  behövs. Utgå från aktuella README-filer och faktisk kod, inte antagna API:er.
- Använd svenska för etiketter, hjälptexter och redovisning om inget annat
  efterfrågas. Funktionsnamn, materialmodul och eventuellt ASCII-alias följer
  beställningen och paketets befintliga konventioner.

## Läs underlaget och avgränsa modellen

- Kontrollera standardens utgåva, avsnitt, ekvationsnummer, villkor och
  tillämpliga nationella val. Skilj mellan normativa krav, rekommenderade
  värden, alternativa metoder och egna förenklingar. Anta inte att ett
  rekommenderat EC-värde automatiskt är svenskt nationellt val.
- Läs omgivande stycken och tillhörande figurer, inte bara en isolerad formel.
  Använd PDF-rendering för måttfigurer och svårlästa symboler; PDF-textextraktion
  kan förväxla exempelvis grekiska bokstäver och olikhetstecken.
- Excel är ett jämförelseunderlag, inte facit för standardtolkning. Kontrollera
  faktisk formel, indata, enhetsomvandlingar och om resultatet är omräknat.
  Redovisa en avvikelse innan du ändrar en korrekt standardformel för att
  efterlikna en arbetsbok.
- Formulera vad modellen omfattar och vilka specialfall som ligger utanför.
  Lägg inte till specialfall som användaren uttryckligen valt bort.
- Bekräfta att källfiler finns på angivna sökvägar. Bilagor kan ligga på
  skrivbordet eller i tillfälliga mappar. Bevara underlag som behövs för
  fortsatt arbete i en tydligt namngiven arbetsmapp vid behov och redovisa
  var det sparats. Käll-PDF:er, arbetsböcker och tillfälliga exportfiler ska
  inte automatiskt följa med en kod-commit.

## Bestäm indata och beräkningsinställningar

- Sammanställ namn/symbol, betydelse, enhet, förval, giltigt intervall och
  vilka metodval som behöver respektive indata. Ange teckenkonventioner.
- Skilj användarens geometri, material, armering och lasteffekter från
  beräkningsinställningar såsom metodval, partialkoefficienter och modellval.
  Hårdkoda standardgränser när det är det avtalade beteendet; gör inte varje
  konstant till en inställning.
- Stöd alternativa inmatningssätt när de behövs, till exempel area direkt
  eller antal/diameter. Definiera avrundningsregler uttryckligen. Återanvänd
  ett mått i modellen i stället för att fråga efter samma värde på flera ställen.
- Förklara kort hur ett betydelsefullt modellval påverkar olika kapaciteter.
  Vinkelomräkningar och liknande hjälp ska vara relevanta för just fältet.
- Håll lasteffekt, bärförmåga och utnyttjandegrad tydligt åtskilda. En reduktion
  ska inte räknas dubbelt. Visa helst den kontrollerade lasten direkt mot
  motsvarande kapacitet; undvik extra omräknade kapaciteter som gör kontrollen
  svår att följa. Särskilj kontroller av reducerad och oreducerad last.

## Implementera beräkning och panel

Läs [paketkontrakt och panelmönster](references/contracts-and-panel.md) när
funktion, `details`, panel eller figurer ska implementeras.

- Håll själva beräkningen fri från widgets, notebookvisning, filinläsning av
  figurer och nätåtkomst. Lägg gemensam presentation i `an-print` och
  funktionsspecifika formler/metadata i rätt materialmodul i `an-calcs`.
- Ett metodval ska styra obligatoriska indata, validering, ekvationer och
  resultat, inte bara vad panelen visar. Inaktiva fält ska inte blockera en
  giltig beräkning. Validera ändliga tal och relevanta gränser; dölj inte
  otillåtna indata genom tyst klippning om modellen inte föreskriver den.
- Bevara befintliga importnamn, dokumenterade positionsformat, fältnycklar
  och sparade fall när en befintlig funktion ändras. Ordna om presentationen
  oberoende av `px` och migrera bara det som faktiskt behöver ändras.
- För nya paneler: använd ett ihopfällbart **Indata**, öppet från början,
  och ett separat **Beräkningsinställningar**, stängt från början. Behåll
  beräkningsknappen utanför Indata. Återanvänd panelens Beräkningsfall och
  Redovisning. Anpassa befintliga paneler endast inom beställt ändringsområde.
- Använd riktiga index, tydliga enheter och korta förklaringar. Kontrollera
  symboler i den faktiska widgeten. Långa villkorskedjor hör hemma i
  ekvationens uttryck eller förklaring, inte som en mycket bred vänstersida.

## Figurer och layout

- Figurer är frivilligt stöd vid relevanta inmatningsfält. Vid begäran om
  stillbilder eller layoutbild: skapa en statisk förhandsvisning. Lägg inte
  till interaktiv figur eller permanenta gränssnittselement från en mockup.
- Använd lämpliga figurer från tillgängligt underlag när det efterfrågas.
  Kontrollera mått, läsbarhet och källhänvisning. Koppla varje figur till
  den metod och de alternativ där den hjälper användaren; en närliggande
  figurs nummer betyder inte att den hör till samma beräkningsmetod.
- Paketera färdiga bildresurser med funktionen så att installerad panel
  fungerar utan originaldokument eller absoluta filsökvägar. Figurer ska
  inte ändra `px`, beräkningsresultat eller sparade indata. Paneler utan
  figurer ska fortsätta fungera.

## Verifiera inom uppdragets omfattning

- Testa aktuell beräkningsfunktion och dess direkta beroenden. Välj exakta
  testmoduler; undvik breda mönster som även träffar andra snurror. Kör inte
  hela repots tester eller exempelvis Grundplan för en isolerad ny funktion.
  Om en verklig beroendeändring kräver bredare kontroll, förklara kopplingen.
- Använd oberoende handberäkningsfall och relevanta gränsfall. Täck metodval,
  enheter, alternativa inmatningar och styrande begränsningar. Vid beställd
  Excel-jämförelse, välj flera varierade fall och förklara differenser.
- Kontrollera `Panel -> funktion -> CalcBlock`, dolda fält, låsta värden,
  sparning/återläsning och bakåtkompatibilitet i den omfattning ändringen
  berör. Använd tillfälliga state-filer så att användarens sparade fall bevaras.
- Vid layoutändring: verifiera riktig widgetvisning i tillgänglig webbläsare,
  bred och smal yta samt relevanta metodkombinationer. Kontrollera mörkt tema
  om den ändrade stilen berör färger. Ingen generell export- eller
  webbläsarinstallation behövs när export inte ingår i ändringen.
- Vid nya paketresurser: bygg wheel och verifiera resurserna från paketet.
  Kontrollera att testerna använder avsedd lokal version av direkta beroenden.

## Leverera

- Beskriv kort vad som implementerats, verifieringen och modellens materiella
  begränsningar. Uppdatera funktionens docstring och relevant README.
- Commit/push görs när det är beställt eller redan auktoriserat för aktuellt
  arbete. Använd explicit filurval, granska diffen och lämna orelaterade
  arbetsfiler utanför. Vid ändringar i båda paketen, leverera nödvändigt
  beroendestöd före den funktion som använder det och verifiera push-resultatet.
- När användaren ska uppdatera: ange kommandon för de paket som faktiskt
  ändrats och påminn om omstart av notebookens kernel. Kontrollera extra-namn
  i `pyproject.toml`; materialmoduler som `betong` är inte automatiskt pip-extras.
