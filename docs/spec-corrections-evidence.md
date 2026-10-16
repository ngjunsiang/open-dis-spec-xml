# Spec-XML correction wave — 2026-10-17

Branch `spec-corrections` (off v0.10.1). Moves the curated downstream
open-dis-python generator-override facts (the wire-shape/cite backlog)
into `xml/` so the bridges can retire. Every item below was surveyed
against **`IEEE Std 1278.1-2012.pdf`** (sole wire/wording authority)
before editing; per-item before/after + PDF quote, style per
`pdf-audit-evidence.md`. One commit per item (1:1 with the later
upstream PRs).

Downstream bridges named per item retire in the open-dis-python
convergence round after this wave tags (no regeneration in this repo).

---

## Item 1 — ChangeOptions: 8-bit record, locked by gate

**Finding:** `xml/DIS_7_2012.xml` already carries the correct size —
`ChangeOptions.value` is `uint8` (since v0.1.0; the upstream open-dis
original and `.references/` both carry uint8 as well). The "uint16 →
uint8" premise from the backlog does not hold for the current tree; the
remaining deliverable is the size lock, which this wave adds.

**PDF evidence:**
- Table B.5 (Change/Options record, §6.2.13/B.2.4): eight 1-bit rows
  (Change Indicator … Test Mode), *"Total Change/Options record size =
  8 bits"*.
- Table 118 (System Identifier record, §6.2.87): System Type 16 +
  System Name 16 + System Mode 8 + **Change/Options — 8-bit record**;
  *"Total System Identifier record size = 48 bits"*.
- Table 167 (Layer 1 basic data, §7.6.5.2): 96 + 48 + 48 + 96 + 48 +
  8 + 8 + 128 = *"Layer 1 size = 480 bits"* — only adds up with
  Change/Options at 8 bits.

**Change:** `scripts/validate.py` gains gate 8f —
`SizeEval("SystemIdentifier") == 48` — so a future u16 flip of the
Change/Options carrier breaks the gate. No `xml/` change.

**Downstream bridge to retire:** the `ChangeOptions` entry of
`PRIMITIVE_BINDINGS` (wrapper-class absorption to a plain `uint8`) is a
generator-side flattening concern and stays on the downstream roadmap;
the wire fact it asserts is now gate-locked here.

**Side note (flag, not fixed):** `SystemIdentifier.changeOptions`'s
field comment cites "see section 6.2.15"; the Change/Options record is
§6.2.13 (Table 118 d, and the class's own comment).

---

## Item 2 — AppearancePdu.appearanceFlag1: uint8 → uint16

**Before:** `<primitive type="uint8"/>` with the Table 221 bit map.
**After:** `<primitive type="uint16"/>`; the comment now names the
field per §9.4.3.5 c) (16-bit record; octets per Tables 221/222). All
`presentIf` terms (`appearanceFlag1:0` … `:7`, and
`appearanceFlag2`'s gate on `appearanceFlag1:7`) are unchanged — the
low octet occupies bits 0-7 of the u16.

**PDF evidence:**
- §9.4.3.5 c): *"Appearance Flags. This field shall identify those
  optional data fields that are being transmitted with the current PDU.
  This field shall be defined as a 16-bit record as specified in item b)
  in 9.4.3.2."*
- 9.4.3.2 b): *"The format of the Appearance Flag fields shall be as
  shown in Table 221 and Table 222"* — Table 221 defines "Flag Octet 1
  meaning", Table 222 "Flag Octet 2 meaning" (the two octets of the
  16-bit record).

**Tension recorded (PDF-internal):** Table 221's own total says *"Total
Appearance Flag-1 field size = 8 bits"*, and Table 223 rows the field
as "Appearance Flag-1 — 8" plus a separate "Appearance Flag-2 — 8F7"
(total 136 + 8F7 + …). The curated ruling modeled here (matching the
locked downstream exemplar, which always serializes a uint16 Flag-1 and
a separate optional Flag Octet 2) follows the §9.4.3.5 c) "16-bit
record" prose. No Table-223 total gate is added for AppearancePdu — the
two readings differ by 8 bits and the exemplar's math is locked
downstream.

