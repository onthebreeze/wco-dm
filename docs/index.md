# The WCO Data Model as linked data

The World Customs Organization (WCO) Data Model is the international standard for the data customs
administrations and the parties that deal with them exchange. Version 4.3.0 defines 273 classes and
1,156 attributes, published as spreadsheets.

This site publishes the same model as a linked data vocabulary: every class, property and code has
its own address, and that address answers a reader with a page and a machine with Turtle, JSON-LD or
RDF/XML.

## Three kinds of term

The vocabulary has three categories, and a code list is one of them rather than a detail hanging off
a property. Each has its own index, each term has its own address, and each resolves as a page, as
Turtle and as JSON-LD.

| | | |
|---|---|---|
| [Classes](classes/) | 283 | A group of information the model treats as a thing: a consignment, a party, a means of transport |
| [Properties](properties/) | 409 | A single piece of information about a class. One property serves every class that uses it |
| [Code lists](code-lists/) | 171 | The value domain of a coded property, with its codes where WCO owns them |

Mappings to vocab.unece.org are carried on the term pages, where a corresponding concept exists.

Every term carries the file, sheet and row of the WCO workbook it came from, so any statement here
can be traced back to a cell in the published model.

## One address, four representations

Ask for a term as a person and you get a page. Ask as a machine and you get the data.

```
curl https://vocabulary.wcoomd.org/Consignment
curl -H "Accept: text/turtle"          https://vocabulary.wcoomd.org/Consignment
curl -H "Accept: application/ld+json"  https://vocabulary.wcoomd.org/Consignment
curl -H "Accept: application/rdf+xml"  https://vocabulary.wcoomd.org/Consignment
```

Every address on this site answers that way, not only the terms: a module, an index, a message
release, and these pages. A client never has to know in advance which addresses are negotiable.

This is what makes the model usable by software that has never been told about it: a system meeting
an unfamiliar identifier can resolve it and find out what it means.

## What this site is not

It is not a replacement for the WCO Data Model, and it is not a second source of truth. The
spreadsheets WCO publishes remain authoritative; everything here is generated from them, and
regenerating is how it is kept current.

## The messages

The library says what a class and an attribute mean. The four Information Package workbooks say how
they are assembled into a message, and crucially how many times each piece may occur, which the
library does not record.

| Package | What it carries |
|---|---|
| Declaration | Business to government submissions: import and export declarations, cargo reports, transit |
| LPCO | Licences, permits, certificates and other documents |
| Additional | The wrapper around business information: Response for G2B, Intergov for G2G |
| Meta Data | The technical aspect of the exchange, kept apart so the others carry only business content |

A JSON Schema and a JSON-LD context are generated for each, and for each of the sixteen derived
packages that subset them, among them the Certificate of Origin, eTIR, Maritime API and the UPU
messages. See [Information packages](packages/).
