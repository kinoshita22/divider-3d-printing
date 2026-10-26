"""
PHASE 7 - compass kinematics and assembly.

Turns the mechanism into the instrument: works out how far the hinge has to
open for a chosen arc radius, places every component, and positions the
whole thing on the reference head.

THE OPENING IS NOT 2*C*sin(theta)

That textbook relation holds when the two functional points sit at the ends
of the legs. Here they do not: the ear piece stands about 60 mm beyond the
pivot leg's tip block, and the marker tip about 59 mm beyond the drawing
leg's, both along the tip tangent rather than along the chord. The radius is
therefore solved numerically from the real geometry, which also copes with
the two modules having different reaches.

    ear tip   = tipframe(+1).origin + tangent * module_reach_pivot
    marker tip= tipframe(-1).origin + tangent * module_reach_drawing
    R(theta)  = | ear tip - marker tip |

COMPASS FRAME
    z along the hinge bolt, pivot leg at z = 0..t, washer, drawing leg above.
    The legs swing +theta and -theta about z.

PLACING IT ON THE HEAD
    The instrument is a rigid body once locked, and it has to touch two
    known points: an ear reference point and a midline arc crossing. Those
    two constraints leave one degree of freedom - rotation about the line
    joining them. That roll is what decides whether the arch clears the
    skull, so it is chosen by search rather than guessed: sample the roll,
    measure the worst clearance along both legs against the reference head,
    keep the best.
"""

from __future__ import annotations

import math

import FreeCAD as App
from FreeCAD import Vector

from . import ear_piece as ear_piece_mod
from . import marker_holder as marker_mod
from . import legs as legs_mod
from . import refmath


def module_reach(p, d):
    """Rough module extents, used only for clearance sampling."""
    return {
        "pivot": -d["socket_base_bottom_z"] + d["ball_centre_standoff"],
        "drawing": p["marker_holder_length"] + p["marker_tip_offset"],
    }


def solve_half_angle(p, d, radius, lo=1.0, hi=None, iters=80):
    """Half opening angle that puts the two functional points `radius` apart."""
    if hi is None:
        hi = p["max_leg_opening_angle"] / 2.0
    f_lo = functional_points(p, d, lo)["radius"]
    f_hi = functional_points(p, d, hi)["radius"]
    if not (min(f_lo, f_hi) <= radius <= max(f_lo, f_hi)):
        return None, {"reachable": False, "min": f_lo, "max": f_hi}
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if (functional_points(p, d, mid)["radius"] - radius) * (f_lo - radius) > 0:
            lo, f_lo = mid, functional_points(p, d, mid)["radius"]
        else:
            hi = mid
    ang = 0.5 * (lo + hi)
    return ang, {"reachable": True, "min": min(f_lo, f_hi), "max": max(f_lo, f_hi),
                 "achieved": functional_points(p, d, ang)["radius"]}


# --------------------------------------------------------------------------
def module_mating_point(p, d, which):
    """
    The point in a module's OWN frame that beds against the leg's tip block.

    The ball joint meets it on its axis; the marker holder does not - its
    barrel is offset sideways so the pen's tail can pass the leg - so this
    cannot be reduced to a distance along the module axis.
    """
    if which == "ball":
        # The tenon moved onto the base plug when the socket was opened for
        # rear loading, so the leg seats below the plug's flange.
        return Vector(0.0, 0.0, d["joint_mating_z"])
    if which == "marker":
        return marker_mod.tenon_face_local(p, d)
    raise ValueError(which)


