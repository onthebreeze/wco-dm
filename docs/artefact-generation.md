# How the artefacts are generated

Every file this site publishes is generated from the WCO workbooks by a rule that is written down.
This page is where the rules are written down.

There are two sources and four kinds of output. The Library and the Overall Information Structure
give the vocabulary, published as Turtle, JSON-LD and RDF/XML. The four Information Package
workbooks give the messages, published as JSON Schema, JSON-LD contexts and XML schemas. Nothing is
authored in between, so a rule that is wrong is wrong in one place.

## The vocabulary

### Turtle, and everything derived from it

`ontology/*.ttl` is the vocabulary. Ten files, one per module, built from every release at once.

| | |
|---|---|
| A class | One `owl:Class` per class in the Library, named as WCO names it, carrying its class identifier |
| A property | One property per attribute concept, not per attribute. Attributes sharing a local name and a core data type become one term with many `schema:domainIncludes` |
| A class-specific definition | `skos:scopeNote`, naming the class, so none of the 174 wordings of `id` is lost |
| A code list | One `skos:ConceptScheme`. Where WCO owns the values, one `skos:Concept` each |
| A superclass | The five the Library names, minted as classes, with `rdfs:subClassOf` on the 170 classes that carry one |
| A lifecycle | `wco:introducedIn`, `wco:presentIn`, and `wco:deprecatedIn` with `owl:deprecated` where a release dropped the term |
| A former name | `skos:altLabel`, because identity across releases is the WCO identifier and a rename is a rename |

Where a merged property turns out to have classes coding against different lists, the attributes
did not mean the same thing and the merge is undone. The part the current release uses keeps the
published name, so adding an older release never moves an address.

### JSON-LD and RDF/XML

Serialisations of the same graph, written by rdflib, with no transformation of their own. A term's
directory holds `index.ttl`, `index.jsonld` and `index.rdf` beside `index.html`, and the edge
chooses between them by `Accept`.

What each address answers with is itself plus one step of what its page shows: a class returns the
properties that apply to it, a code list returns its values, a module returns every term it defines
plus the terms its classes depend on, an index returns its members. Nothing is duplicated in the
source; the overlap exists only in what is generated from it.

## The messages

A package workbook is a tree of positions. Each row gives a model path, a name, a definition, a
format, the number of occurrences, a code list, an XML tag and a JSON tag. The tree is the
structure, and every message artefact is a rendering of it.

### JSON Schema

| Workbook | Schema |
|---|---|
| A class, with positions below it | `"type": "object"` with `properties` and `additionalProperties: false` |
| An element | A typed property, from the WCO format: `an..35` is a string of up to 35, `n..2` a string matching two digits, `a2` exactly two letters |
| Maximum `unbounded` | `"type": "array"` wrapping the item |
| Minimum 1 | The name is added to `required` |
| WCO ID | `x-wco-id` |
| The vocabulary term | `x-wco-term`, where the attribute resolves to a published property |
| Code list | `x-wco-code-list` |

A numeric format becomes a string with a pattern rather than a number, because WCO numerics are
frequently coded values and leading zeros matter.

### JSON-LD context

One entry per JSON tag, bound to the published term that defines it. A tag that means different
things in different places is left out rather than bound to one of them: the Declaration leaves out
sixteen, among them `id`, `name` and `typeCode`.

### XML Schema

Two files per message, named as WCO names them, because the structure imports its types by file
name and ours should drop in where theirs sits.

```
<Name>_4p3p0.xsd                                    the element structure
<Name>_4p3p0_urn_wco_datamodel_WCO_<Name>_DS_4.xsd  one type per class and attribute
```

**The structure.** The target namespace is `urn:wco:datamodel:WCO:<Name>:4` and the type namespace
is the same with `_DS` appended. The element tree is the model path tree: a class becomes an
`xs:element` wrapping an anonymous `xs:complexType` with an `xs:sequence`, and an element becomes an
`xs:element` typed at `ds:<Named Complex Type>`. Occurrences are written only where they differ
from exactly one. Each position carries a short `xs:annotation` with its Dictionary Entry Name,
definition, WCO identifier, Unique Position ID, format and code list.

Two things about a schema are not in the workbooks and are read from WCO's published file instead:
the token used in its name and namespace, and the name of its root element. A derived package
usually keeps the root of the package it subsets, but UPU CUSRSP is rooted at `Response` and UPU
REFRSP at its own name. Both are recorded in `docs/xml-schemas.json`.

**The types.** The type name is the Named Complex Type the Library gives, not a name this generator
invents. The content is determined by the core data type, one shape each:

