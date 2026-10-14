#!/usr/bin/env python3
"""DIS 7 XML standardization transform.

Reads the pristine XML set from .references/ and writes corrected copies to
xml-fixed/ — the source files are never modified. Every change is logged with
its evidence citation to xml-fixed/changes.json, which feeds
changes-evidence.md and overrides.json (the interim generator input per the
pinned ruling in .references/decisions.md).

Vocabulary added (documented in changes-evidence.md):
  presentIf="term [| term] [& term]"  on <attribute> and on variant children
      (<sisoenum>/<sisobitfield>/<primitive>) inside a record class —
      presence condition. A term is field:bit, field:bit=0, field:bit=1,
      or field=V (enum compare). Paths may cross into sibling records
      ("entityType.entityKind"). Inside a classRef'd record, unqualified
      names resolve against the OWNING PDU's fields (cross-scope rule).
      & binds tighter than |.
  when="term"                          on <classRef>/<sisoenum>/
      <sisobitfield> variants — selects among alternative shapes.
  countExpression="a * b - c"          on lists — element-count arithmetic.
  bitCountExpression="a * b"           on lists — length-in-bits arithmetic.
  countListFieldName="X"               on lists — flat list partitioned into
      runs whose lengths are the elements of sibling list X.
  bitCountFieldName (existing upstream attr, reused) — length in bits from
      a single field.
  uid="N" size="8|16|32"               on <sisoenum>/<sisobitfield>.

Fails loud on anything unexpected. Exit non-zero => no output written.
"""
import copy
import io
import json
import os
import re
import zipfile
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                               # spec repo root
OUT = os.path.join(ROOT, "xml")                            # corrected set
SRC = os.environ.get("SPEC_UPSTREAM_DIR", os.path.join(ROOT, "upstream"))
REF010_XML = os.path.join(ROOT, "ref010", "SISO-REF-010.xml")

CHANGES = []


def log(kind, fname, cls, field, detail, evidence):
    CHANGES.append(dict(kind=kind, file=fname, klass=cls, field=field,
                        detail=detail, evidence=evidence))


def fail(msg):
    raise SystemExit(f"fix.py: FATAL: {msg}")


def tag_of(el):
    """Local tag name for real elements, None for comments/PIs."""
    if not isinstance(el.tag, str):
        return None
    return etree.QName(el).localname


# ---------------------------------------------------------------- REF-010 --
def build_ref_join():
    root = etree.parse(REF010_XML).getroot()
    join = {}
    for el in root.iter():
        tag = tag_of(el)
        if tag in ("enum", "bitfield") and el.get("uid"):
            join[int(el.get("uid"))] = dict(name=el.get("name"),
                                            size=el.get("size"), kind=tag)
    if not join:
        fail("REF-010 parse produced no tables")
    return join


UID_COMMENT_RE = [
    (re.compile(r"^(?:uid|UID)\s*=\s*(\d+)"), "eq"),
    (re.compile(r"^(?:uid|UID) (\d+)$"), "clean"),
    (re.compile(r"^(?:uid|UID) (\d+)\b"), "prose"),
    (re.compile(r"^(\d+)$"), "bare"),
]


def uid_from_comment(text):
    for rx, kind in UID_COMMENT_RE:
        m = rx.match(text.strip())
        if m:
            return int(m.group(1)), kind
    return None, None


# ------------------------------------------------------------- xml helpers --
CLASSES = {}
PARSER = etree.XMLParser(remove_blank_text=False, remove_comments=False,
                         resolve_entities=False)


def parse_files():
    trees, order = {}, []
    for fname in sorted(os.listdir(SRC)):
        if not fname.endswith(".xml") or fname.startswith("SISO"):
            continue
        trees[fname] = etree.parse(os.path.join(SRC, fname), PARSER)
        order.append(fname)
    for fname, tree in trees.items():
        for cls in tree.getroot().iter("class"):
            name = cls.get("name")
            if cls.get("aliasFor"):
                continue
            key = (fname, name)
            if key in CLASSES:
                fail(f"duplicate class declaration {key}")
            CLASSES[key] = cls
    return trees, order


def get_class(fname, name):
    el = CLASSES.get((fname, name))
    if el is not None:
        return el
    hits = [v for (f, n), v in CLASSES.items() if n == name]
    if not hits:
        fail(f"class {name!r} not found (needed by {fname})")
    if len(hits) > 1:
        fail(f"ambiguous class name {name!r}")
    return hits[0]


def get_attr(cls, name):
    for a in cls.findall("attribute"):
        if a.get("name") == name:
            return a
    fail(f"attribute {name!r} not found on class {cls.get('name')!r}")


def single_child(parent, tag):
    kids = [c for c in parent if tag_of(c) == tag]
    if len(kids) != 1:
        fail(f"expected exactly one <{tag}> under "
             f"{parent.get('name') or parent.tag!r}, got {len(kids)}")
    return kids[0]


def simple_el(tag, attrs, tail_indent):
    e = etree.Element(tag, attrs)
    e.tail = "\n" + " " * tail_indent
    return e


def attribute_el(name, extra, child, indent=8):
    """Attribute wrapping one child; child at indent+4, close at indent."""
    a = etree.Element("attribute", dict(name=name, **extra))
    a.text = "\n" + " " * (indent + 4)
    a.tail = "\n" + " " * indent
    child.tail = "\n" + " " * indent
    a.append(child)
    return a


def class_el(name, comment, attr_specs):
    """attr_specs: list of (attrName, extraAttrs, childTag, childAttrs)."""
    c = etree.Element("class", {
        "name": name, "inheritsFrom": "root", "comment": comment})
    c.text = "\n\n        "
    c.tail = "\n\n    "
    for i, (an, extra, tag, cattrs) in enumerate(attr_specs):
        child = simple_el(tag, cattrs, 12)
        a = etree.Element("attribute", dict(name=an, **extra))
        a.text = "\n            "
        a.tail = "\n        \n    " if i < len(attr_specs) - 1 else "\n    "
        child.tail = "\n        "
        a.append(child)
        c.append(a)
        _ = a
    return c


def append_class(tree, cls):
    root = tree.getroot()
    last = [c for c in root if tag_of(c) == "class"][-1]
    root.insert(list(root).index(last) + 1, cls)


def replace_child(parent, old, new):
    idx = list(parent).index(old)
    old_tail = old.tail
    parent.remove(old)
    parent.insert(idx, new)
    new.tail = old_tail


def insert_after(parent, anchor, new):
    parent.insert(list(parent).index(anchor) + 1, new)


def census_classref(trees, name):
    return [e for t in trees.values()
            for e in t.getroot().iter("classRef")
            if e.get("name") == name]


