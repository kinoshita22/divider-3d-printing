"""
Shared FreeCAD geometry helpers.

Two jobs:
  * build printable helical threads that are guaranteed to mate, and
  * refuse to hand on geometry that is not a clean single solid.

Nothing here knows anything about the divider. Keep it that way.
"""

from __future__ import annotations

import Part
from FreeCAD import Vector


class GeometryError(RuntimeError):
    """Raised when a build step produced something that is not a valid solid."""


# --------------------------------------------------------------------------
# solid checking
# --------------------------------------------------------------------------
def require_solid(shape, name):
    """
    Hard gate. Every component passes through this before it is added to the
    document, so a malformed boolean fails loudly at the point it happened
    instead of surfacing later as a bad STEP file.
    """
    if shape is None:
        raise GeometryError("%s: build returned None" % name)
    if not shape.isValid():
        raise GeometryError("%s: shape.isValid() is False" % name)
    if len(shape.Solids) != 1:
        raise GeometryError("%s: expected exactly 1 solid, got %d "
                            "(a boolean probably split the part)"
                            % (name, len(shape.Solids)))
    if not shape.isClosed():
        raise GeometryError("%s: shell is not closed" % name)
    if shape.Volume <= 0.0:
        raise GeometryError("%s: volume is %.6f" % (name, shape.Volume))
    return shape


def tight_bbox(shape):
    """
    OCCT's Shape.BoundBox is only a loose hull for swept/B-spline faces - a
    threaded part can report a box several mm too big.

    useTriangulation=False matters: once a shape has been meshed for STL
    export it carries a cached triangulation, and measuring against that
    reports a box up to 0.1 mm oversize. Working from the exact faces makes
    the number reproducible regardless of what has been exported already.
    """
    try:
        return shape.optimalBoundingBox(False, False)
    except Exception:
        try:
            return shape.optimalBoundingBox()
        except Exception:
            return shape.BoundBox


def safe_fillet(shape, edges, radius, label, warnings):
    """
    Fillet that degrades to a reported warning instead of a silent no-op.
    OCCT fillets fail for real geometric reasons; the caller gets the
    unfilleted shape back and the reason is recorded for the report.
    """
    if not edges or radius <= 0.0:
        return shape
    try:
        out = shape.makeFillet(radius, edges)
        if out.isValid() and len(out.Solids) == 1:
            return out
        warnings.append("FILLET %s: r=%.2f produced an invalid shape, "
                        "left unfilleted" % (label, radius))
    except Exception as exc:
        warnings.append("FILLET %s: r=%.2f failed (%s), left unfilleted"
                        % (label, radius, exc))
    return shape


def circular_edges(shape, radius, tol=0.05, zmin=None, zmax=None):
    """Select circular edges of a given radius, optionally within a z band."""
    out = []
    for e in shape.Edges:
        try:
            c = e.Curve
        except Exception:
            # Degenerate edges (sphere poles/seams) raise "undefined curve
            # type" on access. They are never fillet targets.
            continue
        if not isinstance(c, Part.Circle):
            continue
        if abs(c.Radius - radius) > tol:
            continue
        z = c.Center.z
        if zmin is not None and z < zmin:
            continue
        if zmax is not None and z > zmax:
            continue
        out.append(e)
    return out


# --------------------------------------------------------------------------
# threads
# --------------------------------------------------------------------------
def thread_geometry(p, major_radius, pitch=None):
    """Radii and profile widths for a thread, before any clearance growth."""
    pitch = p["thread_pitch"] if pitch is None else pitch
    depth = pitch * p["thread_depth_ratio"]
    return {
        "pitch": pitch,
        "depth": depth,
        "major_radius": major_radius,
        "minor_radius": major_radius - depth,
        "crest_width": pitch * p["thread_crest_ratio"],
        "root_width": pitch * p["thread_root_ratio"],
    }


def _profile_wire(g, grow):
    """
    Axial cross-section of one thread ridge, in the XZ plane, anchored on the
    helix start point (minor_radius, 0, 0).

    `grow` offsets the ridge outwards in every direction. Used to turn the
    screw thread into the tool that cuts its own mating nut, so the two can
    never disagree about profile or pitch.
    """
    min_r = g["minor_radius"] + grow
    maj_r = g["major_radius"] + grow
    cw = g["crest_width"] + 2.0 * grow
    rw = g["root_width"] + 2.0 * grow
    if rw >= g["pitch"] - 1e-6:
        raise GeometryError(
            "thread root width %.3f >= pitch %.3f: adjacent turns merge. "
            "Reduce thread_root_ratio or thread_clearance." % (rw, g["pitch"]))
    if maj_r <= min_r:
        raise GeometryError("thread depth collapsed (major %.3f <= minor %.3f)"
                            % (maj_r, min_r))
    pts = [Vector(min_r, 0.0, -rw / 2.0),
           Vector(maj_r, 0.0, -cw / 2.0),
           Vector(maj_r, 0.0, cw / 2.0),
           Vector(min_r, 0.0, rw / 2.0)]
    if cw <= 1e-6:                      # triangular: crest degenerates to a point
        pts = [Vector(min_r, 0.0, -rw / 2.0),
               Vector(maj_r, 0.0, 0.0),
               Vector(min_r, 0.0, rw / 2.0)]
    return Part.Wire(Part.makePolygon(pts + [pts[0]]))


