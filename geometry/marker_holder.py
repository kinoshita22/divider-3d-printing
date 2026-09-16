"""
PHASE 6 - marker holder.

A split clamp around a plain cylindrical bore, so a commercially available
fine-tip surgical marker can be dropped in, set to the depth the user wants,
and swapped when it dries out.

    z = -22..0 ..... tenon, the SAME interface the ball joint uses
    z = 0..34 ...... clamp body, bore up the middle
    z = 34+ ........ marker protruding towards the scalp
    MARKER_TIP ..... z = marker_holder_length + marker_tip_offset

NO MARKER HAS BEEN SPECIFIED. marker_diameter is a placeholder. Measure the
barrel of the pen that will actually be used and set it before printing;
the clamp only takes up print tolerance and a millimetre or so of grip, not
a wrong nominal diameter.

WHY A METAL SCREW HERE

Every other threaded feature on this device is printed, because they are
coarse (M10 and up) and their loads are spread over many turns. This clamp
is the opposite: a short M4 in a thin lug, tightened repeatedly, right where
the user applies hand force. A printed M4 in a rigid photopolymer would
strip. So the lug takes a clearance hole and a captured hex nut, and the
fastener is a bought-in steel screw.

MARKER_TIP is where the geometry is verified, and it is a SETTING, not a
fixed feature: it assumes the pen is clamped so its tip stands
marker_tip_offset proud of the holder's front face. The clamp allows any
depth within the bore, so the user sets this - and must set it identically
for both arcs, or the two radii will differ.
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
        rot = App.Rotation(Vector(0, 0, 1), direction)
        solid.Placement = App.Placement(base, rot)
    else:
        solid.translate(base)
    return solid


def make_marker_holder(p, d, warnings):
    ro = d["marker_holder_outer_radius"]
    L = p["marker_holder_length"]
    bore_r = d["marker_bore_radius"]
    floor = p["marker_holder_floor"]

    body = Part.makeCylinder(ro, L)

    # --- tenon (identical to the ball joint's, so modules interchange) ----
    tw, tt, tl = (p["connector_tenon_width"], p["connector_tenon_thickness"],
                  p["connector_tenon_length"])
    tenon = Part.makeBox(tw, tt, tl, Vector(-tw / 2.0, -tt / 2.0, -tl))
    body = prim.safe_fuse(body, tenon, "marker_holder")

    # --- clamp lugs -------------------------------------------------------
    ew, el, eh = (p["marker_clamp_ear_width"], p["marker_clamp_ear_length"],
                  p["marker_clamp_ear_height"])
    split = p["marker_split_width"]
    ey = ew + split / 2.0
    z_ear = (L - eh) / 2.0
    ears = Part.makeBox(el, 2.0 * ey, eh, Vector(ro - 2.0, -ey, z_ear))
    body = prim.safe_fuse(body, ears, "marker_holder").removeSplitter()

    # --- bore, blind so the back of the holder stays solid ----------------
    body = prim.safe_cut(body, Part.makeCylinder(bore_r, L - floor + 1.0,
                                      Vector(0, 0, floor)), "marker_holder")

    # --- split, opening the bore to the +X side ---------------------------
    x_end = ro + el + 2.0
    body = prim.safe_cut(body, Part.makeBox(x_end, split, L + 2.0,
                                 Vector(0.0, -split / 2.0, floor * 0.5)), "marker_holder")

    # --- clamp screw and captured nut -------------------------------------
    x_screw = ro - 2.0 + el * 0.55
    z_screw = L / 2.0
    body = prim.safe_cut(body, Part.makeCylinder(
        p["marker_screw_diameter"] / 2.0 + p["connector_clearance"],
        2.0 * ey + 4.0, Vector(x_screw, -(ey + 2.0), z_screw), Vector(0, 1, 0)), "marker_holder")
    nut = hex_prism(p["marker_nut_across_flats"] + 2.0 * p["connector_clearance"],
                    p["marker_nut_thickness"],
                    Vector(x_screw, -ey - 0.01, z_screw), Vector(0, 1, 0))
    body = prim.safe_cut(body, nut, "marker_holder")

    # --- cross pin through the tenon --------------------------------------
    body = prim.safe_cut(body, Part.makeCylinder(
        p["connector_pin_diameter"] / 2.0 + p["connector_clearance"], tw + 4.0,
        Vector(-(tw / 2.0 + 2.0), 0.0, -p["connector_pin_inset"]),
        Vector(1, 0, 0)), "marker_holder")

    return prim.require_solid(body, "marker_holder")


def marker_tip_local(p, d):
    """MARKER_TIP in the holder's own frame."""
    return Vector(0.0, 0.0, p["marker_holder_length"] + p["marker_tip_offset"])


def components(p, d, warnings):
    return {"MarkerHolder": make_marker_holder(p, d, warnings)}
