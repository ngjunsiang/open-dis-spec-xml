# Commented-legacy sweep — v0.12.7 — 2026-10-17

Branch `commented-legacy-sweep`. The last identified spec-side hygiene
item: commented-out XML content carried in the set since upstream.
Fifteen comment blocks containing XML definitions were deleted — six
commented classes and nine commented attribute/classRef fragments.
(An earlier naive census counted "~46 mentions"; a per-block count is
15 — the old figure was a substring regex counting multiple matches
per block.)

All deletions are parser-invisible by construction — commented
content is never parsed, which is also why nothing live referenced
any of it (any live reference would have failed reference gates long
ago). Gates green on all three invocations after the sweep; the diff
is pure text deletion plus blank-line normalization.

## Commented classes deleted (6)

| Block | Was | Dead because |
|---|---|---|
| DIS_7_2012.xml `EnvironmentType` | early EntityType-shaped definition (entityKind/domain/entityClass/category) | superseded by the live `EntityType` (§6.2.30) |
| DIS_7_2012.xml `PduHeader` | duplicate of the header record | header fields live on `PduBase`/`pduHeader` in every PDU |
| DIS_7_2012.xml `PduContainer` | `numberOfPdus` + `pdus` list wrapper | never wired into any live class |
| DIS_7_2012.xml `DamageDescriptionRecord` | DMcG-era damage shape (4 KB block) | the live `EntityDamageStatusPdu` lists `DirectedEnergyDamage` records (§6.2.15.2) |
| EntityInformationFamilyPdus.xml `FastEntityStatePdu` | never-adopted fast-ESPDU variant | the live `EntityStatePdu` (§7.2.2) is the shape |
| LiveEntityFamilyPdus.xml `LiveEntityPdu` | "TODO check, why unused?" + class | its `subprotocolNumber`/`padding` fields live on `LiveEntityFamilyPdu` (stage-1 §9.3.2 composed-header work) |

## Commented fragments deleted (9)

Historical alternative shapes inside live classes, all superseded by
their live elements, none carrying intent prose (the one
prose-with-intent block — DMcG's experimental-XML note — was retired
with the De* hierarchy in v0.12.4): commented `paddingTo64Bits`,
`padding2`, `paddingTo64`, `paddingTo16`, `paddingTo32` ×3,
`paddingTo64bits` attribute definitions, and one inline
`<!--<classRef name="VariableRecordType"/>-->`.

## Also this wave

Issue #11 closed as invalid (2026-10-17): its premise — Table 183's
rows summing to 1056 — was refuted while implementing the row-sum
gate (our sum had dropped the trailing 32-bit M count); table,
formula, draft, and XML are consistent at 1088. The full account is
in `docs/length-semantics-evidence.md` and the gate-8n comment; the
formula's "16P vs 8P" where-notation slip is documented there and
not worth a tracking issue.

## Verification

- `python3 scripts/validate.py` — ALL GATES PASS
- `python3 scripts/check_consistency.py` — CONSISTENT, default and
  pinned-upstream invocations
- Diff: 424 deletions, 13 insertions (blank-line normalization only);
  no live content touched (reference gates prove it)
