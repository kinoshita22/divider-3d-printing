"""
PHASE 2 - adjustable ball joint between an ear piece and a main leg.

Local frame used by every shape in this module:

        +Z  towards the ear piece
        |
       ,-.        ball stud       (ear piece screws on top)
      (   )  <--- ball centre = LOCAL ORIGIN
     /|   |\
    | |   | |     clamping socket, slotted into fingers
    |_|___|_|
      |###|       external thread   <-- collar screws down over the fingers
      |   |
      |___|       tenon into the main leg
        |
        -Z  towards the leg

WHY THIS MECHANISM

Three concepts were considered for holding the ball:

 1. Plain spherical pocket, interference fit only.
    Rejected: the client explicitly ruled it out, and on a rigid printed
    photopolymer the holding force would be set by print tolerance alone,
    with no way to recover it once the socket wears or creeps.

 2. Two-part clamshell socket, ball trapped between a cup and a screwed-on
    cap. Mechanically simplest and needs no flexing material, which suits a
    brittle Eden photopolymer well. Rejected as the default because the
    clamping force acts only on two small contact zones, so the joint tends
    to either slip or lock solid with little usable range between.

 3. Slotted collet socket squeezed by a tapered collar  <-- CHOSEN.
    The collar's internal cone and the fingers' external cone share the same
    half angle, so advancing the collar by x closes the fingers by x*tan(taper).
    With a 6 degree taper that is a ~10:1 motion reduction, which is what
    makes the friction finely adjustable by hand and lets the joint be
    loosened, repositioned and retightened repeatedly. It also matches the
    split socket + retaining collar concept the client asked for.

The cost of choice 3 is that the fingers must spring outwards once, during
assembly, to let the ball past the mouth. That bending strain is computed in
parameters.derive() and checked in validation.py - it is the single most
likely failure mode of this design on a rigid photopolymer, and the
socket_mouth_extra_angle parameter exists to trade capture strength for a
gentler insertion.
"""

from __future__ import annotations

import math

import FreeCAD as App
import Part
from FreeCAD import Vector

from . import primitives as prim


# --------------------------------------------------------------------------
def make_ball_stud(p, d, warnings):
    """Ball + stem + ear-piece interface. Ball centre at the local origin."""
    shape = Part.makeSphere(d["ball_radius"])
    stem = Part.makeCylinder(d["stem_radius"], p["ball_stem_length"])
    shape = prim.safe_fuse(shape, stem, "ball_joint").removeSplitter()

    # Fillet where the stem leaves the ball: this is the highest stressed
    # section of the stud and a sharp re-entrant corner there is the classic
    # break point on a printed part.
    junction = prim.circular_edges(shape, d["stem_radius"],
                                   zmin=0.1, zmax=p["ball_stem_length"] - 0.1)
    shape = prim.safe_fillet(shape, junction, p["ball_stem_fillet"],
                             "ball/stem junction", warnings)

    if p["ball_stud_interface"] == "threaded":
        # Plain run-out neck at the thread's minor diameter. Without it the
        # thread crest runs tangent to the stem wall wherever the two
        # diameters match, which produces self-intersecting facets in the
        # exported STL even though the solid itself is valid.
        neck = Part.makeCylinder(d["stud_thread_minor_radius"],
                                 p["ball_stud_thread_relief"],
                                 Vector(0, 0, p["ball_stem_length"]))
        post = prim.thread_solid(p,
                                 major_radius=p["ball_stud_thread_diameter"] / 2.0,
                                 length=p["ball_stud_thread_length"],
                                 base_z=d["stud_thread_base_z"],
                                 pitch=p["ball_stud_thread_pitch"])
        shape = prim.safe_fuse(shape, neck, "ball_joint").fuse(post).removeSplitter()
    elif p["ball_stud_interface"] != "plain":
        raise prim.GeometryError("unknown ball_stud_interface %r"
                                 % p["ball_stud_interface"])

    return prim.require_solid(shape, "ball_stud")