def _module_placement(frame, leg_rot, mating_local):
    """
    Seat a module on a leg tip.

    All three axes are pinned, not just the module's +Z. A rotation that only
    maps +Z onto the tip direction leaves the spin about that axis free, and
    the tenon then lands at an angle inside its rectangular mortise - which
    shows up as four small corner interferences rather than an obvious error.

        +Z -> the tip tangent, the way the module points
        +Y -> the leg's thickness direction, so the tenon's thickness lines
              up with the mortise
        +X -> completes a right-handed set
    """
    ez = Vector(frame["direction"])
    ez.normalize()
    ey = leg_rot.multVec(Vector(0, 0, 1))
    ey = ey - ez * ey.dot(ez)
    ey.normalize()
    ex = ey.cross(ez)
    m = App.Matrix(ex.x, ey.x, ez.x, 0.0,
                   ex.y, ey.y, ez.y, 0.0,
                   ex.z, ey.z, ez.z, 0.0,
                   0.0, 0.0, 0.0, 1.0)
    rot = App.Placement(m).Rotation
    return App.Placement(frame["origin"] - rot.multVec(mating_local), rot)


def component_placements(p, d, half_angle):
    """Placement of every component, in compass coordinates."""
    out = {
        "Leg_Pivot": legs_mod.leg_placement(p, d, 1, half_angle),
        "Leg_Drawing": legs_mod.leg_placement(p, d, -1, half_angle),
        "HingeBolt": App.Placement(),
        "HingeWasher": App.Placement(),
        "HingeKnob": App.Placement(),
    }
    ear_frame = legs_mod.tip_frame(p, d, 1, half_angle)
    mk_frame = legs_mod.tip_frame(p, d, -1, half_angle)

    out["BallStud"] = _module_placement(ear_frame, out["Leg_Pivot"].Rotation,
                                        module_mating_point(p, d, "ball"))
    out["Socket"] = out["BallStud"]
    out["BasePlug"] = out["BallStud"]
    out["Collar"] = out["BallStud"]
    # Seated on the stud's relief neck, and spun by the thread phase offset
    # so the printed female thread actually meshes with the male one.
    out["EarPiece"] = out["BallStud"].multiply(
        App.Placement(Vector(0, 0, d["stud_thread_base_z"]),
                      App.Rotation(Vector(0, 0, 1),
                                   ear_piece_mod.thread_phase_offset(p))))
    out["MarkerHolder"] = _module_placement(mk_frame, out["Leg_Drawing"].Rotation,
                                            module_mating_point(p, d, "marker"))
    return out


def functional_points(p, d, half_angle):
    """
    The points that matter geometrically, in compass coordinates.

    Two radii are reported because they answer different questions. With the
    ball joint locked the instrument turns about the ear canal, so the arc
    radius is ear tip to marker tip. With it free - the intended use - the
    ear piece stays put and the compass turns about the BALL CENTRE, so the
    radius is measured from there instead. The two differ by roughly the
    length of the ear piece stack, which is not a small number.
    """
    pl = component_placements(p, d, half_angle)
    ball = pl["BallStud"].multVec(Vector(0, 0, 0))
    ear = pl["BallStud"].multVec(Vector(0, 0, d["ball_centre_standoff"]))
    marker = pl["MarkerHolder"].multVec(marker_mod.marker_tip_local(p, d))
    # Stud axis points from the ball towards the ear piece.
    stud_axis = pl["BallStud"].Rotation.multVec(Vector(0, 0, 1))
    out = {
        "ball_centre": ball, "ear": ear, "marker": marker,
        "stud_axis": stud_axis,
        "radius_ear": (ear - marker).Length,
        "radius_ball": (ball - marker).Length,
        "placements": pl,
    }
    out["radius"] = (out["radius_ear"]
                     if p.get("pivot_mode", "ball_centre") == "ear_point"
                     else out["radius_ball"])
    out["pivot"] = ear if p.get("pivot_mode", "ball_centre") == "ear_point" else ball
    return out


