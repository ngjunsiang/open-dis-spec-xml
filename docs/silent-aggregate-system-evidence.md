# Silent Aggregate System — v0.12.3 — 2026-10-17

Branch `silent-aggregate-system` (issue #7). Authors the Table 183
record the Aggregate State PDU's silent-aggregate list actually
carries, replacing the bare `EntityType` placeholder. Surveyed against
**IEEE Std 1278.1-2012.pdf**; before/after below.

## Standard truth

Table 183 (Aggregate State PDU) rows the silent-aggregate list
directly:

> 96 … Silent Aggregate System #1 … #N
> Number of Aggregates—16-bit unsigned integer
> Padding—16 bits unused
> Aggregate Type—Aggregate Type record

counted by *"Number of Silent Aggregate Systems (N)"*, with the total
formula carrying the **96N** term (*"Total Aggregate State PDU size =
1088 + 48W + 48J + 16P + 96N + Σ(96 + 32Aⱼ) + Σ(64 + Kᵢ + Pᵢ)"*). A
bare EntityType record is 64 bits — wrong size and content. (The
formula's fixed term is the #11 erratum candidate — 1088 stated vs
1056 summed — which is why no full-PDU gate exists for
AggregateStatePdu.)

## What changed

- **New class** `SilentAggregateSystem` (xml/DIS_7_2012.xml, beside
  its §6.2.79 sibling): `numberOfAggregates` u16 (genuine wire state —
  no list follows it, so **not** hidden/derived) + `padding` u16 +
  `aggregateType` → `AggregateType` (§6.2.5, the record
  AggregateStatePdu.aggregateType already uses).
- **Rewired** `AggregateStatePdu.silentAggregateSystemList`
  (xml/EntityManagementFamilyPdus.xml): `classRef` EntityType →
  `SilentAggregateSystem`; the comment (previously mislabeled "silent
  entity types") now cites Table 183 / §7.8.2 and the 96-bit size.
- **validate.py gate 8m**: `SilentAggregateSystem == 96` bits.
- **check_consistency drift EXPECTED**: `+classes` gains
  `SilentAggregateSystem` (the element swap is attr-name-invisible).

Template: the v0.11.0 `silentEntitySystemList` → `SilentEntitySystem`
fix (correction-wave item 3, gate 8g).

## Verification

- `python3 scripts/validate.py` — ALL GATES PASS (new 8m)
- `python3 scripts/check_consistency.py` — CONSISTENT, both the
  default and pinned-upstream invocations (gate E green with the one
  new +classes entry)

## Downstream

The generated `AggregateStatePdu.silentAggregateSystemList` becomes
`list[SilentAggregateSystem]` (was `list[EntityType]`) at the next
repin — a wire-shape delta for the following downstream round (the
v0.12.2 alignment is unaffected; it pinned before this wave).
