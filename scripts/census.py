#!/usr/bin/env python3
"""Census of the source DIS 7 XML set — re-verifies every count documented in
docs/design/generator-hazards.md and .references/decisions.md.

Fails (exit 1) if any documented number has drifted. Read-only.
"""
import re
import sys
import glob
import os
from lxml import etree

SRC = os.environ.get(
    "SPEC_UPSTREAM_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", ".references"))

FILES = sorted(glob.glob(os.path.join(SRC, "*.xml")))
DIS_FILES = [f for f in FILES if os.path.basename(f) != "SISO-REF-010.xml"]

# Keep comments so the uid-in-comment census works; report as Comment nodes.
PARSER = etree.XMLParser(remove_blank_text=False, remove_comments=False,
                         resolve_entities=False, load_dtd=False)


def parse_all():
    trees = {}
    for f in DIS_FILES:
        t = etree.parse(f, PARSER)
        trees[os.path.basename(f)] = t
    return trees


def comments_of(el):
    return [c for c in el.itersiblings(preced=True)
            if isinstance(c, etree._Comment)]


def uid_in_comment(comment_text):
    """Extract the REF-010 uid from a sisoenum/sisobitfield trailing comment.
    Returns (kind, value) where kind labels the recognized format."""
    t = comment_text.strip()
    m = re.match(r"^uid (\d+)$", t)
    if m:
        return ("clean", int(m.group(1)))
    m = re.match(r"^UID (\d+)$", t)
    if m:
        return ("caps", int(m.group(1)))
    m = re.match(r"^uid =(\d+)$", t)
    if m:
        return ("eq", int(m.group(1)))
    m = re.match(r"^uid (\d+)-(\d+)$", t)
    if m:
        return ("range", (int(m.group(1)), int(m.group(2))))
    m = re.match(r"^uid (\d+)\b.*", t)
    if m:
        return ("prose", int(m.group(1)))
    m = re.search(r"\buid (\d+)", t)
    if m:
        return ("embedded", int(m.group(1)))
    return (None, None)


