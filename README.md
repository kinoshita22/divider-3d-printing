# Two-leg divider / compass — prototype CAD

Parametric FreeCAD model of a large two-legged divider for marking a midline
on the scalp. One leg pivots in an ear opening, the other carries a fine
marker. Strike an arc from one ear, lock the opening, strike the second arc
from the other ear, and the two crossings — one frontal, one occipital —
define the perpendicular bisector of the ear-to-ear line.

> **This is a prototype CAD project, not a medical device.**
> Nothing here has been clinically validated. No claim is made about
> clinical accuracy, anatomical correctness, patient safety or regulatory
> compliance. The validation report checks that the solid model is
> internally consistent — nothing more. **Every dimension of the ear
> insertion geometry is an engineering placeholder and needs clinical
> sign-off before anything is put near a person.**

> **Revised 2026-09-18** after the client's answers: the ear piece now
> carries a commercial silicone eartip instead of contacting the ear
> directly, the specified marker (Ø9 × 167 mm) is modelled, and the swing
> geometry has been reworked around the pivot the instrument actually turns
> on. See "How it swings" below — that last one changed the working radius.
>
> **Revised 2026-10-26** after the first test print. The socket shattered
> while the ball was being pressed in — all four fingers off at the slot
> roots, exactly where the validation had predicted 2.8% strain against a
> 1.5% limit. The ball now loads from the rear through an open bottom
> closed by a threaded plug, so the press-in step is gone and assembly
> strain is zero. See "Loading the ball" below.

## Status — all mechanisms built

| Phase | Component | State |
|------|-----------|-------|
| 1 | Parameter system, reference frame, CT measurement | built |
| 2 | Ball joint: stud, split socket, base plug, clamping collar | built |
| 3 | Main hinge, friction lock, knob | built |
| 4 | Ear piece with Ø15 stopper | built |
| 5 | Main legs (flat arcs, one design printed twice) | built |
| 6 | Marker holder (split clamp) | built |
| 7 | Full assembly, posed on the reference head | built |
| 8 | Validation | 68 pass, 1 warn, 0 fail |
| 9 | STEP + STL export | built |

Ten components, all verified as single valid closed solids with watertight,
non-self-intersecting meshes. Validation: 88 pass, 0 warn, 0 fail.

## Requirements

FreeCAD 1.x with its Python API — verified against **FreeCAD 1.1.3**. No GUI
needed. Modules used: `FreeCAD`, `Part`, `Import` (STEP), `Mesh`/`MeshPart`
(STL). The CT measuring tool needs only `numpy`.

```bash
export FREECAD_CMD=/path/to/freecadcmd
```

A no-root option: download the official Linux AppImage, `chmod +x`, run
`./FreeCAD-*.AppImage --appimage-extract`, and point `FREECAD_CMD` at
`squashfs-root/usr/bin/freecadcmd`.

## Running it

```bash
./tools/run_freecad.sh main.py --stl      # build, validate, export
./tools/run_freecad.sh main.py --quick    # skip the slow checks
./tools/open_gui.sh                       # inspect in the FreeCAD GUI
```

| Option | Effect |
|---|---|
| `--stl` | export one STL per component, laid flat for printing |
| `--no-step` | skip STEP export |
| `--out DIR` | write somewhere other than `./output` |
| `--params FILE` | JSON file of parameter overrides |
| `--set key=value` | single override, repeatable |
| `--quick` | skip measured gaps, mesh checks and the sweep check |

Exit status 2 means validation reported a failure.

> **Why the wrapper:** FreeCAD parses the command line itself and rejects
> unknown flags; its `--pass` escape reliably carries only one token. The
> wrapper hands options over in `DIVIDER_ARGS` instead.

## Changing parameters

Everything is driven from `parameters.py`. **Never hard-code a dimension in
a geometry module.**

```bash
./tools/run_freecad.sh main.py --set ref_arc_radius=150
echo '{"marker_diameter": 11.4}' > tuning.json
./tools/run_freecad.sh main.py --params tuning.json
```

Unknown keys are rejected, so a typo fails loudly. Inspect the parameter set
and everything derived from it without FreeCAD:

```bash
python3 parameters.py          # 115 inputs and 60+ derived values
python3 geometry/refmath.py    # reference frame and arc geometry
```

`PARAMS` holds free inputs; `derive()` computes what follows from them.
Derived values are not user-editable because the mechanism only stays
consistent if they track their inputs — for instance the collar thread's
major diameter follows the socket wall thickness, and setting it by hand
would build a collar that cannot pass over the clamping fingers.

