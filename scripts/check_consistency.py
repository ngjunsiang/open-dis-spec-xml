#!/usr/bin/env python3
"""Deep consistency verification over xml-fixed/ (beyond validate.py gates).

  A. Syntax — three independent parsers: xmllint, stdlib minidom, lxml.
  B. Reference integrity — every classRef / inheritsFrom / xi:include /
     aliasFor target resolves; no ambiguous class names across the set.
  C. Semantic field references — every countFieldName / bitCountFieldName /
     countListFieldName / presentIf / when / initialValue term resolves to
     a real field of the owning class (via inheritance), into a sibling
     record (dotted paths), or cross-scope into a referencing PDU.
  D. Variant-group sanity — attributes with multiple type children carry
     when= on all but at most one child; children share a tag.
  E. Structural drift — class/attribute inventory delta source -> fixed
     must equal exactly the expected delta of this correction pass
     (nothing else may have changed).
  F. Size parity — standard PDUs vs the standard's totals:
     Entity State 1152 + 128N, Fire 768, Detonation 832 + 128N,
     Variable Parameter record 128 bits.

Exit 0 = consistent.
"""
import os
import re
import subprocess
import sys
import xml.dom.minidom as minidom
from collections import defaultdict
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # spec repo root
FIXED = os.path.join(ROOT, "xml")
SRC = os.environ.get("SPEC_UPSTREAM_DIR")         # optional upstream
# checkout for the drift gate; gate skips when absent
sys.path.insert(0, HERE)
from validate import SizeEval, tag_of  # noqa: E402

FAILURES = []


def check(ok, label, details=()):
    bad = list(details)
    print(("OK  " if ok and not bad else "FAIL") + " " + label +
          ("" if not bad else f" — {len(bad)} problem(s)"))
    for d in bad[:8]:
        print("       " + d)
    if bad:
        FAILURES.append(label)


def files_of(base):
    return sorted(f for f in os.listdir(base)
                  if f.endswith(".xml") and not f.startswith("SISO"))


# ================================================================ A. syntax
def gate_syntax():
    problems = []
    for fname in files_of(FIXED):
        path = os.path.join(FIXED, fname)
        r = subprocess.run(["xmllint", "--noout", path],
                           capture_output=True, text=True)
        if r.returncode != 0:
            problems.append(f"xmllint {fname}: {r.stderr.strip()[:100]}")
        try:
            minidom.parse(path)
        except Exception as ex:
            problems.append(f"minidom {fname}: {ex}")
        try:
            etree.parse(path)
        except Exception as ex:
            problems.append(f"lxml {fname}: {ex}")
    check(not problems, "A. syntax via xmllint + minidom + lxml", problems)


# ============================================================ B. references
class Model:
    def __init__(self, base):
        self.trees = {f: etree.parse(os.path.join(base, f))
                      for f in files_of(base)}
        self.decl = {}          # name -> [file, class]
        self.aliases = {}       # alias name -> canonical name
        for f, t in self.trees.items():
            for c in t.getroot().iter("class"):
                n = c.get("name")
                if c.get("aliasFor"):
                    self.aliases[n] = c.get("aliasFor")
                else:
                    self.decl.setdefault(n, []).append((f, c))

    def classes(self):
        for f, t in self.trees.items():
            for c in t.getroot().iter("class"):
                if not c.get("aliasFor"):
                    yield f, c

    def flat_fields(self, cls_name, _seen=None):
        """MRO-flattened {attrName: attrElement} for a class by name."""
        _seen = _seen or set()
        if cls_name in _seen or cls_name in (None, "root"):
            return {}
        _seen.add(cls_name)
        hits = self.decl.get(cls_name)
        if not hits:
            return {}
        out = {}
        chain = []
        c = hits[0][1]
        while c is not None:
            chain.append(c)
            parent = c.get("inheritsFrom")
            c = self.decl.get(parent, [(None, None)])[0][1] \
                if parent not in (None, "root") else None
        for c in reversed(chain):
            for a in c.findall("attribute"):
                out[a.get("name")] = a
        return out


