#!/usr/bin/env python3
"""Acceptance validation over xml-fixed/ (the corrected DIS 7 XML set).

Gates (from docs/design/xml-fix-kickoff.md):
  1. every sisoenum/sisobitfield carries uid + size, consistent with the
     REF-010 v37 join and with the uid stated in its comment;
  2. no variable list lacks an explicit length source;
  3. every class name is unique or an aliasFor;
  4. LE PDUs reference live shapes only;
  5. defaultValue vocabulary is integers / EnumType.MEMBER symbols;
  6. presentIf/when expressions parse against the mini-grammar;
  7. deleted classes are gone; new classes exist; aliasFor targets resolve;
  8. bit-level spot checks: computed PDU sizes for LiveEntityFirePdu and
     LiveEntityDetonationPdu equal the standard's Table 226/229 formulas
     for several flag combinations; MinefieldDataPdu equals Table 189 for
     two dataFilter/geometry combinations.

Exit 0 = all gates pass.
"""
import io
import os
import re
import sys
import zipfile
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # spec repo root
FIXED = os.path.join(ROOT, "xml")                 # corrected spec set
REF010_XML = os.path.join(ROOT, "ref010", "SISO-REF-010.xml")

FAILURES = []


def check(ok, label, detail=""):
    print(("OK  " if ok else "FAIL") + " " + label +
          ("" if ok else f" — {detail}"))
    if not ok:
        FAILURES.append(label)


def tag_of(el):
    if not isinstance(el.tag, str):
        return None
    return etree.QName(el).localname


# ---------------------------------------------------------------- loading --
def load(fixed=True):
    base = FIXED if fixed else SRC
    trees = {}
    for fname in sorted(os.listdir(base)):
        if fname.endswith(".xml") and not fname.startswith("SISO"):
            trees[fname] = etree.parse(os.path.join(base, fname))
    return trees


def ref_join():
    root = etree.parse(REF010_XML).getroot()
    out = {}
    for el in root.iter():
        if tag_of(el) in ("enum", "bitfield") and el.get("uid"):
            out[int(el.get("uid"))] = el.get("size")
    return out


# ------------------------------------------------------------- the gates --
# uids where IEEE 1278.1-2012 (authoritative for this repo) sizes the field
# differently than REF-010 v37 registers the enum: BeamStatusBeamState is a
# 1-bit enumeration inside an 8-bit record (6.2.12/Table 35);
# ObjectStateModification{Point,Areal,Linear}Object are 8-bit per the
# Modifications field definitions (7.10.4/7.10.6/6.2.52 item b, Table 83).
PDF_SIZE_OVERRIDES = {318: "8", 240: "8", 242: "8", 241: "8"}


def gate_uid_size(trees, ref):
    bad = []
    for fname, tree in trees.items():
        for e in tree.getroot().iter():
            if tag_of(e) not in ("sisoenum", "sisobitfield"):
                continue
            uid, size = e.get("uid"), e.get("size")
            uidless = "no single umbrella table" in (e.get("comment") or "")
            if not size or (not uid and not uidless):
                bad.append(f"{fname}:{e.get('type')} missing uid/size")
                continue
            if not uid:
                continue
            u = int(uid)
            if u not in ref:
                bad.append(f"{fname}:{e.get('type')} uid {u} not in REF-010")
            elif ref[u] != size and PDF_SIZE_OVERRIDES.get(u) != str(size):
                bad.append(f"{fname}:{e.get('type')} size {size} != REF-010 "
                           f"{ref[u]}")
                bad.append(f"{fname}:{e.get('type')} size {size} != REF-010 "
                           f"{ref[u]}")
            m = re.search(r"uid (\d+)", e.get("comment") or "")
            if m and int(m.group(1)) != u:
                bad.append(f"{fname}:{e.get('type')} comment uid "
                           f"{m.group(1)} != attr {u}")
    check(not bad, "gate 1: uid+size on every sisoenum/sisobitfield",
          "; ".join(bad[:5]))


def gate_length_sources(trees):
    bad = []
    for fname, tree in trees.items():
        for e in tree.getroot().iter():
            t = tag_of(e)
            if t not in ("primitivelist", "objectlist"):
                continue
            srcs = ("countFieldName", "countExpression", "bitCountFieldName",
                    "bitCountExpression", "countListFieldName",
                    "isDynamicListLengthField", "length")
            if not any(k in e.attrib for k in srcs):
                owner = e.getparent().get("name")
                bad.append(f"{fname}:{owner} list lacks length source")
    check(not bad, "gate 2: every variable list has an explicit length "
          "source", "; ".join(bad[:5]))