def make_socket(p, d, warnings):
    """
    Slotted collet socket, open at the bottom so the ball loads from behind.

    REVISED 2026-10-26. The first printed socket shattered: all four fingers
    broke clean off at the slot roots while the ball was being pressed in
    through the mouth. The prediction had been 2.8% bending strain at exactly
    that location against a 1.5% limit, and the acrylic UV resin used
    (ProJet 2500) gave way without yielding.

    Widening the mouth would have cut the strain to about 1.5%, but the test
    only told us the material fails somewhere BELOW 2.8% - not where - so a
    1.5% design would have had unknown margin. Opening the bottom removes
    the press-in step altogether, so no part of the answer depends on a
    number nobody has measured.

    What changed:
      * below the equator everything is wider than the ball, so it drops in
      * a threaded plug closes the bottom and carries the lower seat
      * the mouth can stay narrow, so ball retention actually improves
      * the fingers now only ever flex by the clamping clearance

    The fingers, the collet cone, the mouth and the collar are unchanged.
    """
    R0 = d["finger_root_outer_radius"]
    base_r = d["socket_base_outer_radius"]

    # --- outer envelope ---------------------------------------------------
    fingers = Part.makeCone(R0, d["socket_tip_outer_radius"],
                            d["socket_top_z"], Vector(0, 0, 0))
    neck = Part.makeCylinder(R0, -d["socket_neck_bottom_z"],
                             Vector(0, 0, d["socket_neck_bottom_z"]))
    base = Part.makeCylinder(base_r,
                             d["socket_neck_bottom_z"] - d["socket_base_bottom_z"],
                             Vector(0, 0, d["socket_base_bottom_z"]))
    body = prim.safe_fuse(prim.safe_fuse(fingers, neck, "socket"), base, "socket")

    # The base cylinder IS the collar thread's core, so this only adds the ridge.
    body = prim.safe_fuse(body, prim.thread_solid(p, d["thread_major_radius"],
                                                  d["thread_length"],
                                                  base_z=d["thread_bottom_z"]),
                          "socket").removeSplitter()

    # --- internal cavity, mouth and the through bore ----------------------
    body = prim.safe_cut(body, Part.makeSphere(d["cavity_radius"]), "socket")
    cone_h = d["socket_top_z"] + 5.0
    mouth = Part.makeCone(0.0,
                          cone_h * math.tan(math.radians(d["mouth_half_angle"])),
                          cone_h, Vector(0, 0, 0))
    body = prim.safe_cut(body, mouth, "socket")

    # Everything below the equator opens out to clear the ball on its way in.
    bore_len = -d["socket_base_bottom_z"] + 1.0
    body = prim.safe_cut(body, Part.makeCylinder(
        d["plug_bore_radius"], bore_len,
        Vector(0, 0, d["socket_base_bottom_z"] - 1.0)), "socket")

    # --- internal thread for the plug --------------------------------------
    # Cut with the same generator the plug's own thread uses, grown by the
    # print clearance, and built in THIS frame so both are drawn in phase.
    plug_tool = prim.thread_solid(
        p, d["plug_thread_major_radius"],
        p["socket_plug_thread_length"] + 2.0 * p["socket_plug_pitch"],
        base_z=d["plug_thread_bottom_z"] - 2.0 * p["socket_plug_pitch"],
        grow=p["thread_clearance"], pitch=p["socket_plug_pitch"])
    body = prim.safe_cut(body, plug_tool, "socket")

    # --- clamping slots ----------------------------------------------------
    # Each slot ends in a keyhole relief, because a square slot root is a
    # stress raiser and this is where the first socket broke.
    r_in = d["cavity_radius"] * p["socket_slot_inner_ratio"]
    r_out = base_r + 2.0
    w = p["socket_split_width"]
    z_root, z_top = d["slot_root_z"], d["socket_top_z"] + 1.0
    slot = Part.makeBox(r_out - r_in, w, z_top - z_root,
                        Vector(r_in, -w / 2.0, z_root))
    relief = Part.makeCylinder(p["socket_slot_relief_diameter"] / 2.0,
                               r_out - r_in, Vector(r_in, 0.0, z_root),
                               Vector(1, 0, 0))
    body = prim.safe_cut(body, prim.radial_pattern(
        prim.safe_fuse(slot, relief, "socket"), p["socket_split_count"]),
        "socket")

    return prim.require_solid(body, "socket")