# --------------------------------------------------------------------------
def _sample_points(p, d, half_angle, placements, n=48):
    """
    Points to clearance-check, as (point, radius allowance, group).

    Only the parts that MUST miss the head are included. The ear piece and
    the protruding pen are deliberately left out: both are supposed to reach
    the scalp, and treating them as obstructions reports a collision for the
    instrument doing exactly what it is for.

    Allowances are radial: each sample stands for a body of that radius
    around the sampled axis, so the reported clearance is to the outside of
    the part, not to its centreline.
    """
    g = legs_mod.arc_geometry(p, d)
    c, ri = g["centre"], d["leg_inner_radius"]
    half = math.radians(d["leg_arc_half_angle"])
    pts = []

    # (a) the arches themselves - inner edge, the surface facing the head
    for key in ("Leg_Pivot", "Leg_Drawing"):
        pl = placements[key]
        for i in range(n + 1):
            th = half - 2.0 * half * i / n
            local = c + Vector(ri * math.cos(th), ri * math.sin(th),
                               p["leg_thickness"] / 2.0)
            pts.append((pl.multVec(local), 0.0, "leg"))

    # (b) ball joint body: socket base out to the top of the collar, sampled
    #     on the joint axis with the collar's radius as the allowance.
    pl = placements["BallStud"]
    for i in range(11):
        z = d["joint_mating_z"] + (d["collar_top_z"] - d["joint_mating_z"]) * i / 10.0
        pts.append((pl.multVec(Vector(0, 0, z)), d["collar_outer_radius"],
                    "ball joint"))

    # (d) the pen's trailing 108 mm. It is not a printed part, but it sweeps
    #     the same space and has to miss both the head and the leg.
    pl = placements["MarkerHolder"]
    for i in range(13):
        z = -d["marker_tail_length"] * i / 12.0
        pts.append((pl.multVec(Vector(0, 0, z)), d["marker_bore_radius"],
                    "marker tail"))

    # (c) marker holder. The barrel is a cylinder, so its axis carries the
    #     barrel radius as an allowance. The clamp lugs are NOT axisymmetric
    #     - they project from one side only - so they are sampled where they
    #     actually are instead of being smeared into the allowance, which
    #     would report a collision for a part that is nowhere near the head.
    pl = placements["MarkerHolder"]
    ro = d["marker_holder_outer_radius"]
    for i in range(11):
        local = Vector(0, 0, p["marker_holder_length"] * i / 10.0)
        pts.append((pl.multVec(local), ro, "marker holder"))
    ew, el, eh = (p["marker_clamp_ear_width"], p["marker_clamp_ear_length"],
                  p["marker_clamp_ear_height"])
    ey = ew + p["marker_split_width"] / 2.0
    z0 = (p["marker_holder_length"] - eh) / 2.0
    for x in (ro - 2.0, ro - 2.0 + el):
        for y in (-ey, ey):
            for z in (z0, z0 + eh):
                pts.append((pl.multVec(Vector(x, y, z)), 0.0, "marker clamp lugs"))
    return pts


def _rigid_to_head(p, pivot_point, target_point, anchor_local, marker_local,
                   roll_deg):
    """
    Transform taking the compass frame onto the head: the instrument's pivot
    onto the head's pivot point, the marker tip onto the arc crossing, then
    `roll` about the line between them.
    """
    v_local = marker_local - anchor_local
    v_head = Vector(*target_point) - Vector(*pivot_point)
    base = App.Rotation(v_local, v_head)
    axis = Vector(v_head)
    axis.normalize()
    roll = App.Rotation(axis, roll_deg)
    rot = roll.multiply(base)
    pos = Vector(*pivot_point) - rot.multVec(anchor_local)
    return App.Placement(pos, rot)