def gate_references(m):
    problems = []
    # ambiguous names
    for n, hits in m.decl.items():
        if len(hits) > 1:
            problems.append(f"class {n!r} declared in " +
                            ", ".join(sorted({f for f, _ in hits})))
    # classRef resolution
    for f, c in m.classes():
        for a in c.findall("attribute"):
            for cr in a.iter("classRef"):
                n = cr.get("name")
                if n not in m.decl and n not in m.aliases:
                    problems.append(f"{f}:{c.get('name')}.{a.get('name')} "
                                    f"classRef -> undeclared {n!r}")
    # inheritsFrom
    for f, c in m.classes():
        p = c.get("inheritsFrom")
        if p not in (None, "root") and p not in m.decl and p not in m.aliases:
            problems.append(f"{f}:{c.get('name')} inheritsFrom unknown "
                            f"{p!r}")
    # aliasFor targets
    for f, t in m.trees.items():
        for c in t.getroot().iter("class"):
            tgt = c.get("aliasFor")
            if tgt and tgt not in m.decl:
                problems.append(f"{f}: alias {c.get('name')} -> unknown "
                                f"{tgt!r}")
    # xi:include hrefs
    for f, t in m.trees.items():
        for inc in t.getroot().iter(
                "{http://www.w3.org/2001/XInclude}include"):
            href = inc.get("href")
            if not os.path.exists(os.path.join(FIXED, href)):
                problems.append(f"{f}: xi:include href {href!r} missing")
    check(not problems, "B. classRef/inheritsFrom/aliasFor/xi:include "
          "resolve", problems)


# ==================================================== C. semantic references
TERM_PATH = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)")

# Documented exception: EntityAppearance's variant paths resolve against the
# referencing PDU's entityType, which EntityStateUpdatePdu does not carry
# (comment in the XML records the cached-entity-type rule).
WHITELIST = {("EntityAppearance", "entityType")}


def term_paths(expr):
    if not expr:
        return []
    out = []
    for part in re.split(r"\s*\|\s*", expr):
        for term in re.split(r"\s*&\s*", part):
            m = TERM_PATH.match(term.strip())
            if m:
                out.append(m.group(1))
    return out


def referrers(m, target_name):
    """Classes with a classRef (any depth in attributes) to target_name."""
    out = set()
    for f, c in m.classes():
        for cr in c.iter("classRef"):
            if cr.get("name") == target_name or \
                    m.aliases.get(cr.get("name")) == target_name:
                out.add(c.get("name"))
    return out


def field_targets(m, cls_name, field_name):
    """classRef target class names for a field of a class."""
    a = m.flat_fields(cls_name).get(field_name)
    if a is None:
        return []
    return [cr.get("name") for cr in a.iter("classRef")]


def resolves(m, cls_name, path, seen=()):
    """Does path resolve from cls_name? Dotted paths descend classRefs;
    if the first hop fails, retry against referencing classes' fields
    (cross-scope rule)."""
    hops = path.split(".")
    for owner in [cls_name, *referrers(m, cls_name)]:
        fields = m.flat_fields(owner)
        if hops[0] in fields:
            if len(hops) == 1:
                return True
            targets = field_targets(m, owner, hops[0])
            for tgt in targets:
                if len(hops) == 2:
                    if hops[1] in m.flat_fields(tgt):
                        return True
                elif resolves(m, tgt, ".".join(hops[1:]), seen):
                    return True
    if (cls_name, hops[0]) in WHITELIST:
        return True
    return False


