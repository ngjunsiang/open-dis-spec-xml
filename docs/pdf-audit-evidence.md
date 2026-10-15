# IEEE PDF audit — 2026-10-15 (stage 2)

Every class citation, wire shape, and enum `uid`/`size` in `xml/` was checked
directly against **`IEEE Std 1278.1-2012.pdf`** (the sole reference for this
pass; no other materials). Machine-readable change log:
`pdf-audit-changes.json`. Post-state gate: `python3 scripts/fix2_pdf_audit.py`.

## Wire-shape corrections (XML -> PDF)

| Class | Field | Change | PDF evidence |
|---|---|---|---|
| RepairResponsePdu | repairResult | uid 64→**65**, 16→**8** bits | 5.5.10 d): "8-bit enumeration (see [UID 65])"; Table 148; total 224 |
| PointObjectStatePdu | updateNumber | uint32→**uint16** | Table 193 "Update Number 16-bit unsigned integer"; total 704 |
| PointObjectStatePdu | modifications | 16→**8** bits (uid 240) | 7.10.4 Modifications "8-bit enumeration (see [UID 240])"; Table 193 |
| ArealObjectStatePdu | modifications | 16→**8** bits (uid 242) | Table 195; total 384+192N |
| LinearSegmentParameter | segmentModification | 16→**8** bits (uid 241) | Table 83; total 512 |
| RecordReliablePdu | responseSerialNumber | **added** uint32 after eventType | Table 210; 7.11.16 e): "Response Serial Number … 32-bit unsigned integer" |
| MinefieldQueryPdu | padTo32 | **added** trailing pad-to-32 | Table 188 total: "320 + 64N + 16M + **8P** bits" |
| MinefieldResponseNACKPdu | padTo32 | **added** trailing pad-to-32 | Table 190 total: "208 + 8N + **8P** bits" |
| AppearancePdu | appearanceFlag1 | uint16→**uint8** | Table 223 total: "136 + 8F7 + …" (136 = 96 header + 32 LE ID + **8** flag) |
| BeamStatus | beamState | 1-bit → **8-bit** field | Table 35/6.2.12: "Total Beam Status record size = 8 bits" (bit 0 state, bits 1–7 pad) |
| VariableTransmitterParameters | paddingTo64 | commented 2×u8 → **padtoboundary 64** | Table 130 total: "48 + 8K + **8P** bits" (P = padding to 64-bit boundary) |

Field-name corrections (PDF spellings; ruling 2026-10-15: accuracy over
upstream name-compat): `generObjectAppearance` → `generalObjectAppearance`
(PointObjectStatePdu; PDF "General Object Appearance", Tables 193/195 —
ArealObjectStatePdu already used the correct spelling);
`orginatingEntityID` → `originatingEntityID` (IsPartOfPdu,
SupplementalEmissionEntityStatePdu; PDF "Originating Entity ID").

## Citation corrections (all verified against clause headings in the PDF)

Stale 1995-numbering family citations: 5.3.7→**7.6** (Distributed Emission
Regeneration), 5.3.7.1→**5.7.3** (EE PDU), 5.3.7.2→**5.7.4** (Designator PDU),
5.3.11→**7.10** (Synthetic Environment), 5.3.3→**5.3** (Entity
Information/Interaction). SimMgmt superclass "Sectionn 6.2.81"→**7.5**.