# ==================================================================== MAIN ==
def main():
    ref = build_ref_join()
    trees, order = parse_files()

    t_enrich_uids(trees, ref)
    t_default_values(trees)
    t_entitytype_domain(trees)
    t_entity_appearance(trees)
    t_pdu_status_flatten(trees)
    t_length_sources(trees)
    t_minefield(trees)
    t_issue18(trees)
    t_live_entity(trees)
    t_aliases(trees)
    t_citations(trees)

    os.makedirs(OUT, exist_ok=True)
    import re as _re
    for fname in order:
        raw = open(os.path.join(SRC, fname), "rb").read()
        m = _re.search(rb"<classes[\s>]", raw)
        if not m:
            fail(f"{fname}: root <classes> element not found")
        prolog = raw[:m.start()]          # declaration + leading comments,
                                          # byte-identical to the source
        body = etree.tostring(trees[fname].getroot(), encoding="UTF-8")
        with open(os.path.join(OUT, fname), "wb") as fh:
            fh.write(prolog + body + b"\n")
    with open(os.path.join(OUT, "changes.json"), "w") as fh:
        json.dump(CHANGES, fh, indent=1)
    print(f"wrote {len(order)} files + changes.json "
          f"({len(CHANGES)} changes) to {OUT}/")


# ------------------------------------------------------- 1. uid + size attrs
def t_enrich_uids(trees, ref):
    n = 0
    for fname, tree in trees.items():
        for e in tree.getroot().iter():
            if tag_of(e) not in ("sisoenum", "sisobitfield"):
                continue
            ctext = (e.get("comment") or "").strip()
            uid, fmt = uid_from_comment(ctext)
            if uid is None:
                fail(f"{fname}: no uid parseable from comment {ctext!r} "
                     f"(type {e.get('type')!r})")
            if uid not in ref:
                fail(f"{fname}: uid {uid} absent from REF-010 v37")
            e.set("uid", str(uid))
            e.set("size", ref[uid]["size"])
            n += 1
            if fmt in ("eq", "bare"):
                new = (re.sub(r"^(?:uid|UID)\s*=\s*(\d+)", r"uid \1", ctext)
                       if fmt == "eq" else f"uid {ctext}")
                e.set("comment", new)
                log("ENRICH-comment", fname, "?", e.get("type"),
                    f"comment {ctext!r} -> {new!r}",
                    "uid moved to attribute; comment normalized to 'uid N'")
    log("ENRICH-uid-size", "(all)", "-", "-",
        f"added uid= and size= to {n} sisoenum/sisobitfield elements "
        f"(129 distinct uids; sizes from SISO-REF-010 v37 join)",
        "SISO-REF-010 v37 enum/bitfield size attributes")


# ------------------------------------------------------------- 2. defaults
def t_default_values(trees):
    ok_sym = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Z0-9_]+$")
    for fname, tree in trees.items():
        for e in tree.getroot().iter():
            if tag_of(e) not in ("sisoenum", "sisobitfield", "primitive",
                                 "classRef"):
                continue
            dv = e.get("defaultValue")
            if dv is None:
                continue
            if "new " in dv or ".inst(" in dv:
                e.set("defaultValue", "0")
                log("FIX-default", fname, "?", e.get("type") or e.get("name"),
                    f'defaultValue {dv!r} -> "0" (Java source literal '
                    "removed)",
                    "bitfield default zero = no flags set; normalized "
                    "vocabulary is integers or EnumType.MEMBER symbols")
            elif not (dv.isdigit() or ok_sym.match(dv) or
                      re.match(r"^-?\d+\.\d+$", dv)):
                fail(f"{fname}: unnormalized defaultValue {dv!r}")


# ------------------------------------------- 3. EntityType.domain dual table
def t_entitytype_domain(trees):
    fname = "DIS_7_2012.xml"
    et = get_class(fname, "EntityType")
    dom = get_attr(et, "domain")
    old = single_child(dom, "classRef")
    assert old.get("name") == "Domain"
    # ordering convention: conditional variant first, default LAST
    # (legacy SAX generators are last-wins)
    mun = simple_el("sisoenum",
                    {"type": "MunitionDomain", "uid": "14", "size": "8",
                     "when": "entityKind=2",
                     "comment": "uid 14 applies when entityKind = 2 "
                                "(Munition); uid 8 otherwise. SupplyDomain "
                                "uid 600 (kind 6) is not used by DIS 7 "
                                "entity types"}, 12)
    mun.tail = "\n            "
    base = simple_el("sisoenum",
                     {"type": "PlatformDomain", "uid": "8", "size": "8",
                      "defaultValue": "PlatformDomain.OTHER"}, 8)
    base.tail = "\n        "
    replace_child(dom, old, mun)
    dom.insert(list(dom).index(mun) + 1, base)
    log("WIRE-repr", fname, "EntityType", "domain",
        "classRef Domain (specialCase domainHolder) -> conditional sisoenum "
        "variants: uid 14 MunitionDomain when entityKind=2 first, uid 8 "
        "PlatformDomain default LAST (variant ordering convention)",
        "IEEE 1278.1-2012 6.2.30 Entity Type record; kind-conditional uid "
        "ruled in .references/decisions.md (exemplar section 9.4)")
    refs = census_classref(trees, "Domain")
    if refs:
        fail(f"Domain class still referenced {len(refs)}x after rewrite")
    dom_cls = get_class(fname, "Domain")
    dom_cls.getparent().remove(dom_cls)
    log("FIX-cleanup", fname, "Domain", "-",
        "deleted specialCase=domainHolder class (zero refs after rewrite)",
        "replaced by conditional sisoenum variants")


# ------------------------------------------ 4. Entity Appearance uids 31-43
APPEAR_VARIANTS = [
    (32, "AirPlatformAppearance",
     "entityType.entityKind=1 & entityType.domain=2"),
    (33, "SurfacePlatformAppearance",
     "entityType.entityKind=1 & entityType.domain=3"),
    (34, "SubsurfacePlatformAppearance",
     "entityType.entityKind=1 & entityType.domain=4"),
    (35, "SpacePlatformAppearance",
     "entityType.entityKind=1 & entityType.domain=5"),
    (36, "MunitionAppearance", "entityType.entityKind=2"),
    (37, "LifeFormsAppearance", "entityType.entityKind=3"),
    (38, "EnvironmentalAppearance", "entityType.entityKind=4"),
    (39, "CulturalFeatureAppearance", "entityType.entityKind=5"),
    (40, "SupplyAppearance", "entityType.entityKind=6"),
    (41, "RadioAppearance", "entityType.entityKind=7"),
    (42, "ExpendableAppearance", "entityType.entityKind=8"),
    (43, "SensorEmitterAppearance", "entityType.entityKind=9"),
    (31, "LandPlatformAppearance", None),
]


