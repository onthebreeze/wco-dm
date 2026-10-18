# Observations on the model

Things that publishing the WCO Data Model as linked data made visible. None of them is a defect in
the publication, and nothing here has been acted on: the site renders the model as the workbooks
give it. They are recorded because each is a question for the model itself, and the evidence is
cheap to reproduce now that the source is extracted.

Every count below comes from WCO Data Model 4.3.0, Library workbook, sheet `DataSet 1.2, 1.3, 1.4`.

## 1. Roles are modelled as classes, and the model also carries the role as data

The Library has one device that looks like generalization: the **SuperClass Usage** columns, which
flag each class as NONE, DOC, GOV, LOC, PAR or TRA. 171 of the 273 classes carry one. Exactly one
class carries two.

It is a flag rather than a parent. There is no `Party` class, no `Location` class and no `Document`
class in the Library, so there is nothing for a subclass to point at and nothing to inherit. What
the flag marks is that the class *uses* the superclass's standard attributes, and each class then
restates them under its own name: `Agent identifier`, `Applicant identifier`,
`Assembler identifier`.

The effect is clearest in the party superclass.

| | |
|---|---|
| Classes flagged PAR | 90 |
| Distinct attribute signatures, taking the attributes as named | 90 |
| Distinct attribute signatures, after removing the class name from each attribute | 28 |
| Classes sharing the single commonest signature | 43 |

That signature is `identifier`, `name`, `identification issuing country code`, `role code`. Ten
further classes carry the same minus the name, and five add a category of person code, so about 58
of the 90 differ from one another in nothing but what they are called: Applicant, Assembler,
Authenticator, AuthorizedPerson, Carrier, Consolidator, ConsortiumCarrier, Deconsolidator,
Distiller, Stevedore, and the rest.

**83 of the 90 already carry a Role code attribute.** The model therefore expresses the role twice,
once as the class and once as a value inside it, and two statements that can disagree.

The same pattern is milder elsewhere. 14 of the 23 classes flagged GOV have exactly one attribute,
an identifier: AppealOffice, BorderingOffice, ContactOffice, ExitOffice, ExportOffice,
GuaranteeOffice, ItineraryOffice, PaymentOffice, PresentationOffice, SupervisingOffice and four
more. Six of the 33 flagged LOC are an identifier and a name.

Not every one of them is a role. MasterDataOffice carries a country code and a validity period;
EntryOffice carries a sequence number; the transport classes each have substantial structure of
their own. The point is that the model has no stated rule separating the two cases, so the question
has been answered differently in different places.

### A candidate principle

A class earns its own identity when it has state or structure that the general class does not: an
attribute, a relationship or a lifecycle of its own. A distinction carried entirely by which
property points at it is a **role**, and a role belongs in the data or in the property name at the
point of use, not in a new class.

A usable test: strip the class name from the front of each of its attributes. If what remains is a
subset of the general class's attributes, it is a role.

### What is on the other side of the argument

The role-as-class pattern is not an accident and it buys three things in a message. The tag names
the position unambiguously without a discriminator, which matters in XML and in EDIFACT before it.
Cardinality can differ per role - one Exporter, many Carriers - without a conditional rule. And a
constraint can be attached to one role without attaching it to parties in general.

The cost is paid in the Library rather than in the message: 90 party classes, an `identifier`
attribute defined 174 times across the model, and a vocabulary that cannot say two of these classes
are the same kind of thing. Whether that trade is still the right one is the discussion, and it is
a different question for a message format than for a published vocabulary, which is part of why it
is worth having now.

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

## 4. A quarter of the code list register does not resolve to a list

The register (DataSet 1.6) names the basis of each code list as free text. 215 entries join cleanly
to a list. 36 name an external authority's list that the register does not hold - "UN/EDIFACT code
list 3035", "ISO 3166-1 alpha-2" - and are published here as referenced schemes with no values. 25
are prose guidance rather than a reference at all, for example "User code list (see EU CDM code list
for DE 11 10 001 000)".

A consumer cannot tell from the register alone whether a list has values, where they come from, or
whether two attributes citing the same prose string mean the same list. A basis expressed as an
identifier rather than a sentence would settle all three.
