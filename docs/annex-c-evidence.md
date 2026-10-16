# Annex C radio-system records — 2026-10-16

Branch `annex-c-mp-ap`. Every record layout, field size, enum binding, and
dispatch discriminator below was surveyed directly against **Annex C of
`IEEE Std 1278.1-2012.pdf`** (pp. 647–664; also §6.2.8/§6.2.58/§6.2.95,
§7.7.2 Table 176) before authoring. Post-state gates: `python3
scripts/validate.py` (new 8d/8e) and `python3 scripts/check_consistency.py`
(drift EXPECTED extended for this wave).

## What changed

The Transmitter PDU's parameter records section is re-speced from two
wrongly-shaped objectlists to the standard's own shape — §7.7.2 s): *"it
shall contain zero or one Modulation Parameters record (see 6.2.58), zero or
one Antenna Pattern record (see 6.2.8), and zero or more Variable
Transmitter Parameters records (see 6.2.95)"* — and the Annex C record
layouts themselves are authored as named classes.

| XML change | What | PDF evidence |
|---|---|---|
| TransmitterPdu.modulationParametersList → `modulationParameters` | objectlist → single optional record, variant group keyed on Radio System | §7.7.2 s) 1); Table 176 rows "Modulation Parameters … M octets" (a single 8M field, not 8×count) |
| TransmitterPdu.antennaPatternList → `antennaPattern` | objectlist (of the WRONG element — it referenced VariableTransmitterParameters, a copy-paste bug) → single optional Beam Antenna Pattern record keyed on antennaPatternType | §7.7.2 s) 2); Table 176 row "Antenna Pattern … A octets" |
| TransmitterPdu.variableTransmitterParameters | NEW objectlist of the generic §6.2.95 carrier, counted by the existing u16 field | §7.7.2 s) 3); Table 176 "Variable Transmitter Parameters record #1..#N" |
| variableTransmitterParameterCount / antennaPatternCount / modulationParameterCount | comments corrected to the Table 176 semantics (record count N / byte lengths A and M; zero = no record) | Table 176 field names "Number of Variable Transmitter Parameters Records (N)", "Antenna Pattern Length (A)", "Length of Modulation Parameters (M)" |
| `ModulationParametersRecord` (abstract) | Python-side home of §6.2.58; no fields (record-specific fields are Annex C data) | §6.2.58 + Table 89 (8R1…8RN + 8P, total a multiple of 64 bits) |
| `GenericRadio` | zero-length marker (Radio System 1, Major Modulation nonzero) | C.2: "There are no other specific Transmitter, Signal, or Receiver PDU requirements unique to a generic radio" |
| `SimpleIntercomRadio` | zero-length marker (Radio System 1, Major Modulation = No Statement (0)) | C.3.1 identification pair; C.3.2.2 h): "Length of Modulation Parameters. This field shall be set to zero" |
| `BasicHaveQuickMP` | 128 bits: netId u16 (packed NET ID), mwodIndex u16 (default 1), reserved u16 + u8 + u8, timeOfDay u32, padding u32 | Table C.3 (field list + "Total … = 128 bits"); defaults from C.4.2.2 b) and Table C.2 Note 2; reserved-zero from C.4.2.1 |
| `CCTTSincgarsMP` | 128 bits: fhNetId/hopSetId/lockoutSetId u16, startOfMessage enum8 [UID 170], clearChannel enum8 [UID 171], fhSyncTimeOffset u32, transmissionSecurityKey u16, padding u16 | Table C.7 + C.6.2.3 a)–g); "Total … = 128 bits" |
| `AntennaPatternRecord` (abstract) | Python-side home of §6.2.8; Beam Antenna Pattern (DIS_7_2012.xml) now inherits it | §6.2.8.1: "The total length of each record shall be a multiple of 64 bits"; non-self-identifying (typed by the Transmitter's antennaPatternType — settled in the 2026-10-16 seam-promotion review) |
| `VariableTransmitterParametersRecord` (abstract) | Python-side home of §6.2.95 | §6.2.83 SV format via Table 130; §6.2.95 a)–d) |
| `HighFidelityHAVEQUICKRadio` | 320 bits: recordType u32 = 3000, recordLength u16 = 40, padding u16, netId u16, todTransmitIndicator enum8 [UID 297], padding u8, todDelta **int32 (signed)**, wod1–wod6 u32 | Table C.4 + C.4.2.3 a)–f); "Record Type = 3000", "Record Length = 40", "TOD Delta … 32-bit signed integer", "Total … = 320 bits" |
| BeamAntennaPattern | inheritsFrom root → AntennaPatternRecord | §6.2.8.2 is the only typed AP record ([UID 167] value 1; omni = 0 carries no record) |