## Head dimensions — what was actually measured

The client supplied a figshare link with `file=17264471`. **That file is a
screenshot of the StudierFenster viewer, not CT data.** It cannot be
measured.

Rather than guess, the model uses a citable open head-CT dataset from the
same research group:

> Case01, *Head CT collection for patient-specific craniofacial implant
> (PSI) design*, DOI **10.6084/m9.figshare.12423872**

`tools/measure_ct.py` reads the segmented bone mesh, identifies the
anatomical axes from the extents, fits a least-squares ellipsoid to the
cranial vault, and reports the width profile against height:

```bash
python3 tools/measure_ct.py "Case01 cropped bone.stl" -o config/ct_case01_measurements.json
```

| Quantity | Measured |
|---|---|
| Head width (L–R) | 153.7 mm |
| Head length (A–P) | 189.3 mm |
| Vault ellipsoid semi-axes | 74.8 / 89.7 / 73.2 mm (median fit error 1.33 mm) |
| Inter-aural distance at the assumed ear depth | 144.3 mm |

Results are stored in `config/ct_case01_measurements.json` and applied as
the `ref_*` defaults.

**Three limits on these numbers, all of which matter:**

1. **One individual.** A single scan is not a population. It sizes a
   prototype; it does not define a device.
2. **Bone, not skin.** Arcs are struck on the scalp, so
   `ref_scalp_thickness` (6 mm, assumed) is added to every semi-axis.
3. **The ear height is an input, not a result.** The external auditory
   meatus cannot be located reliably by geometry alone, so
   `ref_ear_depth_below_vertex` (130 mm) is assumed and the script reports
   the width at every height so a clinician can choose properly.

## The geometry it is built on

```
origin  midpoint between the two ear reference points
+X      towards the LEFT ear reference point
+Y      anterior (towards the face)
+Z      superior (towards the vertex)
z = 0   the ear-to-ear axis, by definition
```

Both arc centres lie on the X axis and both radii are equal, so every point
equidistant from them lies on the plane x = 0. **The midline construction is
exact and does not depend on the head model at all.** The reference head only
answers *where on the scalp* the crossings fall.

At the default radius of 160 mm about the ball centres they fall at:

| Crossing | Position | Distance from each pivot |
|---|---|---|
| Anterior | (0, 91.0, 56.9) | 160.000 mm |
| Posterior | (0, −98.9, 41.8) | 160.000 mm |

giving a 190.5 mm baseline for the midline. Construction points in the
document: `LEFT_EAR_REFERENCE`, `RIGHT_EAR_REFERENCE`, `HEAD_CENTER`,
`HEAD_TOP`, `MARKER_TIP`, `MARKER_TIP_BUILT`, the two radius lines, the ear
axis, the midsagittal plane and both scalp arcs.

`MARKER_TIP` is where the geometry says the marker should land;
`MARKER_TIP_BUILT` is where it lands once the instrument is assembled and
posed. Validation measures the gap between them rather than assuming it is
zero. It currently reads 0.00000 mm.

## The mechanisms, and why each is built that way

### Ball joint — slotted collet squeezed by a tapered collar

Three concepts were considered:

1. **Plain spherical pocket, interference fit.** Rejected: the client ruled
   it out, and holding force would be set by print tolerance alone with no
   way to recover it as the socket wears.
2. **Two-part clamshell**, ball trapped between a cup and a screwed cap.
   Needs no flexing material, which suits a brittle photopolymer, but the
   clamping force acts on two small zones so the joint either slips or locks
   solid with little usable range between.
3. **Slotted collet socket squeezed by a tapered collar.** *Chosen.* Collar
   cone and finger cone share a half angle, so advancing the collar by *x*
   closes the fingers by *x*·tan(taper) — about 10:1 at 6°. That reduction
   is what makes friction finely adjustable by hand and lets the joint be
   loosened, repositioned and retightened.

### Loading the ball — why the bottom opens

The first printed socket shattered. All four fingers broke clean off at the
slot roots while the ball was being pressed in through the mouth, in an
acrylic UV resin (ProJet 2500, not the Eden the design had assumed). The
validation had predicted 2.8% bending strain at exactly that location
against a 1.5% limit, and had flagged it as the one thing to settle with a
test print before anything else was committed.

Widening the mouth would have cut the strain to about 1.5%. That was the
prepared fix, and it was rejected: the test established only that the
material fails somewhere **below** 2.8%, not where, so a 1.5% design would
have had unknown margin — and opening the mouth costs ball retention.

