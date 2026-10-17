# §6.3.2 alignment invariant — v0.12.5 — 2026-10-17

Branch `alignment-invariant`. Ships the record-section alignment
invariant gate (new check_consistency gate G) and the three
wrapper-as-element wire fixes its discovery scan exposed. Design item
4 (`padtoboundary scope="record"`) closes as **no-term-needed** —
verified end-to-end this wave. All facts surveyed against **IEEE Std
1278.1-2012.pdf**.

## The mandate

§6.3.2 Alignment: *"Each field in a PDU starts at an offset from the
beginning of the PDU that is a multiple of its size. Each record in a
PDU shall start at an offset that is a multiple of the size of the
largest field in the record. … Padding bits shall be used to achieve
these offsets."* And §6.2.83 states the record-family consequence
outright: *"The first SV record of a Standard Variable Specification
record shall start on a 64-bit boundary. Therefore, the Number of
Standard Variable Records field starts 16 bits before a 64-bit
boundary."* The alignment frame is **PDU-relative**; the per-family
length-multiple rules (§6.2.8.1, §6.2.43, §6.2.46, §6.2.73 g,
§6.2.83, Tables 68–70, Table 130, Table C.4) are consistent with it
by construction.

## Design item 4: resolved no-term-needed

`padtoboundary` stays single-discipline (PDU-relative):
- Every pad-hosting record section in the set starts aligned to its
  family boundary (the verified scan: Transmitter 832, TO/Record-R/
  SetRecord-R 320, GriddedData 512, Attribute 256, DE Fire 704,
  EntityDamageStatus 192 — mod 64 = 0; Intercom Control 320 and the
  IFF layers 224/224/288/288/128 — mod 32 = 0).
- The one genuine unaligned-64 context in the standard — the IFF PDU —
  is answered by §6.2.43's NOTE (*"Due to lack of 64-bit alignment in
  the IFF PDU, new records … shall not contain 64-bit float or 64-bit
  integer values"*): the standard defines a 32-bit record family
  there rather than relative padding.
- During this wave a DE Fire table extraction briefly suggested an
  SV section at ≡32 mod 64 (which would have required record-relative
  semantics); re-reading the table found the dropped 96-bit
  Aperture/Emitter Location row — the fixed part is 704 ≡ 0 (mod 64)
  and the section is aligned. No divergence site exists.

## Bugs found and fixed (wrapper-as-element)

The discovery scan exposed three lists whose element was a
**specification wrapper record** — adding a spurious second count (and,
in the gate's terms, landing the real record section 16/32 bits past
where the table puts it):

| Site | Before | After | PDF evidence |
|---|---|---|---|
| `SetRecordReliablePdu.recordSets` | `RecordSpecification` | `RecordSpecificationElement` | Table 209: the PDU carries Request ID + reliability + pads (8+16+32) + its own "Number of Record Sets (R)"; Record Set #1..#R follow flat at 320 ≡ 0 (mod 64) |
| `RecordReliablePdu.recordSets` | `RecordSpecification` | `RecordSpecificationElement` | Table 210: Request ID + reliability + pad 8 + Event Type 16 + Response Serial Number 32 + count; sets at 320 ≡ 0 (mod 64) |
| `DirectedEnergyFirePdu.dERecords` | `StandardVariableSpecification` | `StandardVariableRecord` | §7.3.4 o): the DE records *"conform to the variable record format of a Standard Variable Specification record (see 6.2.83) and may contain other Standard Variable records"* — the PDU's own 16-bit count (Table: 688+16) precedes generic SV records at 704 ≡ 0 (mod 64) |

The TransferOwnership flattening precedent (v0.11.0 item 7); all three
are element-type swaps only — field inventories, counts and pads were
already correct per the tables (SetRecord-R's 8+16+32 pad set,
Record-R's eventType/responseSerialNumber, DE Fire's u16 count).
After the fixes, the wrappers (`RecordSpecification`,
`StandardVariableSpecification`) become unreferenced orphans, like
`IFFDataSpecification` since v0.11.0.

## The gate

`check_consistency.py` gate G — walks every PDU's fields at
zero-state, tracking the running position; for every `classRef`
(single or list element) whose target hosts a `padtoboundary(N)` in
its MRO, requires `(position + preoffset) ≡ 0 (mod N)`:

- **preoffset** — the target's internal prefix before its alignment
  point: 0 for records carrying the pad themselves; the wrapper's
  count prefix for specification records (§6.2.83's 16-bit,
  §6.2.73/Table 105's 32-bit).
- **PDU-anchored** — only PDU classes are walked as owners (§6.3.2
  speaks of PDU offsets); record-internal sites are covered through
  the hosts' recursion, orphan wrappers ride no wire.
- **stream-pad family excluded** — Fixed/Variable Datum records pad
  the stream to a 64-bit boundary (§6.2.37/§6.2.93) with no
  record-length-multiple rule, and the -R PDU tables legitimately
  host them at ≡32 (mod 64) starts.
- **variable-content preservation** — each element of a preceding
  list must itself be ≡ 0 (mod N) (e.g. GriddedData's axis
  descriptors are 64-multiples ahead of the 16-family grid records).

**Mutation-tested:** inserting a stray u16 ahead of TransmitterPdu's
VTP section fails the gate with `section start 848 mod 64 = 16`;
reverted, all suites green.

## Verification

- `python3 scripts/validate.py` — ALL GATES PASS
- `python3 scripts/check_consistency.py` — CONSISTENT (new gate G),
  default and pinned-upstream invocations
- Element swaps are drift-invisible (no field/class-name changes);
  gate E unchanged.
