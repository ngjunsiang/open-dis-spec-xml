# XML comment enrichment — 2026-10-16

Branch `comment-enrichment` off v0.10.0 main. Comment-text-only wave: the
ENRICH items of `.references/docstring-enrichment-candidates.md`, each
sentence surveyed against **`IEEE Std 1278.1-2012.pdf`** before writing
(the collation doc's old-exemplar text was the draft; the standard is the
authority). No wire shapes, field names, enum bindings, or sizes changed;
one commit per candidate (each maps to a later upstream PR). Post-state
gates: `python3 scripts/validate.py` + `python3 scripts/check_consistency.py`
— both green; comment-only edits, no gate was expected to move.

Downstream note: docstring-only drift against the open-dis-python
byte-identity harness is expected until dis7-ng re-converges on whatever
tag this becomes; that is handled in that repo, not here.

Quotation convention: PDF text is transcribed from `pdftotext -layout`
output; the PDF's typographic apostrophes are rendered here and in the
XML comments as ASCII `'`.

## 1. Vector3Float — §6.2.96 Vector record (commit 53f6e90)

Before:

```text
Three floating point values, x, y, and z. Section 6.2.96
```

After (full §6.2.96 body; items a)–c) folded as labeled sentences,
otherwise the standard's wording):

```text
Vector values for entity coordinates, linear acceleration, and linear
velocity shall be represented using a Vector record. This record shall
consist of three fields, each a 32-bit floating point number. The unit of
measure represented by these fields shall depend on the information
represented. Entity Coordinate Vector: location relative to a particular
entity shall be specified with respect to the origin of the entity's
coordinate system; the entity coordinate system shall be as specified in
1.6.3. Linear Acceleration Vector: linear acceleration shall be
represented as a vector with components in either world coordinate system
or entity's coordinate system depending on the value in the Dead Reckoning
Algorithm field; each vector component shall represent acceleration in
meters per second squared. Linear Velocity Vector: linear velocity shall
be represented as a vector with three components in either world
coordinate system or entity's coordinate system depending on the value in
the Dead Reckoning Algorithm field; each vector component shall represent
velocity in meters per second. Section 6.2.96
```

PDF (§6.2.96, opening + items a)–c)):

> Vector values for entity coordinates, linear acceleration, and linear
> velocity shall be represented using a Vector record. This record shall
> consist of three fields, each a 32-bit floating point number. The unit of
> measure represented by these fields shall depend on the information
> represented. […] a) Entity Coordinate Vector. Location relative to a
> particular entity shall be specified with respect to the origin of the
> entity's coordinate system. The entity coordinate system shall be as
> specified in 1.6.3. b) Linear Acceleration Vector. Linear acceleration
> shall be represented as a vector with components in either world
> coordinate system or entity's coordinate system depending on the value in
> the Dead Reckoning Algorithm field. Each vector component shall represent
> acceleration in meters per second squared. c) Linear Velocity Vector.
> Linear velocity shall be represented as a vector with three components in
> either world coordinate system or entity's coordinate system depending on
> the value in the Dead Reckoning Algorithm field. Each vector component
> shall represent velocity in meters per second.

The unit-of-measure sentence is the load-bearing one: the same record
encodes velocity (m/s) and acceleration (m/s²).

## 2. EulerAngles — §6.2.32 Euler Angles record (commit a0ba67e)

Before:

```text
Three floating point values representing an orientation, psi, theta, and
phi, aka the euler angles, in radians. Section 6.2.32
```

After (coordinate-system sentence appended):

```text
Three floating point values representing an orientation, psi, theta, and
phi, aka the euler angles, in radians. These angles shall be specified
with respect to the entity's coordinate system. Section 6.2.32
```

PDF (§6.2.32):

> Orientation of a simulated entity shall be specified by the Euler Angles
> record. This record shall specify three angles as described in Figure 3
> and 3.1. These angles shall be specified with respect to the entity's
> coordinate system. The three angles shall each be specified by a 32-bit
> floating point number representing radians.

## 3. MunitionDescriptor — §6.2.19.2 (commit bb0dd98)

Before:

```text
Represents the firing or detonation of a munition. Section 6.2.19.2
```

After (field semantics + the descriptor-slot wire-sharing note):

```text
The firing or detonation of a munition shall be represented by a Munition
Descriptor record. Munition Type is an Entity Type record (see 6.2.30);
Warhead is a 16-bit enumeration (see [UID 60]); Fuse is a 16-bit
enumeration (see [UID 61]); Quantity is the number of rounds fired in the
burst or the number of munitions simultaneously launched; Rate is the rate
of fire such as rounds per minute, and shall contain zero if Quantity
equals one. The Descriptor field of the Fire and Detonation PDUs carries
one 128-bit descriptor record: a Munition Descriptor (this record), an
Explosion Descriptor (6.2.19.3), or an Expendable Descriptor (6.2.19.4;
expendable type plus 64 bits of padding, the same 128-bit size on the
wire). Section 6.2.19.2
```

PDF (§6.2.19.2, definition + items b)–e)):

> The firing or detonation of a munition shall be represented by a
> Munition Descriptor record. […] b) Warhead. This field shall specify the
> type of warhead. It shall be represented by a 16-bit enumeration (see
> [UID 60]). c) Fuse. This field shall indicate the fusing. It shall be
> represented by a 16-bit enumeration (see [UID 61]). d) Quantity. This
> field shall represent the number of rounds fired in the burst or the
> number of munitions simultaneously launched. It shall be represented by a
> 16-bit unsigned integer. e) Rate. This field shall indicate the rate of
> fire such as the rounds per minute for a munition. If the Quantity field
> is equal to one, the Rate field shall contain zero. It shall be
> represented by a 16-bit unsigned integer.

