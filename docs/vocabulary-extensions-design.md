# Vocabulary-gap design notes — 2026-10-17

Design note for issue #5 (bucket B of the overrides audit: spec truths
the conditional vocabulary cannot declare). Every standard fact below
was surveyed against **`IEEE Std 1278.1-2012.pdf`** before designing.
Deliverable per the issue: proposed syntax, SizeEval rules,
downstream-consumability sketch, and fail-loud rules — implementation
follows as its own wave(s) (roadmap at the end).

## 0. Upstream ignorability (verified against the pinned source)

Constraint: upstream (`open-dis/opendis7-source-generator` @ 7d271613)
must not choke on any extension. Its SAX handler
(`GeneratePdusForGivenLanguage.java`, `startElement`) dispatches on
**element names** via a fixed switch, and each handler reads only the
attributes it knows by name (`handleAttribute` iterates
`attributes.getLength()` but its inner switch only matches
`name`/`comment`/`serialize`/…). Consequences:

- **New attributes on existing elements are inert upstream** — every
  proposal below is attribute-only.
- New *elements* are also skipped by the switch, but they change the
  tree for lxml consumers downstream — rejected as a design option.

## 1. Length-driven optional records (IFF layers 2–5) — premise refuted; no new vocabulary

**The issue's premise ("There is no flag anywhere saying which layers
are present") is wrong.** The standard carries an explicit presence
flag inside Layer 1:

- §6.2.39 c) (Fundamental Operational Data record): *"Information
  Layers. This field shall specify the information layers that are
  present. It shall contain the Information Layers record (see
  6.2.45)."*
- §6.2.45 a) (Information Layers record): in Layer 1's FOD it
  *"indicates which information layers (layers) are present in an IFF
  PDU. In this case, each Layer 1 through 7 field shall be set to
  either Not Present (0) or Present (1)."*
- Table 74: bit 0 unused, **bit N = Layer N** (bits 1–7), 8 bits total.

Table 165 (overall structure — Layer 1 required, Layers 2–5
optional/"varies", Layers 6–7 reserved) is consistent with this: the
*issuance* rules (which layers a system type requires) are prose
(Clause B.5); the *parse shape* is flagged.

### Design: apply the existing `presentIf` vocabulary

On `IdentificationFriendOrFoePdu` (cross-scope dotted path, the
gate-8e `modulationType.radioSystem` precedent):

| Attribute | Term |
|---|---|
| `iFFPduLayer2Data` | `presentIf="fundamentalParameters.informationLayers:2"` |
| `iFFPduLayer3TransponderFormatData` | `presentIf="fundamentalParameters.informationLayers:3"` |
| `iFFPduLayer3InterrogatorFormatData` | `presentIf="fundamentalParameters.informationLayers:3"` |
| `iFFPduLayer4InterrogatorFormatData` | `presentIf="fundamentalParameters.informationLayers:4"` |
| `iFFPduLayer4TransponderFormatData` | `presentIf="fundamentalParameters.informationLayers:4"` |
| `iFFPduLayer5Data` | `presentIf="fundamentalParameters.informationLayers:5"` |

The two Layer 3 classRefs (and the two Layer 4 classRefs) share a bit:
§7.6.5.4.1 — *"The Layer 1 System Type field shall be used to
determine whether Layer 3 represents a Mode 5 capable interrogator or
transponder"* — so the implementation wave should also fold each pair
into a `when=` variant group keyed on `systemID.systemType` (enum
[UID 82] values surveyed from Annex B at implementation time).

**Caution:** Layer 5's `applicableLayers` field carries the *same*
§6.2.45 record with different semantics — §6.2.45 b): applicability
of Layer 5's IFF Data records *"to which layer(s)"*, not presence.
Do not conflate the two.

**SizeEval/gate sketch:** `SizeEval` already resolves dotted
`values` keys (gate 8e pattern). New gate:
`IdentificationFriendOrFoePdu` with
`fundamentalParameters.informationLayers = 0` → **480 bits**
(Layer 1 only; Table 165/167 "Layer 1 size = 480 bits"); with bit 2
set and `numberOfIFFFundamentalParameterDataRecords = 0` →
480 + 224 = 704 (Table 168 "Layer 2 size = 224 + 192N"); bit 5 set
with `numberOfIFFDataRecords = 0` → 480 + 128 = 608 (Table 173).