So the press-in step was removed instead. Everything below the equator is
now wider than the ball (Ø18.6 bore against an Ø18.0 ball), the ball drops
in from underneath, and a threaded plug (M20.8 × 2.0, five turns engaged)
closes the bottom and carries the lower half of the spherical seat.

| | Before | After |
|---|---:|---:|
| Finger spread to assemble | 1.45 mm | **0 mm** |
| Strain at the slot root, assembling | 2.8% (broke) | **0%** |
| Strain at the slot root, clamping | — | 0.96% |
| Ball capture ratio | 0.84 | 0.89 |
| Socket across flats | 27.7 mm | 29.0 mm |

Nothing in the answer now depends on a number nobody has measured.

Two things follow from it. The mouth can stay narrow, so retention improved
rather than degraded. And with insertion no longer constraining the mouth
angle, the tilt range went from 22° to **27°** — the stroke needs 19.3°, so
the margin went from 2.7° to 7.7°.

The plug also carries the tenon into the leg. That puts the leg's load
through the plug thread, which is far stronger than the 12 × 6 mm tenon it
feeds, and the tenon doubles as the wrench for screwing the plug home.

### Main hinge — friction clamp, deliberately not toothed

A toothed lock is positive, which is the obvious answer to "must not drift".
But it quantises the opening, and that quantisation lands on the
measurement itself:

    R = 2·C·sin(θ)  →  dR = 2·C·cos(θ)·dθ

At C = 200 mm even 360 teeth (1° steps) gives dR ≈ 3.3 mm. Trading a 3 mm
quantum in selectable radius for a lock that only has to resist a hand-scale
moment is a poor deal, so the hinge is a friction clamp: leg, washer, leg,
squeezed by a bolt and a fluted knob.

Its capacity is computed rather than assumed — hand torque → bolt tension →
friction torque, against the moment the drawing hand applies:

| | |
|---|---|
| Clamp force from 1.5 N·m on the knob | 750 N |
| Holding torque, two faces at r_eff 15.3 mm | 5.75 N·m |
| Applied moment, 5 N at the 200 mm leg | 1.00 N·m |
| **Safety factor** | **5.7** |

The hand torque and friction coefficient are assumptions, flagged as such.

### Legs — flat planar arcs, one design printed twice

The Eden 260V is priced by build height, so what matters is how tall a part
stands, not how long it is. A planar leg lies down with only its thickness
in Z: **12 mm**, against roughly 200 mm if the same arch were stood upright.
Nothing is out of plane, so no support is trapped inside the curve.

The legs are symmetric through their thickness, so **the second leg is the
first one flipped over** — one design, printed twice, and a spare is always
the right spare.

The bow is not decoration: the straight line from ear to marking point
passes about 20 mm *inside* the scalp, so a straight leg would foul the
head. Validation measures the real clearance rather than trusting the
number.

Stiffness follows the same trade. In the plane of the arc the beam is 16 mm
deep and very stiff, which is the direction the drawing force acts. Out of
plane it is only 12 mm — that is what the print constraint buys, and it is
why `leg_thickness` should not be reduced without re-checking deflection.

### Modules — one interface, either end

The ball joint and the marker holder share an identical tenon
(12 × 6 × 22 mm plus a 4 mm cross pin), so **either module fits either leg**.
Print a second ear module and the instrument becomes symmetric; print a
second marker holder and it becomes a plain caliper.

### Ear piece — a carrier for a silicone eartip

Revised at the client's request: the printed resin no longer touches the
ear. The tip is an earphone-style nozzle — Ø4.5 shaft, Ø5.5 retaining bead,
6.0 mm long, all client-stated — and a commercial silicone eartip goes over
it. The Ø15 stopper is retained and now does double duty: it still limits
insertion depth, and it is the wall the silicone base seats against.

The bead gives 0.5 mm of interference on the radius, reached over a 0.6 mm
ramp, so the eartip can be pushed on by hand and will not fall off.

**The nozzle root is deliberately left sharp.** A fillet there would hold the
silicone base off the flange, and the flange is exactly what the client
wants it to seat against. Every other exposed edge is broken.

### Marker holder — the pen's length drives the layout

The specified pen (AS ONE ProShare, Ø9 × 167 mm) will not fit inside a 34 mm
holder, so the bore runs straight through and about 108 mm of pen trails out
of the back. In line with the tenon that tail would drive straight into the
leg, so the barrel is offset 18 mm sideways and the pen passes alongside the
tip block with 2.25 mm to spare. The offset is in the plane of the leg's
arc, so the compass stays a planar linkage.