def t_entity_appearance(trees):
    fname_main = "DIS_7_2012.xml"
    cls = etree.Element("class", {
        "name": "EntityAppearance", "inheritsFrom": "root",
        "comment": "Entity Appearance record: one 32-bit record whose bit "
                   "layout is selected by entity kind and domain "
                   "(Section 6.2.26, [UID 31-43]). If the referencing PDU "
                   "carries no entityType (EntityStateUpdatePdu), the "
                   "receiving application resolves the variant from its "
                   "cached entity type."})
    cls.text = "\n\n        "
    cls.tail = "\n\n    "
    value = etree.Element("attribute", {
        "name": "value",
        "comment": "Exactly one variant is present: the first whose when= "
                   "matches; the Land variant (no when=) is the default "
                   "(domain 1, 0 or unspecified). Paths resolve against "
                   "the referencing PDU's fields (entityType.entityKind / "
                   "entityType.domain)."})
    value.text = "\n            "
    value.tail = "\n    "
    for uid, typ, when in APPEAR_VARIANTS:
        attrs = {"type": typ, "uid": str(uid), "size": "32"}
        if when:
            attrs["when"] = when
        else:
            attrs["comment"] = ("uid 31; default variant (Land and "
                                "other/unspecified domains)")
        child = simple_el("sisobitfield", attrs, 12)
        child.tail = "\n            "
        value.append(child)
    value[-1].tail = "\n        "
    cls.append(value)
    append_class(trees[fname_main], cls)
    log("ADD-class", fname_main, "EntityAppearance", "-",
        "new record class: value attribute wrapping 13 kind/domain-"
        "conditional 32-bit appearance variants (uids 31-43); exactly one "
        "variant present, Land default",
        "IEEE 1278.1-2012 6.2.26 Entity Appearance record [UID 31-43]; "
        "REF-010 v37 bitfield tables")

    fname = "EntityInformationFamilyPdus.xml"
    n = 0
    for cls in trees[fname].getroot().iter("class"):
        if cls.get("aliasFor"):
            continue
        for a in cls.findall("attribute"):
            if a.get("name") != "entityAppearance":
                continue
            old = single_child(a, "primitive")
            if old.get("type") != "uint32":
                fail("entityAppearance not a uint32 in "
                     f"{cls.get('name')}")
            new = simple_el("classRef", {"name": "EntityAppearance"}, 12)
            replace_child(a, old, new)
            if "entityType" not in [x.get("name") for x in
                                    cls.findall("attribute")]:
                a.set("comment", (a.get("comment") or "").rstrip() +
                       " This PDU carries no entityType; the appearance "
                       "variant is resolved from the receiving "
                       "application's cached entity type.")
            n += 1
            log("WIRE-repr", fname, cls.get("name"), "entityAppearance",
                "plain uint32 -> classRef EntityAppearance (13 conditional "
                "variants, uids 31-43)",
                "IEEE 1278.1-2012 6.2.26 Entity Appearance record; "
                "5.3.2/7.6.2 Entity State PDU, 7.6.3 Entity State Update "
                "PDU formats")
    if n != 2:
        fail(f"expected 2 entityAppearance sites, patched {n}")


# ------------------------------------------------- 5. PduStatus flatten
def t_pdu_status_flatten(trees):
    fname = "DIS_7_2012.xml"
    attr = get_attr(get_class(fname, "PduBase"), "pduStatus")
    old = single_child(attr, "classRef")
    assert old.get("name") == "PduStatus"
    new = simple_el(
        "sisobitfield",
        {"type": "PduStatus", "size": "8", "defaultValue": "0",
         "comment": "uid-less 8-bit record per 6.2.67; sub-field enums: "
                    "TEI 301, LVC 302, CEI 303, FTI 304, DTI 305, RAI 306, "
                    "IAI 307, ISM 308, AII 309 (REF-010 has no single "
                    "umbrella table)"},
        12)
    new.tail = "\n        "
    replace_child(attr, old, new)
    log("WIRE-repr", fname, "PduBase", "pduStatus",
        "classRef to abstract single-field PduStatus record -> inline "
        "sisobitfield u8 (flatten-to-primitive applied in the XML)",
        "IEEE 1278.1-2012 6.2.67 PDU Status record; 7.2.2 PDU Header")
    if census_classref(trees, "PduStatus"):
        fail("PduStatus still referenced")
    st = get_class(fname, "PduStatus")
    st.getparent().remove(st)
    log("FIX-cleanup", fname, "PduStatus", "-",
        "deleted abstract wrapper class (zero refs after inlining)",
        "kickoff scope: flatten vs inline decided — inline")


# ------------------------------------------------- 6. length sources
def t_length_sources(trees):
    f = "DIS_7_2012.xml"

    mp = get_class(f, "ModulationParameters")
    pl = single_child(get_attr(mp, "recordSpecificFields"), "primitivelist")
    pl.set("isDynamicListLengthField", "true")
    log("ENRICH-length", f, "ModulationParameters", "recordSpecificFields",
        'marked isDynamicListLengthField="true" (no length field exists; '
        "content defined per radio system in Annex C)",
        "IEEE 1278.1-2012 6.2.58 + Annex C; Table 89 shows per-field R1..RN "
        "octets with no count field")

    rse = get_class(f, "RecordSpecificationElement")
    pl = single_child(get_attr(rse, "recordValues"), "primitivelist")
    pl.set("bitCountExpression", "recordLength * recordCount")
    log("ENRICH-length", f, "RecordSpecificationElement", "recordValues",
        'added bitCountExpression="recordLength * recordCount"',
        "IEEE 1278.1-2012 6.2.73 d)-f): Record Length is in bits; Record "
        "Values length = Record Length x Record Count, in bits")
    a = get_attr(rse, "padTo64")
    old = single_child(a, "primitivelist")
    new = simple_el("padtoboundary", {"length": "64"}, 12)
    new.tail = "\n        "
    replace_child(a, old, new)
    log("FIX-length", f, "RecordSpecificationElement", "padTo64",
        "unsized primitivelist -> padtoboundary 64",
        "IEEE 1278.1-2012 6.2.73 g): 0-63 unused bits for 64-bit alignment")

    env = get_class(f, "Environment")
    pl = single_child(get_attr(env, "geometry"), "primitivelist")
    pl.set("bitCountExpression", "length - 64")
    log("ENRICH-length", f, "Environment", "geometry",
        'added bitCountExpression="length - 64" (length covers the whole '
        "record in bits; fixed header is 64 bits)",
        "IEEE 1278.1-2012 6.2.31 b) Length = length in bits of the "
        "Environment record; type(32)+length(16)+index(8)+pad(8)")

    g = get_class(f, "GridAxisDescriptorVariable")
    pl = single_child(get_attr(g, "xiValues"), "primitivelist")
    pl.set("countFieldName", "numberOfPointsOnXiAxis")
    log("ENRICH-length", f, "GridAxisDescriptorVariable", "xiValues",
        'added countFieldName="numberOfPointsOnXiAxis"',
        "IEEE 1278.1-2012 6.2.42 Grid Axis Descriptor: one Xi value per "
        "grid point on the axis")

    ic = get_class(f, "IntercomCommunicationsParameters")
    pl = single_child(get_attr(ic, "recordSpecificField"), "primitivelist")
    pl.set("countFieldName", "recordLength")
    log("ENRICH-length", f, "IntercomCommunicationsParameters",
        "recordSpecificField", 'added countFieldName="recordLength" '
        "(octets)",
        "IEEE 1278.1-2012 6.2.46 b): Record Length = total length of the "
        "Record-Specific fields in octets")

    vtp = get_class(f, "VariableTransmitterParameters")
    pl = single_child(get_attr(vtp, "recordSpecificFields"), "primitivelist")
    pl.set("countExpression", "recordLength - 6")
    log("ENRICH-length", f, "VariableTransmitterParameters",
        "recordSpecificFields",
        'added countExpression="recordLength - 6" (recordLength covers '
        "type(4)+length(2)+fields+padding)",
        "IEEE 1278.1-2012 6.2.95 b): Record Length = total octets incl. "
        "type, length, fields and 64-bit padding; multiple of 8")
    pad = get_attr(vtp, "padding")
    pad.getparent().remove(pad)
    log("FIX-length", f, "VariableTransmitterParameters", "padding",
        "removed trailing padtoboundary (padding is already inside "
        "recordLength)",
        "IEEE 1278.1-2012 6.2.95 b)")

    fr = "RadioCommunicationsFamilyPdus.xml"
    for cls_name in ("SignalPdu", "IntercomSignalPdu"):
        cls = get_class(fr, cls_name)
        pl = single_child(get_attr(cls, "data"), "primitivelist")
        pl.attrib.pop("countFieldName", None)
        pl.set("bitCountFieldName", "dataLength")
        log("FIX-length", fr, cls_name, "data",
            'length governed by dataLength in bits '
            '(bitCountFieldName="dataLength")'
            + ("; was incorrectly a byte countFieldName" if cls_name ==
               "IntercomSignalPdu" else "; was unsized"),
            "IEEE 1278.1-2012 7.7.4/7.7.6: the Data Length field specifies "
            "the length of the Data field in bits")