## Dispatch discriminators (variant group, first-true-wins)

| Member | when= | PDF evidence |
|---|---|---|
| SimpleIntercomRadio | radioSystem=1 **and** majorModulation=0 | C.3.1: identified by BOTH fields |
| BasicHaveQuickMP | radioSystem=2 \| 3 \| 4 | C.4.3.3.1 b) 3) iv): "HAVE QUICK (2), HAVE QUICK II (3), or HAVE QUICK IIA (4)" (REF-010 uid 163 labels value 4 "SATURN" — the same radio family; PDF wording kept) |
| CCTTSincgarsMP | radioSystem=6 | C.6.1: "set to a CCTT SINCGARS (6) radio" |
| GenericRadio (declared last) | radioSystem=1 | C.2; declared after SimpleIntercomRadio because first-true-wins needs specific-before-general, which also satisfies the ruled default-last convention |

No MP record is declared for radio systems without one (SINCGARS (5):
"There are no specific requirements currently defined" — C.5; EPLRS (7):
C.7 defines none; JTIDS/MIDS (8): MP records live in SISO-STD-002 — C.8.2.3),
so those systems resolve to no member, matching a zero Length of Modulation
Parameters on the wire.

## NET ID packing (Table C.5, quoted verbatim)

| Field | Bits (Table C.5 column) | Value |
|---|---|---|
| Net Number | 0 to 9 | Unsigned integer (0–999) |
| Frequency Table | 10 to 11 | Enumeration [UID 299] |
| Mode | 12 to 13 | Enumeration [UID 298] |
| Padding | 14 to 15 | 2 bits unused |

Bit 0 is the most significant (first transmitted) bit — the standard's
multi-octet convention ("the left-most bit of the entire multi-octet field
shall be the most significant bit", §5.2.6 Figures 39/40) and the same
row-order convention as Table C.7's Crypto Key ID sibling (Table 175) and
Table 90 (Spread Spectrum, bit 0 = Frequency Hopping). The packed u16 is
therefore `(netNumber << 6) | (frequencyTable << 4) | (mode << 2) | pad`.
This corrects the retiring hand seam's comment, which numbered the bits
from the other end (netId itself stays a packed u16 — no wire change).

## Notes

* `netId` stays a packed 16-bit field (not sub-fields): the ruled
  representation for NET ID holders (open-dis-python milestone 4), and the
  conditional vocabulary has no non-octet sub-field form.
* `mwodIndex` carries `defaultValue="1"` (C.4.2.2 b): "the default
  maintenance and training MWOD Index value of 1 shall be used".
* The generic §6.2.58/§6.2.95 byte-form carriers (`ModulationParameters`,
  `VariableTransmitterParameters` in DIS_7_2012.xml) stay: the latter is
  now the (correct) element type of the VTP objectlist; the former remains
  the standard's generic-form definition for out-of-standard radio systems.
* Sizes locked by new validate.py gates 8d/8e: Table C.3 = 128, Table C.4 =
  320, Table C.7 = 128, zero-length markers = 0, and TransmitterPdu =
  832 + 8M + 8A bits across 7 record patterns (Table 176).