**What remains for the downstream generator (parse strategy, not
vocabulary):** a receiver may also parse *"until the PDU length is
exhausted"* — each layer is self-framed by its §6.2.51 Layer Header
(*"Length. This field shall specify the length in octets of the
layer, including the Layer Header record"*). That robustness loop
(and the Information-Layers-vs-length precedence rule) is a codegen
concern to record in the generator's parse notes; it needs no XML
term. **No vocabulary extension ships for item 1.**

## 2. Product-over-list counts (GriddedData G = V × ∏Ni)

**Standard truth** — Table 192 where-clause: *"G is the number of
grid points in the PDU, which is V ∏(k=1..N) Nk; V is the vector
dimension; Nk is the number of points in Axis k"*. Derived, never
stored. (The correction wave removed the wrong
`countFieldName="numberOfGridAxes"` and parked
`isDynamicListLengthField` on the list —
`docs/spec-corrections-evidence.md` item 4.)

### Design: extend `countExpression` with a `product()` function

```xml
<attribute name="gridDataRecords" comment="Grid Data records #1..#G (6.2.41).">
    <objectlist countExpression="vectorDimension * product(gridAxisDescriptors.numberOfPointsOnXiAxis)">
        <classRef name="GridData" initialClass="GridDataType0"/>
    </objectlist>
</attribute>
```

- **Syntax:** `countExpression` gains exactly one function form,
  `product(listField.elementField)` — a dotted path whose first hop is
  an `objectlist` attribute of the owning class and whose second hop
  names a field of the element class. Both `GridAxisDescriptorFixed`
  and `GridAxisDescriptorVariable` carry
  `numberOfPointsOnXiAxis`, so the path is well-defined across the
  variant elements (fixed: visible wire state; variable: derived from
  `xiValues` — visibility is orthogonal to the product).
- **SizeEval rule:** the values dict supplies lists as either
  list-of-ints (`gridAxisDescriptors=[4, 2]`) or list-of-maps; `arith`
  binds `product(p)` by resolving the path against the dict. Scalars
  (`vectorDimension`) bind as today.
- **Gate sketch:** GriddedDataPdu with N=2 axes
  (`numberOfGridAxes=2`, `gridAxisDescriptors=[4,2]`,
  `vectorDimension=1`) → G = 8 grid-data records; with zero-length
  data records the Table 192 total evaluates to 512 + 8(K1+K2) + 8·ΣD.
- **check_consistency gate C:** whitelist `product` as the one
  function keyword (not a field lookup); validate the dotted arg
  resolves: first hop an objectlist attribute, element class (via
  classRef, resolving `initialClass` variants) has the named field.
- **Fail-loud rules:** `product()` takes exactly one dotted path; a
  list carrying a `countExpression` with `product()` must not also
  carry `countFieldName`/`countListFieldName` (single length source —
  existing gate 2 rule); the referenced element field must exist on
  **every** variant element class of the list.
- **Downstream consumption:** the generator already evaluates counts
  against runtime state; `product(path)` maps to
  `math.prod(getattr(e, field) for e in <resolved list>)`. Retires the
  `("GriddedDataPdu", "gridDataRecords")` FIELD_OVERRIDES entry for
  real (the correction wave only made the XML truthful, not
  generatable).

## 3. `derived="true"` — "computed, never stored" for counts

**Standard truth** — counts defined as cardinalities, e.g. Table 176:
*"Number of Variable Transmitter Parameters Records (N)"*. The wire
carries the field; the value is defined by the list.

**Current state** — `hidden="true"` means "marshaller-managed, not
user-facing" (the field is still serialized instance state); nothing
asserts "this value is a pure function of sibling state". The
downstream generator encodes the distinction by hand (FIELD_DROPS /
curated properties).

### Design

```xml
<attribute name="numberOfVariableTransmitterParameters" derived="true" hidden="true">
    <primitive type="uint16"/>
</attribute>
```

- **Semantics:** `derived="true"` = the field is **not instance
  state**; its value is computed at marshal time. First (and only)
  v1 binding: **cardinality of the single list whose
  `countFieldName` names this field.** The field is still on the wire
  (serialized from the computed value).
- **Relationship to `hidden`:** orthogonal attributes — `hidden`
  governs user-facingness, `derived` governs statefulness. In
  practice derived counts are also hidden; both markers may appear,
  and downstream maps `derived` → read-only `len()` property.
- **Migration candidates** (first wave): every hidden count that
  mirrors its list — the Table 176 VTP count, the SM/SMWR datum
  counts, the minefield counts, the correction wave's FIELD_HIDDEN
  seven. **Explicitly out of scope for v1:** length formulas
  (`recordLength = 6 + K + P`, `systemDataLength`, `beamDataLength` —
  the surviving FIELD_DROPS families). Those need an expression form
  (`derivedExpression="…"`) and should be designed only if the
  generator wants to retire those bridges too.
- **Fail-loud rules (gate C):** a `derived="true"` attribute must be
  referenced by exactly one list's `countFieldName` (no orphans, no
  double references); `derived="true"` on a non-primitive child is
  rejected; `derived` + `defaultValue` is rejected (a computed value
  has no default).
- **Gate sketch:** structural (inventory) rather than size — the
  count/list pairing check above; sizes don't change.