# ------------------------------------------------- 7. Minefield Data PDU
def t_minefield(trees):
    f = "MinefieldFamilyPdus.xml"
    md = get_class(f, "MinefieldDataPdu")

    a = get_attr(md, "minefieldSequenceNumbeer")
    a.set("name", "minefieldSequenceNumber")
    log("FIX-typo", f, "MinefieldDataPdu", "minefieldSequenceNumbeer",
        "renamed minefieldSequenceNumbeer -> minefieldSequenceNumber",
        "IEEE 1278.1-2012 7.9.4 d) Minefield Sequence Number")

    a = get_attr(md, "dataFilter")
    old = single_child(a, "classRef")
    assert old.get("name") == "DataFilterRecord"
    new = simple_el(
        "primitive",
        {"type": "uint32",
         "comment": "32-bit Data Filter record (6.2.16, Table 38): bit 0 "
                    "ground burial depth offset, 1 water, 2 snow, 3 mine "
                    "orientation, 4 thermal contrast, 5 reflectance, "
                    "6 mine emplacement time, 7 trip/detonation wire data, "
                    "8 fusing, 9 scalar detection coefficient, 10 paint "
                    "scheme; 11-31 reserved"}, 12)
    new.tail = "\n        "
    replace_child(a, old, new)
    log("WIRE-repr", f, "MinefieldDataPdu", "dataFilter",
        "classRef DataFilterRecord (staticivar bit constants) -> inline "
        "uint32 with 6.2.16 bit-map comment",
        "IEEE 1278.1-2012 6.2.16 Data Filter record, Table 38")
    q = get_class(f, "MinefieldQueryPdu")
    aq = get_attr(q, "dataFilter")
    oldq = single_child(aq, "classRef")
    assert oldq.get("name") == "DataFilterRecord"
    newq = copy.deepcopy(new)
    replace_child(aq, oldq, newq)
    log("WIRE-repr", f, "MinefieldQueryPdu", "dataFilter",
        "classRef DataFilterRecord -> inline uint32 (as MinefieldDataPdu)",
        "IEEE 1278.1-2012 6.2.16; 7.9.3")
    if census_classref(trees, "DataFilterRecord"):
        fail("DataFilterRecord still referenced")
    dfr = get_class("DIS_7_2012.xml", "DataFilterRecord")
    dfr.getparent().remove(dfr)
    log("FIX-cleanup", "DIS_7_2012.xml", "DataFilterRecord", "-",
        "deleted wrapper class with staticivar constants (zero refs)",
        "bit map carried by the inline comment instead")

    spec = [
        ("groundBurialDepthOffset",
         "dataFilter:0 | dataFilter:1 | dataFilter:2", None,
         "G = 1 if any of F0,F1,F2 (6.2.16 a)-c))"),
        ("waterBurialDepthOffset", "dataFilter:1", None, "F1"),
        ("snowBurialDepthOffset", "dataFilter:2", None, "F2"),
        ("mineOrientation",
         "dataFilter:0 | dataFilter:1 | dataFilter:2 | dataFilter:3", None,
         "R = 1 if any of F0..F3 (6.2.16 d))"),
        ("thermalContrast", "dataFilter:4", None, "F4"),
        ("reflectance", "dataFilter:5", None, "F5"),
        ("mineEmplacementTime", "dataFilter:6", None, "F6"),
        ("mineEntityNumber", None, None, "unconditional (16N)"),
        ("fusing", "dataFilter:8", None, "F8"),
        ("scalarDetectionCoefficient", "dataFilter:9",
         "numberOfMinesInThisPdu * numberOfSensorTypes",
         "F9; S = M x N, mine-major runs of M values per 5.10.4.5.1"),
        ("paintScheme", "dataFilter:10", None, "F10"),
        ("numberOfTripDetonationWires", "dataFilter:7", None,
         "F7; one count per mine (NF7)"),
    ]
    for field, cond, expr, why in spec:
        a = get_attr(md, field)
        if cond:
            a.set("presentIf", cond)
        if expr:
            for child in a:
                if tag_of(child) in ("primitivelist", "objectlist"):
                    child.set("countExpression", expr)
        log("WIRE-presence", f, "MinefieldDataPdu", field,
            ((f'presentIf="{cond}" ' if cond else "") +
             (f'countExpression="{expr}"' if expr else "")).strip(),
            f"IEEE 1278.1-2012 Table 189 total-size formula ({why})")

    a = get_attr(md, "numberOfVertices")
    pl = single_child(a, "primitivelist")
    pl.set("countListFieldName", "numberOfTripDetonationWires")
    a.set("presentIf", "dataFilter:7")
    log("FIX-length", f, "MinefieldDataPdu", "numberOfVertices",
        'countListFieldName="numberOfTripDetonationWires" (U = sum of '
        'per-mine wire counts), presentIf dataFilter:7',
        "IEEE 1278.1-2012 7.9.4 z) + Table 189 (8UF7); per-mine runs per "
        "5.10.4.5.2")

    pad4 = attribute_el("padTo32_4", {"presentIf": "dataFilter:7"},
                        simple_el("padtoboundary", {"length": "32"}, 12))
    pad4.tail = "\n        \n        "
    insert_after(md, a, pad4)
    log("WIRE-add", f, "MinefieldDataPdu", "padTo32_4",
        "added missing P4 padding (presentIf dataFilter:7, derived from "
        "UF7 per Table 189)",
        "IEEE 1278.1-2012 Table 189: 8P4 between Number of Vertices and "
        "Vertex fields; P4 = ceil4(U)-U")
    p3 = get_attr(md, "padTo32_3")
    p3.set("presentIf", "dataFilter:7")
    log("WIRE-presence", f, "MinefieldDataPdu", "padTo32_3",
        'presentIf="dataFilter:7" (P3 derived from NF7)',
        "IEEE 1278.1-2012 Table 189: P3 = ceil4(NF7)-NF7")

    verts = etree.Element("attribute", {
        "name": "vertices", "presentIf": "dataFilter:7",
        "comment": "Vertex: Entity Coordinate Vector per "
                   "trip/detonation-wire vertex; wire runs partitioned by "
                   "numberOfVertices (V = sum of J_i), per-mine per-wire "
                   "ordering per 5.10.4.5.3"})
    verts.text = "\n            "
    verts.tail = "\n    \n    "
    ol = etree.Element("objectlist",
                       {"countListFieldName": "numberOfVertices"})
    ol.text = "\n                "
    ol.tail = "\n        "
    cr = simple_el("classRef", {"name": "Vector3Float"}, 16)
    cr.tail = "\n            "
    ol.append(cr)
    verts.append(ol)
    insert_after(md, pad4, verts)
    log("WIRE-add", f, "MinefieldDataPdu", "vertices",
        "added the missing Vertex list (Vector3Float) with runs "
        "partitioned by numberOfVertices",
        "IEEE 1278.1-2012 7.9.4 aa) + Table 189 (96VF7); 5.10.4.5.3 "
        "ordering")