PDF (§6.2.19.4, the wire-sharing counterpart):

> The burst of a chaff expendable or ignition of a flare shall be
> represented by an Expendable Descriptor record. The Expendable Descriptor
> record is applicable to the Fire and Detonation PDU. […] b) Padding. This
> field shall consist of 64 bits of padding.

Table 41 (Munition), Table 42 (Explosion), and Table 43 (Expendable) each
total 128 bits, which is what lets the three records share the Descriptor
slot.

## 4. EntityIdentifier — §6.2.28 (commit b0f9e80)

Before (loose wording; grammar errors "an simulation address", "a entity
number"):

```text
Entity Identifier. Unique ID for entities in the world. Consists of an
simulation address and a entity number. Section 6.2.28.
```

After (the standard's definition, verbatim; the rewrite removes the
grammar errors):

```text
The unique designation of each entity in an event or exercise that is not
contained in a Live Entity PDU shall be specified by an Entity Identifier
record. The Entity Identifier (Entity ID) record shall consist of a
Simulation Address (see 6.2.80) and an Entity Number. The Entity
Identifier is an object identifier; general requirements for all object
identifiers are specified in 4.2.5.2. Section 6.2.28.
```

PDF (§6.2.28, complete body):

> The unique designation of each entity in an event or exercise that is not
> contained in a Live Entity PDU shall be specified by an Entity Identifier
> record. The Entity Identifier (Entity ID) record shall consist of a
> Simulation Address (see 6.2.80) and an Entity Number.
>
> The Entity Identifier is an object identifier. General requirements for
> all object identifiers are specified in 4.2.5.2.

## 5. VariableParameter — §6.2.94 (commit 3002020)

Before (usage list only):

```text
Used in DetonationPdu, ArticulatedPartsPdu among others. Section 6.2.94.
```

After (purpose sentences prepended; usage list retained):

```text
The specification of additional information associated with an entity or
detonation, not otherwise accounted for in a PDU, shall be represented by a
Variable Parameter record. This record shall provide information on
articulated parts, attached parts, and other data associated with an entity
or detonation. Used in DetonationPdu, ArticulatedPartsPdu among others.
Section 6.2.94.
```

PDF (§6.2.94.1):

> The specification of additional information associated with an entity or
> detonation, not otherwise accounted for in a PDU, shall be represented by
> a Variable Parameter record. This record shall provide information on
> articulated parts, attached parts, and other data associated with an
> entity or detonation. This record shall be contained in the Variable
> Parameter records field of PDUs that have that field.

## 6. ClockTime — §6.2.14 (commit 07c9bc1)

Before (informal epoch phrasing):

```text
Time measurements that exceed one hour are represented by this record. The
first field is the hours since the unix epoch (Jan 1 1970, used by most
Unix systems and java) and the second field the timestamp units since the
top of the hour. Section 6.2.14
```

After (the standard's epoch wording, UTC-explicit):

```text
Time measurements that surpass 1 h shall be represented by a Clock Time
record. The first field is the hours since 0000 h 1 January 1970 UTC and
the second field the time past the hour indicated in the Hour field,
represented by a Timestamp record (see 6.2.88). The reference time
represented shall be either Absolute or Relative Time (see Annex G).
Section 6.2.14
```

PDF (§6.2.14, definition + items a)–b) + reference-time sentence):

> Time measurements that surpass 1 h shall be represented by a Clock Time
> record. […] a) Hours. This field shall specify the hours since 0000 h 1
> January 1970 UTC. This field shall be represented by a 32-bit integer.
> b) Time Past the Hour. This field shall specify the time past the hour
> indicated in the Hour field. This field shall be represented by a
> Timestamp (see 6.2.88). […] The reference time represented shall be
> either Absolute or Relative Time (see Annex G).

## 7. SimulationAddress — §6.2.80 (commit 086d430)

Verified before drafting: §6.2.80.1 does carry the usage sentence, clean
to fold in. Before (composition only; non-standard field wording "Site
Identification number / Application Identification number"; stray trailing
space after the cite):

```text
A Simulation Address record shall consist of the Site Identification
number and the Application Identification number. Section 6.2.80
```

After (usage sentence prepended; composition sentence aligned to the
standard's exact wording):

```text
A simulation's designation associated with all object identifiers except
those contained in Live Entity PDUs shall be specified by a Simulation
Address record. A Simulation Address record shall consist of the Site
Number and the Application Number. Section 6.2.80
```

PDF (§6.2.80.1, complete body):

> A simulation's designation associated with all object identifiers except
> those contained in Live Entity PDUs shall be specified by a Simulation
> Address record. A Simulation Address record shall consist of the Site
> Number and the Application Number.

## Found along the way — documented, not fixed (outside this wave's collated scope)

Both are comment-level (no wire impact); neither is in the collation doc's
ENRICH list, so they are recorded here as candidates for a later wave:

- `xml/WarfareFamilyPdus.xml` Fire PDU `descriptor` field comment cites
  "Munition Descriptor (6.2.20.2) or Expendable Descriptor (6.2.20.4)" —
  wrong clause numbers (§6.2.20 is the Directed Energy records; the
  descriptor records are §6.2.19.2 / §6.2.19.4). The record set named
  (Munition or Expendable only) is correct for the Fire PDU per
  §6.2.19.1 a).
- `xml/DIS_7_2012.xml` class `ExpendableDescriptor` comment is thin and
  misspells the record: "Burst of chaff or expendible device. Section
  6.2.19.4". Standard wording: "The burst of a chaff expendable or
  ignition of a flare shall be represented by an Expendable Descriptor
  record." (§6.2.19.4.)
