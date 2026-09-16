"""
PHASE 5 - the two main legs.

ONE DESIGN, PRINTED TWICE. The legs are planar and symmetric through their
thickness, so the second leg is the first one flipped over. That halves the
design surface and means a spare is always the right spare.

Local frame:

        +Z   hinge axis, thickness 0 .. leg_thickness
        |
        o----- +X   in-plane, the arc bows this way
       /
     -Y   towards the tip

    pivot  = origin (bolt axis)
    tip    = (0, -leg_chord_length, 0)
    arc    = circle through both, bowing +X by leg_sagitta at mid-chord

WHY A FLAT ARC

The Eden 260V is priced by build height, so the governing constraint is how
tall the part stands on the tray, not how long it is. A leg that is planar
lies down with only its thickness in Z: 12 mm here, against roughly 200 mm
if the same arch were stood upright. Nothing about the arch is out of plane,
so no support material is trapped inside the curve either.

The bow is not decoration. The straight line from the ear to the marking
point passes about 20 mm INSIDE the scalp, so a straight leg would foul the
head. leg_sagitta pushes the beam out around it; validation measures the
real clearance against the reference head rather than trusting the number.

Stiffness follows from the same choice. In the plane of the arc the beam is
leg_width deep (16 mm) and very stiff, which is the direction the drawing
force acts. Out of plane it is only leg_thickness (12 mm), which is the
weaker axis - that is the trade the print constraint buys, and it is why
leg_thickness should not be reduced without re-checking deflection.
"""

from __future__ import annotations

import math

import FreeCAD as App
import Part
from FreeCAD import Vector

from . import primitives as prim


def arc_geometry(p, d):
    """Centre, end points and tip tangent of the leg's centreline arc."""
    C = p["leg_chord_length"]
    centre = Vector(p["leg_sagitta"] - d["leg_arc_radius"], -C / 2.0, 0.0)
    pivot = Vector(0.0, 0.0, 0.0)
    tip = Vector(0.0, -C, 0.0)
    half = math.radians(d["leg_arc_half_angle"])
    # Travelling pivot -> tip the polar angle about `centre` decreases, so the
    # tangent at the tip is (sin, -cos) of that angle.
    tangent = Vector(math.sin(-half), -math.cos(-half), 0.0)
    return {"centre": centre, "pivot": pivot, "tip": tip,
            "tangent": tangent,
            "tip_angle_deg": math.degrees(math.atan2(-tangent.x, tangent.y))}


def _band_face(p, d, g):
    """Planar annular-sector face between the inner and outer arc radii."""
    c = g["centre"]
    ri, ro = d["leg_inner_radius"], d["leg_outer_radius"]

    def at(point, radius):
        u = (point - c)
        u.normalize()
        return c + u * radius

    a_out, a_in = at(g["pivot"], ro), at(g["pivot"], ri)
    b_out, b_in = at(g["tip"], ro), at(g["tip"], ri)
    m_out = c + Vector(ro, 0.0, 0.0)          # apex of the bow
    m_in = c + Vector(ri, 0.0, 0.0)

    wire = Part.Wire([
        Part.Arc(a_out, m_out, b_out).toShape(),
        Part.makeLine(b_out, b_in),
        Part.Arc(b_in, m_in, a_in).toShape(),
        Part.makeLine(a_in, a_out),
    ])
    if not wire.isClosed():
        raise prim.GeometryError("leg band wire did not close")
    return Part.Face(wire)


def make_leg(p, d, warnings):
    """One leg: hinge boss, curved beam, tip block with the module mortise."""
    g = arc_geometry(p, d)
    t = p["leg_thickness"]

    band = _band_face(p, d, g).extrude(Vector(0, 0, t))
    boss = Part.makeCylinder(p["hinge_body_diameter"] / 2.0, t)
    body = prim.safe_fuse(band, boss, "legs")

    # --- tip block -------------------------------------------------------
    # Built along +Y then swung onto the tip tangent, so the module leaves
    # the leg along the direction the arc was already travelling.
    tw, tt, tl = p["leg_tip_width"], p["leg_tip_thickness"], p["leg_tip_length"]
    overlap = 10.0
    block = Part.makeBox(tw, tl + overlap, tt,
                         Vector(-tw / 2.0, -overlap, 0.0))
    place = App.Placement(g["tip"], App.Rotation(Vector(0, 0, 1),
                                                 g["tip_angle_deg"]))
    block.Placement = place
    body = prim.safe_fuse(body, block, "legs").removeSplitter()

    # --- bolt bore -------------------------------------------------------
    body = prim.safe_cut(body, Part.makeCylinder(d["hinge_bore_radius"], t + 2.0,
                                      Vector(0, 0, -1.0)), "legs")

    # --- mortise + cross pin --------------------------------------------
    mw, mt, md = d["mortise_width"], d["mortise_thickness"], d["mortise_depth"]
    mortise = Part.makeBox(mw, md + 1.0, mt,
                           Vector(-mw / 2.0, tl - md, (tt - mt) / 2.0))
    mortise.Placement = place
    body = prim.safe_cut(body, mortise, "legs")

    pin = Part.makeCylinder(p["connector_pin_diameter"] / 2.0 + p["connector_clearance"],
                            tw + 4.0,
                            Vector(-(tw / 2.0 + 2.0), tl - p["connector_pin_inset"],
                                   tt / 2.0),
                            Vector(1, 0, 0))
    pin.Placement = place
    body = prim.safe_cut(body, pin, "legs")

    return prim.require_solid(body, "leg")


def leg_placement(p, d, side, half_angle):
    """
    Put a leg into the hinge stack.

    `side` +1 is the pivot leg, -1 the drawing leg. The second leg is the
    same part flipped through 180 degrees about Y, which both stacks it
    above the washer and turns its bow outwards - the reason only one leg
    design has to be printed.
    """
    stack = d["hinge_stack_thickness"]
    if side > 0:
        local = App.Placement()
    else:
        local = App.Placement(Vector(0, 0, stack),
                              App.Rotation(Vector(0, 1, 0), 180))
    swing = App.Placement(Vector(0, 0, 0),
                          App.Rotation(Vector(0, 0, 1), side * half_angle))
    return swing.multiply(local)


def tip_frame(p, d, side, half_angle):
    """
    Where a module attaches, in hinge coordinates: the outer face of the tip
    block and the direction the module points.
    """
    g = arc_geometry(p, d)
    pl = leg_placement(p, d, side, half_angle)
    # Module axis sits on the mid-plane of the tip block, not on the leg's
    # bottom face - that is where the mortise is centred.
    face_local = (g["tip"] + g["tangent"] * p["leg_tip_length"]
                  + Vector(0, 0, p["leg_tip_thickness"] / 2.0))
    origin = pl.multVec(face_local)
    direction = pl.Rotation.multVec(g["tangent"])
    return {"origin": origin, "direction": direction}


def components(p, d, warnings):
    return {"Leg": make_leg(p, d, warnings)}
