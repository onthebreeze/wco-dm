# Observations on the model

The working notes behind the published page at `/docs/future/`, which is the version intended for a
reader. This file keeps the counts and the method; the page states the case. If they disagree, this
file is the one to check first.

Things that publishing the WCO Data Model as linked data made visible. None of them is a defect in
the publication, and nothing here has been acted on: the site renders the model as the workbooks
give it. They are recorded because each is a question for the model itself, and the evidence is
cheap to reproduce now that the source is extracted.

Every count below comes from WCO Data Model 4.3.0, Library workbook, sheet `DataSet 1.2, 1.3, 1.4`.

## 1. The superclass is recorded and then discarded

The Library carries a SuperClass block that nothing downstream uses. Every class names its
superclass - SC1 RootDocument, SC2 GovernmentAgency, SC3 Location, SC4 Party, SC5 TransportMeans -
and every attribute names the superclass element it realises. The model therefore does state that a
Carrier is a Party, and that Agent identifier and Carrier identifier are both S009, identification.

| Release | Classes with a superclass | Attributes realising a superclass element |
|---|---|---|
| 4.0.0 | 163 of 260 | 540 of 1,092 |
| 4.1.0 | 167 of 266 | 557 of 1,146 |
| 4.2.0 | 170 of 273 | 558 of 1,152 |
| 4.3.0 | 170 of 273 | 559 of 1,156 |

There is no Party row in the class list, nothing inherits, and each subclass restates the inherited
elements under its own name. The published artefacts carry none of it.

An earlier version of this note said the model had no generalization. That was wrong: it has one,
in columns 23 to 26 of the Library sheet, which the extractor was not reading. The site now
publishes it - five minted superclasses, `rdfs:subClassOf` on the 170 classes that carry one, and
the superclass element on each property - without merging anything on that basis, so no term moved.

The duplication is what remains. Ninety classes are flagged PAR; taken as named they have 90
distinct attribute signatures, and with the class name removed from each attribute they collapse to
28, one of which covers 43 of them: identifier, name, identification issuing country code, role
code. 83 of the 90 already carry a Role code attribute, so the role is stated three times - as the
class, as the superclass link, and as a value.

**Why:** the question of when a thing deserves its own class has been answered differently in
different parts of the model, and the model states no rule.

**How to apply:** a class earns its identity when it has state or structure the general class does
not. The model already has the data to test it: a class whose attributes all realise superclass
elements has nothing of its own.

## 2. Nothing in any Information Package is mandatory

Every position in all four packages is `0..1` or `0..unbounded`. There is not one minimum of 1 in
9,064 Declaration positions, 763 LPCO, 440 AIP or 67 MDIP.

That is defensible - a Base Information Package is a catalogue, and obligation belongs to the
regulation that uses it - but it means a schema generated faithfully from a package accepts an
almost empty document, and that the first real narrowing is the derived package. It also means the
model offers no machine-readable statement of what any message actually needs, which is the thing
an implementer asks for first.

## 3. Attributes are named inside their class, so the same concept is defined many times

`identifier` occurs 174 times across the Library and `typeCode` 49, each as a separate attribute
with its own ID and its own definition. The definitions are usually the same sentence with the
class name substituted.

This is what the published vocabulary merges: an attribute sharing a local name and a core data
type becomes one property carrying many `schema:domainIncludes`, with each class-specific wording
kept as a scope note. The merge is only safe where the value domains agree, and in twelve cases
they did not, which is itself the useful signal: those are the places where one name was doing two
jobs.

## 4. A code list is cited in prose, and most citations do not resolve to one list

The register (DataSet 1.6) names the basis of each code list as free text, and so do the attributes
that cite it. Of the 573 citations, 214 resolve to exactly one of the 135 register entries; 140
match several, because registered lists share basis strings; 219 match none. Of those 219, the ones
naming an external authority's list - "UN/EDIFACT code list 3035", "ISO 3166-1 alpha-2" - are
published here as 36 referenced schemes with no values, and 138 are guidance rather than a
reference, for example "User code list (see EU CDM code list for DE 11 10 001 000)".

Counts: `python3 scripts/build_vocabulary.py` reports 135 registered and 36 referenced schemes; the
citation breakdown is a join of intermediate/attributes.json against intermediate/code-lists.json.

A consumer cannot tell from the register alone whether a list has values, where they come from, or
whether two attributes citing the same prose string mean the same list. A basis expressed as an
identifier rather than a sentence would settle all three.
