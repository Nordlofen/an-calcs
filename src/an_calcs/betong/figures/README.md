Figurer för Tvärkrafts inmatningspanel
====================================

Originalfigurer ur användarens SS-EN 1992-1-1:2005 (Sv).
Figurerna är statiska PNG-bilder, renderade i tre gånger PDF-sidans punktupplösning.

- ec2-figure-6-3.png: figur 6.3, tryckt sida 83 (PDF-sida 87).
- ec2-figure-6-4.png: figur 6.4, tryckt sida 84 (PDF-sida 88).
- ec2-figure-6-5.png: figur 6.5, tryckt sida 85 (PDF-sida 89).
- ec2-figure-6-6.png: figur 6.6, tryckt sida 87 (PDF-sida 91).

Bilderna används endast som mått- och begreppsstöd i panelen.
Beräkningsfunktionen läser inte bildfilerna. Bildtext och källa anges i panelschemat.

Figurer för Pelarholk
--------------------

- ec2-figure-10-7.png: originalfigur 10.7, tryckt sida 181 (PDF-sida 185),
  SS-EN 1992-1-1:2005 (Sv), användarens utgåva med AC:2008.
  Båda delfigurer och figurtext ingår. Originalets dubbla (a) är bevarad;
  den högra med slät fogyta motsvarar 10.7b i standardtexten.
  Beskärning av originalsidan i PDF-punkter: [83, 437, 572, 692],
  renderad med fyra pixlar per PDF-punkt.
- pelarholk-kontaktzoner.png: egen principskiss, inte skalenlig, med
  uppdaterade beteckningar D, b₂, b₁, B och H. Kraftlägen enligt 10.7b;
  triangulärt tryck och spridningsvinkel enligt projektets handberäkningsmodell.
  F3 visar endast kraftläge; bottenkontaktens tryckmodell ingår inte.
  Den tidigare detaljerade utformningen används åter i panelen, med högst
  780 px visningsbredd. Redigerbar källa: `docs/figures/rita_pelarholk_kontaktzoner.py`.
  Källan återskapar PDF och PNG (2400 × 1830) i angiven utdatakatalog.
- pelarholk-lastavstand.svg: separat detalj av vänstra holkväggen, med F₂
  som kraft på väggen och måttkedjan a_v,2 = 0,1l + t_ig,b. Pelarfot och
  holkbotten (underkant bottenigjutning) markeras. Egen principskiss enligt
  avtalad modell, ej skalenlig, högst 560 px bred i båda holktyperna.
- pelarholk-bojarmering.png: egen principskiss av högra holkväggen, endast
  för fristående holk. Visar F1 med a1=0,9l och snittets V=F1 samt kraftparet
  Fs/Fc med z=0,9d. Måttdetaljen visar hur d bestäms från bh, t_ig, c_nom
  och phi. Gynnsam lokal friktion utelämnas enligt projektets konsolmodell.
  Redigerbart SVG-original: `docs/figures/pelarholk-bojarmering.svg` från
  repots rot. PNG är renderad från SVG i dubbla upplösningen (2800 × 2160).

Den dynamiska måttskissen ligger som Python-renderare i `_pelarholk_skiss.py`.
Inga absoluta källsökvägar eller originaldokument behövs i installerad panel.

Kompakta panelversioner
----------------------

- `pelarholk-kontaktzoner-kompakt.svg`: äldre kompakt variant av kontaktzoner
  och tryckspridning, bevarad som resurs men används inte i panelen.
- `pelarholk-bojarmering-kompakt.svg`: frilagd högra holkvägg med F1, V,
  Fs/Fc, a1, d och z. Sidomått b₁ och tvärkraft V_Ed,1.
  Samma konsolmodell som den större figuren.

Den kompakta böjfiguren är ritad för högst 560 px visningsbredd. Stora rubriker,
formelrutor och upprepade textförklaringar utgår ur bilderna; bildtext och
ekvationsredovisning ger denna information. De större PNG-originalen bevaras.