**Downstream bridge to retire:** the `("AppearancePdu",
"appearanceFlag1")` entry of `FIELD_OVERRIDES`.

---

## Item 3 — AggregateStatePdu.silentEntitySystemList: EntityType → SilentEntitySystem

**Before:**
```xml
<attribute name="silentEntitySystemList" comment="silent entity types">
    <objectlist countFieldName="numberOfSilentEntityTypes">
        <classRef name="EntityType"/>
    </objectlist>
</attribute>
```
**After:** the `classRef` names `SilentEntitySystem` (the orphaned
§6.2.79 class in DIS_7_2012.xml); the comment cites the record and its
size.

**PDF evidence:**
- Table 183 (Aggregate State PDU): rows *"Silent Entity System #1 …
  #S — Silent Entity System record"* at *"96 + 32A1 … 96 + 32AS"*
  bits, counted by *"Number of Silent Entity Systems (S)"*.
- §6.2.79 / Table 110 (Silent Entity System record): Number of
  Entities 16 + Number of Appearance Records (A) 16 + Entity Type 64 +
  A × Entity Appearance 32; *"Total Silent Entity System record size =
  96 + 32A bits"*.

**Change:** `xml/EntityManagementFamilyPdus.xml` classRef swap;
`scripts/validate.py` gains gate 8g —
`SizeEval("SilentEntitySystem", A=0) == 96` (Table 110).

**Downstream bridge to retire:** the `("AggregateStatePdu",
"silentEntitySystemList")` entry of `FIELD_SHAPES`.

**Flagged (not fixed — outside this wave):**
- `silentAggregateSystemList` still references `EntityType`; Table
  183's "Silent Aggregate System" rows are their own 96-bit record
  (Number of Aggregates 16 + Padding 16 + Aggregate Type 64). No
  `SilentAggregateSystem` class exists in the XML yet — authoring one
  is a vocabulary addition for a later wave.
- Table 183's stated total (1088 fixed bits) does not reconcile with
  its own field rows (they sum to 1056); no full-PDU gate added.
- `SilentEntitySystem`'s class comment carries typos ("information
  abou an enitity not producing espdus").

---

## Item 4 — GriddedDataPdu.gridDataRecords: wrong countFieldName removed

**Before:**
```xml
<attribute name="gridDataRecords" comment="">
    <objectlist countFieldName="numberOfGridAxes">
        <classRef name="GridData" initialClass="GridDataType0"/>
    </objectlist>
</attribute>
```
**After:** `countFieldName="numberOfGridAxes"` removed (replaced by
`isDynamicListLengthField="true"` — the repo's marker for a list with
no wire-stated count, per gate 2's vocabulary); the comment records
the derivation.

**PDF evidence:** Table 192 (Gridded Data PDU) rows the two lists
separately — *"Grid Axis Descriptor #1 … #N"* (8K1…8KN, counted by
"Number of Grid Axes (N)") and *"Grid Data #1 … #G"* (8D1…8DG) — with
the where-clause: *"G is the number of grid points in the PDU, which
is V ∏(k=1..N) Nk; V is the vector dimension; Nk is the number of
points in Axis k"*. G is a derived product, not the axis count.

**Note:** a product `countExpression` (V × ∏Nk) would express the
derivation natively but is a vocabulary extension — deferred per the
wave rules; the downstream `("GriddedDataPdu", "gridDataRecords")`
`FIELD_OVERRIDES` bridge (plain list, curated body owns the count)
retires against this shape.

**Downstream bridge to retire:** that FIELD_OVERRIDES entry.

---

## Item 5 — IFF layer classes: count names + flat §6.2.43 IFF Data records

**Before (all six layer classes):** count attribute named
`numberOfIFFFundamentalParameterDataRecordsParameters`; Layers 3/4/5
listed `IFFDataSpecification` wrapper records (which would add a second
count + nesting the layer table doesn't carry).

**After:**
- Layer 2 (`IFFPduLayer2Data`): count →
  `numberOfIFFFundamentalParameterDataRecords` (PDF spelling; elements
  stay `IFFFundamentalParameterData`).
- Layers 3/4/5 (`IFFPduLayer3{Transponder,Interrogator}FormatData`,
  `IFFPduLayer4{Interrogator,Transponder}FormatData`,
  `IFFPduLayer5Data`): count → `numberOfIFFDataRecords`; the list
  elements are flat `IFFData` records (§6.2.43). List attribute name
  `IFFFundamentalParameterDataRecord` unchanged (matches the locked
  downstream exemplar field name).

**PDF evidence:**
- Table 168 (Layer 2): *"Number of IFF Fundamental Parameter Data
  Records (N)—16-bit unsigned integer"*; *"Layer 2 size = 224 + 192N
  bits"* — the record is "IFF Fundamental Parameter Data record"
  (§6.2.44); the "…RecordsParameters" tail is copy-paste.
- Tables 169/170 (Layer 3 Mode 5 Interrogator/Transponder), 171/172
  (Layer 4 Mode S Interrogator/Transponder), 173 (Layer 5): each rows
  *"Number of IFF Data Records (N)—16-bit unsigned integer"* followed
  by flat *"IFF Data record #1 … #N"* rows (48 + 8K + 8P bits:
  Record Type 32 + Record Length 16 + Record-Specific fields K octets
  + padding to 32-bit boundary). §7.6.5.4.2 d)/e): *"Number of IFF
  Data Records… IFF Data records… shall conform to the variable record
  format of the IFF Data Specification record (see 6.2.43)"* — the
  records conform to the §6.2.43 format; the layer carries the count
  itself (the wrapper's own count field is not an additional wire
  field). Record-R flattening precedent.