def gate_semantic_refs(m):
    problems = []
    for f, c in m.classes():
        cn = c.get("name")
        fields = m.flat_fields(cn)
        # initialValue names
        for iv in c.findall("initialValue"):
            if iv.get("name") not in fields:
                problems.append(f"{f}:{cn} initialValue {iv.get('name')!r} "
                                "not a field")
        for a in c.findall("attribute"):
            an = a.get("name")
            where = f"{f}:{cn}.{an}"
            # count field names on lists
            for lst in a.iter():
                if tag_of(lst) not in ("primitivelist", "objectlist"):
                    continue
                for k in ("countFieldName", "bitCountFieldName"):
                    v = lst.get(k)
                    if v and v not in fields:
                        problems.append(f"{where} {k} -> unknown field {v!r}")
                v = lst.get("countListFieldName")
                if v:
                    if v not in fields:
                        problems.append(f"{where} countListFieldName -> "
                                        f"unknown field {v!r}")
                    else:
                        tgt = fields[v]
                        if tgt.find("primitivelist") is None:
                            problems.append(f"{where} countListFieldName -> "
                                            f"{v!r} is not a primitivelist")
                # countExpression / bitCountExpression variables
                for k in ("countExpression", "bitCountExpression"):
                    v = lst.get(k)
                    if not v:
                        continue
                    # product(listField.elementField): the one function
                    # form — validate the path reaches a field of the
                    # list's concrete element class (initialClass is the
                    # declared variant carrier; the bare classRef name is
                    # an abstract parent and not a wire element)
                    for pm in re.finditer(
                            r"product\(\s*'?([A-Za-z_][A-Za-z0-9_.]*)'?\s*\)",
                            v):
                        ppath = pm.group(1)
                        hops = ppath.split(".")
                        if len(hops) != 2 or hops[0] not in fields:
                            problems.append(f"{where} {k} product() arg "
                                            f"{ppath!r} must be "
                                            "listField.elementField")
                            continue
                        ol = fields[hops[0]].find("objectlist")
                        elems = []
                        if ol is not None:
                            for cr in ol.iter("classRef"):
                                elems.append(cr.get("initialClass")
                                             or cr.get("name"))
                        if not elems:
                            problems.append(f"{where} {k} product() arg "
                                            f"{hops[0]!r} not an "
                                            "objectlist")
                        for ecn in elems:
                            if hops[1] not in m.flat_fields(ecn):
                                problems.append(
                                    f"{where} {k} product() field "
                                    f"{hops[1]!r} missing on element "
                                    f"{ecn}")
                    plain = re.sub(
                        r"product\(\s*'?[A-Za-z_][A-Za-z0-9_.]*'?\s*\)",
                        " ", v)
                    for var in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", plain):
                        if var not in fields:
                            problems.append(f"{where} {k} variable {var!r} "
                                            "unknown")
        # presentIf / when term resolution (attribute + variant children)
        for an, expr in exprs_of(c):
            for p in term_paths(expr):
                if not resolves(m, cn, p):
                    problems.append(f"{f}:{cn}.{an} condition path {p!r} "
                                    "unresolvable")
    check(not problems, "C. condition/count field references resolve",
          problems)


def exprs_of(c):
    out = []
    for a in c.findall("attribute"):
        if a.get("presentIf"):
            out.append((a.get("name"), a.get("presentIf")))
        for child in a:
            ct = tag_of(child)
            if not ct:
                continue
            if child.get("presentIf"):
                out.append((f"{a.get('name')}/{ct}", child.get("presentIf")))
            if child.get("when"):
                out.append((f"{a.get('name')}/{ct}", child.get("when")))
    return out


# ======================================================== D. variant groups
def gate_variant_groups(m):
    problems = []
    for f, c in m.classes():
        for a in c.findall("attribute"):
            kids = [k for k in a if tag_of(k) in
                    ("classRef", "sisoenum", "sisobitfield", "primitive")]
            if len(kids) < 2:
                continue
            tags = {tag_of(k) for k in kids}
            if len(tags) > 1:
                problems.append(f"{f}:{c.get('name')}.{a.get('name')} mixes "
                                f"child tags {tags}")
            nowhen = [k for k in kids if not k.get("when")]
            if len(kids) > 1 and len(nowhen) > 1 and tag_of(kids[0]) != \
                    "primitive":
                # multiple plain primitives are legitimate (fixed layout);
                # multiple variant carriers need when= selectors
                problems.append(f"{f}:{c.get('name')}.{a.get('name')} has "
                                f"{len(nowhen)} children without when=")
    check(not problems, "D. variant groups well-formed", problems)


# ============================================ D2. sisoenum type/uid binding
def gate_type_uid_unique(m):
    """Each sisoenum/sisobitfield type name must bind to exactly one uid
    across the set (opendis7-source-generator issue #18 bug class)."""
    binding = {}
    problems = []
    for f, t in m.trees.items():
        for c in t.getroot().iter("class"):
            for a in c.findall("attribute"):
                for e in a.iter():
                    if tag_of(e) in ("sisoenum", "sisobitfield") and e.get("type") \
                            and e.get("uid"):
                        key = e.get("type")
                        binding.setdefault(key, set()).add(e.get("uid"))
    for typ, uids in sorted(binding.items()):
        if len(uids) > 1:
            problems.append(f"type {typ!r} bound to uids "
                            f"{sorted(uids)}")
    check(not problems,
          "D2. sisoenum/sisobitfield type names bind to one uid "
          "(issue #18 class)", problems)