Every other thread on the device is printed and coarse; the clamp screw is a
short M4 in a thin lug, tightened repeatedly, so it takes a **bought-in steel
screw and a captured hex nut** instead.

`marker_tip_offset` is a user **setting**, not a fixed feature — the clamp
grips anywhere along the barrel. The same value must be used for both arcs
or the radii differ.

## How it swings, and where the radius is measured from

The client asked whether the long stroke from forehead to occiput is carried
by the ball joint's **spin**, with the tilt only taking up the difference
between the ear canal's direction and the leg's. It is — but working that
out surfaced something that changed the numbers.

**The instrument does not pivot at the ear canal.** With the ball joint left
at light friction, the ear piece stays put in the ear and the compass swings
about the **ball centre**, which sits 46.5 mm further out along the canal
axis. The ball centre belongs to both bodies, so it is fixed relative to both
— that is what makes it the pivot.

This matters because the arc radius has to be measured from the pivot:

| Pivot mode | Pivot separation (half) | Usable radius |
|---|---:|---|
| `ear_point` — joint locked | 72.2 mm | 96.2 – 153.6 mm |
| `ball_centre` — joint free | 118.7 mm | **134.6 – 180.2 mm** |

At the originally assumed 130 mm the arcs **never reach the midline** in
`ball_centre` mode. 160 mm about the ball centre puts the crossings within
2 mm of where 130 mm ear-to-marker would have — same marking points, correct
reference — so that is the default.

The construction stays exact in either mode, because both pivots remain
symmetric about x = 0. That symmetry now depends on **the ear pieces being
inserted equally on both sides**, which is a new error source worth
controlling in use.

### What the joint actually has to do

Sampled at 38 positions along the stroke, landing the instrument on its pivot
and marker tip and choosing the roll that minimises the lean:

| | |
|---|---|
| Spin swept by the stroke | **124°** (unlimited, so not a constraint) |
| Tilt demanded | **1.2° – 14.6°** |
| Tilt available | 22° |
| Margin | 7.4° |

So the client's reading is right: spin carries the arc, and the tilt only
absorbs the changing angle between the canal and the leg. Clearance to the
head stays above 12.3 mm across the whole stroke, including the pen's
trailing 108 mm.

## Printing (Stratasys Eden 260V, inkjet, soluble support)

Components are separate solids and are never fused. STLs are exported
**already laid flat** — each part rotated to put its smallest dimension
along Z.

| Component | Print height | Footprint | Qty |
|---|---|---|---|
| Leg | **12.00 mm** | 249.7 × 71.5 mm | 2 |
| HingeWasher | 2.00 mm | 44.0 × 44.0 mm | 1 |
| HingeKnob | 14.00 mm | 43.3 × 43.3 mm | 1 |
| EarPiece | 15.00 mm | 23.0 × 15.0 mm | 1 |
| MarkerHolder | 17.60 mm | 56.0 × 43.8 mm | 1 |
| BallStud | 18.00 mm | 42.5 × 18.0 mm | 1 |
| HingeBolt | 21.29 mm | 43.0 × 21.3 mm | 1 |
| Collar | 26.23 mm | 37.0 × 36.7 mm | 1 |
| BasePlug | 26.80 mm | 40.8 × 26.8 mm | 1 |
| Socket | 27.35 mm | 29.0 × 29.0 mm | 1 |

Printed together the build height is set by the Socket at **27.4 mm**.
Printing the two legs on their own costs only 12 mm.

**Do not assume printed threads work first time.** Every critical fit is a
parameter, listed in `parameters.TUNABLE_FITS` and reprinted in every report:
`socket_clearance` (0.25 mm radial), `thread_clearance` (0.20 mm radial),
`hinge_clearance`, `marker_clearance`, `connector_clearance`.

## Validation

`output/validation_report.txt` covers solid integrity, mesh printability,
bounding boxes, ball-socket fits, assembly strain, angular range, clamping
action, threads, internal consistency, boolean interference with measured
gaps, reference geometry, instrument kinematics, marking accuracy, head
clearance over the whole stroke, hinge lock capacity, print heights, module
interchange, the ear piece, outstanding work, CT-measured values and every
provisional parameter.

Four checks are worth understanding:

- **Interference** is a real boolean between the *placed* components, with
  a bounding-box broad phase. It caught a collar fouling a socket, a thread
  drawn a fraction of a turn out of phase, and modules seated at the wrong
  angle inside their mortises.
- **Mesh printability** tessellates each part exactly as the STL export does
  and demands a watertight, non-self-intersecting result. A valid solid does
  not guarantee a valid mesh: a thread crest running tangent to a cylinder
  of the same diameter gives a perfect B-rep and a broken STL.