| Core data type | Content |
|---|---|
| Text | `xs:string`, with an optional `languageID` |
| Identifier | `xs:string`, with `schemeID`, `schemeName`, `schemeAgencyID`, `schemeAgencyName`, `schemeVersionID`, `schemeDataURI` and `schemeURI` |
| Code | `xs:token`, or a named content type where the values belong to a standard list, with the nine `list…` attributes |
| Date Time | A choice of `DateTimeString` carrying a required `formatCode` |
| Indicator | A choice of `IndicatorString` and a boolean `Indicator` |
| Measure | `xs:decimal` with `unitCode` |
| Quantity | `xs:decimal` with `unitCode` as a token |
| Amount | `xs:decimal` with `currencyID` |
| Binary Object | `xs:base64Binary` with `format`, `mimeCode`, `encodingCode`, `characterSetCode`, `uri` and `filename` |
| Numeric | `xs:decimal` |

A coded attribute restricts to a named content type when its register entry names a standard
authority - UN/EDIFACT, ISO, UN/LOCODE - and takes `xs:token` directly when the list is the
implementer's own or WCO's.

The four code list schemas a type file imports - the UN/CEFACT agency identification codes, the
UNECE character set encoding codes and the two IANA lists - are UN/CEFACT and IANA publications,
referenced exactly as WCO references them and included in WCO's own download package. They are not
reproduced here.

## Checking the rules against WCO's own output

The rules above are not asserted, they are tested. `scripts/compare_xsd.py` reduces each schema WCO
publishes for 4.3.0 to the set of element paths it defines, with cardinality and type, and diffs it
against what this repository generates.

| Message | Positions | Matched | Cardinality | Type names |
|---|---|---|---|---|
| Declaration | 9,064 | 9,064 | all | 7,152 of 7,217 |
| LPCO | 763 | 763 | all | 587 of 591 |
| Certificate of Origin | 107 | 107 | all | all but one |
| Meta Data | 67 | 67 | all | all |
| Maritime API | 86 | 86 | all | all but two |
| Maritime BRI | 144 | 144 | all | all but seven |
| AEO Master Data | 46 | 46 | all | all |

10,444 positions compared and no cardinality differs. Seven of the ten messages reproduce the
element tree exactly; the other three differ by one or two positions, each a case where a derived
package embeds another message, which this generator does not model.

Type definitions were compared in full for the Meta Data package: 62 type names, 59 definitions
byte-identical once annotations are set aside. Of the three that differ, one is a serialisation
difference and two are inconsistencies in WCO's own output. `Additional Identifier. Sequence.
Numeric` restricts to zero and above and `Communication Meta Data. Sequence. Numeric` does not,
though both are `n..5` and both are a sequence number; `schemeID` is required on one of seventeen
identifiers and optional on the rest. No rule produces both, so this generator picks the consistent
form and says so here.

## Where the workbooks are not enough

Three gaps, each recorded rather than guessed.

**Cardinality for a derived package.** A base package's schema agrees with its workbook on every
occurrence. A derived package's does not: the workbook marks that a position is used by a message,
never how often it must appear, so WCO's published schema is the only statement of obligation there
is. Those 191 positions are taken from the schema, recorded in `docs/cardinality-overrides.json`
with what the workbook said, and applied to every artefact so that all of them agree.

**Sixty-five type names in the Declaration** where the Library's Named Complex Type column differs
from the type the published schema uses - `AdditionalDocumentIssueLocationTextType` against
`AdditionalDocumentIssueLocationNameTextType`. The schema is more specific in every case examined.

**Ten tag cells** hold two candidate tags, the same pair on rows needing different ones:
`Invoice/type` and `Invoice/Issuer/name` both say `TypeCode` and `Name` on separate lines. WCO's
schemas take `TypeCode` on one and `Name` on the other. The tag is chosen here by matching the model
path, which gets all ten right.

Each of these says the same thing: the published schemas are not generated from these spreadsheets.
Something upstream knows what the spreadsheet lost. That is an argument for holding the model where
it can be reviewed rather than exported.

## What this demonstrates

The XML schemas WCO publishes today are produced by a commercial modelling tool from a model that
is not public. This repository generates the same schemas from the published workbooks, and the
comparison is run on every build. A model held in git, with the generators and the comparison
alongside it, would produce the artefacts implementers already depend on, with the diff against the
current output as the evidence on every release.

That does not require a version 5.0, a migration, or anything to be retired first. It requires only
that the generated artefacts match, which is a thing that can be measured.
