# IFF layer presence — 2026-10-17

Branch `iff-layer-presence`. Implements item 1 of the vocabulary-gap
design (`docs/vocabulary-extensions-design.md`, issue #5 / PR #14):
declare IFF layers 2–5 as presence-conditional using the **existing**
conditional vocabulary — no new terms. Surveyed against **IEEE Std
1278.1-2012.pdf**; before/after + quotes below.

## Standard truth

**Presence is flagged, not length-inferred** (the design note's
headline finding, reversing the issue's premise):

- §6.2.39 c) (Fundamental Operational Data): *"Information Layers.
  This field shall specify the information layers that are present."*
- §6.2.45 a): in Layer 1's FOD the record *"indicates which
  information layers (layers) are present in an IFF PDU … each Layer 1
  through 7 field shall be set to either Not Present (0) or Present
  (1)."*
- Table 74: bit 0 unused, **bit N = Layer N** (bits 1–7).
- Table 165: Layer 1 required (480 bits); Layers 2–5 optional;
  Layers 6–7 reserved.

**Format dispatch for Layers 3/4** (Table 165 X-rows; §7.6.5.4.1:
*"The Layer 1 System Type field shall be used to determine whether
Layer 3 represents a Mode 5 capable interrogator or transponder"*):

- Interrogator side — System Types [UID 82]: 6 (Mark XIIA
  Interrogator), 7 (Mode 5 Interrogator) for L3; 6, 8 (Mode S
  Interrogator) for L4; plus the Combined Interrogator/Transponders
  **when their Change/Options Transponder/Interrogator Indicator
  (Table B.5, bit 4) reads Interrogator (1)** — B.5.13 b)/c) (type 12:
  indicator 1 → System Type 6 rules, indicator 0 → System Type 9) and
  B.5.14 b)/c) (type 13: indicator 1 → System Type 2, indicator 0 →
  System Type 1).
- Transponder side — everything else (the default). This must be a
  **default**, not an enumeration: Layers 3/4 are *"Conditionally
  Required … if the [manufacturer included a] capability"* for ANY
  system type (B.5.1.1 b) 2)/3); e.g. Table B.63 rows L3/L4 as CR even
  for System Type 1. The transponder side is a true complement and
  not positively enumerable.

## What changed

`IdentificationFriendOrFoePdu` (xml/DistributedEmissionsFamilyPdus.xml):

| Before | After |
|---|---|
| `iFFPduLayer2Data` unconditional | `presentIf="fundamentalParameters.informationLayers:2"` |
| `iFFPduLayer3TransponderFormatData` + `iFFPduLayer3InterrogatorFormatData` (two unconditional attributes) | one `iFFPduLayer3Data` attribute: `presentIf="…informationLayers:3"`, variant group — interrogator format under `when="systemID.systemType=6 \| systemID.systemType=7 \| systemID.systemType=12 & systemID.changeOptions.value:4 \| systemID.systemType=13 & systemID.changeOptions.value:4"`, transponder format as the no-when default |
| `iFFPduLayer4InterrogatorFormatData` + `iFFPduLayer4TransponderFormatData` | one `iFFPduLayer4Data` attribute, same shape (`systemType=8` in the interrogator when-clause) |
| `iFFPduLayer5Data` unconditional | `presentIf="…informationLayers:5"` |

The L3/L4 fold follows the merged design note (PR #14): the
transponder-side complement requires a variant-group default; six
separate attributes could not express mutual exclusions without an
unenumerable negative disjunction.

## Verification

- `scripts/validate.py` gate 8k: IFF PDU totals across 11 presence /
  system-type / CIT-indicator cases — Layer 1 alone = 480 (Tables
  165/167); +L2 = 704 (Table 168); +L5 = 608 (Table 173); L3 (either
  format) = +224 (Tables 169/170 — both Mode 5 basic data records are
  128 bits); L4 (either format) = +288 (Tables 171/172 — Mode S basic
  data 192); all four layers on a type-12 interrogator-side CIT =
  1344. (Correction during gating: this survey initially mis-read
  Table 170's Mode 5 Transponder Basic Data as 192 bits; the table
  says 128 — the XML was right.)
- `scripts/check_consistency.py` — CONSISTENT (drift EXPECTED gains
  the fold: +`iFFPduLayer3Data`/`iFFPduLayer4Data`, − the four format
  attributes).

## Downstream notes (convergence round)

- The six `("IdentificationFriendOrFoePdu", …)` FIELD_OVERRIDES
  entries retire: the XML now declares the optionals natively
  (`Optional[Layer]` per bit-gated attribute).
- The generated surface becomes **four** optional fields
  (`iFFPduLayer2Data`, `iFFPduLayer3Data` union,
  `iFFPduLayer4Data` union, `iFFPduLayer5Data`) where the locked
  exemplar had six — locked-test review applies (expected wire-delta
  round). The exemplar's length-driven parse loop remains valid as a
  receiver strategy (layers self-framed per §6.2.51 c: Layer Header
  *"Length … in octets of the layer, including the Layer Header
  record"*); the Information Layers bits are the declared sender
  truth.
- The exemplar's L3/L4 dispatch sets ({6,7,12,13} interrogator /
  else) match this XML's rules for all conformant PDUs; the XML adds
  the CIT indicator refinement (bit 4) the exemplar approximates by
  treating types 12/13 as always-interrogator.

## Not confused with

Layer 5's `applicableLayers` field carries the same §6.2.45 record
with different semantics — §6.2.45 b): applicability of Layer 5's IFF
Data records, not presence. Unchanged.