- **Sweep clearance** samples 38 positions along the arc the marker actually
  travels, not just its endpoints, because the instrument leans furthest
  over the vault in the middle of the stroke. Worst case is 13.1 mm.
- **Hinge capacity** computes the slip safety factor instead of asserting
  that the lock holds.

A PASS means the solid model is coherent. It is not evidence of clinical
accuracy.

## Open issues

### 1. Ball insertion strain — RESOLVED 2026-10-26

This was the open risk, and it failed in test exactly as predicted. It is
closed by rear loading (above): assembly strain is now zero and the
validation warning is gone. What remains is to confirm on a second print
that the ball does drop in by hand and the plug screws home.

### 1b. Plug anti-rotation — open

The plug is held by thread friction alone. If it backs off in use, it needs
thread locking or a detent. Nothing has been tested yet.

### 2. Still needed from the client

- Confirm or replace the **ear reference height** (`ref_ear_depth_below_vertex`)
- Confirm the **working arc radius** (`ref_arc_radius`, currently 130 mm)
- The **range of head sizes** the instrument must cover
- The **marker model** — barrel diameter and length
- **Clinical sign-off on the ear insertion geometry**
- Confirm the CT substitution above, or supply the intended dataset

### 3. Known limitations

- The head reference is a fitted ellipsoid; clearance is measured radially
  from it, which is exact for a sphere and slightly optimistic otherwise.
- No structural analysis. Leg deflection, tenon strength and hinge stresses
  are unanalysed; sizes come from engineering judgement.
- Hand torque, friction coefficient and drawing force are assumed values.
- `marker_tip_offset` is a user *setting*, not a fixed feature. **The same
  value must be used for both arcs**, or the two radii differ.

## Recommended prototype testing sequence

1. **Socket alone.** Print one, try inserting a ball. Settles open issue 1
   before anything else is committed.
2. **Thread pair.** Print socket and collar. Check the collar runs down
   freely and the cone reaches the fingers before the thread bottoms. Tune
   `thread_clearance`, reprint.
3. **Full ball joint.** Add the stud and ear piece. Check the tilt range,
   that the stem clears the collar rim, and that the joint holds position
   hand-tight. Tune `socket_clearance`.
4. **Hinge.** Print two legs, washer, bolt and knob. Set an opening, then
   try to move it by hand at the leg tips. If it creeps, revisit the clamp
   before the rest is designed around it.
5. **Dry assembly.** Whole instrument, no patient. Check the modules swap
   between legs and the pin holes line up.
6. **Geometry check on a dummy head.** Mark two arcs on a mannequin or a
   printed skull, confirm the crossings are symmetric, and measure the
   repeatability of the radius after locking and re-locking.
7. Only then discuss clinical evaluation, which needs the ear geometry
   signed off first.

## File organisation

```
parameters.py               all inputs + derive(); no FreeCAD dependency
main.py                     entry point: build, validate, export
geometry/
    refmath.py              reference frame, arcs, sweep; no FreeCAD dependency
    primitives.py           threads, verified booleans, solid gate, fillets
    ball_joint.py           PHASE 2  stud, split socket, clamping collar
    main_hinge.py           PHASE 3  bolt, friction washer, knob
    ear_piece.py            PHASE 4  cone, stopper, female thread
    legs.py                 PHASE 5  flat arc legs
    marker_holder.py        PHASE 6  split clamp
    compass.py              PHASE 7  kinematics and assembly pose
    reference_geometry.py   PHASE 1  datum points, arcs, reference head
    validation.py           PHASE 8  checks and report writer
tools/
    run_freecad.sh          headless FreeCAD wrapper
    open_gui.sh             GUI launcher with visibility and camera set up
    gui_open.py             startup script it hands to FreeCAD
    measure_ct.py           CT skull measurement (numpy only)
config/
    ct_case01_measurements.json   full CT measurement output
    ct_case01_params.json         just the ref_* parameters
output/                     generated; safe to delete
```

`parameters.py` and `geometry/refmath.py` deliberately import no FreeCAD, so
the parameter system and the workflow geometry can be checked with plain
`python3`.

Every component passes through `primitives.require_solid()`, which raises
unless the result is exactly one valid, closed, positive-volume solid. All
booleans go through `primitives.safe_cut()` / `safe_fuse()`, which operate on
copies and **verify the operation actually did something** — OCCT will
occasionally return the base shape untouched from a cut with no error at
all, and that silent no-op once put a bolt through solid material.