# ---------------------------------------------- 7b. issue #18 type collision
def t_issue18(trees):
    """opendis7-source-generator issue #18: sisoenum type
    EntityAssociationAssociationType was bound to two different REF-010
    tables (uid 330 Association Type at associationType, uid 319
    Association Status at associationStatus). Rename the uid-319 site to
    the REF-010-derived name EntityAssociationAssociationStatus."""
    fname = "DIS_7_2012.xml"
    et = get_class(fname, "EntityAssociationVP")
    a = get_attr(et, "associationStatus")
    e = single_child(a, "sisoenum")
    if e.get("uid") != "319" or e.get("type") != "EntityAssociationAssociationType":
        fail("issue-18 fix: unexpected associationStatus state")
    e.set("type", "EntityAssociationAssociationStatus")
    log("FIX-typo", fname, "EntityAssociationVP", "associationStatus",
        "sisoenum type renamed EntityAssociationAssociationType -> "
        "EntityAssociationAssociationStatus (type name was bound to both "
        "uid 330 and uid 319)",
        "opendis7-source-generator issue #18; SISO-REF-010 v37 uid 319 "
        "'Entity Association-Association Status' vs uid 330 '... Type'; "
        "IEEE 1278.1-2012 6.2.94.4.3 c) [UID 319]")