def head_placement(p, d, half_angle, pivot_point, target_point, roll_deg=None,
                   coarse=10.0, mode=None):
    """
    Put the assembled compass on the head.

    With roll_deg given, that roll is used. Otherwise the roll is searched:

      "max_clearance" - whatever keeps the mechanism furthest off the head
      "hinge_up"      - hold it the way a compass normally is, hinge above
                        the ear axis, among the rolls that still clear the
                        head by assembly_min_clearance

    The roll changes nothing about the printed parts. It only decides how
    the instrument is presented in the assembly, which is a handling
    question, not a geometric one - so it is a parameter rather than a
    silent choice.
    """
    fp = functional_points(p, d, half_angle)
    placements = fp["placements"]
    samples = _sample_points(p, d, half_angle, placements)
    # The instrument is landed by its PIVOT, not by the ear tip: with the
    # ball joint free it is the pivot that stays put while everything else
    # swings around it.
    anchor = fp["pivot"]

    def clearance_by_group(roll):
        tr = _rigid_to_head(p, pivot_point, target_point, anchor, fp["marker"], roll)
        out = {}
        for pt, allow, grp in samples:
            q = tr.multVec(pt)
            v = refmath.ellipsoid_clearance(p, (q.x, q.y, q.z)) - allow
            if grp not in out or v < out[grp]:
                out[grp] = v
        return out

    def worst_clearance(roll):
        return min(clearance_by_group(roll).values())

    if roll_deg is not None:
        return (_rigid_to_head(p, pivot_point, target_point, anchor, fp["marker"],
                               roll_deg), worst_clearance(roll_deg), roll_deg,
                clearance_by_group(roll_deg))

    mode = p.get("assembly_roll_mode", "max_clearance") if mode is None else mode

    def hinge_height(roll):
        tr = _rigid_to_head(p, pivot_point, target_point, anchor, fp["marker"],
                            roll)
        return tr.multVec(Vector(0, 0, 0)).z

    if mode == "hinge_up":
        floor = p.get("assembly_min_clearance", 2.0)
        best_roll, best_h, best = None, -1e9, None
        r = 0.0
        while r < 360.0:
            c = worst_clearance(r)
            if c >= floor:
                h = hinge_height(r)
                if h > best_h:
                    best_h, best_roll, best = h, r, c
            r += coarse
        if best_roll is None:          # nothing clears: fall back, and say so
            mode = "max_clearance"
        else:
            step = coarse / 2.0
            while step > 0.25:
                for cand in (best_roll - step, best_roll + step):
                    if worst_clearance(cand) >= floor and hinge_height(cand) > best_h:
                        best_h, best_roll, best = hinge_height(cand), cand, worst_clearance(cand)
                step *= 0.5

    if mode != "hinge_up":
        best_roll, best = 0.0, -1e9
        r = 0.0
        while r < 360.0:
            c = worst_clearance(r)
            if c > best:
                best, best_roll = c, r
            r += coarse
        step = coarse / 2.0
        while step > 0.25:
            for cand in (best_roll - step, best_roll + step):
                c = worst_clearance(cand)
                if c > best:
                    best, best_roll = c, cand
            step *= 0.5
    return (_rigid_to_head(p, pivot_point, target_point, anchor, fp["marker"],
                           best_roll), best, best_roll % 360.0,
            clearance_by_group(best_roll))


def sweep_clearance(p, d, half_angle, pivot_point, targets, coarse=15.0):
    """
    Clearance along the whole marking stroke, not just at its ends.

    Checking only the two midline crossings would miss the middle of the
    stroke, where the instrument leans furthest over the vault. At each
    target the best available roll is found, so the result answers "can this
    be drawn at all", assuming the user is free to orient the instrument
    comfortably as they sweep.
    """
    worst = None
    rows = []
    for t in targets:
        pt = t["point"]
        _, clear, roll, groups = head_placement(p, d, half_angle, pivot_point,
                                                pt, coarse=coarse)
        rows.append({"point": pt, "clearance": clear, "roll": roll,
                     "groups": groups})
        if worst is None or clear < worst["clearance"]:
            worst = rows[-1]
    return {"worst": worst, "samples": rows}


def assembly(p, d, radius=None, pivot_point=None, target=None, roll=None):
    """
    Everything needed to place the instrument on the head for one arc:
    the opening angle, the component placements, and the pose.
    """
    radius = p["ref_arc_radius"] if radius is None else radius
    half, info = solve_half_angle(p, d, radius)
    if half is None:
        return {"solved": False, "radius_info": info, "half_angle": None}
    out = {"solved": True, "half_angle": half, "radius_info": info,
           "opening_angle": 2.0 * half,
           "placements": component_placements(p, d, half),
           "functional": functional_points(p, d, half)}
    if pivot_point is not None and target is not None:
        pose, clear, used_roll, groups = head_placement(p, d, half, pivot_point,
                                                        target, roll_deg=roll)
        out.update({"pose": pose, "clearance": clear, "roll": used_roll,
                    "clearance_groups": groups})
    return out


