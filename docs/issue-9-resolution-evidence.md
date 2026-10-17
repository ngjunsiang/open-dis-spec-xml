# Issue #9 resolution — v0.12.4 — 2026-10-17

Branch `datum-id-registers` (the wave began as #12, which resolved as
a no-op — see below). Closes #9 with user rulings 2026-10-17 on its
two open bullets; the first bullet was already resolved in v0.12.2.

## Ruling 1 — IntercomCommunicationsParameters.recordLength: visible wire state

§6.2.46 b): Record Length (R) is the record's octet count and sizes
the Record-Specific fields on parse. **Ruled: stays visible
(`hidden`/`derived` deliberately NOT applied)** — the stored length is
caller-settable wire state, matching the downstream BytesPayload
contract (stored length = wire truth). Derived-ness for the
byte/formula-length family remains the deferred `derivedExpression`
vocabulary design (parked with design item 4). Recorded in the field
comment.

## Ruling 2 — legacy De* hierarchy: retire

The De* set (`DeBeamAntennaPatternRecord`, `DeTargetEnergyDepositionRecord`,
`DeAreaAimpointRecord`, `DeFirePdu`, plus the never-defined `DeRecord`)
turned out to be **entirely inside an XML comment block** (lines
3005–3200: DMcG's experimental-XML prose note + the commented classes,
carrying old `unsigned short`/`float` primitives). Dead source text —
never part of the parsed model (hence every gate green and nothing
generated downstream), superseded by the canonical `DirectedEnergy*`
SV records (§6.2.20.x) and `DirectedEnergyFirePdu`.

**Change:** the comment block is deleted (196 lines). No model change,
no drift impact (commented classes were never in the inventory), no
gate changes — the diff is pure source-text cleanup.

## #12 — resolved as no-op (context)

The wave was scoped for #12 (datum-ID uid rebinding) but the survey
refuted its premise: §6.2.37 a) and §6.2.93 a) **literally cite
[UID 66]** for Fixed/Variable Datum IDs, and REF-010's uid 64/65 are
the *repair* registers — uid 66 "Variable Record Types" (1271 rows)
is the consolidated register the PDF mandates. Closed with evidence;
no XML change (issue #12, closed 2026-10-17).

## Found along the way (flagged, not fixed)

A second commented legacy block follows in DIS_7_2012.xml:
`DamageDescriptionRecord` (same DMcG-era pattern). Not covered by the
De* ruling — same cleanup candidate for a future pass.

## Verification

- `python3 scripts/validate.py` — ALL GATES PASS
- `python3 scripts/check_consistency.py` — CONSISTENT (default and
  pinned-upstream invocations)
