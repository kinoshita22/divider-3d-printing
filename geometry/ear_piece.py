"""
PHASE 4 - ear piece.

Client-stated shape: a smooth tapered cone that centres itself in the ear
opening, with a stopper flange of about 15 mm diameter a few millimetres
back from the tip so the cone cannot be pushed in too far.

    z = 0 .......... rear face, screws onto the ball stud
    z = 0..14 ...... body, with the female thread bored into it
    z = 14..17 ..... stopper flange, 15 mm diameter (client-stated)
    z = 17..24 ..... tapered cone
    z = 24 ......... rounded tip

NOT CLINICALLY VALIDATED. Every insertion dimension here - tip diameter,
taper angle, how far the stopper sits behind the tip, insertion depth - was
chosen by the CAD engineer so that a model could be built at all. None of it
came from the client, from anatomy, or from any measurement. The stopper
diameter is the single exception and is the client's own figure.

Anything that goes near an ear canal has to be signed off by someone
clinically qualified before a prototype is put anywhere near a person.

Every edge that could contact tissue is filleted; the tip is a sphere rather
than a flat face, so there is no sharp rim anywhere on the inserted length.
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


def make_ear_piece(p, d, warnings):
    body_l = p["earpiece_body_length"]
    stop_t = p["earpiece_stopper_thickness"]
    cone_l = p["earpiece_stopper_offset"]
    tip_r = p["earpiece_tip_diameter"] / 2.0
    base_r = d["earpiece_base_diameter"] / 2.0

    body = Part.makeCylinder(p["earpiece_body_diameter"] / 2.0, body_l)
    stopper = Part.makeCylinder(p["earpiece_stopper_diameter"] / 2.0, stop_t,
                                Vector(0, 0, body_l))
    shape = prim.safe_fuse(body, stopper, "ear_piece")

    # Cone, stopping short by the tip radius so a sphere can cap it without
    # the nose growing past earpiece_total_length.
    z_cone = body_l + stop_t
    cone_h = cone_l - tip_r
    if cone_h <= 0.1:
        raise prim.GeometryError(
            "earpiece_stopper_offset (%.2f) must exceed the tip radius (%.2f)"
            % (cone_l, tip_r))
    # Radius where the sphere meets the cone, so the two blend tangentially.
    r_at_sphere = base_r - (base_r - tip_r) * (cone_h / cone_l)
    cone = Part.makeCone(base_r, r_at_sphere, cone_h, Vector(0, 0, z_cone))
    nose = Part.makeSphere(tip_r, Vector(0, 0, z_cone + cone_h))
    shape = prim.safe_fuse(shape, cone, "ear_piece").fuse(nose).removeSplitter()

    # Female thread for the ball stud. Cut with the SAME generator as the
    # stud's male thread, grown by the print clearance. Both threads start at
    # the same height in the assembled joint, so they are drawn in phase.
    # The tool runs past this part's z = 0 - which is where the stud's own
    # thread starts once assembled - so the first turn is fully formed.
    #
    # It deliberately does NOT start a whole number of pitches back. At a
    # whole-pitch offset the swept thread's seam edge lands exactly on the
    # rear face and OCCT returns an invalid solid. Instead the tool starts
    # wherever is geometrically clean, and the resulting phase difference is
    # taken out by ROTATING the ear piece as it is assembled - which is
    # exactly what screwing it on does in reality. See thread_phase_offset().
    lead_in = thread_lead_in(p)
    tool = prim.thread_solid(p,
                             major_radius=p["ball_stud_thread_diameter"] / 2.0,
                             length=p["earpiece_socket_depth"] + lead_in,
                             base_z=-lead_in, grow=p["thread_clearance"],
                             pitch=p["ball_stud_thread_pitch"])
    shape = prim.safe_cut(shape, tool, "ear_piece")

    # Break every exposed edge. These are the surfaces that would touch a
    # patient, so a failed fillet is reported rather than passed over.
    #
    # Two passes, deliberately. The body/stopper junction at z = body_l is a
    # concave corner sharing its location with the stopper's own convex rim;
    # asking OCCT to blend both in one operation fails, while doing them in
    # sequence succeeds.
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
