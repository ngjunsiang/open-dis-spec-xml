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
