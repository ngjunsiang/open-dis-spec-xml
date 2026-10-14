#!/usr/bin/env python3
"""Census of SISO-REF-056-2018 (XML Style Guide) hygiene for the xml/ set.

Measures the transferable subset of REF-056 best practices (the PDU XML is
a generator vocabulary, not an xsd:schema product, so most BPs apply by
analogy): document metadata/versioning, namespace discipline, component
documentation coverage, machine-readable-annotation namespacing, duplicate
definitions, identifier hygiene, and content-mutating defaults.

Read-only. Results are recorded and interpreted in
docs/ref056-compliance.md; re-run after any xml/ change and refresh the
report if numbers move:

    python3 scripts/ref056_check.py            # census xml/ (default)
    python3 scripts/ref056_check.py OTHER_DIR  # census any other set,
                                               # e.g. an upstream checkout
"""
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

FIELD_TAGS = {
    "primitive", "primitivelist", "objectlist",
    "sisoenum", "sisobitfield", "attribute", "padtoboundary", "enum",
}
# Conditional-selection vocabulary (drives generator branching)
COND_VOCAB = {
    "presentIf", "when", "countExpression", "countFieldName",
    "countListFieldName", "bitCountExpression", "aliasFor",
}
# Structural joins (enumeration references), ubiquitous rather than conditional
STRUCT_VOCAB = {"uid", "size"}
XML_NAME_BAD = re.compile(r"[_.]|\d")


def default_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "xml"


def parse_family(dirpath: Path):
    """Yield (file, class-elem) for master + each family file, xi:include-free."""
    files = [dirpath / "DIS_7_2012.xml"] + sorted(dirpath.glob("*FamilyPdus.xml"))
    for f in files:
        try:
            tree = etree.parse(str(f))
        except etree.XMLSyntaxError as e:
            print(f"WELLFORMEDNESS: FAIL {f.name}: {e}")
            continue
        for cls in tree.getroot().iter("class"):
            yield f.name, cls


def main(dirpath: Path):
    root = etree.parse(str(dirpath / "DIS_7_2012.xml")).getroot()
    print(f"== Document metadata ({dirpath.name})")
    print(f"root element: <{root.tag}> attributes={dict(root.attrib) or '(none)'}")
    print(f"namespaces declared: "
          f"{sorted(k for k in root.nsmap if k)}")
    print(f"version attribute present: {'version' in root.attrib}")

    classes_total = classes_doc = fields_total = fields_doc = 0
    class_names, field_names, item_names = [], [], []
    defaults = Counter()
    cond_vocab = Counter()
    struct_vocab = Counter()
    cond_namespaced = 0
    sig_groups = defaultdict(list)
    wellformed = True

    for fname, cls in parse_family(dirpath):
        classes_total += 1
        name = cls.get("name", "(none)")
        class_names.append(name)
        if cls.get("comment"):
            classes_doc += 1
        if "aliasFor" in cls.attrib:
            cond_vocab["aliasFor"] += 1
            if cls.get("aliasFor", "").startswith("{"):
                cond_namespaced += 1
        sig = []
        for elem in cls.iter():
            if elem is cls:
                continue
            if elem.tag in FIELD_TAGS:
                fields_total += 1
                if elem.get("comment"):
                    fields_doc += 1
                fname_ = elem.get("name", "(none)")
                field_names.append(fname_)
                sig.append((elem.tag, fname_, elem.get("type", "")))
            for k in elem.attrib:
                if k in COND_VOCAB:
                    cond_vocab[k] += 1
                    if k.startswith("{"):
                        cond_namespaced += 1
                elif k in STRUCT_VOCAB:
                    struct_vocab[k] += 1
                elif k == "default":
                    defaults[elem.tag] += 1
            if elem.tag == "item":
                item_names.append(elem.get("name", "(none)"))
        if sig:
            body = hashlib.md5(repr(sorted(sig)).encode()).hexdigest()
            sig_groups[body].append(name)

    bad_idents = sorted(n for n in class_names + field_names + item_names
                        if XML_NAME_BAD.search(n))
    dupes = {sig: names for sig, names in sig_groups.items() if len(names) > 1}

    print(f"\n== Well-formedness: all files parsed"
          if wellformed else "\n== Well-formedness: FAILURES above")

    print(f"\n== Documentation coverage (comment= attribute)")
    print(f"classes documented: {classes_doc}/{classes_total} "
          f"({100*classes_doc/max(classes_total,1):.0f}%)")
    print(f"fields  documented: {fields_doc}/{fields_total} "
          f"({100*fields_doc/max(fields_total,1):.0f}%)")
    undocumented = [c.get("name") for _, c in parse_family(dirpath)
                    if not c.get("comment")]
    print(f"example undocumented classes: {undocumented[:8]}")

    print(f"\n== Machine-readable vocabulary (BP 8-43/8-44 analogue)")
    print(f"conditional vocabulary (bare attributes): "
          f"{sum(cond_vocab.values())} {dict(cond_vocab)}")
    print(f"structural joins uid=/size=:             "
          f"{sum(struct_vocab.values())} {dict(struct_vocab)}")
    print(f"namespaced usage:                        {cond_namespaced}")

    print(f"\n== Duplicate class field-signatures (Principle 16)")
    print(f"signature groups with >1 class: {len(dupes)}")
    for names in sorted(dupes.values(), key=len, reverse=True)[:6]:
        print(f"  x{len(names)}: {sorted(names)}")

    print(f"\n== Identifier hygiene (BP 10-3/10-7)")
    print(f"names with underscore/period/digits: {len(bad_idents)}")
    for n in bad_idents[:12]:
        print(f"  {n}")
    lower_classes = [n for n in class_names if n[:1].islower()]
    print(f"class-style names starting lowercase: {len(lower_classes)} {lower_classes[:5]}")

    print(f"\n== Defaults (BP 8-20/8-21 analogue)")
    print(f"default= usage: {sum(defaults.values())} {dict(defaults)} or none")


if __name__ == "__main__":
    arg = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_dir()
    main(arg)