# ------------------------------------------------- 8. Live Entity family
def t_live_entity(trees):
    f = "LiveEntityFamilyPdus.xml"
    root = trees[f].getroot()
    main = trees["DIS_7_2012.xml"]

    # LE header completion
    lef = get_class(f, "LiveEntityFamilyPdu")
    sub = attribute_el(
        "subprotocolNumber", {},
        simple_el("sisoenum",
                  {"type": "DISLiveEntitySubprotocolNumber", "uid": "417",
                   "size": "8",
                   "comment": "uid 417; subprotocol used to decode the "
                              "PDU. Section 13 of EBV."}, 12))
    anchor = lef.findall("initialValue")[-1]
    anchor.tail = "\n        "   # reopen anchor line at attribute indent
    sub.tail = "\n        \n        "
    insert_after(lef, anchor, sub)
    padattr = attribute_el(
        "padding", {},
        simple_el("primitive",
                  {"type": "uint8", "defaultValue": "0",
                   "comment": "LE PDU Header padding (9.3.2): 8 bits unused"},
                  12))
    padattr.tail = "\n    "
    insert_after(lef, sub, padattr)
    log("WIRE-add", f, "LiveEntityFamilyPdu", "subprotocolNumber",
        "added subprotocolNumber (uid 417) + trailing padding u8 — they "
        "existed only inside the commented-out LiveEntityPdu, so every LE "
        "PDU header was 2 bytes short",
        "IEEE 1278.1-2012 9.3.2 LE PDU Header record; Tables 223/226/229: "
        "LE PDU Header = 96 bits ending Subprotocol Number (8) + Padding "
        "(8)")

    # new records
    append_class(main, class_el(
        "EventIdentifierLiveEntityElided",
        "Event ID, live-entity elided form: Event Number only (16 bits). "
        "Used when the Site/Application numbers equal the Firing Live "
        "Entity ID's and are therefore not included (see 9.4.5 f), "
        "9.4.6 f)). Named shape per the pinned event taxonomy.",
        [("eventNumber", {}, "primitive",
          {"type": "uint16", "comment": "Event number"})]))
    log("ADD-class", "DIS_7_2012.xml", "EventIdentifierLiveEntityElided",
        "-", "declared the missing 2-byte elided event-ID shape",
        "IEEE 1278.1-2012 9.4.5 f): 'shall not be included, and the "
        "associated Fire Flag field bit shall be set to zero'; event "
        "taxonomy in .references/decisions.md")

    append_class(main, class_el(
        "LiveEntityRelativeEntityCoordinates",
        "Location in Entity's Coordinates for LE PDUs: Entity Coordinate "
        "Vector (6.2.96 item a) subject to the decreased field sizes of "
        "the LE protocol — three 16-bit fixed-binary components (48 "
        "bits). See 9.4.6.8 k).",
        [("deltaX", {}, "primitive", {"type": "uint16",
                                       "comment": "16-bit fixed binary"}),
         ("deltaY", {}, "primitive", {"type": "uint16",
                                       "comment": "16-bit fixed binary"}),
         ("deltaZ", {}, "primitive", {"type": "uint16",
                                       "comment": "16-bit fixed binary"})]))
    log("ADD-class", "DIS_7_2012.xml", "LiveEntityRelativeEntityCoordinates",
        "-", "declared the 48-bit LE Location-in-Entity's-Coordinates shape "
        "(was previously mis-modeled as LiveEntityLinearVelocity 3xu16 by "
        "reuse, or LiveEntityRelativeWorldCoordinates 4xu16)",
        "IEEE 1278.1-2012 9.4.6.8 k): Entity Coordinate Vector [6.2.96 "
        "item a)] subject to decreased field sizes; Table 229 term 48F6")

    append_class(main, class_el(
        "LiveEntityIdentifierElided",
        "Live Entity Identifier, elided form: Entity Number only (16 "
        "bits). Used for LE Fire/Detonation Munition ID when the "
        "Site/Application numbers equal the Firing Live Entity ID's "
        "(see 9.4.5 e)).",
        [("entityNumber", {}, "primitive",
          {"type": "uint16", "comment": "Live entity number"})]))
    log("ADD-class", "DIS_7_2012.xml", "LiveEntityIdentifierElided", "-",
        "declared the 2-byte elided munition-ID shape",
        "IEEE 1278.1-2012 9.4.5 e): same-site/app elision rule")

    append_class(main, class_el(
        "LEMunitionDescriptor",
        "Munition Descriptor record (6.2.19.2) as used in the LE "
        "Information/Interaction protocol: warhead, fuse, quantity and "
        "rate are optional, governed by the owning PDU's Fire/Detonation "
        "flag fields (cross-scope presentIf; 9.4.5 h), 9.4.6 j)).",
        [("munitionType", {}, "classRef", {"name": "EntityType"}),
         ("warhead",
          {"presentIf": "fireFlag:4 | detonationFlag1:4"},
          "sisoenum", {"type": "MunitionDescriptorWarhead", "uid": "60",
                       "size": "16"}),
         ("fuse",
          {"presentIf": "fireFlag:4 | detonationFlag1:4"},
          "sisoenum", {"type": "MunitionDescriptorFuse", "uid": "61",
                       "size": "16"}),
         ("quantity", {"presentIf": "fireFlag:5 | detonationFlag1:5"},
          "primitive", {"type": "uint16"}),
         ("rate", {"presentIf": "fireFlag:5 | detonationFlag1:5"},
          "primitive", {"type": "uint16"})]))
    log("ADD-class", "DIS_7_2012.xml", "LEMunitionDescriptor", "-",
        "LE-context Munition Descriptor with flag-conditional warhead/fuse "
        "(bit 4) and quantity/rate (bit 5)",
        "IEEE 1278.1-2012 9.4.5 h) 'the warhead, fuse, quantity, and rate "
        "fields of this record shall be optional'; Tables 225/227 bits 4/5; "
        "Table 189-family formulas 32F4 + 32F5")

    # the 9 EntityID -> LiveEntityIdentifier swaps
    swaps = 0
    for cls in root.iter("class"):
        if cls.get("aliasFor"):
            continue
        for a in cls.findall("attribute"):
            cr = a.find("classRef") if len(a) else None
            if cr is not None and cr.get("name") == "EntityID":
                cr.set("name", "LiveEntityIdentifier")
                swaps += 1
                log("WIRE-ref", f, cls.get("name"), a.get("name"),
                    "classRef EntityID (6-byte standard shape) -> "
                    "LiveEntityIdentifier (4-byte live shape)",
                    "IEEE 1278.1-2012 9.4.2 b)/9.4.3 b)/9.4.4 b)/9.4.5 "
                    "b),d),e)/9.4.6 b),d),e): 'Entity Identifier record "
                    "(see 6.2.28) except that the Site Number and "
                    "Application Number fields shall be only 8 bits long'; "
                    "6.2.53 Live Entity Identifier record")
    if swaps != 9:
        fail(f"expected 9 EntityID swaps in LE family, did {swaps}")

    # ---- AppearancePdu
    ap = get_class(f, "AppearancePdu")
    af = get_attr(ap, "appearanceFlags")
    af.set("name", "appearanceFlag1")
    af.set("comment",
           "Appearance Flag-1 (Table 221): bit 7 flag-2 included, 6 "
           "Appearance-IR, 5 Appearance-Visual, 4 Capabilities, 3 Entity "
           "Marking, 2 Alternate Entity Type, 1 Entity Type, 0 Force ID")
    idx = list(ap).index(af)
    af2 = attribute_el(
        "appearanceFlag2", {"presentIf": "appearanceFlag1:7"},
        simple_el("primitive", {"type": "uint8"}, 12))
    af2.set("comment", "Appearance Flag-2 (Table 222): bit 1 "
                       "Appearance-Audio, bit 0 Appearance-EM; bits 7-2 "
                       "reserved/unused")
    af2.tail = "\n        \n        "
    ap.insert(idx + 1, af2)
    log("WIRE-repr", f, "AppearancePdu", "appearanceFlags",
        "single u16 -> appearanceFlag1 (u8) + appearanceFlag2 (u8, "
        "presentIf appearanceFlag1:7)",
        "IEEE 1278.1-2012 9.4.3.5 c) + Tables 221/222; Table 223 (8F7)")

    for name, bit in (("forceId", "0"), ("entityType", "1"),
                      ("alternateEntityType", "2"), ("entityMarking", "3"),
                      ("capabilities", "4")):
        get_attr(ap, name).set("presentIf", f"appearanceFlag1:{bit}")
    log("WIRE-presence", f, "AppearancePdu",
        "forceId/entityType/alternateEntityType/entityMarking/capabilities",
        "presentIf appearanceFlag1:0..:4 per Table 221",
        "IEEE 1278.1-2012 Table 221; Table 223 formula terms "
        "8F0/64F1/64F2/96F3/32F4")

    app_f = get_attr(ap, "appearanceFields")
    app_f.getparent().remove(app_f)
    for name, cond in (("appearanceVisual", "appearanceFlag1:5"),
                       ("appearanceIR", "appearanceFlag1:6"),
                       ("appearanceEM", "appearanceFlag2:0"),
                       ("appearanceAudio", "appearanceFlag2:1")):
        at = attribute_el(name, {"presentIf": cond},
                          simple_el("classRef",
                                    {"name": "EntityAppearance"}, 12))
        at.tail = "\n        \n        "
        ap.append(at)
        log("WIRE-repr", f, "AppearancePdu", name,
            f"classRef EntityAppearance, presentIf {cond} (was one "
            "unconditional ill-spec'ed 4xu32 appearanceFields)",
            "IEEE 1278.1-2012 9.4.3.5 i)-l) Entity Appearance record "
            "(6.2.26); Table 223 formula 32(F5+F6+G0+G1)")
    if census_classref(trees, "Appearance"):
        fail("Appearance class still referenced")
    appcls = get_class("DIS_7_2012.xml", "Appearance")
    appcls.getparent().remove(appcls)
    log("FIX-cleanup", "DIS_7_2012.xml", "Appearance", "-",
        "deleted ill-spec'ed unconditional Appearance (4xu32) class",
        "IEEE 1278.1-2012 9.4.3.5 i)-l), Table 223")

    # ---- LEFirePdu
    fire = get_class(f, "LEFirePdu")
    fl = get_attr(fire, "flags")
    fl.set("name", "fireFlag")
    fl.set("comment",
           "Fire Flag (Table 225): bit 7 reserved (flag continuation), "
           "6 Location included, 5 Quantity+Rate included, 4 Warhead+Fuse "
           "included, 3 Event ID Site/App included, 2 Munition ID "
           "included, 1 Munition ID Site/App included, 0 Target Entity ID "
           "included")
    log("WIRE-rename", f, "LEFirePdu", "flags",
        "renamed flags -> fireFlag with Table 225 bit-map comment",
        "IEEE 1278.1-2012 9.4.5.6 c); Table 225")

    def set_variants(attr, full, elided, disc):
        """Two classRef variants selected by a 1-bit flag. Ordering
        convention: the full/default shape LAST — legacy SAX generators
        are last-wins, so they degrade onto the correct wire shape."""
        old = attr.find("classRef")
        if old is None:
            fail(f"no classRef under {attr.get('name')}")
        old.set("name", elided)
        old.set("when", f"{disc}=0")
        old.tail = "\n            "
        e2 = simple_el("classRef", {"name": full, "when": f"{disc}=1"}, 8)
        e2.tail = "\n        "
        insert_after(attr, old, e2)

    a = get_attr(fire, "targetLiveEntityId")
    a.set("presentIf", "fireFlag:0")
    a = get_attr(fire, "munitionLiveEntityId")
    a.set("presentIf", "fireFlag:2")
    set_variants(a, "LiveEntityIdentifier", "LiveEntityIdentifierElided",
                 "fireFlag:1")
    set_variants(get_attr(fire, "eventId"),
                 "EventIdentifierLiveEntity",
                 "EventIdentifierLiveEntityElided", "fireFlag:3")
    get_attr(fire, "location").set("presentIf", "fireFlag:6")
    single_child(get_attr(fire, "munitionDescriptor"),
                 "classRef").set("name", "LEMunitionDescriptor")
    log("WIRE-conditional", f, "LEFirePdu",
        "targetLiveEntityId+munitionLiveEntityId+eventId+location+"
        "munitionDescriptor",
        "target presentIf fireFlag:0; munition presentIf fireFlag:2 with "
        "4B/2B variants on fireFlag:1; eventId 4B/2B variants on "
        "fireFlag:3; location presentIf fireFlag:6; descriptor -> "
        "LEMunitionDescriptor",
        "IEEE 1278.1-2012 9.4.5.6 d)-h); Table 226 formula "
        "280 + 32F0 + (16F1+16)F2 + 16F3 + 64F6 + 32F4 + 32F5 bits")

    # ---- LEDetonationPdu
    det = get_class(f, "LEDetonationPdu")
    get_attr(det, "detonationFlag2").set("presentIf", "detonationFlag1:7")
    get_attr(det, "targetLiveEntityId").set("presentIf",
                                            "detonationFlag1:0")
    a = get_attr(det, "munitionLiveEntityId")
    a.set("presentIf", "detonationFlag1:2")
    set_variants(a, "LiveEntityIdentifier", "LiveEntityIdentifierElided",
                 "detonationFlag1:1")
    a = get_attr(det, "eventId")
    a.set("presentIf", "detonationFlag1:7 & detonationFlag2:1")
    set_variants(a, "EventIdentifierLiveEntity",
                 "EventIdentifierLiveEntityElided", "detonationFlag1:3")
    get_attr(det, "worldLocation").set("presentIf", "detonationFlag1:6=0")
    a = get_attr(det, "entityLocation")
    cr = single_child(a, "classRef")
    cr.set("name", "LiveEntityRelativeEntityCoordinates")
    cr.attrib.pop("comment", None)  # stale 'not a typo' note
    a.set("presentIf", "detonationFlag1:6")
    a.set("comment",
          "Location in Entity's Coordinates: three 16-bit fixed binaries "
          "(48 bits; Entity Coordinate Vector with decreased sizes per "
          "9.4.6.8 k)). Previously mis-referenced as "
          "LiveEntityLinearVelocity.")
    get_attr(det, "munitionOrientation").set("presentIf", "detonationFlag2:0")
    single_child(get_attr(det, "munitionDescriptor"),
                 "classRef").set("name", "LEMunitionDescriptor")
    dr = get_attr(det, "detonationResult")
    old = single_child(dr, "primitive")
    new = simple_el("sisoenum",
                    {"type": "DetonationResult", "uid": "62", "size": "8",
                     "comment": "uid 62"}, 12)
    new.tail = "\n        "
    replace_child(dr, old, new)
    log("WIRE-conditional", f, "LEDetonationPdu",
        "detonationFlag2+targetLiveEntityId+munitionLiveEntityId+eventId+"
        "worldLocation+entityLocation+munitionOrientation+"
        "munitionDescriptor+detonationResult",
        "flag-2 presentIf detonationFlag1:7; target :0; munition :2 with "
        "4B/2B variants on :1; eventId presentIf flag1:7 & flag2:1 with "
        "4B/2B variants on :3; worldLocation presentIf :6=0; "
        "entityLocation (re-referenced) presentIf :6; orientation "
        "presentIf flag2:0; descriptor -> LEMunitionDescriptor; result -> "
        "sisoenum uid 62",
        "IEEE 1278.1-2012 9.4.6.8; Tables 227/228/229 formula "
        "256 + 8F7 + 32F0 + (16F1+16)F2 + (16F3+16)G1 + 64(1-F6) + 48G0 "
        "+ 32F4 + 32F5 + 48F6 bits; 9.4.6.8 l) '[UID 62]'")
    log("NOTE", f, "LEDetonationPdu", "firingLiveEntityId",
        "kept unconditional: Table 229's formula includes it in the "
        "256-bit base and no flag bit governs it, contradicting 9.4.6.8 b) "
        "prose",
        "IEEE 1278.1-2012 Table 229 formula vs 9.4.6.8 b)")