# ======================================================== E. inventory drift
EXPECTED = {
    # file -> {class: (added, removed, renamed_from)}
    "DIS_7_2012.xml": {
        "+classes": {"EntityAppearance", "EventIdentifierLiveEntityElided",
                     "LiveEntityIdentifierElided", "LEMunitionDescriptor",
                     "LiveEntityRelativeEntityCoordinates"},
        "-classes": {"PduStatus", "Domain", "Appearance", "DataFilterRecord"},
        # stage-2 audit: the generic 6.2.95 carrier gained explicit
        # 64-bit alignment (Table 130); its stage-1 -padding removal is
        # recorded below under -attrs
        "+attrs": {"VariableTransmitterParameters": {"paddingTo64"}},
    },
    "LiveEntityFamilyPdus.xml": {
        "renames": {  # fixed-name: (was-name, added, removed)
            "TimeSpacePositionInformationPdu": ("TSPIPdu", set(), set()),
            "AppearancePdu": ("AppearancePdu", {
                "appearanceFlag2", "appearanceVisual", "appearanceIR",
                "appearanceEM", "appearanceAudio"},
                {"appearanceFields"}),
            "LiveEntityFirePdu": ("LEFirePdu", set(), set()),
            "LiveEntityDetonationPdu": ("LEDetonationPdu", set(), set()),
        },
        "+attrs": {"LiveEntityFamilyPdu": {"subprotocolNumber", "padding"}},
        "renamed_attrs": {("AppearancePdu", "appearanceFlag1"):
                          "appearanceFlags",
                          ("LiveEntityFirePdu", "fireFlag"): "flags"},
    },
    "MinefieldFamilyPdus.xml": {
        "+attrs": {"MinefieldDataPdu": {"padTo32_4", "vertices"},
                   # 32-bit boundary pads on the two query/NACK PDUs
                   # (Tables 188/190; predate the logged stages)
                   "MinefieldQueryPdu": {"padTo32"},
                   "MinefieldResponseNACKPdu": {"padTo32"}},
        "renamed_attrs": {("MinefieldDataPdu", "minefieldSequenceNumber"):
                          "minefieldSequenceNumbeer"},
    },
    # Annex C radio-system records (IEEE 1278.1-2012 Annex C survey):
    # typed MP records + the HF HAVE QUICK VTP record replace the
    # Transmitter's objectlists (the standard allows zero or one MP and
    # zero or one AP record; the counts are byte lengths, Table 176).
    "RadioCommunicationsFamilyPdus.xml": {
        "+classes": {"ModulationParametersRecord", "GenericRadio",
                     "SimpleIntercomRadio", "BasicHaveQuickMP",
                     "CCTTSincgarsMP", "AntennaPatternRecord",
                     "VariableTransmitterParametersRecord",
                     "HighFidelityHAVEQUICKRadio"},
        "+attrs": {"TransmitterPdu": {"modulationParameters",
                                      "antennaPattern",
                                      "variableTransmitterParameters"}},
    },
    "RadioCommunicationsFamilyPdus.xml-attrs": {
        "-attrs": {"TransmitterPdu": {"modulationParametersList",
                                      "antennaPatternList"}},
    },
    "DIS_7_2012.xml-attrs": {
        "-attrs": {"VariableTransmitterParameters": {"padding"}},
    },
    # spec-corrections wave (2026-10-17): the downstream generator
    # override facts move into xml/ — IFF count renames (Tables 168-173),
    # the TO PDU's own record-set count (Table 185), and the Comment
    # PDUs' fixed-datum lists (7.5.13 b; kept for round-trip robustness).
    # Element-type/hidden/comment changes are invisible to the inventory.
    "DistributedEmissionsFamilyPdus.xml": {
        # IFF layer presence wave (2026-10-17): the L3/L4 format pairs
        # fold into when= variant groups (Table 165/6.2.45 presence bits
        # + [UID 82] format dispatch), so two attributes become one per
        # layer.
        "+attrs": {"IdentificationFriendOrFoePdu": {"iFFPduLayer3Data",
                                                    "iFFPduLayer4Data"}},
        "renamed_attrs": {
            # stage-2 spelling audit: PDF "Originating Entity ID" (Table 174)
            ("SupplementalEmissionEntityStatePdu", "originatingEntityID"):
                "orginatingEntityID",
            ("IFFPduLayer2Data",
             "numberOfIFFFundamentalParameterDataRecords"):
                "numberOfIFFFundamentalParameterDataRecordsParameters",
            ("IFFPduLayer3TransponderFormatData",
             "numberOfIFFDataRecords"):
                "numberOfIFFFundamentalParameterDataRecordsParameters",
            ("IFFPduLayer3InterrogatorFormatData",
             "numberOfIFFDataRecords"):
                "numberOfIFFFundamentalParameterDataRecordsParameters",
            ("IFFPduLayer4InterrogatorFormatData",
             "numberOfIFFDataRecords"):
                "numberOfIFFFundamentalParameterDataRecordsParameters",
            ("IFFPduLayer4TransponderFormatData",
             "numberOfIFFDataRecords"):
                "numberOfIFFFundamentalParameterDataRecordsParameters",
            ("IFFPduLayer5Data",
             "numberOfIFFDataRecords"):
                "numberOfIFFFundamentalParameterDataRecordsParameters",
        },
    },
    "EntityManagementFamilyPdus.xml": {
        "+attrs": {"TransferOwnershipPdu": {"numberOfRecordSets"}},
        # stage-2 spelling audit: PDF "Originating Entity ID"
        "renamed_attrs": {("IsPartOfPdu", "originatingEntityID"):
                          "orginatingEntityID"},
    },
    "SimulationManagementFamilyPdus.xml": {
        "+attrs": {"CommentPdu": {"fixedDatums"}},
    },
    "SimulationManagementWithReliabilityFamilyPdus.xml": {
        "+attrs": {"CommentReliablePdu": {"fixedDatumRecords"},
                   # stage-2 audit: Record-R's response serial number
                   # (Table 210; 7.11.16 e)
                   "RecordReliablePdu": {"responseSerialNumber"}},
    },
    # stage-2 spelling audit: PDF "General Object Appearance"
    "SyntheticEnvironmentFamilyPdus.xml": {
        "renamed_attrs": {("PointObjectStatePdu", "generalObjectAppearance"):
                          "generObjectAppearance"},
    },
    "DistributedEmissionsFamilyPdus.xml-attrs": {
        "-attrs": {"IdentificationFriendOrFoePdu": {
            "iFFPduLayer3TransponderFormatData",
            "iFFPduLayer3InterrogatorFormatData",
            "iFFPduLayer4InterrogatorFormatData",
            "iFFPduLayer4TransponderFormatData"}},
    },
}
def inventory(base):
    inv = {}
    m = Model(base)
    for f, c in m.classes():
        inv[(f, c.get("name"))] = sorted(a.get("name")
                                         for a in c.findall("attribute"))
    return inv, m