def make_base_plug(p, d, warnings):
    """
    Threaded plug that closes the socket and forms the ball's lower seat.

    Built in the JOINT frame, like the socket and collar, so its thread and
    the socket's internal thread start at the same height and are therefore
    drawn in phase.

    It also carries the tenon into the leg. That puts the leg's load through
    the plug thread, which is fine: an M%.0f thread with %.0f mm of
    engagement is far stronger than the %.0f x %.0f mm tenon it feeds.

    The tenon doubles as the wrench - grip it to screw the plug home - so no
    separate spanner flats are needed.
    """ % (2 * d["plug_thread_major_radius"], p["socket_plug_thread_length"],
           p["connector_tenon_width"], p["connector_tenon_thickness"])
    seat_z = -p["plug_seat_depth"]

    # Shank runs the full height, from the socket's bottom face up to the
    # seat rim. It has to bridge the thread run-out as well, or the flange
    # and the threaded section come out as two separate solids.
    body = Part.makeCylinder(d["plug_body_radius"],
                             seat_z - d["socket_base_bottom_z"],
                             Vector(0, 0, d["socket_base_bottom_z"]))

    # Threaded shank.
    body = prim.safe_fuse(body, prim.thread_solid(
        p, d["plug_thread_major_radius"], p["socket_plug_thread_length"],
        base_z=d["plug_thread_bottom_z"], pitch=p["socket_plug_pitch"]),
        "base_plug")

    # Flange: bottoms against the socket, so the seat lands at a known height.
    body = prim.safe_fuse(body, Part.makeCylinder(
        d["socket_base_outer_radius"], p["plug_flange_thickness"],
        Vector(0, 0, d["joint_mating_z"])), "base_plug")

    # Tenon into the leg, identical to the marker holder's.
    tw, tt, tl = (p["connector_tenon_width"], p["connector_tenon_thickness"],
                  p["connector_tenon_length"])
    body = prim.safe_fuse(body, Part.makeBox(
        tw, tt, tl, Vector(-tw / 2.0, -tt / 2.0, d["joint_mating_z"] - tl)),
        "base_plug").removeSplitter()

    # Spherical seat for the ball, concentric with the socket's cavity.
    body = prim.safe_cut(body, Part.makeSphere(d["cavity_radius"]), "base_plug")

    # Cross pin through the tenon.
    z_pin = d["joint_mating_z"] - p["connector_pin_inset"]
    body = prim.safe_cut(body, Part.makeCylinder(
        p["connector_pin_diameter"] / 2.0 + p["connector_clearance"], tw + 4.0,
        Vector(-(tw / 2.0 + 2.0), 0.0, z_pin), Vector(1, 0, 0)), "base_plug")

    return prim.require_solid(body, "base_plug")


