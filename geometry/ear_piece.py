"""
PHASE 4 - ear piece.

REVISED 2026-09-18 at the client's request.

The printed resin no longer touches the ear. The tip is an earphone-style
nozzle that carries a commercial silicone eartip (standard size), so the
only thing entering the ear is the same silicone the patient would meet in
a pair of earphones. The Ø15 stopper flange is retained and now does double
duty: it still limits insertion depth, and it is the wall the silicone base
seats against.

    z = 0 ......... rear face, screws onto the ball stud
    z = 0..14 ..... body, with the female thread bored into it
    z = 14..17 .... stopper flange, Ø15 (client-stated)
    z = 17..23 .... nozzle, Ø4.5 shaft with a Ø5.5 retaining bead
    z = 23 ........ tip

The three nozzle figures - Ø4.5 shaft, Ø5.5 bead at the tip, 6.0 mm long -
are client-stated. The bead's ramp and crest widths are not, and are set so
the eartip can be pushed on by hand: a 0.5 mm interference on the radius,
reached over a 0.6 mm ramp.

THE NOZZLE ROOT IS DELIBERATELY NOT FILLETED. A radius there would hold the
silicone base off the stopper face, and the client specifically wants the
flange to act as the wall that base seats against. Every other exposed edge
is broken.

Still not clinically validated: how deep the silicone sits, which eartip
size suits, and whether the stopper's Ø15 is right for the intended
population. Those are clinical questions, not CAD ones.
"""

from __future__ import annotations

import Part
from FreeCAD import Vector

from . import primitives as prim


def thread_lead_in(p):
    """
    How far the thread-cutting tool starts below the ear piece's rear face.

    Kept off a whole-pitch multiple on purpose: see make_ear_piece.
    """
    return 0.6667 * p["ball_stud_thread_pitch"]


def thread_phase_offset(p):
    """
    Rotation, in degrees about the part's own axis, that brings this female
    thread into step with the stud's male thread in the assembly.

    The female thread's helix starts lead_in below the mating face while the
    male one starts at it, so the two are offset by lead_in/pitch of a turn.
    Backing the ear piece off by that much is what a real assembly does when
    the thread pulls the part to its seated position.
    """
    return -360.0 * (thread_lead_in(p) / p["ball_stud_thread_pitch"]) % 360.0


def nozzle_profile(p, d):
    """
    Half-section of the nozzle, as (radius, z) pairs measured from the
    stopper's front face. Revolved to make the nozzle.

    Shape, base to tip: a plain shaft the eartip grips, a short ramp onto the
    retaining bead, the bead crest, then a chamfer to a small flat at the
    tip. The eartip is pushed on over the chamfer, stretches across the bead
    and snaps down onto the shaft behind it.
    """
    L = p["earpiece_nozzle_length"]
    r_shaft = p["earpiece_nozzle_diameter"] / 2.0
    r_lip = p["earpiece_nozzle_lip_diameter"] / 2.0
    r_tip = p["earpiece_nozzle_tip_diameter"] / 2.0
    lip_len = p["earpiece_nozzle_lip_length"]
    ramp = p["earpiece_nozzle_lip_ramp"]
    cham = p["earpiece_nozzle_tip_chamfer"]

    z_ramp_start = L - cham - lip_len - ramp
    if z_ramp_start <= 0.2:
        raise prim.GeometryError(
            "nozzle features (%.2f + %.2f + %.2f mm) do not fit in "
            "earpiece_nozzle_length %.2f mm"
            % (ramp, lip_len, cham, L))
    if r_lip <= r_shaft:
        raise prim.GeometryError(
            "earpiece_nozzle_lip_diameter (%.2f) must exceed "
            "earpiece_nozzle_diameter (%.2f) or the eartip has nothing to "
            "snap behind" % (p["earpiece_nozzle_lip_diameter"],
                             p["earpiece_nozzle_diameter"]))
    return [
        (0.0, 0.0),
        (r_shaft, 0.0),
        (r_shaft, z_ramp_start),
        (r_lip, z_ramp_start + ramp),
        (r_lip, z_ramp_start + ramp + lip_len),
        (r_tip, L),
        (0.0, L),
    ]


def make_nozzle(p, d):
    """Solid of revolution for the eartip nozzle, based at z = 0."""
    pts = [Vector(r, 0.0, z) for r, z in nozzle_profile(p, d)]
    wire = Part.Wire(Part.makePolygon(pts + [pts[0]]))
    face = Part.Face(wire)
    return face.revolve(Vector(0, 0, 0), Vector(0, 0, 1), 360.0)


def make_ear_piece(p, d, warnings):
    body_l = p["earpiece_body_length"]
    stop_t = p["earpiece_stopper_thickness"]

    body = Part.makeCylinder(p["earpiece_body_diameter"] / 2.0, body_l)
    stopper = Part.makeCylinder(p["earpiece_stopper_diameter"] / 2.0, stop_t,
                                Vector(0, 0, body_l))
    shape = prim.safe_fuse(body, stopper, "ear_piece")

    nozzle = make_nozzle(p, d)
    nozzle.translate(Vector(0, 0, d["earpiece_nozzle_base_z"]))
    shape = prim.safe_fuse(shape, nozzle, "ear_piece").removeSplitter()

    # Female thread for the ball stud, cut with the SAME generator as the
    # stud's male thread and grown by the print clearance.
    #
    # The tool deliberately does NOT start a whole number of pitches back:
    # at a whole-pitch offset the swept thread's seam edge lands exactly on
    # the rear face and OCCT returns an invalid solid. It starts somewhere
    # geometrically clean instead, and the resulting phase difference is
    # taken out by rotating the ear piece as it is assembled - which is
    # exactly what screwing it on does. See thread_phase_offset().
    lead_in = thread_lead_in(p)
    tool = prim.thread_solid(p,
                             major_radius=p["ball_stud_thread_diameter"] / 2.0,
                             length=p["earpiece_socket_depth"] + lead_in,
                             base_z=-lead_in, grow=p["thread_clearance"],
                             pitch=p["ball_stud_thread_pitch"])
    shape = prim.safe_cut(shape, tool, "ear_piece")

    # Break the exposed edges, in two passes: the stopper's convex rim and
    # the concave corner where it meets the body share a height, and asking
    # OCCT to blend both at once fails while doing them in sequence works.
    #
    # The nozzle root is left sharp on purpose - see the module docstring.
    r = p["earpiece_fillet_radius"]
    outer = (prim.circular_edges(shape, p["earpiece_stopper_diameter"] / 2.0,
                                 zmin=body_l - 0.1, zmax=body_l + stop_t + 0.1)
             + prim.circular_edges(shape, p["earpiece_body_diameter"] / 2.0,
                                   zmin=-0.1, zmax=0.1))
    shape = prim.safe_fillet(shape, outer, r, "ear piece outer edges", warnings)

    root = prim.circular_edges(shape, p["earpiece_body_diameter"] / 2.0,
                               zmin=body_l - 0.1, zmax=body_l + 0.1)
    shape = prim.safe_fillet(shape, root, min(r, 0.8),
                             "ear piece stopper root", warnings)

    return prim.require_solid(shape, "ear_piece")


def components(p, d, warnings):
    return {"EarPiece": make_ear_piece(p, d, warnings)}