def gate_drift():
    if not SRC:
        print("SKIP E. structural drift (no SPEC_UPSTREAM_DIR set)")
        return
    src_inv, src_m = inventory(SRC)
    fix_inv, fix_m = inventory(FIXED)
    problems = []

    # class-level
    src_keys = set(src_inv)
    fix_keys = set(fix_inv)
    # map fixed class names back to source names via expected renames
    rename_to_src = {}
    for f, spec in EXPECTED.items():
        if "renames" not in spec:
            continue
        for new, (old, _, _) in spec["renames"].items():
            rename_to_src[(f, new)] = (f, old)
    # SIMAN-R + DistributedEmissions alias flips: read from the fixed files'
    # alias elements ("Alias (abbreviation) for X.") — those pairs were
    # flipped, so fixed canonical name == source alias name
    for f, t in fix_m.trees.items():
        for c in t.getroot().iter("class"):
            if c.get("aliasFor") and c.get("comment", "").startswith(
                    "Alias (abbreviation)"):
                canon = c.get("aliasFor")
                if (f, canon) in fix_keys and (f, canon) not in src_keys:
                    rename_to_src[(f, canon)] = (f, c.get("name"))

    src_of = {}
    for k in fix_keys:
        src_of[k] = rename_to_src.get(k, k)

    # deletions and additions
    expected_del = {(f, n) for f, spec in EXPECTED.items()
                    for n in spec.get("-classes", ())}
    expected_add = {(f, n) for f, spec in EXPECTED.items()
                    for n in spec.get("+classes", ())}
    missing = src_keys - {v for v in src_of.values()} - expected_del
    added = {k for k, v in src_of.items() if v not in src_keys} - expected_add
    for k in sorted(missing):
        problems.append(f"class vanished unexpectedly: {k}")
    for k in sorted(added):
        problems.append(f"class added unexpectedly: {k}")

    # attribute-level (per class present under the same resolved name)
    for k in sorted(fix_keys & {x for x in src_of if src_of[x] in src_keys}):
        f, cn = k
        src_attrs = set(src_inv[src_of[k]])
        fix_attrs = set(fix_inv[k])
        exp = EXPECTED.get(f, {})
        adds = set()
        rems = set()
        ren = {}
        if "renames" in exp and cn in exp["renames"]:
            _, a, r = exp["renames"][cn]
            adds |= a
            rems |= r
        if "+attrs" in exp and cn in exp["+attrs"]:
            adds |= exp["+attrs"][cn]
        neg = EXPECTED.get(f + "-attrs", {}).get("-attrs", {})
        rems |= neg.get(cn, set())
        if "renamed_attrs" in exp:
            for (c2, new), old in exp["renamed_attrs"].items():
                if c2 == cn:
                    ren[new] = old
        real_add = fix_attrs - src_attrs - set(ren)
        real_rem = src_attrs - fix_attrs - set(ren.values())
        if real_add != adds:
            problems.append(f"{f}:{cn} unexpected +attrs {sorted(real_add - adds)} "
                            f"(expected {sorted(adds)})")
        if real_rem != rems:
            problems.append(f"{f}:{cn} unexpected -attrs "
                            f"{sorted(real_rem - rems)} (expected {sorted(rems)})")
        for new, old in ren.items():
            if new in fix_attrs and old not in src_attrs:
                problems.append(f"{f}:{cn} rename {old}->{new} not reflected")
    check(not problems, "E. structural drift == expected delta only",
          problems)


