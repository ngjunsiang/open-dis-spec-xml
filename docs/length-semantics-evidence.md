# Length semantics — v0.12.6 — 2026-10-17

Branch `length-semantics`. Three items per the approved scope, plus
one significant correction that item 1's implementation forced
(issue #11 resolved as **not an erratum** — the error was in our own
original row sum). User rulings of 2026-10-17 recorded in the
design-doc item-5 addendum.

## Item 1 — Aggregate State PDU gate, and the #11 correction

Implementing the "row-sum" gate forced a field-position
reconciliation that overturned the premise: the original 1056 sum
**dropped Table 183's 32-bit "Number of Variable Datum Records (M)"
row**, which the table places *after* the Silent Entity System rows.
Including it, the rows sum to exactly **1088** — the table, its total
formula, and the 1278.1-200X draft are internally consistent. The XML
was correct all along (its field order already carried the M count in
table position). Gate 8n now asserts the full-PDU total —
**1088 + 48W + 48J + 8P + 96N + Σ(96 + 32A) + Σ(64 + K + P)** —
across six cases (empty; W=2; W=1 with P=2 octets; S=1; N=1; the
four-list combination). Residual trivia only, documented in the gate
comment: the printed formula's "16P" padding term vs the row's 8
bits-per-octet — a where-notation units slip, immaterial to the
constant. Correction posted on issue #11 with a close recommendation;
the earlier keep-open ruling was predicated on the dropped-count
analysis.

## Item 2 — `byteCountFieldName`

New list-length source for **octet**-counted payloads (the existing
`bitCountFieldName` counts bits). validate gate 2 accepts it;
SizeEval maps it to the element count (u8 lists); gate C resolves the
field. Bound to `TimeSpacePositionInformationPdu.systemSpecificData`
(§9.4.2: N octets of system-specific data), replacing its
`countFieldName` — parity with the downstream's
`BytesPayload(count_is_bits=False)`.

## Item 3 — `lengthRole` (the role vocabulary; no expression syntax)

Per the rulings: precedents (DFDL/Kaitai/SQL) are whole languages;
runtime never evaluates XML formulas; the standard names **roles**, so
the XML declares roles and the formulas stay in the gates.

- `lengthRole="recordOctets"` (§6.2.83 b) 2) — the SV `recordLength`s
  (DirectedEnergyDamage/AreaAimpoint/PrecisionAimpoint,
  HighFidelityHAVEQUICKRadio, Attribute, StandardVariableRecord) and
  `Environment.length`. The record self-frames: parse reads the
  6-byte header, consumes the remainder.
- `lengthRole="recordWords32"` (§7.6.2, "length of this emitter
  system's data in 32-bit words") — `systemDataLength`/
  `beamDataLength` on ElectronicEmitter/EmitterBeam/UAEmitter/UABeam.
- Gate C2 extended: computed fields (derived counts + lengthRole)
  must be primitive, defaultless, hidden, and carry a known role. The
  rules caught the migration's own gaps on first run — four missing
  `hidden` flags and three stale fixed-layout `defaultValue`s
  (DirectedEnergyDamage 40, PrecisionAimpoint 88, HighFidelityHAVEQUICK
  40), all corrected; a computed field has no default.
- Pads stay explicit `padtoboundary` elements; the role reads the
  whole record including them. `recordType` stays generator-side
  (ClassVar emission from the declared constant).

## Verification

- `python3 scripts/validate.py` — **ALL GATES PASS** (new 8n; the
  AggregateStatePdu full-PDU gate that the #11 analysis had blocked)
- `python3 scripts/check_consistency.py` — **CONSISTENT** (C2
  extended), default and pinned-upstream invocations
- Drift-invisible: additive attributes plus one list-attribute
  binding change; gate E unchanged.

## Downstream

Inert until consumed. When adopted: the FIELD_DROPS length family
retires (the ten `recordLength`/`systemDataLength`/`beamDataLength`/
`Environment.length` entries), the BytesPayload shapes re-type from
the declared bindings, and — with the roles — the records
self-frame at parse.
