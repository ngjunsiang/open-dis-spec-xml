# open-dis-spec-xml

The **DIS 7 (IEEE 1278.1-2012) wire specification as machine-readable
XML** — the open-dis XML vocabulary, systematically corrected against the
IEEE standard and SISO-REF-010 v37, with a validating conformance suite.

This is the *what the wire actually says* companion to the generator-input
XML in [opendis7-source-generator](https://github.com/open-dis/opendis7-source-generator):
every correction carries an IEEE §/REF-010 citation (see
`docs/changes-evidence.md`), and the set passes bit-level size parity with
the standard's own PDU-size formulas (Tables 189, 223, 226, 229, and the
Entity State / Fire / Detonation totals).

## Layout

```
xml/            the corrected 13-file spec set (DIS_7_2012.xml + 12 families)
scripts/        fix.py (upstream -> xml/ transform, v0.1.0 set),
                fix2_pdf_audit.py (2026-10-15 IEEE-PDF audit gate),
                validate.py, check_consistency.py, census.py,
                ref056_check.py, make_docs.py
docs/           changes.json / overrides.json / changes-evidence.md /
                citations-report.txt (v0.1.0 set) — plus the 2026-10-15
                IEEE PDF audit: pdf-audit-changes.json /
                pdf-audit-evidence.md — and the SISO-REF-056 hygiene
                assessment: ref056-compliance.md
ref010/         submodule -> siso-ref-010-xml @ v37-docs (v37 enum tables
                for the uid/size join + the official v37 distribution docs
                and the REF-010.1 operations manual)
```

## Using it

- **As a spec**: parse `xml/` — every `<sisoenum>`/`<sisobitfield>` carries
  `uid` + `size`; conditional wire shapes are explicit
  (`presentIf`/`when`/`countExpression`/`countListFieldName`; vocabulary
  documented in `docs/changes-evidence.md`).
- **As upstream + overrides**: `docs/overrides.json` encodes the same
  corrections keyed file → class → field, applicable to the upstream XML
  (the interim-generator-input pattern).
- **Verify**: `python3 scripts/validate.py && python3 scripts/check_consistency.py`
  (drift gate needs `SPEC_UPSTREAM_DIR` pointing at an upstream checkout).
- **Style hygiene audit**: `python3 scripts/ref056_check.py` — read-only census of
  the set against SISO-REF-056-2018's transferable best practices; results recorded
  in `docs/ref056-compliance.md`.
- **Reproduce xml/ from upstream**: see `MANIFEST`.

## Source of truth

This repository (with the [siso-ref-010-xml](https://github.com/ngjunsiang/siso-ref-010-xml)
mirror as its enums counterpart) is the **pinned source of truth** for
DIS 7 consumers such as open-dis-python: `xml/` is the canonical final
word on any wire discrepancy or deviation, superseding consumers' local
XML copies. `.references/` (gitignored) holds the authority documents
this repo aligns against — IEEE Std 1278.1-2012 with its color figures,
DIS tutorials and source-generator design material, and the upstream XML
collection with its derived XSDs and schema documentation. Aligning the
XML to the IEEE/SISO source as faithfully as possible is this repo's
responsibility, not the consumer's: consumers resolve discrepancies
against `xml/` alone and do not consult the PDFs unless a spec-repo
issue says otherwise.

## Corrections at a glance (106 changes + 2026-10-15 IEEE PDF audit)

Wire-shape fixes (LE identifiers/headers/flags, Minefield Data vertices +
dataFilter conditions, typed enums, length sources), mechanical enrichment
(uid/size from the REF-010 join), 20 alias canonicalizations, and 14
citation corrections — each mapped to its standard clause in
`docs/changes-evidence.md`. Corrects opendis7-source-generator issue #18
along the way.

## Relationship to upstream

The intent is that these corrections land in
opendis7-source-generator's `xml/` directory; this repository tracks the
corrected set (and the reproducible delta) so consumers don't have to
wait. As fixes merge upstream, the delta shrinks. The XML is BSD-licensed
downstream of the NPS MOVES original (see `LICENSE`); the enumerations
submodule is SISO-licensed with attribution (see its LICENSE).

## IEEE PDF audit (2026-10-15)

A full pass of `xml/` against `IEEE Std 1278.1-2012.pdf` (citations, wire
shapes, enum uid/size): 11 wire-shape corrections, ~40 citation corrections,
3 field-name corrections to the PDF spellings, 1 PDF-internal discrepancy
ruled on (Attribute Record Protocol Version kept literal `[UID 5]`).
Evidence: `docs/pdf-audit-evidence.md`, `docs/pdf-audit-changes.json`.
Gate: `python3 scripts/fix2_pdf_audit.py`.
