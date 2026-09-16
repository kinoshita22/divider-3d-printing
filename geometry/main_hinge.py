"""
PHASE 3 - main hinge and its lock.

The two legs pivot here, and this joint alone decides whether the two arcs
are struck at the SAME radius. If it creeps between the first and second
arc, the construction is wrong and nothing downstream can recover it.

Local frame (z along the bolt axis, the stack as assembled):

    z = collar_top ---  knob            (hand-tightened, pulls the bolt up)
    z = 22 ..........  leg B top face
    z = 12..22 ......  leg B            (drawing leg)
    z = 10..12 ......  friction washer
    z = 0..10 .......  leg A            (pivot leg)
    z = 0 ...........  bolt head bears here
    z < 0 ...........  bolt head

WHY A FRICTION CLAMP AND NOT TEETH

The client asked for a lock that cannot drift. A toothed or ratcheted lock
is positive, so it is the obvious first thought, but it quantises the
opening angle, and here that quantisation lands directly on the measurement:

    R = 2 * C * sin(theta)   ->   dR = 2 * C * cos(theta) * dtheta

With C = 200 mm, even 360 teeth (1 degree steps) gives dR of about 3.3 mm.
The whole point of the instrument is that both arcs share one radius, and a
3 mm quantum in the radius the surgeon can actually select is a poor trade
for a lock that only has to resist a hand-scale moment.

A friction clamp holds any radius continuously. Its weakness is capacity,
so that is computed rather than assumed: hand torque on the knob becomes
bolt tension, tension times the friction radius becomes holding torque, and
validation compares it against the moment the drawing hand applies at the
marker. With the default numbers the margin is about 5x - see the report.

Both legs also clamp against a washer rather than against each other, which
keeps the rubbing surfaces flat and away from the printed layer lines.
"""

from __future__ import annotations

import Part
from FreeCAD import Vector

from . import primitives as prim


def _flutes(p, d, shape, radius, z0, height, count, flute_r, depth):
    """Scalloped grip around a disc."""
    if count <= 0 or flute_r <= 0:
        return shape
    cutter = Part.makeCylinder(flute_r, height + 2.0,
                               Vector(radius + flute_r - depth, 0.0, z0 - 1.0))
    return prim.safe_cut(shape, prim.radial_pattern(cutter, count), "main_hinge")


def make_hinge_bolt(p, d, warnings):
    """Fluted head, plain shank through the stack, threaded nose for the knob."""
    hd, ht = p["hinge_bolt_head_diameter"], p["hinge_bolt_head_thickness"]
    shank_r = p["hinge_bolt_diameter"] / 2.0

    head = Part.makeCylinder(hd / 2.0, ht, Vector(0, 0, -ht))
    head = _flutes(p, d, head, hd / 2.0, -ht, ht,
                   p["hinge_knob_flute_count"], p["hinge_knob_flute_radius"] * 0.6,
                   p["hinge_knob_flute_depth"])

    shank = Part.makeCylinder(shank_r, d["hinge_thread_base_z"])
    body = prim.safe_fuse(head, shank, "main_hinge")

    # Relief neck at the thread's minor diameter. The thread major diameter
    # equals the shank diameter, so without this the crest would run tangent
    # to the shank wall and the STL tessellation breaks (see ball_joint).
    minor_r = shank_r - p["hinge_bolt_pitch"] * p["thread_depth_ratio"]
    body = prim.safe_cut(body, Part.makeCylinder(shank_r + 1.0, d["hinge_neck_length"],
                                      Vector(0, 0, d["hinge_stack_thickness"])), "main_hinge")
    body = prim.safe_fuse(body, Part.makeCylinder(minor_r, d["hinge_neck_length"],
                                       Vector(0, 0, d["hinge_stack_thickness"])), "main_hinge")

    thread = prim.thread_solid(p, major_radius=shank_r,
                               length=d["hinge_thread_length"],
                               base_z=d["hinge_thread_base_z"],
                               pitch=p["hinge_bolt_pitch"])
    body = prim.safe_fuse(body, thread, "main_hinge").removeSplitter()
    return prim.require_solid(body, "hinge_bolt")


def make_hinge_washer(p, d, warnings):
    """Flat friction washer between the two legs."""
    outer = Part.makeCylinder(p["hinge_washer_outer_diameter"] / 2.0,
                              p["hinge_washer_thickness"],
                              Vector(0, 0, p["leg_thickness"]))
    bore = Part.makeCylinder(d["hinge_bore_radius"],
                             p["hinge_washer_thickness"] + 2.0,
                             Vector(0, 0, p["leg_thickness"] - 1.0))
    return prim.require_solid(prim.safe_cut(outer, bore, "main_hinge"), "hinge_washer")


def make_hinge_knob(p, d, warnings):
    """Hand knob with a blind internal thread."""
    kd, kt = p["hinge_knob_diameter"], p["hinge_knob_thickness"]
    z0 = d["hinge_stack_thickness"]
    body = Part.makeCylinder(kd / 2.0, kt, Vector(0, 0, z0))
    body = _flutes(p, d, body, kd / 2.0, z0, kt,
                   p["hinge_knob_flute_count"], p["hinge_knob_flute_radius"],
                   p["hinge_knob_flute_depth"])

    # Cut with the same thread definition as the bolt, grown by the print
    # clearance, and started a WHOLE NUMBER OF PITCHES from the bolt's own
    # thread start so the two are drawn in phase and actually mate.
    pitch = p["hinge_bolt_pitch"]
    tool_base = d["hinge_thread_base_z"] - 2.0 * pitch
    top_of_thread = z0 + p["hinge_knob_thread_depth"]
    tool = prim.thread_solid(p, major_radius=p["hinge_bolt_diameter"] / 2.0,
                             length=top_of_thread - tool_base,
                             base_z=tool_base, grow=p["thread_clearance"],
                             pitch=pitch)
    body = prim.safe_cut(body, tool, "main_hinge").removeSplitter()
    return prim.require_solid(body, "hinge_knob")


def components(p, d, warnings):
    return {
        "HingeBolt": make_hinge_bolt(p, d, warnings),
        "HingeWasher": make_hinge_washer(p, d, warnings),
        "HingeKnob": make_hinge_knob(p, d, warnings),
    }