# =========================================================== F. size parity
def gate_size_parity(m):
    ev = SizeEval(m.trees)
    problems = []

    def expect(cls, values, want, label):
        try:
            got = ev.size_class(cls, dict(values))
        except Exception as ex:
            problems.append(f"{cls}: evaluation failed: {ex}")
            return
        if got != want:
            problems.append(f"{cls} {label}: computed {got}, standard "
                            f"says {want}")

    expect("EntityStatePdu", dict(numberOfVariableParameters=0), 1152,
           "(N=0)")
    expect("EntityStatePdu", dict(numberOfVariableParameters=3),
           1152 + 3 * 128, "(N=3)")
    expect("FirePdu", {}, 768, "")
    # EntityType with kind=Munition must pick the uid-14 domain variant and
    # suppress the default (variant groups contribute exactly one member)
    expect("EntityType", {"entityKind": 2}, 64, "(kind=2 variant)")
    expect("EntityType", {}, 64, "(default variant)")
    expect("DetonationPdu", dict(numberOfVariableParameters=0), 832, "(N=0)")
    expect("DetonationPdu", dict(numberOfVariableParameters=2),
           832 + 2 * 128, "(N=2)")
    # Variable Parameter record itself = 128 bits (recordType 8 + fields 120)
    try:
        got = ev.size_class("VariableParameter", {})
        if got != 128:
            problems.append(f"VariableParameter record: computed {got}, "
                            "standard says 128")
    except Exception as ex:
        problems.append(f"VariableParameter: evaluation failed: {ex}")
    check(not problems, "F. standard-PDU size parity (ESPDU 1152+128N, "
          "Fire 768, Detonation 832+128N, VP 128)", problems)


def main():
    print(f"checking {FIXED}\n")
    gate_syntax()
    m = Model(FIXED)
    gate_references(m)
    gate_semantic_refs(m)
    gate_variant_groups(m)
    gate_type_uid_unique(m)
    gate_drift()
    gate_size_parity(m)
    print()
    if FAILURES:
        print(f"CONSISTENCY CHECK FAILED: {FAILURES}")
        sys.exit(1)
    print("CONSISTENT — all checks pass")


if __name__ == "__main__":
    main()
