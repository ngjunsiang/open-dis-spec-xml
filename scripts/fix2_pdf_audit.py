#!/usr/bin/env python3
"""Stage-2 audit gate: verifies that xml/ carries the 2026-10-15 IEEE PDF audit.

Stage 1 (fix.py) reproduces the v0.1.0 corrected set from upstream + REF-010.
Stage 2 is this audit: every class citation, wire shape, and uid/size in xml/
was checked directly against 'IEEE Std 1278.1-2012.pdf' (the sole source of
truth for this pass) and corrected where they disagreed. The full change list
with per-change citations lives in docs/pdf-audit-changes.json; the human
readable rationale is in docs/pdf-audit-evidence.md.

This script asserts the post-state of every stage-2 delta (no upstream needed):

    python3 scripts/fix2_pdf_audit.py [DIR]     # default DIR: ../xml

Exit 0 = the set carries the audit; non-zero lists the missing deltas.
"""
import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_XML = os.path.join(os.path.dirname(HERE), "xml")

# (file, regex-or-substring that must be present, label)
POSTCONDITIONS = [
    ("LogisticsFamilyPdus.xml",
     '<sisoenum type="RepairResponseRepairResult" comment="uid 65" uid="65" size="8"/>',
     "RepairResponsePdu.repairResult uid 65 size 8 (Table 148)"),
    ("SyntheticEnvironmentFamilyPdus.xml",
     '<attribute name="updateNumber" comment="unique update number of each state transition of an object">\n            <primitive type="uint16"/>',
     "PointObjectStatePdu.updateNumber uint16 (Table 193)"),
    ("SyntheticEnvironmentFamilyPdus.xml",
     '<sisobitfield type="ObjectStateModificationPointObject" size="8"',
     "PointObjectStatePdu.modifications 8-bit (uid 240)"),
    ("SyntheticEnvironmentFamilyPdus.xml",
     '<sisobitfield type="ObjectStateModificationArealObject" size="8"',
     "ArealObjectStatePdu.modifications 8-bit (uid 242)"),
    ("DIS_7_2012.xml",
     '<sisobitfield type="ObjectStateModificationLinearObject" size="8"',
     "LinearSegmentParameter.segmentModification 8-bit (uid 241)"),
    ("SimulationManagementWithReliabilityFamilyPdus.xml",
     '<attribute name="responseSerialNumber" comment="Serial number of the Record-R PDU',
     "RecordReliablePdu.responseSerialNumber (Table 210, 7.11.16 e))"),
    ("MinefieldFamilyPdus.xml",
     'comment="Padding to 32-bit boundary (P in Table 188 total)"',
     "MinefieldQueryPdu trailing pad (Table 188)"),
    ("MinefieldFamilyPdus.xml",
     'comment="Padding to 32-bit boundary (P in Table 190 total)"',
     "MinefieldResponseNACKPdu trailing pad (Table 190)"),
    ("LiveEntityFamilyPdus.xml",
     '<primitive type="uint8"/>\n        </attribute>\n        \n        <attribute name="appearanceFlag2"',
     "AppearancePdu.appearanceFlag1 uint8 (Table 223 base 136)"),
    ("DIS_7_2012.xml",
     '<sisobitfield type="BeamStatusBeamState" comment="uid 318" uid="318" size="8"/>',
     "BeamStatus 8-bit record (Table 35)"),
    ("DIS_7_2012.xml",
     '<attribute name="paddingTo64" comment="Padding of 0 to 7 octets as required for 64-bit alignment (Table 130)">',
     "VariableTransmitterParameters trailing 64-bit pad (Table 130)"),
    ("SyntheticEnvironmentFamilyPdus.xml",
     '<attribute name="generalObjectAppearance" comment="General object appearance">',
     "PointObjectStatePdu.generalObjectAppearance rename (PDF spelling)"),
    ("EntityManagementFamilyPdus.xml",
     '<attribute name="originatingEntityID" comment="ID of entity originating PDU">',
     "IsPartOfPdu.originatingEntityID rename (PDF spelling)"),
    ("DistributedEmissionsFamilyPdus.xml",
     '<attribute name="originatingEntityID" comment="Originating entity ID provides a unique identifier">',
     "SupplementalEmissionEntityStatePdu.originatingEntityID rename"),
    ("DIS_7_2012.xml",
     'PduHeader record, section 6.2.66',
     "PduBase citation 6.2.66 (PDU Header record)"),
    ("DIS_7_2012.xml",
     'radiation from an antenna. Section 6.2.8.2',
     "BeamAntennaPattern citation 6.2.8.2"),
    ("DIS_7_2012.xml",
     'list of DE target deposition records. See 6.2.20.4',
     "DE deposition list citation 6.2.20.4"),
    ("DIS_7_2012.xml",
     'Removable parts that may be attached to an entity.  Section 6.2.94.3',
     "AttachedPartVP citation 6.2.94.3"),
    ("DIS_7_2012.xml",
     'See section 6.2.13, described in B.2.4',
     "ChangeOptions B.2.4 per 6.2.13"),
    ("DIS_7_2012.xml",
     'system (see 1.6.3)',
     "(see 1.4.3) -> (see 1.6.3) in EE attribute azimuth/elevation comments"),
    ("DIS_7_2012.xml",
     'comment="Three floating point values, x, y, and z. Section 6.2.96"',
     "Vector3Float citation 6.2.96 (Vector record)"),
    ("DIS_7_2012.xml",
     'comment="Three double precision floating point values, x, y, and z. Used for world coordinates Section 6.2.98."',
     "Vector3Double citation 6.2.98 (World Coordinates)"),
    ("DIS_7_2012.xml",
     'comment="Current Shaft RPM, Ordered Shaft RPM for use by Underwater Acoustic (UA) PDU. Section 7.6.4"',
     "ShaftRPM citation 7.6.4 retained (UA PDU)"),
    ("DIS_7_2012.xml",
     'comment="Dead Reckoning Parameters field of the ESPDU (7.2.2 item k)',
     "DeadReckoningParameters reference comment"),
    ("DistributedEmissionsFamilyPdus.xml",
     'Section 7.6. Distributed Emission Regeneration protocol family',
     "EE family superclass citation 7.6"),
    ("DistributedEmissionsFamilyPdus.xml",
     'Section 5.7.3.',
     "ElectronicEmissionsPdu clause-5 citation 5.7.3"),
    ("DistributedEmissionsFamilyPdus.xml",
     'See 5.7.4.',
     "DesignatorPdu clause-5 citation 5.7.4"),
    ("DistributedEmissionsFamilyPdus.xml",
     'Entity Coordinate Vector record see 6.2.96',
     "Emitter location citations 6.2.96"),
    ("SyntheticEnvironmentFamilyPdus.xml",
     'Section 7.10: Abstract superclass for synthetic environment PDUs',
     "SE family superclass citation 7.10"),
    ("SimulationManagementFamilyPdus.xml",
     'SIMAN-Reliability (SIMAN-R) PDU. Section 7.5',
     "SimMgmt family superclass citation 7.5 (typo fixed)"),
    ("EntityInformationFamilyPdus.xml",
     'Section 5.3. Common superclass',
     "EntityInfo family superclass citation 5.3"),
    ("EntityInformationFamilyPdus.xml",
     'although the field is a Protocol Version ([UID 3]); kept literal per ruling',
     "AttributePdu.attributeRecordProtocolVersion ruling note ([UID 5] literal)"),
    ("MinefieldFamilyPdus.xml",
     'per-mine per-wire ordering per 5.10.4.5 item 3)',
     "MinefieldDataPdu.vertices ordering citation"),
    ("EntityInformationFamilyPdus.xml",
     '[see 6.2.96 item c)]',
     "Collision velocity Vector-record item citation"),
]


def main():
    xml_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XML
    missing = []
    for fname, needle, label in POSTCONDITIONS:
        path = os.path.join(xml_dir, fname)
        try:
            txt = open(path).read()
        except OSError as e:
            missing.append(f"{fname}: unreadable ({e})")
            continue
        if needle not in txt:
            missing.append(f"{fname}: {label}")
    # whole-set assertions
    for f in glob.glob(os.path.join(xml_dir, "*.xml")):
        txt = open(f).read()
        for bad in ("6.2.95 item", "(see 1.4.3)", "5.3.7.1", "5.3.7.2",
                    "Section 5.3.11", "aka B.2.41", "orginatingEntityID",
                    "generObjectAppearance", "5.10.4.5.3"):
            if bad in txt:
                missing.append(f"{os.path.basename(f)}: stale fragment {bad!r} still present")
    if missing:
        print("PDF-audit stage 2 NOT fully applied:")
        for m in missing:
            print("  -", m)
        sys.exit(1)
    print(f"OK  PDF-audit stage 2 present ({len(POSTCONDITIONS)} postconditions, "
          f"{xml_dir})")


if __name__ == "__main__":
    main()