## 4. (rider) `padtoboundary` scope semantics

**Evidence** — the SV-format rule is record-relative: §6.2.83 b) 2):
Record Length includes *"any padding required to end the record on a
64-bit boundary"* (and *"All Record Length values shall be a multiple
of 8"*); §6.2.8.1: *"The total length of each record shall be a
multiple of 64 bits."* The current `padtoboundary length="64"`
evaluates against the **PDU-relative** running position (SizeEval
threads `pos` from the PDU root). The two origins coincide whenever
everything upstream is 8-octet aligned — which is why nothing has
misfired — but a record whose body is 4-but-not-8 aligned into a
misaligned upstream would diverge (the downstream replacement review's
"not solved locally" case).

### Design (low priority, settled deliberately)

```xml
<padtoboundary length="64" scope="record"/>
```

- `scope` omitted or `"pdu"`: current behavior (position from the PDU
  start — the trailing 32-bit PDU alignment case).
- `scope="record"`: the alignment origin resets to the start of the
  **containing record's** evaluation (the SV/antenna-pattern
  per-record rule). In SizeEval, `size_class` records the class-entry
  position and `scope="record"` pads against `(pos + total) −
  class_entry_pos`.
- **Fail-loud:** none required (default preserves behavior); a survey
  note in the implementation wave should confirm which of the 22
  current `padtoboundary` uses are record-scoped (the SV-format
  records: DirectedEnergy*, Attribute, …) vs PDU-trailing.

## Implementation roadmap

1. **Item 1** is not a vocabulary extension at all — it is a
   correction-wave-style change (presentIf on six attributes, L3/L4
   variant groups on `systemID.systemType`, gate 8k). Small,
   evidence-doc'd, can go first.
2. **Items 2 + 3** are the actual vocabulary wave: grammar + gate C +
   SizeEval support + migrating the GriddedData expression and the
   cardinality counts. (Issue #13's EXPECTED bookkeeping is a
   prerequisite for clean drift review of any wave.)
3. **Item 4** rides the next wave that touches SV records, or stands
   alone when prioritized.

## Item 4 — resolved no-term-needed (2026-10-17, v0.12.5)

§6.3.2 Alignment settles the boundary question: the frame is
PDU-relative ("Each record in a PDU shall start at an offset [from the
beginning of the PDU] that is a multiple of the size of the largest
field in the record"), and §6.2.83 makes the record-family consequence
explicit ("The first SV record … shall start on a 64-bit boundary.
Therefore, the Number of Standard Variable Records field starts 16
bits before a 64-bit boundary"). The scan for this resolution verified
every pad-hosting record section in the set starts aligned to its
family boundary, and the standard's one genuinely unaligned-64 context
is answered by §6.2.43's NOTE — a 32-bit record family for the IFF
PDU, not relative padding. No divergence site exists; no term ships.
The invariant is locked instead by check_consistency gate G (with the
three wrapper-as-element fixes its discovery exposed). Full account:
`docs/alignment-invariant-evidence.md`.

## Item 5 — length roles (2026-10-17, v0.12.6; supersedes any
derivedExpression idea)

Ruled after surveying the precedents (expression-bearing format
languages — DFDL, Kaitai Struct — are whole languages; SQL generated
columns cover the derived-value concept): **no expression syntax**.
The runtime never evaluates XML formulas (generators compute from
actual marshalled size), so the XML declares **roles** — a closed
vocabulary the standard itself names — and formulas live in the
gates:

- `lengthRole="recordOctets"` — the record's total octets (§6.2.83
  b) 2); makes the record self-framing: parse reads the 6-byte
  header, consumes the remainder). Migrated: the SV `recordLength`s
  (DirectedEnergy ×3, HighFidelityHAVEQUICK, Attribute,
  StandardVariableRecord) and `Environment.length`.
- `lengthRole="recordWords32"` — 32-bit words including the header
  (§7.6.2). Migrated: `systemDataLength`/`beamDataLength` on
  ElectronicEmitter/EmitterBeam/UAEmitter/UABeam.
- Cardinality stays `derived="true"` (v0.12.2) — the third role,
  already shipped.
- `byteCountFieldName` added for octet-counted payloads (§9.4.2 TSPI
  `systemSpecificData`; the bit-granular `bitCountFieldName` remains
  for bit counts).
- `recordType` stays **generator-side**: the XML already carries the
  constant (`defaultValue`); ClassVar emission is codegen.
- Pads stay **explicit** `padtoboundary` elements; a role reads the
  whole record's size including them (retires the absorb-the-pad
  payload hack downstream).

Gate C2 enforces: primitive child, no `defaultValue`, `hidden`,
known role. Downstream consumption: role → computed property
(`marshalledSize()` / word count); parse self-frames. Retires the
FIELD_DROPS length family when consumed.
