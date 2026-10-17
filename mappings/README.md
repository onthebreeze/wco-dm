# Mappings to vocab.unece.org

`wco-to-unece.csv` is the ledger of record. `../ontology/mappings.ttl` is generated from it and
should not be edited: change the `decision` column here, run `scripts/map_to_unece.py` again, and the
TTL is rebuilt.

| Column | Meaning |
|---|---|
| `score` | 0 to 1, from the named signals in `evidence`. At or above 0.90 the script proposes acceptance; between 0.42 and 0.90 it proposes review; below that it says nothing. |
| `relation` | `skos:exactMatch` for a near-certain equivalence, `skos:closeMatch` for the same concept differently expressed, `skos:relatedMatch` where one vocabulary models as a class what the other models as a property. |
| `decision` | `accepted` or `review`. Change it by hand to accept or reject a candidate. |
| `decided_by` | `auto` if the script set it, `human` if a reviewer did. Only a human decision survives the next run, so thresholds can be changed without losing review work. |

## What the numbers mean

112 candidates over 105 of 692 WCO terms. That is a real result rather than a weak one: the two
vocabularies cover overlapping but different ground, and proposing more would be guessing.

The `skos:relatedMatch` rows are the most interesting. WCO models Consignor, Carrier and Importer as
classes; vocab.unece.org models `consignor`, `carrier` and `importer` as properties. Neither is
wrong, and the relation between them is exactly what a reader crossing from one vocabulary to the
other needs to know.