Off-by-one/misdirected record citations: Vector3Float 6.2.95→**6.2.96**
(Vector record; 6.2.95 is Variable Transmitter Parameters), Vector3Double
6.2.97→**6.2.98** (World Coordinates), VectoringNozzleSystem 6.2.96→**6.2.97**,
TotalRecordSets 6.2.88→**6.2.89**, TrackJamData 6.2.89→**6.2.90**, Expendable
6.2.36→**6.2.35**, ExpendableReload 6.2.37→**6.2.36**, EulerAngles
6.2.33→**6.2.32** (Euler Angles; 6.2.33 is Event Identifier), IntercomIdentifier
6.2.48→**6.2.47**, GridAxisDescriptorFixed 6.2.41→**6.2.40** (Grid Axis
Descriptor covers fixed and variable spacing), BeamAntennaPattern / beam
antenna list 6.2.9.2→**6.2.8.2** (Beam Antenna Pattern record), DE deposition
list 6.2.21.4→**6.2.20.4** (DE Target Energy Deposition), AttachedPartVP
6.2.93.3→**6.2.94.3** (Attached Part VP record), BlankingSector
6.2.21.2→**6.2.21.1**, AngleDeception 6.2.21.2.2→**6.2.21.2**, EntityAssociationVP
6.2.94.4.3→**6.2.94.4**. All "Entity/Linear Velocity Coordinate Vector [see
6.2.95 item a/c)]"→**6.2.96** (9 places). PduBase header citation
7.2.2→**6.2.66** (PDF: "PDU Header record (see 6.2.66)"). Minefield vertex
ordering "per 5.10.4.5.3"→"per **5.10.4.5 item 3)**" (5.10.4.5 has no
subclauses; the ordering rules are items 1)–3)). EE attribute azimuth/elevation
"(see 1.4.3)"→"(see **1.6.3**)" (entity coordinate system; matches the PDF's
own wording). ChangeOptions "aka B.2.41"→"described in **B.2.4**" (6.2.13:
"the Change/Options record is described in B.2.4").

Citations added where missing (unambiguous anchors): EntityType 6.2.30,
EntityID 6.2.28, VariableParameter 6.2.94, GridAxisDescriptorVariable 6.2.40,
ElectronicEmitter 7.6.2, IFFData 6.2.43, RadioCommsHeader 6.2.70,
IntercomReferenceID 6.2.47, MineEmplacementTime 6.2.14.
DeadReckoningParameters comment rewritten: it is the 320-bit ESPDU field
(7.2.2 item k: 8-bit algorithm [UID 44] + 120 bits per 5.3.2.3.2 item f +
linear acceleration + angular velocity), not a named 6.2.x record.

## Enum uid/size audit

212 bound enums checked against every sized "[UID n]" citation in the PDF
(222 refs; no uid is cited with two sizes). Three mismatches, all fixed (the
Modification bitfields above). 20 uids are not size-cited in the PDF; each was
verified against its table cell (e.g. Aggregate Kind 8-bit Table 29, Radio
Type category/subcategory 8-bit Table 103, appearance uids 31–43 all 32-bit,
Capability Report 8-bit Table in B.2.41 area).

## PDF-internal discrepancies found (rulings)

1. **Attribute Record Protocol Version** (7.2.6 d)): defined as a Protocol
   Version but cited "[UID 5]" — the PDF's own mapping (7.5.6 preamble table
   area: "Type [UID 4] and Protocol Family [UID 5] fields in the PDU Header
   record") makes UID 5 = Protocol Family, while the header's Protocol Version
   is [UID 3]. **Ruling (AUQ 2026-10-15): keep the literal [UID 5]** → type
   stays DISProtocolFamily; discrepancy documented on the field comment.
2. Record Specification record (6.2.73): the prose field list omits the
   explicit per-set "Padding—32 bits unused" that Table 105 shows (twice) and
   that the total formula (32 + Σ(128 + LiQi + Pi)) requires. XML follows the
   table (self-consistent; RecordSpecificationElement is correct as-is).

## Verified as already conformant (spot list)

ESPDU, Collision(-Elastic), ES Update, Fire, Detonation, DE Fire, Entity
Damage Status, all Logistics PDUs, all SimMgmt PDUs, all -R PDUs (post-fix),
EE/UA PDU hierarchies (per 7.6.2/7.6.4 prose), IFF layer 1 structure, SEES,
Transmitter/Signal/Receiver/Intercom Signal/Intercom Control, Entity
Management PDUs, Minefield State/Data, Environmental/Gridded/Point/Linear/
Areal Object PDUs (post-fix), IO PDUs, LE TSPI/Appearance/Articulated
Parts/Fire/Detonation (flag formulas per Tables 219–229), and ~100 record
classes against their 6.2 tables.
