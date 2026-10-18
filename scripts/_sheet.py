"""Finding a column by what it is called, not by where it sits.

The four releases do not agree on layout. 4.3.0 adds a JSON Tag Name column, which shifts
everything after it by one; 4.0.0 calls the path column XPath where the others call it UML Model
Path; 4.2.0 writes Attribute UPI where the others write Attr. UPI. Reading by position would need a
table of offsets per release, and would fail silently when a release moved something, so every
column here is resolved by its heading.

Some headings repeat - the Library has a Class Name in the main block and another under SuperClass,
and two columns simply called ID - so a lookup can be qualified by the group label above it, which
the sheets carry in a row of their own and which this module carries forward across the blank cells
that follow it.
"""


def _text(cell):
    return str(cell).replace("\n", " ").strip() if cell is not None else ""


class Headings:
    def __init__(self, ws, header_row, group_rows=()):
        rows = list(ws.iter_rows(min_row=1, max_row=header_row, values_only=True))
        self.headings = [_text(c) for c in rows[header_row - 1]]
        # A group label sits above the first column of its block and the rest are blank, so it is
        # carried forward until the next label.
        self.groups = [""] * len(self.headings)
        for gr in group_rows:
            if gr > len(rows):
                continue
            current = ""
            for i in range(len(self.headings)):
                label = _text(rows[gr - 1][i]) if i < len(rows[gr - 1]) else ""
                if label:
                    current = label
                if i < len(self.groups) and not self.groups[i]:
                    self.groups[i] = current
        self.by_heading = {}
        for i, h in enumerate(self.headings):
            if h and h not in self.by_heading:
                self.by_heading[h] = i

    def find(self, *names, group=None):
        """The index of the first of `names` that is present, optionally within `group`."""
        for name in names:
            if group is None:
                if name in self.by_heading:
                    return self.by_heading[name]
            else:
                for i, h in enumerate(self.headings):
                    if h == name and self.groups[i].lower().startswith(group.lower()):
                        return i
        return None

    def require(self, *names, group=None):
        i = self.find(*names, group=group)
        if i is None:
            raise KeyError(f"no column named {' or '.join(names)}"
                           + (f" in group {group}" if group else ""))
        return i

    def columns_in(self, group, stop_groups=()):
        """Every named column of one group, stopping where another named block begins.

        The package workbooks put the derived-package flags in a group of their own, then continue
        with unrelated blocks - the IMO Compendium mapping, the per-message names - which the group
        row does not re-label. `stop_groups` names the blocks from a different row that end it.
        """
        out = []
        started = False
        for i, h in enumerate(self.headings):
            in_group = self.groups[i].lower().startswith(group.lower())
            if in_group:
                started = True
            elif started:
                break
            if in_group and h and h not in stop_groups:
                out.append((i, h))
        return out
