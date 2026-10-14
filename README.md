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
scripts/        fix.py (upstream -> xml/ transform), validate.py,
                check_consistency.py, census.py, make_docs.py
docs/           changes.json / overrides.json / changes-evidence.md /
                citations-report.txt — every change with its citation
ref010/         submodule -> siso-ref-010-xml @ v37 (enum tables for the
                uid/size join)
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
- **Reproduce xml/ from upstream**: see `MANIFEST`.

## Corrections at a glance (106 changes)

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