def joint_demand(p, d, half_angle, side="left", coarse=6.0, refine=True):
    """
    What the ball joint is actually asked to do while an arc is drawn.

    The client's question: is the long swing from forehead to occiput carried
    by the joint's SPIN, with the tilt only taking up the difference between
    the ear canal's direction and the leg's? This answers it with numbers.

    Geometry of the problem. The ear piece is held in the ear, so the stud
    axis is fixed in space along the canal. The ball centre is fixed too - it
    belongs to both bodies. The compass therefore has exactly three freedoms
    about that centre: spin about the stud axis, which is UNLIMITED, and tilt
    away from it, which is not.

    For each point along the stroke the instrument is landed on its pivot and
    its marker tip, which leaves one freedom - roll about the line joining
    them. Rolling changes how far the stud axis has to lean, so the roll that
    minimises the lean is the one the user would naturally adopt, and that
    minimum is the tilt the joint must supply. Anything above
    ball_joint_max_angle is a position the instrument cannot reach.

    Returns the tilt demanded at each sample, plus the spin swept, which is
    what actually carries the stroke.
    """
    fp = functional_points(p, d, half_angle)
    pivot_l, pivot_r = refmath.pivot_points(p, d)
    pivot = pivot_l if side == "left" else pivot_r
    # The ear piece points INTO the ear, i.e. opposite the outward canal axis.
    u_out = refmath.ear_axis(p, d, side)
    required_axis = Vector(-u_out[0], -u_out[1], -u_out[2])

    targets = refmath.sweep_targets(p, d, pivot)
    if not targets:
        return {"reachable": False, "samples": [], "targets": 0}

    rows = []
    for t in targets:
        best = None
        r = 0.0
        while r < 360.0:
            tr = _rigid_to_head(p, pivot, t["point"], fp["pivot"], fp["marker"], r)
            axis = tr.Rotation.multVec(fp["stud_axis"])
            tilt = math.degrees(axis.getAngle(required_axis))
            if best is None or tilt < best[0]:
                best = (tilt, r, axis)
            r += coarse
        if refine:
            step = coarse / 2.0
            while step > 0.05:
                for cand in (best[1] - step, best[1] + step):
                    tr = _rigid_to_head(p, pivot, t["point"], fp["pivot"],
                                        fp["marker"], cand)
                    axis = tr.Rotation.multVec(fp["stud_axis"])
                    tilt = math.degrees(axis.getAngle(required_axis))
                    if tilt < best[0]:
                        best = (tilt, cand, axis)
                step *= 0.5
        rows.append({"point": t["point"], "tilt": best[0], "roll": best[1] % 360.0})

    tilts = [r["tilt"] for r in rows]
    # Spin swept: how far the marker travels around the canal axis. This is
    # the motion that actually draws the arc.
    def azimuth(pt):
        v = Vector(pt[0] - pivot[0], pt[1] - pivot[1], pt[2] - pivot[2])
        axial = Vector(*u_out) * v.dot(Vector(*u_out))
        perp = v - axial
        return perp

    ref = azimuth(rows[0]["point"])
    spins = []
    for r in rows:
        q = azimuth(r["point"])
        if ref.Length > 1e-9 and q.Length > 1e-9:
            spins.append(math.degrees(ref.getAngle(q)))
    return {
        "reachable": True,
        "targets": len(rows),
        "samples": rows,
        "tilt_min": min(tilts),
        "tilt_max": max(tilts),
        "tilt_range": max(tilts) - min(tilts),
        "spin_swept": max(spins) if spins else 0.0,
        "limit": p["ball_joint_max_angle"],
        "within_limit": max(tilts) <= p["ball_joint_max_angle"],
    }
