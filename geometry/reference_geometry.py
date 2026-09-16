"""
PHASE 1 - construction geometry that defines the coordinate system.

None of this is a printed part. It exists so that the mechanism can be
checked against the intended workflow:

    LEFT_EAR_REFERENCE / RIGHT_EAR_REFERENCE
        the two pivot points, on the X axis at +/- ref_ear_to_ear_distance/2
    HEAD_CENTER / HEAD_TOP
        centroid and vertex of the reference ellipsoid
    MARKER_TIP
        where the two equal-radius arcs actually meet on the midline
    ScalpArc_Left / ScalpArc_Right
        the two arcs themselves, as they would fall on the reference head

THE REFERENCE HEAD IS NOT ANATOMY. It is a tri-axial ellipsoid built from
guessed semi-axes (every one of them is in parameters.PROVISIONAL). The
client's CT dataset has NOT been downloaded or measured - see README. Only
the z >= 0 half is drawn, because only the cranial vault is meaningful.

What does NOT depend on the head model: both arc centres lie on the X axis
and both radii are equal, so the arcs must meet on the plane x = 0. The
perpendicular bisector of the ear-to-ear segment is therefore exact by
construction. The ellipsoid only answers "where on the scalp", not "is the
midline correct".
"""

from __future__ import annotations

import FreeCAD as App
import Part
from FreeCAD import Vector

from . import refmath


def _v(t):
    return Vector(t[0], t[1], t[2])


def make_head_solid(p):
    """Upper half of the reference ellipsoid (the cranial vault)."""
    m = App.Matrix()
    m.scale(p["ref_head_semi_x"], p["ref_head_semi_y"], p["ref_head_semi_z"])
    ell = Part.makeSphere(1.0).transformGeometry(m)
    ell.translate(Vector(0.0, p["ref_head_center_y"], p["ref_head_center_z"]))
    big = 4.0 * max(p["ref_head_semi_x"], p["ref_head_semi_y"], p["ref_head_semi_z"])
    keep = Part.makeBox(2 * big, 2 * big, 2 * big, Vector(-big, -big, 0.0))
    return ell.common(keep)


def make_scalp_arc(p, ear_point, radius=None):
    """
    The arc a leg of the given radius sweeps across the reference scalp:
    the intersection of a sphere centred on the ear point with the head.
    Trimmed to z >= 0.
    """
    R = p["ref_arc_radius"] if radius is None else radius
    m = App.Matrix()
    m.scale(p["ref_head_semi_x"], p["ref_head_semi_y"], p["ref_head_semi_z"])
    ell = Part.makeSphere(1.0).transformGeometry(m)
    ell.translate(Vector(0.0, p["ref_head_center_y"], p["ref_head_center_z"]))
    arc = ell.section(Part.makeSphere(R, _v(ear_point)))
    big = 4.0 * max(p["ref_head_semi_x"], p["ref_head_semi_y"], p["ref_head_semi_z"])
    keep = Part.makeBox(2 * big, 2 * big, 2 * big, Vector(-big, -big, 0.0))
    return arc.common(keep)


def make_midsagittal_face(p):
    """Rectangular patch of the x = 0 plane, for visual reference."""
    cy, b = p["ref_head_center_y"], p["ref_head_semi_y"] * 1.1
    cz, c = p["ref_head_center_z"], p["ref_head_semi_z"] * 1.1
    pts = [Vector(0.0, cy - b, 0.0), Vector(0.0, cy + b, 0.0),
           Vector(0.0, cy + b, cz + c), Vector(0.0, cy - b, cz + c)]
    return Part.Face(Part.Wire(Part.makePolygon(pts + [pts[0]])))


def build(doc, p, d, warnings, group=None):
    """Create all construction objects. Returns refmath.summary()."""
    info = refmath.summary(p, d)
    objs = []

    def add(name, shape, label=None):
        o = doc.addObject("Part::Feature", name)
        o.Label = label or name
        o.Shape = shape
        if group is not None:
            group.addObject(o)
        objs.append(o)
        return o

    # --- datum points -----------------------------------------------------
    add("LEFT_EAR_REFERENCE", Part.Vertex(_v(info["left_ear_reference"])))
    add("RIGHT_EAR_REFERENCE", Part.Vertex(_v(info["right_ear_reference"])))
    add("HEAD_CENTER", Part.Vertex(_v(info["head_center"])))
    add("HEAD_TOP", Part.Vertex(_v(info["head_top"])))

    tip = info["marker_tip"]
    if tip is None:
        warnings.append(
            "REFERENCE: arc radius %.1f mm never reaches the mid-sagittal "
            "plane on the reference head, so MARKER_TIP could not be placed. "
            "Increase ref_arc_radius or revise the head reference."
            % p["ref_arc_radius"])
    else:
        add("MARKER_TIP", Part.Vertex(_v(tip)))
        # The two radii, drawn so they can be measured in the GUI.
        add("Radius_Left", Part.makeLine(_v(info["left_ear_reference"]), _v(tip)))
        add("Radius_Right", Part.makeLine(_v(info["right_ear_reference"]), _v(tip)))

    # --- frame ------------------------------------------------------------
    add("EarAxis", Part.makeLine(_v(info["left_ear_reference"]),
                                 _v(info["right_ear_reference"])))
    add("MidsagittalPlane", make_midsagittal_face(p))

    if p["ref_build_head_solid"]:
        add("HeadReference", make_head_solid(p), "HeadReference (PROVISIONAL)")

    if p["ref_build_arcs"]:
        for side, ear in (("Left", info["left_ear_reference"]),
                          ("Right", info["right_ear_reference"])):
            arc = make_scalp_arc(p, ear)
            if not arc.Edges:
                warnings.append("REFERENCE: %s scalp arc is empty at radius "
                                "%.1f mm (arc misses the reference head)."
                                % (side, p["ref_arc_radius"]))
            else:
                add("ScalpArc_%s" % side, arc)

    info["objects"] = objs
    return info


def add_built_marker_tip(doc, point, group=None):
    """
    MARKER_TIP_BUILT: where the marker tip lands once the instrument is
    actually assembled and posed, as opposed to MARKER_TIP, which is where
    the geometry says it should land.

    Keeping the two separate is the point. If the CAD is self-consistent
    they coincide; any gap between them is modelling error and validation
    measures it rather than assuming it away.
    """
    o = doc.addObject("Part::Feature", "MARKER_TIP_BUILT")
    o.Label = "MARKER_TIP_BUILT (as assembled)"
    o.Shape = Part.Vertex(Vector(point[0], point[1], point[2]))
    if group is not None:
        group.addObject(o)
    return o