# ------------------------------------------------- 9. alias canonicalization
def t_aliases(trees):
    flipped = []
    for fname, tree in trees.items():
        root = tree.getroot()
        for alias in list(root.iter("class")):
            target_name = alias.get("aliasFor")
            if not target_name:
                continue
            alias_name = alias.get("name")
            comment = (alias.get("comment") or "").lower()
            if "more descriptive" not in comment:
                continue
            target = None
            for c in root.iter("class"):
                if c.get("name") == target_name and not c.get("aliasFor"):
                    target = c
                    break
            if target is None:
                fail(f"{fname}: alias {alias_name} -> missing {target_name}")
            target.set("name", alias_name)
            target.set("comment",
                       (target.get("comment") or "").rstrip(". ") +
                       f". Canonical descriptive name; {target_name} is an "
                       f"alias.")
            alias.set("name", target_name)
            alias.set("aliasFor", alias_name)
            alias.set("comment", f"Alias (abbreviation) for {alias_name}.")
            flipped.append((fname, target_name, alias_name))
    for fname, abbr, desc in flipped:
        log("NAMING-canonical", fname, desc, "-",
            f"canonical/descriptive name is now {desc}; {abbr} demoted to "
            "aliasFor (both names resolve; the generator emits one class)",
            "aliasFor ruling in .references/decisions.md: descriptive name "
            "canonical, abbreviation aliased")
    print(f"alias flips: {len(flipped)}")