def gate_unique_names(trees):
    bad = []
    for fname, tree in trees.items():
        seen = {}
        for c in tree.getroot().iter("class"):
            n = c.get("name")
            if n in seen:
                bad.append(f"{fname}: {n} declared twice")
            seen[n] = True
        for c in tree.getroot().iter("class"):
            if c.get("aliasFor"):
                names = [x.get("name") for x in tree.getroot().iter("class")]
                if c.get("aliasFor") not in names:
                    bad.append(f"{fname}: alias {c.get('name')} -> missing "
                               f"{c.get('aliasFor')}")
    check(not bad, "gate 3: class names unique or aliasFor", "; ".join(bad[:5]))
    n_alias = sum(1 for t in trees.values()
                  for c in t.getroot().iter("class") if c.get("aliasFor"))
    check(n_alias == 20, "aliasFor pairs preserved (20)", str(n_alias))


def gate_le_shapes(trees):
    le = trees["LiveEntityFamilyPdus.xml"]
    bad = []
    for cr in le.getroot().iter("classRef"):
        if cr.get("name") in ("EntityID", "EventIdentifier"):
            bad.append(f"LE file still refs {cr.get('name')} at "
                       f"{cr.getparent().get('name')}")
    check(not bad, "gate 4: LE PDUs reference live shapes only",
          "; ".join(bad))
    names = [c.get("name") for c in le.getroot().iter("class")]
    for live in ("LiveEntityFirePdu", "LiveEntityDetonationPdu",
                 "TimeSpacePositionInformationPdu"):
        check(live in names, f"canonical descriptive name present: {live}")


def gate_defaults(trees):
    rx = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Z0-9_]+$")
    bad = []
    for fname, tree in trees.items():
        for e in tree.getroot().iter():
            if tag_of(e) not in ("sisoenum", "sisobitfield", "primitive"):
                continue
            dv = e.get("defaultValue")
            if dv is None:
                continue
            if not (dv.isdigit() or rx.match(dv) or
                    re.match(r"^-?\d+\.\d+$", dv)):
                bad.append(f"{fname}: {dv!r}")
    check(not bad, "gate 5: defaultValue vocabulary normalized",
          "; ".join(bad[:5]))


TERM = re.compile(
    r"([A-Za-z_][A-Za-z0-9_.]*)"
    r"(?::(\d+)(?:=(0|1))?|=(\d+))?$")


def parse_expr(expr):
    """Validate presentIf/when mini-grammar: terms with & | separators."""
    if expr is None:
        return
    for part in re.split(r"\s*\|\s*", expr):
        for term in re.split(r"\s*&\s*", part):
            m = TERM.match(term.strip())
            if not m or not term.strip():
                raise ValueError(f"bad term {term!r} in {expr!r}")


def gate_condition_grammar(trees):
    bad = []
    for fname, tree in trees.items():
        for e in tree.getroot().iter():
            for attr in ("presentIf", "when"):
                v = e.get(attr)
                if v is None:
                    continue
                try:
                    parse_expr(v)
                except ValueError as ex:
                    bad.append(f"{fname}:{e.get('name') or e.get('type')}: "
                               f"{ex}")
    check(not bad, "gate 6: presentIf/when expressions parse",
          "; ".join(bad[:5]))


def gate_class_changes(trees):
    dis = trees["DIS_7_2012.xml"]
    names = [c.get("name") for c in dis.getroot().iter("class")]
    for gone in ("PduStatus", "Domain", "Appearance", "DataFilterRecord"):
        check(gone not in names, f"deleted class gone: {gone}")
    for added in ("EntityAppearance", "EventIdentifierLiveEntityElided",
                  "LiveEntityIdentifierElided", "LEMunitionDescriptor"):
        check(added in names, f"new class present: {added}")


# --------------------------------------------------- 8. size spot checks --
PRIM_BITS = {
    "uint8": 8, "uint16": 16, "uint32": 32, "uint64": 64,
    "int8": 8, "int16": 16, "int32": 32, "int64": 64,
    "float32": 32, "float64": 64,
}