def make_collar(p, d, warnings):
    """
    Clamping collar. Internal thread at the bottom, matching cone above it
    running out through an open top, scalloped for finger grip.

    Positioned as drawn at its nominal (just-touching) height, so the preview
    assembly has no interference. Tightening is the user advancing it by
    collar_advance_to_close.
    """
    blank = Part.makeCylinder(d["collar_outer_radius"], d["collar_height"],
                              Vector(0, 0, d["collar_bottom_z"]))

    # Cut with the SAME thread definition, grown by the print clearance.
    #
    # The tool must start a WHOLE NUMBER OF PITCHES from where the socket's
    # thread starts. A helix's angular phase is fixed by its start point, so
    # a tool begun at any other height draws the collar a fraction of a turn
    # out of step with the socket it has to screw onto - which shows up as
    # real interference in the assembled model even though a physical nut
    # would simply rotate into place.
    tool_base = d["thread_bottom_z"] - 2.0 * p["thread_pitch"]
    # Plain bore first, clearing the socket's neck and base all the way up
    # to where the cone starts, then the thread is carved into its lower part.
    plain_r = d["socket_base_outer_radius"] + p["thread_clearance"]
    body = prim.safe_cut(blank, Part.makeCylinder(
        plain_r, -d["collar_bottom_z"] + 1.0,
        Vector(0, 0, d["collar_bottom_z"] - 1.0)), "ball_joint")

    bore_tool = prim.thread_solid(p, d["thread_major_radius"],
                                  d["thread_top_z"] - tool_base,
                                  base_z=tool_base,
                                  grow=p["thread_clearance"])
    body = prim.safe_cut(body, bore_tool, "ball_joint")

    # The cone runs right out through the top face - no top plate. Anything
    # closing over the top would foul the finger tips as the collar advances,
    # and would sit exactly where the tilting stem needs room.
    cone = Part.makeCone(d["collar_cone_bottom_radius"],
                         d["collar_cone_top_radius"],
                         d["collar_cone_length"] + 0.01, Vector(0, 0, 0))
    body = prim.safe_cut(body, cone, "ball_joint")

    flute = Part.makeCylinder(
        p["collar_flute_radius"], d["collar_height"] + 2.0,
        Vector(d["collar_outer_radius"] + p["collar_flute_radius"]
               - p["collar_flute_depth"], 0.0, d["collar_bottom_z"] - 1.0))
    body = prim.safe_cut(body, prim.radial_pattern(flute, p["collar_flute_count"]), "ball_joint")

    return prim.require_solid(body, "collar")


# --------------------------------------------------------------------------
def components(p, d, warnings):
    """All three parts of one ball joint, in the local frame."""
    return {
        "BallStud": make_ball_stud(p, d, warnings),
        "Socket": make_socket(p, d, warnings),
        "BasePlug": make_base_plug(p, d, warnings),
        "Collar": make_collar(p, d, warnings),
    }


def joint_placement(p, d, side):
    """
    Put a joint at an ear reference point.

    Local +Z points at the ear, so for the LEFT ear (global +X) the joint
    sits outboard of the ear and its +Z maps to global -X.
    """
    e = d["ear_half_distance"]
    stand = d["ball_centre_standoff"]
    if side == "Left":
        return App.Placement(Vector(e + stand, 0, 0),
                             App.Rotation(Vector(0, 1, 0), -90))
    if side == "Right":
        return App.Placement(Vector(-(e + stand), 0, 0),
                             App.Rotation(Vector(0, 1, 0), 90))
    raise ValueError("side must be 'Left' or 'Right'")


def stud_tilt_placement(p, d):
    """Demo tilt of the stud inside its socket, about the ball centre."""
    if abs(p["ball_joint_demo_tilt"]) < 1e-9:
        return App.Placement()
    return App.Placement(Vector(0, 0, 0),
                         App.Rotation(Vector(0, 1, 0), p["ball_joint_demo_tilt"]))


def build(doc, p, d, side, warnings, group=None):
    """Create the three document objects for one ball joint."""
    shapes = components(p, d, warnings)
    base = joint_placement(p, d, side)
    objs = []
    for name, shape in shapes.items():
        obj = doc.addObject("Part::Feature", "%s_%s" % (name, side))
        obj.Label = "%s %s" % (name, side)
        obj.Shape = shape
        local = stud_tilt_placement(p, d) if name == "BallStud" else App.Placement()
        obj.Placement = base.multiply(local)
        if group is not None:
            group.addObject(obj)
        objs.append(obj)
    return objs