# ------------------------------------------------- 10. citations
CLASS_CITATION_FIXES = [
    ("DIS_7_2012.xml", "EventIdentifier", "Section 6.2.34",
     "Section 6.2.33", "6.2.33 Event Identifier record (6.2.34 = Exercise "
     "identifier)"),
    ("DIS_7_2012.xml", "EventIdentifierLiveEntity", "Section 6.2.34",
     "Section 9.4.5", "shape defined contextually in 9.4.5 f)/9.4.6 f)"),
    ("DIS_7_2012.xml", "SimulationAddress", "Section 6.2.79",
     "Section 6.2.80",
     "6.2.80 Simulation Address record (6.2.79 = Silent Entity System)"),
    ("DIS_7_2012.xml", "SimulationIdentifier", "Section 6.2.80",
     "Section 6.2.81", "6.2.81 Simulation Identifier record"),
    ("DIS_7_2012.xml", "LiveEntityIdentifier", "Section 6.2.54",
     "Section 6.2.53", "6.2.53 Live Entity Identifier record"),
    ("DIS_7_2012.xml", "LiveSimulationAddress", "Section 6.2.55",
     "Section 6.2.54", "6.2.54 Live Simulation Address record"),
    ("DIS_7_2012.xml", "EntityMarking", "Section 6.29", "Section 6.2.29",
     "6.2.29 Entity Marking record"),
    ("DIS_7_2012.xml", "GroupID", "Section 6.2.43", "Section 6.2.42",
     "6.2.42 Group identifier (6.2.43 = IFF Data Specification record)"),
    ("DIS_7_2012.xml", "UnattachedIdentifier", "Section 6.2.91",
     "Section 6.2.92",
     "6.2.92 Unattached Identifier record (6.2.91 = UA Fundamental "
     "Parameter Data record)"),
]

ATTR_CITATION_FIXES = [
    # EntityStateUpdatePdu cluster (EntityInformationFamilyPdus.xml)
    ("EntityInformationFamilyPdus.xml", "EntityStateUpdatePdu",
     "entityLinearVelocity", "see 6.2.95 item c)]", "see 6.2.96 item c)]",
     "Linear Velocity Vector is item c) of 6.2.96 Vector record; 6.2.95 is "
     "Variable Transmitter Parameters"),
    ("EntityInformationFamilyPdus.xml", "EntityStateUpdatePdu",
     "entityLocation", "(see 6.2.97)", "(see 6.2.98)",
     "6.2.98 World Coordinates record (6.2.97 = Vectoring Nozzle System "
     "Data)"),
    ("EntityInformationFamilyPdus.xml", "EntityStateUpdatePdu",
     "entityOrientation", "(see 6.2.33)", "(see 6.2.32)",
     "6.2.32 Euler Angles record (6.2.33 = Event Identifier record)"),
    ("EntityInformationFamilyPdus.xml", "EntityStateUpdatePdu",
     "variableParameters", "(see 6.2.93 and Annex I)",
     "(see 6.2.94 and Annex I)",
     "6.2.94 Variable Parameter record (6.2.93 = Variable Datum record)"),
    ("EntityInformationFamilyPdus.xml", "EntityStatePdu",
     "variableParameters", "(see 6.2.93 and Annex I)",
     "(see 6.2.94 and Annex I)" if True else "",
     "6.2.94 Variable Parameter record"),
]

RECORD_CLAUSES = {
    "Euler Angles": "6.2.32",
    "World Coordinates": "6.2.98",
    "Linear Velocity Vector": "6.2.96",
    "Entity Coordinate Vector": "6.2.96",
    "Variable Parameter": "6.2.94",
    "Variable Datum": "6.2.93",
    "Clock Time": "6.2.14",
    "Entity Type": "6.2.30",
    "Entity Identifier": "6.2.28",
    "Event Identifier": "6.2.33",
    "Simulation Address": "6.2.80",
    "Minefield Identifier": "6.2.56",
    "Minefield Sensor Type": "6.2.57",
}


def t_citations(trees):
    for fname, cls_name, old, new, why in CLASS_CITATION_FIXES:
        cls = get_class(fname, cls_name)
        c = cls.get("comment") or ""
        if old not in c:
            fail(f"citation fix: {cls_name} comment lacks {old!r} "
                 f"(has {c!r})")
        cls.set("comment", c.replace(old, new))
        log("CITATION", fname, cls_name, "-", f"{old} -> {new}",
            f"IEEE 1278.1-2012 clause map: {why}")

    for fname, cls_name, attr_name, old, new, why in ATTR_CITATION_FIXES:
        cls = get_class(fname, cls_name)
        a = get_attr(cls, attr_name)
        c = a.get("comment") or ""
        if old not in c:
            continue  # already correct in this file/attr
        a.set("comment", c.replace(old, new))
        log("CITATION", fname, cls_name, attr_name, f"{old} -> {new}",
            f"IEEE 1278.1-2012 clause map: {why}")

    # generic record-name sweep over attribute comments
    pat = re.compile(
        r"([A-Z][A-Za-z]+(?: [A-Za-z]+)*) record \((?:see |)(6\.2\.\d+)\)")
    for fname, tree in trees.items():
        for cls in tree.getroot().iter("class"):
            if cls.get("aliasFor"):
                continue
            for a in cls.findall("attribute"):
                c = a.get("comment")
                if not c:
                    continue
                for m in pat.finditer(c):
                    rname, cited = m.group(1).strip(), m.group(2)
                    true = RECORD_CLAUSES.get(rname)
                    if true and true != cited:
                        frag = f"{m.group(1)} record (see {cited})"
                        a.set("comment", c.replace(
                            frag, f"{m.group(1)} record (see {true})"))
                        log("CITATION", fname, cls.get("name"),
                            a.get("name"), f"{cited} -> {true} "
                            f"for {rname!r} record",
                            f"IEEE 1278.1-2012 clause map: {true} is the "
                            f"{rname} record clause; {cited} is not")
                        c = a.get("comment")


if __name__ == "__main__":
    main()