class SizeEval:
    """Evaluates a class's wire size in bits under concrete field values.

    Handles the standardized vocabulary: presentIf, when variants,
    countFieldName/countExpression/bitCountFieldName/bitCountExpression/
    countListFieldName, padtoboundary (position-aware), and cross-scope
    presentIf inside classRef'd records (terms resolve against the owning
    PDU's field values).
    """

    def __init__(self, trees):
        self.trees = trees
        self.classes = {}
        for t in trees.values():
            for c in t.getroot().iter("class"):
                if not c.get("aliasFor"):
                    self.classes[c.get("name")] = c

    def fields(self, cls_name):
        """Flattened (attrName, attrEl) in declaration order via MRO."""
        out = []
        seen = set()
        c = self.classes[cls_name]
        chain = []
        while c is not None:
            chain.append(c)
            c = (self.classes.get(c.get("inheritsFrom"))
                 if c.get("inheritsFrom") not in (None, "root") else None)
        for c in reversed(chain):
            for a in c.findall("attribute"):
                if a.get("name") in seen:
                    continue
                seen.add(a.get("name"))
                out.append((a.get("name"), a))
        return out

    def eval_term(self, term, values):
        m = TERM.match(term.strip())
        path, bit, bitval, enumval = m.groups()
        if enumval is not None:
            return str(values.get(path)) == enumval
        v = values.get(path)
        if v is None:
            # cross-scope rule: a field absent from the current context
            # (the other PDU's flag) evaluates false
            return False
        if bit is None:
            return bool(v)
        b = (int(v) >> int(bit)) & 1
        return (b == int(bitval)) if bitval is not None else (b == 1)

    def present(self, expr, values):
        if not expr:
            return True
        for part in re.split(r"\s*\|\s*", expr):
            if all(self.eval_term(t, values) for t in
                   re.split(r"\s*&\s*", part)):
                return True
        return False

    def size_class(self, cls_name, values, pos=0):
        """values is mutated to model sequential parsing: a field whose
        presentIf is false is removed, so later conditions referencing it
        evaluate false (as on the wire, where it was never read)."""
        bits = 0
        for aname, a in self.fields(cls_name):
            if not self.present(a.get("presentIf"), values):
                values.pop(aname, None)
                continue
            bits += self.size_attr(aname, a, values, pos + bits)
        return bits

    def size_attr(self, aname, a, values, pos):
        if not self.present(a.get("presentIf"), values):
            return 0
        kids = [c for c in a if tag_of(c) in
                ("primitive", "primitivelist", "classRef", "objectlist",
                 "sisoenum", "sisobitfield", "padtoboundary")]
        total = 0
        # Variant-group selection, grouped by tag: if any child of a tag
        # carries when=, exactly one child of that tag is present — the
        # first whose when= is true, else the no-when default, else none.
        # Children of tags with no when= members are all present.
        by_tag = {}
        for c in kids:
            by_tag.setdefault(tag_of(c), []).append(c)
        chosen = []
        for tag, group in by_tag.items():
            if any(c.get("when") for c in group):
                pick = None
                default = None
                for c in group:
                    if c.get("when"):
                        if pick is None and self.present(c.get("when"),
                                                        values):
                            pick = c
                    elif default is None:
                        default = c
                chosen.append(pick if pick is not None else default)
            else:
                chosen.extend(group)
        for c in [c for c in chosen if c is not None]:
            t = tag_of(c)
            if t == "primitive":
                total += PRIM_BITS[c.get("type")]
            elif t in ("sisoenum", "sisobitfield"):
                if self.present(c.get("presentIf"), values):
                    total += int(c.get("size"))
            elif t == "classRef":
                total += self.size_class(c.get("name"), values,
                                         pos + total)
            elif t == "padtoboundary":
                L = int(c.get("length"))
                total += (L - ((pos + total) % L)) % L
            elif t in ("primitivelist", "objectlist"):
                n = self.list_count(c, values)
                el = c[0] if len(c) else None
                if t == "primitivelist":
                    total += n * PRIM_BITS[el.get("type")]
                else:
                    ct = tag_of(el)
                    if ct in ("sisobitfield", "sisoenum"):
                        total += n * int(el.get("size"))
                    else:
                        for _ in range(n):
                            total += self.size_class(el.get("name"), values,
                                                     pos + total)
        return total

    def list_count(self, c, values):
        if "countFieldName" in c.attrib:
            return int(values[c.get("countFieldName")])
        if "countExpression" in c.attrib:
            return self.arith(c.get("countExpression"), values)
        if "bitCountFieldName" in c.attrib:
            return int(values[c.get("bitCountFieldName")]) // 8
        if "bitCountExpression" in c.attrib:
            return self.arith(c.get("bitCountExpression"), values) // 8
        if "countListFieldName" in c.attrib:
            return sum(values[c.get("countListFieldName")])
        if c.get("isDynamicListLengthField") == "true":
            return 0  # dynamic: not evaluable without a stream
        if "length" in c.attrib:
            return int(c.get("length"))
        raise ValueError("no length source")

    def arith(self, expr, values):
        env = {k: v for k, v in values.items() if isinstance(v, int)}
        return int(eval(expr, {"__builtins__": {}}, env))


