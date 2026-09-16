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
    """Slotted collet socket with external thread and a leg tenon."""
    R0 = d["finger_root_outer_radius"]

    # --- outer envelope ---------------------------------------------------
    base = Part.makeCylinder(R0, -d["socket_base_bottom_z"],
                             Vector(0, 0, d["socket_base_bottom_z"]))
    fingers = Part.makeCone(R0, d["socket_tip_outer_radius"],
                            d["socket_top_z"], Vector(0, 0, 0))
    body = prim.safe_fuse(base, fingers, "ball_joint")

    # The base cylinder IS the thread core, so this only adds the ridge.
    body = prim.safe_fuse(body, prim.thread_solid(p, d["thread_major_radius"],
                                       d["thread_length"],
                                       base_z=d["thread_bottom_z"]), "ball_joint")

    # --- leg tenon --------------------------------------------------------
    tw, tt, tl = (p["connector_tenon_width"], p["connector_tenon_thickness"],
                  p["connector_tenon_length"])
    tenon = Part.makeBox(tw, tt, tl,
                         Vector(-tw / 2.0, -tt / 2.0,
                                d["socket_base_bottom_z"] - tl))
    body = prim.safe_fuse(body, tenon, "ball_joint").removeSplitter()

    # --- internal cavity and mouth ---------------------------------------
    body = prim.safe_cut(body, Part.makeSphere(d["cavity_radius"]), "ball_joint")
    cone_h = d["socket_top_z"] + 5.0
    mouth = Part.makeCone(0.0,
                          cone_h * math.tan(math.radians(d["mouth_half_angle"])),
                          cone_h, Vector(0, 0, 0))
    body = prim.safe_cut(body, mouth, "ball_joint")

    # --- clamping slots ---------------------------------------------------
    # Each slot ends in a keyhole relief, because a square slot root is a
    # stress raiser and this part is expected to flex there on assembly.
    r_in = d["cavity_radius"] * p["socket_slot_inner_ratio"]
    r_out = R0 + 2.0
    w = p["socket_split_width"]
    z_root, z_top = d["slot_root_z"], d["socket_top_z"] + 1.0
    slot = Part.makeBox(r_out - r_in, w, z_top - z_root,
                        Vector(r_in, -w / 2.0, z_root))
    relief = Part.makeCylinder(p["socket_slot_relief_diameter"] / 2.0,
                               r_out - r_in, Vector(r_in, 0.0, z_root),
                               Vector(1, 0, 0))
    body = prim.safe_cut(body, prim.radial_pattern(prim.safe_fuse(slot, relief, "ball_joint"),
                                        p["socket_split_count"]), "ball_joint")

    # --- tenon pin hole ---------------------------------------------------
    z_pin = d["socket_base_bottom_z"] - p["connector_pin_inset"]
    body = prim.safe_cut(body, Part.makeCylinder(p["connector_pin_diameter"] / 2.0,
                                      tt + 4.0,
                                      Vector(0.0, -(tt / 2.0 + 2.0), z_pin),
                                      Vector(0, 1, 0)), "ball_joint")

    return prim.require_solid(body, "socket")


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
    bore_tool = prim.thread_solid(p, d["thread_major_radius"],
                                  -tool_base,          # runs up to exactly z = 0
                                  base_z=tool_base,
                                  grow=p["thread_clearance"])
    body = prim.safe_cut(blank, bore_tool, "ball_joint")

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