def thread_solid(p, major_radius, length, base_z=0.0, grow=0.0,
                 pitch=None, profile=None):
    """
    Solid thread: minor-diameter core plus a swept helical ridge, axis +Z,
    occupying exactly z = [base_z, base_z + length].

    grow=0                 -> the external thread itself
    grow=thread_clearance  -> the tool to cut a mating internal thread

    thread_profile == "none" returns a plain cylinder at the minor diameter,
    which is the fallback for a bought-in metal fastener or heat-set insert.
    """
    profile = p["thread_profile"] if profile is None else profile
    g = thread_geometry(p, major_radius, pitch)
    min_r = g["minor_radius"] + grow

    if profile == "none":
        return Part.makeCylinder(min_r, length, Vector(0, 0, base_z))
    if profile == "triangular":
        g["crest_width"] = 0.0
    elif profile != "trapezoidal":
        raise GeometryError("unknown thread_profile %r" % profile)

    # Sweep one turn-profile along the helix, then add the minor-diameter core.
    helix = Part.makeLongHelix(g["pitch"], length, min_r)
    ridge = Part.Wire(helix.Edges).makePipeShell([_profile_wire(g, grow)], True, True)
    core = Part.makeCylinder(min_r, length)
    out = core.copy().fuse(ridge.copy()).removeSplitter()

    # The swept ridge overhangs each end by half a root width. Trim it back
    # with planar cuts: a cylindrical common() against these helical B-spline
    # faces is unreliable in OCCT and silently returns an empty shape.
    big = 2.0 * (g["major_radius"] + grow + 2.0)
    out = out.copy().cut(Part.makeBox(2 * big, 2 * big, length + 1.0,
                                      Vector(-big, -big, -length - 1.0)))
    out = out.copy().cut(Part.makeBox(2 * big, 2 * big, length + 1.0,
                                      Vector(-big, -big, length)))

    out.translate(Vector(0, 0, base_z))
    return require_solid(out, "thread(maj=%.2f,L=%.2f,grow=%.2f)"
                         % (major_radius, length, grow))


def nut_crest_thickness(p, pitch=None):
    """
    Axial thickness left on the internal thread's crest after the grown tool
    has cut it. Goes to zero if clearance eats the whole gap between turns.
    """
    pitch = p["thread_pitch"] if pitch is None else pitch
    return pitch - (pitch * p["thread_root_ratio"] + 2.0 * p["thread_clearance"])


# --------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------
def radial_pattern(shape, count, axis=Vector(0, 0, 1), center=Vector(0, 0, 0)):
    """Copies of `shape` rotated evenly about `axis`, fused into one tool."""
    out = []
    for i in range(count):
        s = shape.copy()
        s.rotate(center, axis, 360.0 * i / count)
        out.append(s)
    fused = out[0]
    for s in out[1:]:
        fused = fused.fuse(s)
    return fused


# --------------------------------------------------------------------------
# booleans
# --------------------------------------------------------------------------
# OCCT will occasionally return the base shape untouched from a cut instead
# of raising - a silent no-op. It happened here cutting a threaded bore out
# of a knob: valid tool, valid blank, clearly overlapping, zero material
# removed, no error. The part looked fine until an interference check found
# the bolt passing through solid material.
#
# Two defences, and both matter:
#   * operate on copies - that alone fixed the case above, and costs nothing
#   * verify the result - a cut whose tool demonstrably overlapped must
#     remove volume, or the build stops
#
# Never call .cut()/.fuse()/.common() directly on component geometry.

def safe_cut(base, tool, label, expect_change=True):
    """Subtract `tool` from `base`, refusing to accept a silent no-op."""
    out = base.copy().cut(tool.copy())
    if expect_change and out.Volume >= base.Volume - 1e-9:
        overlap = base.copy().common(tool.copy()).Volume
        if overlap > 1e-6:
            raise GeometryError(
                "%s: cut removed nothing although the tool overlaps by "
                "%.3f mm3 - OCCT returned the base shape unchanged"
                % (label, overlap))
    return out


def safe_fuse(base, tool, label):
    """Union that checks the result actually grew to contain both parts."""
    out = base.copy().fuse(tool.copy())
    if out.Volume < max(base.Volume, tool.Volume) - 1e-6:
        raise GeometryError(
            "%s: fuse produced %.3f mm3, smaller than its largest input "
            "(%.3f mm3)" % (label, out.Volume, max(base.Volume, tool.Volume)))
    return out


def safe_common(a, b):
    """Intersection, on copies."""
    return a.copy().common(b.copy())