def gate_size_spot_checks(trees):
    ev = SizeEval(trees)

    # ---- LiveEntityFirePdu vs Table 226:
    # total = 280 + 32F0 + (16F1+16)F2 + 16F3 + 64F6 + 32F4 + 32F5 bits
    def fire_total(F):
        return (280 + 32 * F[0] + (16 * F[1] + 16) * F[2] + 16 * F[3]
                + 64 * F[6] + 32 * F[4] + 32 * F[5])

    ok = True
    for flags in (0b00000000, 0b00000001, 0b00001000, 0b00001111,
                  0b01001111, 0b01111111):
        vals = dict(fireFlag=flags)
        got = ev.size_class("LiveEntityFirePdu", vals)
        F = [(flags >> i) & 1 for i in range(8)]
        want = fire_total(F)
        if got != want:
            ok = False
            print(f"   fireFlag={flags:08b}: computed {got}, "
                  f"Table 226 says {want}")
    check(ok, "gate 8a: LiveEntityFirePdu size == Table 226 formula "
              "(6 flag patterns)")

    # ---- LiveEntityDetonationPdu vs Table 229:
    # 256 + 8F7 + 32F0 + (16F1+16)F2 + (16F3+16)G1 + 64(1-F6) + 48G0
    #   + 32F4 + 32F5 + 48F6
    def det_total(F, G):
        G = [g and F[7] for g in G]     # G* = F7 AND G per Table 229
        return (256 + 8 * F[7] + 32 * F[0] + (16 * F[1] + 16) * F[2]
                + (16 * F[3] + 16) * G[1] + 64 * (1 - F[6]) + 48 * G[0]
                + 32 * F[4] + 32 * F[5] + 48 * F[6])

    ok = True
    cases = [
        (0b00000000, 0b00000000),
        (0b00000001, 0b00000000),
        (0b01000001, 0b00000000),          # flag2 present, no event id
        (0b01001001, 0b00000010),          # flag2 + full event id
        (0b01001111, 0b00000011),          # everything incl. orientation
        (0b11001111, 0b00000011),          # + entity-coords location (F6)
    ]
    for f1, f2 in cases:
        vals = dict(detonationFlag1=f1, detonationFlag2=f2)
        got = ev.size_class("LiveEntityDetonationPdu", vals)
        F = [(f1 >> i) & 1 for i in range(8)]
        G = [(f2 >> i) & 1 for i in range(8)]
        want = det_total(F, G)
        if got != want:
            ok = False
            print(f"   f1={f1:08b} f2={f2:08b}: computed {got}, "
                  f"Table 229 says {want}")
    check(ok, "gate 8b: LiveEntityDetonationPdu size == Table 229 formula "
              "(6 flag patterns)")

    # ---- MinefieldDataPdu vs Table 189 (N=1, M=1, one wire/one vertex)
    def mf_total(N, M, F, wires, verts):
        G = 1 if (F[0] or F[1] or F[2]) else 0
        R = 1 if (F[0] or F[1] or F[2] or F[3]) else 0
        S = M * N
        U = sum(wires)
        V = sum(verts)
        P1 = 2 * (((M + 1) // 2) * 2 - M)          # pad sensors to 32-bit
        used = 2 * N + 2 * N * F[8] + S * F[9] + N * F[10]
        P2 = (4 - used % 4) % 4                    # pad that run to 32-bit
        P3 = (4 - (N * F[7]) % 4) % 4
        P4 = (4 - (U * F[7]) % 4) % 4
        return (352 + 16 * M + 8 * P1 + 96 * N + 32 * N * G
                + 32 * N * F[1] + 32 * N * F[2] + 96 * N * R
                + 32 * N * F[4] + 32 * N * F[5] + 64 * N * F[6]
                + 16 * N + 16 * N * F[8] + 8 * S * F[9] + 8 * N * F[10]
                + 8 * P2 + 8 * N * F[7] + 8 * P3 + 8 * U * F[7]
                + 8 * P4 + 96 * V * F[7])

    ok = True
    for df, wires, verts in ((0, [], []), (0b11111111111, [1], [1]),
                             (0b10000000, [1], [1])):
        vals = dict(numberOfMinesInThisPdu=1, numberOfSensorTypes=1,
                    dataFilter=df,
                    numberOfTripDetonationWires=wires,
                    numberOfVertices=verts)
        got = ev.size_class("MinefieldDataPdu", vals)
        F = [(df >> i) & 1 for i in range(11)]
        want = mf_total(1, 1, F, wires, verts)
        if got != want:
            ok = False
            print(f"   dataFilter={df:011b}: computed {got}, Table 189 "
                  f"says {want}")
    check(ok, "gate 8c: MinefieldDataPdu size == Table 189 formula "
              "(3 dataFilter patterns)")


def main():
    trees = load(fixed=True)
    ref = ref_join()
    gate_uid_size(trees, ref)
    gate_length_sources(trees)
    gate_unique_names(trees)
    gate_le_shapes(trees)
    gate_defaults(trees)
    gate_condition_grammar(trees)
    gate_class_changes(trees)
    gate_size_spot_checks(trees)
    print()
    if FAILURES:
        print(f"VALIDATION FAILED: {len(FAILURES)} gate(s): {FAILURES}")
        sys.exit(1)
    print("ALL GATES PASS")


if __name__ == "__main__":
    main()