- §6.2.43: the IFF Data Specification record is "used when variable
  records are required to be included in a layer format for Layers 3
  through 7" — its a)/b) structure (count + IFF Data records) is what
  the layer tables inline directly.

**Change:** `xml/DistributedEmissionsFamilyPdus.xml` (six classes);
`scripts/validate.py` gate 8h — Layer 2 = 224/416 (N=0/1, Table 168),
Layer 5 = 128/192 (N=0/1; one K=0 IFF Data record pads 6→8 octets =
64 bits per §6.2.43).

**Downstream bridges to retire:** the six IFF entries of
`FIELD_RENAMES`, the five `IFFFundamentalParameterDataRecord`
`FIELD_SHAPES` entries, and the six IFF entries of `FIELD_HIDDEN`
(after item 9).

---

## Item 6 — Data Query PDU (+Reliable): the lists carry datum IDs

**Before:** `fixedDatums`/`variableDatums` (and
`fixedDatumRecords`/`variableDatumRecords` on Data Query-R) were
objectlists of `FixedDatum`/`VariableDatum` records.

**After:** each list is an enum-value list — `objectlist` with a 32-bit
`sisoenum` element (bound uid 66, matching `FixedDatum.fixedDatumID`'s
existing binding), counted by the unchanged u32 count fields. Attribute
names unchanged.

**PDF evidence:** §7.5.9 d): *"Datum Information. This field shall
specify the types of datum for which information is required. Datum
IDs, but not datum values, are listed in the Data Query Datum
Specification record (see 6.2.17)."* Table 156 rows *"Fixed Datum ID
#1 … #N — 32-bit enumeration"* and *"Variable Datum ID #1 … #M —
32-bit enumeration"*; *"Total Data Query PDU size = 320 + 32N + 32M
bits"*. Data Query-R carries the same lists (§5.12.4.9 defers to the
Data Query PDU shape).

**Change:** `xml/SimulationManagementFamilyPdus.xml` (DataQueryPdu),
`xml/SimulationManagementWithReliabilityFamilyPdus.xml`
(DataQueryReliablePdu only — the SetData/Data/EventReport/Comment-R
siblings genuinely carry datum records);
`scripts/validate.py` gate 8i — DataQueryPdu = 320 + 32N + 32M
(N,M = 0/0 and 2/3).

**Downstream bridges to retire:** the four Data Query `FIELD_SHAPES`
entries (PrimitiveList rebinding).

**Flagged (not fixed):** the datum-ID registers are semantically their
own ([UID 64/65]-space datum IDs); the XML's established binding of
`FixedDatum.fixedDatumID` to uid 66 (VariableRecordType) is followed
here for consistency — worth revisiting in a registry-accuracy pass.
