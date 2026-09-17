"""
PHASE 6 - marker holder.

REVISED 2026-09-18 for the specified pen: AS ONE ProShare skin marker,
Ø9 mm x 167 mm.

THE LENGTH DRIVES THE LAYOUT. 167 mm of pen cannot live inside a 34 mm
holder, so the bore is a THROUGH hole and the pen's tail - about 108 mm of
it - trails out of the back. If the barrel sat in line with the tenon, that
tail would run straight into the leg. So the barrel is offset sideways from
the tenon by marker_mount_offset and the pen passes cleanly alongside the
leg's tip block.

    +Z   towards the scalp
    +X   away from the leg; the clamp lugs open this way
    -X   the tenon, which plugs into the leg

    z = -22..0 .... tenon (the SAME interface the ball joint uses), at -X
    z = 0..12 ..... bridge joining tenon to barrel
    z = 0..34 ..... barrel, bore straight through
    z = 34+ ....... pen protruding by marker_tip_offset
    z < 0 ......... pen tail, running back past the leg

The offset keeps the whole mechanism planar - barrel and tenon both lie in
the plane of the leg's arc - so the compass stays a planar linkage and the
kinematics keep a single plane to work in.

MARKER_TIP is a SETTING, not a fixed feature. The clamp grips the pen
anywhere along its length, so marker_tip_offset is how far the user chooses
to let it stand proud. The same value must be used for both arcs, or the two
radii differ and the crossings leave the midline.

WHY A METAL SCREW HERE

Every other threaded feature on this device is printed, because they are
coarse and their loads are spread over many turns. This clamp is the
opposite: a short M4 in a thin lug, tightened repeatedly, right where the
user applies hand force. A printed M4 in a rigid photopolymer would strip.
So the lug takes a clearance hole and a captured hex nut, and the fastener
is a bought-in steel screw.
"""

from __future__ import annotations

import math

import FreeCAD as App
import Part
from FreeCAD import Vector

from . import primitives as prim


def hex_prism(across_flats, height, base, direction=Vector(0, 0, 1)):
    """Hexagonal prism for capturing a standard nut."""
    r = across_flats / math.sqrt(3.0)          # circumradius
    pts = [Vector(r * math.cos(math.radians(60 * i)),
                  r * math.sin(math.radians(60 * i)), 0.0) for i in range(6)]
    face = Part.Face(Part.Wire(Part.makePolygon(pts + [pts[0]])))
    solid = face.extrude(Vector(0, 0, height))
    if direction != Vector(0, 0, 1):
        solid.Placement = App.Placement(base, App.Rotation(Vector(0, 0, 1), direction))
    else:
        solid.translate(base)
    return solid


def make_marker_holder(p, d, warnings):
    ro = d["marker_holder_outer_radius"]
    L = p["marker_holder_length"]
    bore_r = d["marker_bore_radius"]
    off = p["marker_mount_offset"]
    tw, tt, tl = (p["connector_tenon_width"], p["connector_tenon_thickness"],
                  p["connector_tenon_length"])
    bridge_t = p["marker_bridge_thickness"]

    body = Part.makeCylinder(ro, L)

    # --- bridge: barrel across to the tenon -------------------------------
    x_min = -(off + tw / 2.0)
    bridge = Part.makeBox(ro - x_min, tt + 2.0 * p["marker_clamp_thickness"],
                          bridge_t,
                          Vector(x_min, -(tt / 2.0 + p["marker_clamp_thickness"]),
                                 0.0))
    body = prim.safe_fuse(body, bridge, "marker_holder")

    # --- tenon, identical to the ball joint's so modules interchange ------
    tenon = Part.makeBox(tw, tt, tl, Vector(-off - tw / 2.0, -tt / 2.0, -tl))
    body = prim.safe_fuse(body, tenon, "marker_holder").removeSplitter()

    # --- clamp lugs, opening away from the leg ---------------------------
    ew, el, eh = (p["marker_clamp_ear_width"], p["marker_clamp_ear_length"],
                  p["marker_clamp_ear_height"])
    split = p["marker_split_width"]
    ey = ew + split / 2.0
    z_ear = (L - eh) / 2.0
    ears = Part.makeBox(el, 2.0 * ey, eh, Vector(ro - 2.0, -ey, z_ear))
    body = prim.safe_fuse(body, ears, "marker_holder").removeSplitter()

    # --- bore, straight through: the pen has to pass all the way -----------
    body = prim.safe_cut(body, Part.makeCylinder(bore_r, L + tl + 4.0,
                                                 Vector(0, 0, -tl - 2.0)),
                         "marker_holder")

    # --- split, opening the bore to the +X side ---------------------------
    x_end = ro + el + 2.0
    body = prim.safe_cut(body, Part.makeBox(x_end, split, L + 2.0,
                                            Vector(0.0, -split / 2.0, 1.0)),
                         "marker_holder")

    # --- clamp screw and captured nut -------------------------------------
    x_screw = ro - 2.0 + el * 0.55
    z_screw = L / 2.0
    body = prim.safe_cut(body, Part.makeCylinder(
        p["marker_screw_diameter"] / 2.0 + p["connector_clearance"],
        2.0 * ey + 4.0, Vector(x_screw, -(ey + 2.0), z_screw), Vector(0, 1, 0)),
        "marker_holder")
    nut = hex_prism(p["marker_nut_across_flats"] + 2.0 * p["connector_clearance"],
                    p["marker_nut_thickness"],
                    Vector(x_screw, -ey - 0.01, z_screw), Vector(0, 1, 0))
    body = prim.safe_cut(body, nut, "marker_holder")

    # --- cross pin through the tenon --------------------------------------
    body = prim.safe_cut(body, Part.makeCylinder(
        p["connector_pin_diameter"] / 2.0 + p["connector_clearance"], tw + 4.0,
        Vector(-off - (tw / 2.0 + 2.0), 0.0, -p["connector_pin_inset"]),
        Vector(1, 0, 0)), "marker_holder")

    return prim.require_solid(body, "marker_holder")


def marker_tip_local(p, d):
    """MARKER_TIP in the holder's own frame: on the bore axis, past the nose."""
    return Vector(0.0, 0.0, p["marker_holder_length"] + p["marker_tip_offset"])


def tenon_face_local(p, d):
    """
    The point on the tenon's mating face that seats against the leg tip
    block, in holder coordinates. This is what the assembly lines up.
    """
    return Vector(-p["marker_mount_offset"], 0.0, 0.0)


def pen_tail_solid(p, d):
    """
    The trailing part of the pen, as a solid, for clearance checking. It is
    not a printed component - it stands in for the bought-in marker.
    """
    return Part.makeCylinder(d["marker_bore_radius"], d["marker_tail_length"],
                             Vector(0, 0, -d["marker_tail_length"]))


def components(p, d, warnings):
    return {"MarkerHolder": make_marker_holder(p, d, warnings)}