def main():
    trees = parse_all()
    failures = []

    def check(label, actual, expected):
        ok = actual == expected
        print(f"{'OK ' if ok else 'FAIL'} {label}: {actual} (documented {expected})")
        if not ok:
            failures.append(label)

    # ---- sisoenum / sisobitfield element counts -------------------------
    sisoenums = {}   # file -> count of <sisoenum>
    sisobitfields = {}
    for name, t in trees.items():
        sisoenums[name] = len(t.findall(".//sisoenum", ))
        sisobitfields[name] = len(t.findall(".//sisobitfield"))

    total_sisoenum = sum(sisoenums.values())
    total_sisobf = sum(sisobitfields.values())
    print(f"sisoenum per file: {sisoenums}")
    print(f"sisobitfield per file: {sisobitfields}")
    check("total sisoenum elements (all files)", total_sisoenum, 181)
    check("total sisobitfield elements (all files)", total_sisobf, 13)

    # ---- uid comment formats --------------------------------------------
    formats = {}
    missing_uid = []
    distinct_uids = set()
    for name, t in trees.items():
        for el in t.iter("sisoenum", "sisobitfield"):
            # uid comments live as the LAST comment child of the element
            ctext = None
            for c in el:
                if isinstance(c, etree._Comment):
                    ctext = c.text
            if ctext is None:
                # some uids sit in the parent attribute comment; record those too
                missing_uid.append((name, el.get("type"), "no comment"))
                continue
            kind, val = uid_in_comment(ctext)
            if kind is None:
                missing_uid.append((name, el.get("type"), ctext))
            else:
                formats[kind] = formats.get(kind, 0) + 1
                if isinstance(val, int):
                    distinct_uids.add(val)
    print(f"uid comment formats: {formats}")
    print(f"unparseable-uid sites: {missing_uid}")
    check("clean 'uid N' sites", formats.get("clean", 0), 179)
    if missing_uid:
        failures.append("unparseable uid comments present")

    # ---- classRef censuses ------------------------------------------------
    def classref_counts(refname):
        n = 0
        sites = []
        for name, t in trees.items():
            for el in t.iter("classRef"):
                if el.get("name") == refname:
                    n += 1
                    # owning attribute name
                    sites.append(f"{name}:{el.getparent().get('name')}")
        return n, sites

    n, sites = classref_counts("EntityID")
    print(f"EntityID classRefs: {n}")
    for s in sites:
        print(f"   {s}")
    check("EntityID classRefs", n, 62)
    le_entity_refs = [s for s in sites if s.startswith("LiveEntityFamilyPdus.xml")]
    check("EntityID refs in LE family", len(le_entity_refs), 9)

    n, sites = classref_counts("EventIdentifier")
    le_event_refs = [s for s in sites if s.startswith("LiveEntityFamilyPdus.xml")]
    check("EventIdentifier refs in LE family", len(le_event_refs), 2)

    n, _ = classref_counts("EventIdentifierLiveEntity")
    check("EventIdentifierLiveEntity refs (declared, zero refs)", n, 0)
    n, _ = classref_counts("LiveEntityIdentifier")
    check("LiveEntityIdentifier refs (declared, zero refs)", n, 0)

    n, _ = classref_counts("Vector3Double")
    check("Vector3Double classRefs", n, 13)
    n, _ = classref_counts("WorldCoordinates")
    check("WorldCoordinates refs (must be 0; never declared)", n, 0)

    # ---- aliasFor ---------------------------------------------------------
    aliases = []
    for name, t in trees.items():
        for el in t.iter("class"):
            if el.get("aliasFor"):
                aliases.append((name, el.get("name"), el.get("aliasFor")))
    per_file = {}
    for name, a, t_ in aliases:
        per_file[name] = per_file.get(name, 0) + 1
    print(f"aliasFor pairs: {len(aliases)} per-file {per_file}")
    check("total aliasFor elements", len(aliases), 20)

    # ---- duplicate ids -----------------------------------------------------
    ids = {}
    for name, t in trees.items():
        for el in t.iter("class"):
            cid = el.get("id")
            if cid is not None:
                ids.setdefault((cid, name), []).append(el.get("name"))
    dup = {k: v for k, v in ids.items() if len(v) > 1}
    check("duplicate id groups per file", len(dup), 11)

    # ---- variable-length lists ---------------------------------------------
    unsized = []
    for name, t in trees.items():
        for pl in t.iter("primitivelist"):
            if pl.get("length") == "0" and not pl.get("countFieldName"):
                prim = pl.find("primitive")
                unsized.append((name, pl.getparent().get("name"),
                                prim.get("type") if prim is not None else "?"))
    print("unsized primitivelist sites (length=0, no countFieldName):")
    for u in unsized:
        print(f"   {u}")
    check("unsized primitivelist sites", len(unsized), 7)

    minefield_data = None
    for name, t in trees.items():
        for c in t.iter("class"):
            if c.get("name") == "MinefieldDataPdu":
                minefield_data = (name, c)
    nlists = 0
    shared = {}
    if minefield_data:
        for pl in minefield_data[1].iter("primitivelist"):
            nlists += 1
            key = pl.get("countFieldName")
            shared[key] = shared.get(key, 0) + 1
    check("MinefieldDataPdu primitivelists", nlists, 14)
    check("MinefieldDataPdu shared count field", shared, {"numberOfMinesInThisPdu": 14})

    # ---- couldBeString -----------------------------------------------------
    cbs = []
    for name, t in trees.items():
        for el in t.iter():
            if el.get("couldBeString") == "true":
                cbs.append((name, el.getparent().get("name")))
    check("couldBeString sites", len(cbs), 2)

    # ---- Java defaultValue literals ----------------------------------------
    java_defaults = []
    for name, t in trees.items():
        for el in t.iter():
            dv = el.get("defaultValue") or ""
            if "new " in dv or ".inst(" in dv:
                java_defaults.append((name, el.get("type") or el.get("name"), dv))
    print(f"Java-source defaultValues: {java_defaults}")
    if not java_defaults:
        failures.append("expected at least one Java literal defaultValue")

    # ---- commented-out classes ----------------------------------------------
    raw = open(os.path.join(SRC, "DIS_7_2012.xml")).read()
    check("FastEntityStatePdu commented out",
          1 if re.search(r"<!--.*FastEntityStatePdu.*-->", raw, re.S) else 0, 1)

    print()
    if failures:
        print(f"CENSUS FAILURES: {failures}")
        sys.exit(1)
    print("All documented counts verified.")


if __name__ == "__main__":
    main()
