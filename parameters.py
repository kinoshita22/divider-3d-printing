"""
Central parameter system for the two-leg divider / compass prototype.

UNITS: all lengths in millimetres, all angles in degrees.

THIS IS A PROTOTYPE CAD PARAMETER SET.
No value in this file has been clinically validated. Any key listed in
PROVISIONAL is an engineering placeholder chosen so that the model can be
built at all -- it is NOT a client-supplied or anatomically verified figure.

Editing model dimensions:
  1. change a value in PARAMS below, or
  2. leave PARAMS alone and pass a JSON override file:
         freecadcmd main.py --params my_tuning.json
     The JSON is a flat {"key": value} object and is merged over PARAMS.

Never hard-code a dimension in a geometry module. Add it here instead.

Two kinds of value live in this file:
  * PARAMS   -- free inputs the user may set.
  * derive() -- values COMPUTED from PARAMS. These are not user-editable
                because the mechanism only stays self-consistent if they
                follow the inputs (e.g. the socket thread diameter must
                follow the socket wall thickness, or the collar will not
                pass over the clamping fingers).
"""

from __future__ import annotations

import json
import math

UNITS = {"length": "mm", "angle": "deg"}

# --------------------------------------------------------------------------
# PARAMETERS
# --------------------------------------------------------------------------
PARAMS = {

    # ---- reference frame / head model -----------------------------------
    # Coordinate system (global, mm):
    #   origin  = midpoint of the two ear reference points
    #   +X      = towards the LEFT ear reference point
    #   +Y      = anterior (towards the face)
    #   +Z      = superior (towards the vertex)
    #   z = 0   = the ear-to-ear axis, BY DEFINITION
    # MEASURED from an open research head CT - see tools/measure_ct.py and
    # config/ct_case01_measurements.json. Source: Case01 of "Head CT
    # collection for patient-specific craniofacial implant (PSI) design",
    # DOI 10.6084/m9.figshare.12423872. ONE ADULT INDIVIDUAL, bone surface
    # plus an assumed scalp thickness. Not a population statistic.
    "ref_ear_to_ear_distance": 144.3,      # MEASURED (at the assumed ear depth)
    "ref_head_semi_x": 80.8,               # MEASURED vault fit + scalp
    "ref_head_semi_y": 95.7,               # MEASURED vault fit + scalp
    "ref_head_semi_z": 79.2,               # MEASURED vault fit + scalp
    "ref_head_center_y": -4.7,             # MEASURED vault centroid vs ear line
    "ref_head_center_z": 55.9,             # MEASURED vault centroid above ear axis
    "ref_scalp_thickness": 6.0,            # PROVISIONAL  bone -> skin offset
    "ref_ear_depth_below_vertex": 130.0,   # PROVISIONAL  INPUT to the CT measurement,
                                           # not measured from it. Confirm clinically.
    # Radius of the struck arc, measured FROM THE PIVOT (see pivot_mode).
    # 160 mm about the ball centre puts the crossings within ~2 mm of where
    # the client's assumed 130 mm would, measured ear-to-marker: same marking
    # points, different reference. Usable band in this mode is 134.6-180.2 mm.
    "ref_arc_radius": 160.0,               # PROVISIONAL

    # ---- how the instrument actually swings -------------------------------
    # Which point the instrument turns about while an arc is being drawn.
    #   "ball_centre" : ball joint left at light friction. The ear piece stays
    #                   put in the ear and the compass spins about the ball.
    #                   Comfortable, and what the client describes.
    #   "ear_point"   : ball joint locked. The whole instrument pivots at the
    #                   ear canal, so the ear piece twists in the ear.
    # The bisector construction holds either way, because both pivots are
    # symmetric about the midline - but the two modes need DIFFERENT radii.
    "pivot_mode": "ball_centre",
    # Direction of the ear canal, as angles off pure lateral. Both zero means
    # the canal axis is horizontal and points straight at the opposite ear.
    "ref_ear_axis_anterior_angle": 0.0,    # PROVISIONAL  degrees towards the face
    "ref_ear_axis_superior_angle": 0.0,    # PROVISIONAL  degrees towards the vertex
    "ref_build_head_solid": True,          # draw the reference ellipsoid
    "ref_build_arcs": True,                # draw the two scalp arcs

    # ---- ball joint : ball stud -----------------------------------------
    "ball_diameter": 18.0,                 # PROVISIONAL
    "ball_stem_diameter": 10.0,            # PROVISIONAL  drives the tilt range, see derive()
    "ball_stem_length": 22.0,              # PROVISIONAL  ball centre -> start of ear interface
    "ball_stem_fillet": 2.0,               # fillet at the ball/stem junction
    "ball_stud_interface": "threaded",     # "threaded" | "plain" : how the ear piece attaches
    "ball_stud_thread_diameter": 10.0,     # PROVISIONAL
    "ball_stud_thread_pitch": 1.5,
    "ball_stud_thread_length": 10.0,
    "ball_stud_thread_relief": 1.5,        # plain run-out neck at the thread's minor
                                           # diameter, between stem and thread. Also keeps
                                           # the thread crest from running tangent to the
                                           # stem wall when the two diameters are equal,
                                           # which breaks tessellation.

    # ---- ball joint : clamping socket ------------------------------------
    "socket_clearance": 0.25,              # RADIAL gap, ball surface -> cavity surface.
                                           # TUNE THIS AFTER THE FIRST PRINT.
    "socket_wall_thickness": 3.5,
    "socket_split_width": 1.2,             # slot width
    "socket_split_count": 4,               # number of clamping fingers
    "socket_slot_root_offset": 2.0,        # slot root, measured below the cavity bottom
    "socket_slot_relief_diameter": 2.6,    # keyhole relief at each slot root
    "socket_slot_inner_ratio": 0.55,       # slot inner radius, as a fraction of cavity_radius
    "socket_taper_angle": 6.0,             # half-angle of the external collet cone
    "socket_min_tip_wall": 1.2,            # wall left at the very tip of a finger
    "socket_floor_thickness": 5.0,         # material below the cavity. Must leave a
                                           # floor under the slot relief - see validation.
    "socket_mouth_extra_angle": 0.0,       # opens the mouth beyond the minimum needed.
                                           # >0 : easier ball insertion, weaker capture.
    "ball_joint_max_angle": 22.0,          # REQUESTED half-cone tilt range of the stem

    # ---- ball joint : threaded clamping collar ---------------------------
    "thread_pitch": 2.0,
    "thread_depth_ratio": 0.55,            # thread depth = pitch * ratio
    "thread_crest_ratio": 0.30,            # crest width = pitch * ratio
    "thread_root_ratio": 0.50,             # root width  = pitch * ratio.
                                           # Kept well under 1.0 so that the clearance-grown
                                           # cutting tool still leaves a real crest on the nut.
    "thread_profile": "trapezoidal",       # "trapezoidal" | "triangular" | "none"
    "thread_clearance": 0.20,              # RADIAL clearance cut into the collar.
                                           # TUNE THIS AFTER THE FIRST PRINT.
    "socket_thread_end_gap": 1.0,          # unthreaded run-out at the bottom
    "socket_thread_top_gap": 1.0,          # unthreaded run-out below the fingers
    "collar_thread_bore_length": 11.0,     # threaded length inside the collar
    "collar_cone_overshoot": 1.5,          # cone length beyond what is needed to close the
                                           # clearance, so the collar cannot jam on the
                                           # finger tips before it has clamped
    "collar_wall_thickness": 4.0,
    "collar_fit_gap": 0.05,                # CAD-only gap so cone faces are not coincident
    "collar_bore_clearance": 0.6,          # extra room for the stem at the collar rim
    "collar_flute_count": 6,               # hand-grip scallops
    "collar_flute_depth": 1.2,
    "collar_flute_radius": 3.5,

    # The leg-side connector lives with the other module-interface
    # parameters further down: one definition, shared by the ball joint and
    # the marker holder so the two modules stay interchangeable.

    # ---- export ----------------------------------------------------------
    "stl_linear_deflection": 0.05,         # STL chord tolerance
    "stl_angular_deflection": 0.5,         # STL angular tolerance (rad)

    # ---- validation thresholds -------------------------------------------
    # Limits used by geometry/validation.py. They encode printed-material
    # engineering judgement, not client requirements.
    "warn_finger_strain": 0.015,           # bending strain at a slot root on ball insertion.
                                           # Rigid Eden photopolymers fail in flexure around
                                           # 3-4% strain, so this leaves roughly 2x margin.
    "warn_min_wall": 1.0,                  # thinnest printable/serviceable wall
    "warn_min_capture_ratio": 0.75,        # mouth_radius / ball_radius, lower = stronger capture
    "warn_max_capture_ratio": 0.95,        # above this the mouth barely retains the ball
    "warn_min_thread_turns": 4.0,          # engaged turns for a printed thread

    # ---- assembly preview -------------------------------------------------
    # How the instrument is oriented about the line joining its two contact
    # points. Affects the PREVIEW POSE ONLY - no printed part changes.
    #   "max_clearance" : whatever keeps the mechanism furthest off the head
    #   "hinge_up"      : hinge held above the ear axis, the way a compass is
    #                     normally held, provided clearance stays positive
    "assembly_roll_mode": "max_clearance",
    "assembly_min_clearance": 2.0,         # mm a pose must keep to be acceptable

    # ---- assembly preview (legacy) -------------------------------------------------
    "ball_joint_demo_tilt": 0.0,           # tilt shown in the preview assembly
    "build_left": True,
    "build_right": True,

    # ======================================================================
    # PARAMETERS FOR LATER PHASES - declared here so that every dimension
    # lives in one place. NOT yet consumed by any geometry module.
    # ======================================================================

    # ---- ear piece (PHASE 4) ---------------------------------------------
    # REVISED at the client's request (2026-09-18): the printed resin no
    # longer contacts the ear. The tip is now an earphone-style nozzle that
    # carries a commercial silicone eartip (standard size), and the Ø15
    # stopper is retained to act as the wall the silicone base seats against.
    # The three nozzle figures below are CLIENT-STATED.
    "earpiece_nozzle_diameter": 4.5,       # CLIENT-STATED  shaft the eartip grips
    "earpiece_nozzle_lip_diameter": 5.5,   # CLIENT-STATED  retaining bead, max dia at the tip
    "earpiece_nozzle_length": 6.0,         # CLIENT-STATED  stopper face to tip
    "earpiece_nozzle_lip_length": 0.5,     # PROVISIONAL  axial length of the bead crest
    "earpiece_nozzle_lip_ramp": 0.6,       # PROVISIONAL  lead-in ramp onto the bead
    "earpiece_nozzle_tip_chamfer": 0.5,    # PROVISIONAL  eases the eartip on
    "earpiece_nozzle_tip_diameter": 3.8,   # PROVISIONAL  flat left at the very tip
    "earpiece_stopper_diameter": 15.0,     # client-stated nominal
    "earpiece_stopper_thickness": 3.0,     # PROVISIONAL
    "earpiece_body_length": 14.0,          # PROVISIONAL  stopper -> stud interface
    "earpiece_body_diameter": 12.0,        # PROVISIONAL
    "earpiece_fillet_radius": 1.0,         # PROVISIONAL - removes sharp edges
    "earpiece_socket_depth": 11.0,         # female thread depth for the ball stud

    # ---- main hinge (PHASE 3) --------------------------------------------
    # Friction clamp: leg / washer / leg squeezed by a bolt and a hand knob.
    # A toothed lock was rejected - see geometry/main_hinge.py.
    "hinge_bolt_diameter": 10.0,
    "hinge_bolt_pitch": 1.5,
    "hinge_bolt_head_diameter": 22.0,
    "hinge_bolt_head_thickness": 6.0,
    "hinge_clearance": 0.20,               # TUNE AFTER FIRST PRINT
    "hinge_body_diameter": 46.0,           # clamping disc diameter on each leg
    "hinge_washer_thickness": 2.0,
    "hinge_washer_outer_diameter": 44.0,
    "hinge_knob_diameter": 44.0,
    "hinge_knob_thickness": 14.0,
    "hinge_knob_flute_count": 8,
    "hinge_knob_flute_radius": 5.0,
    "hinge_knob_flute_depth": 2.2,
    "hinge_knob_thread_depth": 12.0,
    "max_leg_opening_angle": 120.0,        # mechanical limit, both legs together
    "hinge_hand_torque": 1.5,              # N.m a hand can apply to the knob (ASSUMED)
    "hinge_friction_coefficient": 0.25,    # printed polymer on polymer (ASSUMED)
    "hinge_thread_torque_factor": 0.20,    # T = K.F.d nut factor (ASSUMED)
    "hinge_draw_force": 5.0,               # N pressed on the marker in use (ASSUMED)

    # ---- main legs (PHASE 5) ---------------------------------------------
    # Flat planar arcs: the whole leg lies in one plane, so it prints lying
    # down and its height on the tray is just leg_thickness.
    "leg_chord_length": 200.0,             # hinge pivot to tip interface, straight line
    "leg_sagitta": 38.0,                   # outward bow at mid-chord: head clearance
    "leg_width": 16.0,                     # radial width of the curved band
    "leg_thickness": 12.0,                 # PRINT HEIGHT when laid flat
    "leg_tip_width": 22.0,                 # tip block that receives a module
    "leg_tip_thickness": 12.0,             # kept FLUSH with leg_thickness: a thicker
                                           # tip block would raise the whole part's
                                           # print height on a Z-priced machine
    "leg_tip_length": 26.0,
    "leg_end_radius": 3.0,                 # edge rounding
    "leg_profile_type": "flat_arc",        # "flat_arc" only, for now

    # ---- module connector (legs <-> ball joint / marker holder) -----------
    # One interface for every end module, so either leg can take either one.
    "connector_tenon_width": 12.0,
    "connector_tenon_thickness": 6.0,
    "connector_tenon_length": 22.0,
    "connector_pin_diameter": 4.0,
    "connector_pin_inset": 11.0,
    "connector_clearance": 0.20,           # TUNE AFTER FIRST PRINT

    # ---- marker holder (PHASE 6) -----------------------------------------
    # Split clamp so the marker can be swapped and the bore adjusted.
    # Marker specified by the client 2026-09-18:
    #   AS ONE ProShare skin marker, Ø9 mm barrel x 167 mm long.
    # 167 mm will not fit inside a holder, so the bore is a THROUGH hole and
    # the tail trails back past the leg - which is why the barrel is offset
    # from the tenon. See geometry/marker_holder.py.
    "marker_diameter": 9.0,                # CLIENT-STATED  barrel diameter
    "marker_length": 167.0,                # CLIENT-STATED  overall pen length
    "marker_clearance": 0.25,              # TUNE AFTER FIRST PRINT
    "marker_holder_length": 34.0,          # PROVISIONAL  clamped length
    "marker_mount_offset": 18.0,           # barrel axis offset from the tenon, so the
                                           # pen's tail clears the leg tip block
    "marker_bridge_thickness": 12.0,       # arm joining the tenon to the barrel
    "marker_clamp_thickness": 4.0,         # PROVISIONAL  wall around the bore
    "marker_screw_diameter": 4.0,          # PROVISIONAL  clamp screw
    "marker_screw_pitch": 0.7,
    "marker_split_width": 1.6,             # clamp gap
    "marker_clamp_ear_width": 8.0,         # lugs the screw pulls together
    "marker_clamp_ear_length": 13.0,
    "marker_clamp_ear_height": 14.0,
    "marker_nut_across_flats": 7.0,        # M4 hex nut, captured in a pocket
    "marker_nut_thickness": 3.2,
    "marker_tip_offset": 25.0,             # PROVISIONAL  bore end -> pen tip
}

# --------------------------------------------------------------------------
# MEASURED REGISTER
# Values taken from a real CT scan rather than guessed. They are still only
# ONE individual and must not be treated as covering the adult population.
MEASURED = {
    "ref_ear_to_ear_distance": "CT Case01, skull width at the assumed ear depth.",
    "ref_head_semi_x": "CT Case01 cranial vault ellipsoid fit + ref_scalp_thickness.",
    "ref_head_semi_y": "CT Case01 cranial vault ellipsoid fit + ref_scalp_thickness.",
    "ref_head_semi_z": "CT Case01 cranial vault ellipsoid fit + ref_scalp_thickness.",
    "ref_head_center_y": "CT Case01 vault centroid relative to the ear line.",
    "ref_head_center_z": "CT Case01 vault centroid above the ear axis.",
}
CT_SOURCE = ("Case01, 'Head CT collection for patient-specific craniofacial "
             "implant (PSI) design', DOI 10.6084/m9.figshare.12423872")

# PROVISIONAL REGISTER
# Every key here is an assumption made by the CAD engineer, not a client
# requirement. validation.py reprints this list in the report.
# --------------------------------------------------------------------------
PROVISIONAL = {
    # --- reference frame ---------------------------------------------------
    "ref_scalp_thickness": "Bone-to-skin offset added to the CT measurement. Assumed, not measured.",
    "ref_ear_depth_below_vertex": "INPUT to the CT measurement, not a result of it. The ear canal "
                                  "cannot be located reliably by geometry alone. Confirm clinically.",
    "ref_ear_axis_anterior_angle": "Ear canal direction. Assumed straight lateral; not measured.",
    "ref_ear_axis_superior_angle": "Ear canal direction. Assumed straight lateral; not measured.",
    "ref_arc_radius": "Working compass opening. Must be chosen by the clinical user.",

    # --- ball joint ---------------------------------------------------------
    "ball_diameter": "Chosen for print strength and hand feel, not from a requirement.",
    "ball_stem_diameter": "Drives both stiffness and the achievable tilt angle.",
    "ball_stem_length": "Chosen to clear the collar; no load case has been analysed.",
    "ball_joint_max_angle": "Required tilt range has not been specified by the client.",
    "ball_stud_thread_diameter": "Ear-piece interface sized by feel, not by load.",

    # --- ear piece ------------------------------------------------------------
    # The nozzle diameters and length are CLIENT-STATED and so are not listed
    # here. What remains provisional is the detail shape of the bead and the
    # parts behind the stopper.
    "earpiece_nozzle_lip_length": "Bead crest width. Chosen for printability, not from an eartip spec.",
    "earpiece_nozzle_lip_ramp": "Lead-in ramp onto the bead. Chosen so the eartip can be pushed on by hand.",
    "earpiece_nozzle_tip_chamfer": "Front chamfer. Chosen to ease the eartip on.",
    "earpiece_nozzle_tip_diameter": "Flat left at the very tip. Not specified.",
    "earpiece_stopper_thickness": "Not specified; chosen for printed stiffness.",
    "earpiece_body_length": "Set by the thread socket depth, not by anatomy.",
    "earpiece_body_diameter": "Chosen to clear the stopper fillet.",
    "earpiece_fillet_radius": "Chosen to remove sharp edges; magnitude not specified.",

    # --- hinge ---------------------------------------------------------------
    "hinge_bolt_diameter": "Hinge loads estimated, not analysed.",
    "hinge_body_diameter": "Sized for clamping area; no stress analysis.",
    "hinge_hand_torque": "ASSUMED hand torque on the knob. Not measured.",
    "hinge_friction_coefficient": "ASSUMED printed-polymer friction. Not measured.",
    "hinge_thread_torque_factor": "ASSUMED nut factor for a printed thread.",
    "hinge_draw_force": "ASSUMED force applied to the marker in use. Not measured.",
    "max_leg_opening_angle": "Chosen limit; depends on the radius range actually needed.",

    # --- legs -----------------------------------------------------------------
    "leg_chord_length": "Sets the instrument's size and the moment on the hinge lock.",
    "leg_sagitta": "Head clearance bow. Validated against the reference head only.",
    "leg_width": "In-plane stiffness. No deflection analysis has been done.",
    "leg_thickness": "Out-of-plane stiffness AND the print height. No deflection analysis.",
    "leg_tip_length": "Joint strength not analysed.",

    # --- connector ------------------------------------------------------------
    "connector_tenon_width": "Joint strength not analysed.",
    "connector_tenon_thickness": "Joint strength not analysed.",
    "connector_tenon_length": "Joint strength not analysed.",
    "connector_pin_diameter": "Fastener schedule not defined.",

    # --- marker holder ---------------------------------------------------------
    "marker_holder_length": "Clamped length. Chosen for grip, not from a requirement.",
    "marker_mount_offset": "Set so the pen's tail clears the leg. No load case analysed.",
    "marker_clamp_thickness": "Chosen for printed stiffness.",
    "marker_screw_diameter": "Fastener schedule not defined.",
    "marker_tip_offset": "Depends on the unspecified marker. It is also a user SETTING, "
                         "not a fixed feature: the same value must be used for both arcs.",
}

# Clearances that exist specifically to be tuned against a physical print.
TUNABLE_FITS = (
    "socket_clearance",
    "thread_clearance",
    "hinge_clearance",
    "marker_clearance",
    "collar_bore_clearance",
)


# --------------------------------------------------------------------------
def load(overrides=None, path=None):
    """Return PARAMS merged with an optional dict and/or JSON file."""
    p = dict(PARAMS)
    if path:
        with open(path, "r") as fh:
            file_over = json.load(fh)
        unknown = sorted(set(file_over) - set(p))
        if unknown:
            raise KeyError("unknown parameter(s) in %s: %s" % (path, ", ".join(unknown)))
        p.update(file_over)
    if overrides:
        unknown = sorted(set(overrides) - set(p))
        if unknown:
            raise KeyError("unknown parameter override(s): %s" % ", ".join(unknown))
        p.update(overrides)
    return p


def derive(p):
    """
    Compute every dimension that is a CONSEQUENCE of the parameters.

    The ball-joint local frame used throughout:
        origin = ball centre
        +Z     = towards the ear piece (stem direction)
        -Z     = towards the leg (socket base, tenon)
    """
    d = {}
    rad = math.radians

    # ---- ball / cavity ---------------------------------------------------
    d["ball_radius"] = p["ball_diameter"] / 2.0
    d["stem_radius"] = p["ball_stem_diameter"] / 2.0
    d["cavity_radius"] = d["ball_radius"] + p["socket_clearance"]

    # The stem, seen from the ball centre, subtends this half-angle at the
    # cavity surface. The mouth cone must clear it before the stem can tilt.
    d["stem_half_angle"] = math.degrees(math.asin(d["stem_radius"] / d["cavity_radius"]))

    # Mouth cone: apex at the ball centre, opening towards +Z.
    d["mouth_half_angle"] = (p["ball_joint_max_angle"] + d["stem_half_angle"]
                             + p["socket_mouth_extra_angle"])
    d["achieved_tilt"] = d["mouth_half_angle"] - d["stem_half_angle"]
    d["mouth_radius"] = d["cavity_radius"] * math.sin(rad(d["mouth_half_angle"]))
    d["mouth_z"] = d["cavity_radius"] * math.cos(rad(d["mouth_half_angle"]))

    # Ball retention: the mouth must be narrower than the ball.
    d["capture_ratio"] = d["mouth_radius"] / d["ball_radius"]
    d["snap_in_deflection"] = d["ball_radius"] - d["mouth_radius"]

    # ---- socket outer envelope -------------------------------------------
    R0 = d["cavity_radius"] + p["socket_wall_thickness"]
    d["finger_root_outer_radius"] = R0
    tan_taper = math.tan(rad(p["socket_taper_angle"]))
    tan_mouth = math.tan(rad(d["mouth_half_angle"]))

    # The fingers end where the outward-opening mouth cone meets the
    # inward-sloping collet cone, leaving socket_min_tip_wall of material.
    d["socket_top_z"] = (R0 - p["socket_min_tip_wall"]) / (tan_mouth + tan_taper)
    d["socket_tip_outer_radius"] = R0 - d["socket_top_z"] * tan_taper
    d["socket_tip_inner_radius"] = d["socket_top_z"] * tan_mouth

    d["socket_base_bottom_z"] = -(d["cavity_radius"] + p["socket_floor_thickness"])
    d["slot_root_z"] = -(d["cavity_radius"] + p["socket_slot_root_offset"])
    d["socket_total_height"] = d["socket_top_z"] - d["socket_base_bottom_z"]

    # Flexing length of one finger, measured to the point that actually has
    # to open up (the mouth), not to the finger tip.
    d["finger_lever_length"] = d["mouth_z"] - d["slot_root_z"]

    # Cantilever surface strain at the slot root for a tip deflection equal
    # to snap_in_deflection:  eps = 3 * t * delta / (2 * L^2)
    d["finger_root_strain"] = (3.0 * p["socket_wall_thickness"] * d["snap_in_deflection"]
                               / (2.0 * d["finger_lever_length"] ** 2))

    # ---- thread -----------------------------------------------------------
    h = p["thread_pitch"] * p["thread_depth_ratio"]
    d["thread_depth"] = h
    # The socket base cylinder IS the thread core, so the major diameter
    # follows the wall thickness. This is why it is derived, not set.
    d["thread_major_radius"] = R0 + h
    d["thread_diameter"] = 2.0 * d["thread_major_radius"]
    d["thread_bottom_z"] = d["socket_base_bottom_z"] + p["socket_thread_end_gap"]
    d["thread_top_z"] = -p["socket_thread_top_gap"]
    d["thread_length"] = d["thread_top_z"] - d["thread_bottom_z"]
    d["thread_turns"] = d["thread_length"] / p["thread_pitch"]

    # Slots cut through the threaded zone interrupt it. A small interruption
    # is harmless; validation reports the fraction.
    if d["slot_root_z"] < d["thread_top_z"]:
        d["thread_interruption"] = (p["socket_split_count"] * p["socket_split_width"]
                                    / (math.pi * d["thread_diameter"]))
    else:
        d["thread_interruption"] = 0.0

    # ---- collar -----------------------------------------------------------
    # Axial travel needed to take up the nominal ball clearance. The wedge
    # ratio tan(taper) is what makes the friction adjustable by hand.
    d["collar_advance_to_close"] = p["socket_clearance"] / tan_taper

    d["collar_bottom_z"] = -p["collar_thread_bore_length"]

    # The cone must stay longer than the fingers over the whole tightening
    # stroke, otherwise the collar's top rim lands on the finger tips and the
    # joint jams before it clamps.
    d["collar_cone_length"] = (d["socket_top_z"] + d["collar_advance_to_close"]
                               + p["collar_cone_overshoot"])
    d["collar_cone_bottom_radius"] = R0 + p["collar_fit_gap"]
    d["collar_cone_top_radius"] = (d["collar_cone_bottom_radius"]
                                   - d["collar_cone_length"] * tan_taper)

    # The cone runs straight out to the top face: there is no top plate. The
    # ball is retained by the socket mouth, not by the collar, so a plate
    # would only add a thin-walled ring in the way of the tilting stem.
    d["collar_top_z"] = d["collar_cone_length"]
    d["collar_height"] = d["collar_top_z"] - d["collar_bottom_z"]
    d["collar_outer_radius"] = d["thread_major_radius"] + p["collar_wall_thickness"]

    # Stem clearance at the rim: the far side of a stem tilted by theta sits
    # at z*tan(theta) + r/cos(theta). Worst case is the loosest (highest)
    # collar position, which is the nominal one.
    #
    # Checked against the ACHIEVED tilt, not the requested one. Opening
    # socket_mouth_extra_angle raises the achievable tilt above the request,
    # and the rim has to clear whatever the mouth actually allows.
    th = rad(d["achieved_tilt"])
    d["collar_rim_required_radius"] = (d["collar_top_z"] * math.tan(th)
                                       + d["stem_radius"] / math.cos(th)
                                       + p["collar_bore_clearance"])
    d["collar_rim_margin"] = (d["collar_cone_top_radius"]
                              - d["collar_rim_required_radius"])

    # ---- stud -------------------------------------------------------------
    d["stud_interface_start_z"] = p["ball_stem_length"]
    if p["ball_stud_interface"] == "threaded":
        d["stud_thread_minor_radius"] = (p["ball_stud_thread_diameter"] / 2.0
                                         - p["ball_stud_thread_pitch"]
                                         * p["thread_depth_ratio"])
        d["stud_thread_base_z"] = p["ball_stem_length"] + p["ball_stud_thread_relief"]
        d["stud_top_z"] = d["stud_thread_base_z"] + p["ball_stud_thread_length"]
    else:
        d["stud_top_z"] = p["ball_stem_length"]

    # ---- ear piece --------------------------------------------------------
    # Nozzle, stopper flange, body. The silicone eartip covers the nozzle and
    # bottoms against the stopper, so the resin never touches the ear.
    d["earpiece_nozzle_base_z"] = (p["earpiece_body_length"]
                                   + p["earpiece_stopper_thickness"])
    d["earpiece_total_length"] = (d["earpiece_nozzle_base_z"]
                                  + p["earpiece_nozzle_length"])
    # Free length of Ø nozzle shaft behind the bead: this is what the eartip
    # actually grips once it has snapped past the bead.
    d["earpiece_nozzle_grip_length"] = (p["earpiece_nozzle_length"]
                                        - p["earpiece_nozzle_lip_length"]
                                        - p["earpiece_nozzle_lip_ramp"]
                                        - p["earpiece_nozzle_tip_chamfer"])
    # How far the eartip has to stretch to pass the bead, on the radius.
    d["earpiece_lip_interference"] = (p["earpiece_nozzle_lip_diameter"]
                                      - p["earpiece_nozzle_diameter"]) / 2.0
    d["earpiece_stopper_overhang"] = (p["earpiece_stopper_diameter"]
                                      - p["earpiece_nozzle_lip_diameter"]) / 2.0
    # Material behind the female thread, at the bottom of the blind socket.
    d["earpiece_socket_floor"] = p["earpiece_body_length"] - p["earpiece_socket_depth"]

    # ---- module connector (tenon / mortise) --------------------------------
    d["mortise_width"] = p["connector_tenon_width"] + 2.0 * p["connector_clearance"]
    d["mortise_thickness"] = (p["connector_tenon_thickness"]
                              + 2.0 * p["connector_clearance"])
    d["mortise_depth"] = p["connector_tenon_length"] + 1.0
    d["leg_tip_wall_side"] = (p["leg_tip_width"] - d["mortise_width"]) / 2.0
    d["leg_tip_wall_face"] = (p["leg_tip_thickness"] - d["mortise_thickness"]) / 2.0

    # ---- legs : the flat arc ----------------------------------------------
    # Circular arc through the two ends with the given mid-chord bow.
    C, S = p["leg_chord_length"], p["leg_sagitta"]
    d["leg_arc_radius"] = (S * S + (C / 2.0) ** 2) / (2.0 * S)
    d["leg_arc_half_angle"] = math.degrees(math.asin((C / 2.0) / d["leg_arc_radius"]))
    d["leg_arc_angle"] = 2.0 * d["leg_arc_half_angle"]
    d["leg_arc_length"] = d["leg_arc_radius"] * rad(d["leg_arc_angle"])
    d["leg_inner_radius"] = d["leg_arc_radius"] - p["leg_width"] / 2.0
    d["leg_outer_radius"] = d["leg_arc_radius"] + p["leg_width"] / 2.0
    # Laid flat on the tray this is the only thing that costs Z height.
    d["leg_print_height"] = p["leg_thickness"]

    # ---- compass opening ---------------------------------------------------
    # Two identical legs, tips a chord apart: R = 2 * C * sin(half angle).
    R = p["ref_arc_radius"]
    ratio = R / (2.0 * C)
    d["compass_reachable"] = ratio <= 1.0
    if d["compass_reachable"]:
        d["compass_half_angle"] = math.degrees(math.asin(ratio))
        d["compass_opening_angle"] = 2.0 * d["compass_half_angle"]
        d["hinge_to_tip_chord_midpoint"] = math.sqrt(max(C * C - (R / 2.0) ** 2, 0.0))
    else:
        d["compass_half_angle"] = None
        d["compass_opening_angle"] = None
        d["hinge_to_tip_chord_midpoint"] = None
    # Largest radius the hinge stop allows.
    d["max_arc_radius"] = 2.0 * C * math.sin(rad(p["max_leg_opening_angle"] / 2.0))

    # ---- hinge : clamping capacity ----------------------------------------
    # Hand torque on the knob -> axial bolt force -> friction torque on the
    # clamp faces, against the moment the drawing hand applies at the tip.
    K = p["hinge_thread_torque_factor"]
    d["hinge_clamp_force"] = (p["hinge_hand_torque"]
                              / (K * p["hinge_bolt_diameter"] / 1000.0))
    ro = p["hinge_washer_outer_diameter"] / 2000.0          # m
    ri = (p["hinge_bolt_diameter"] / 2.0 + p["hinge_clearance"]) / 1000.0
    if ro > ri:
        d["hinge_effective_radius"] = (2.0 / 3.0) * (ro ** 3 - ri ** 3) / (ro ** 2 - ri ** 2)
    else:
        d["hinge_effective_radius"] = 0.0
    # Two rubbing interfaces: leg/washer and washer/leg.
    d["hinge_holding_torque"] = (2.0 * p["hinge_friction_coefficient"]
                                 * d["hinge_clamp_force"]
                                 * d["hinge_effective_radius"])
    d["hinge_applied_moment"] = p["hinge_draw_force"] * C / 1000.0
    d["hinge_safety_factor"] = (d["hinge_holding_torque"] / d["hinge_applied_moment"]
                                if d["hinge_applied_moment"] > 0 else 0.0)
    d["hinge_stack_thickness"] = (2.0 * p["leg_thickness"] + p["hinge_washer_thickness"])
    # Bolt stops just short of the bottom of the knob's blind thread, so the
    # knob always bears on the leg face and never bottoms out on the bolt.
    d["hinge_bolt_length"] = (d["hinge_stack_thickness"]
                              + p["hinge_knob_thread_depth"] - 1.0)
    d["hinge_neck_length"] = 1.5           # plain relief before the thread starts
    d["hinge_thread_base_z"] = d["hinge_stack_thickness"] + d["hinge_neck_length"]
    d["hinge_thread_length"] = d["hinge_bolt_length"] - d["hinge_thread_base_z"]
    d["hinge_bore_radius"] = p["hinge_bolt_diameter"] / 2.0 + p["hinge_clearance"]

    # ---- marker holder -----------------------------------------------------
    d["marker_bore_radius"] = p["marker_diameter"] / 2.0 + p["marker_clearance"]
    d["marker_holder_outer_radius"] = d["marker_bore_radius"] + p["marker_clamp_thickness"]
    # The pen is longer than the holder, so part of it protrudes towards the
    # scalp and the rest trails out of the back.
    d["marker_tail_length"] = (p["marker_length"] - p["marker_tip_offset"]
                               - p["marker_holder_length"])
    # Gap between the trailing pen and the leg's tip block, on the radius.
    d["marker_tail_clearance"] = (p["marker_mount_offset"]
                                  - p["leg_tip_width"] / 2.0
                                  - d["marker_bore_radius"])

    # ---- reference frame --------------------------------------------------
    d["ear_half_distance"] = p["ref_ear_to_ear_distance"] / 2.0
    # Ball centre to ear-piece tip, along the joint axis. The ear piece screws
    # down onto the stud's relief neck, so its rear face sits at the thread base.
    d["ball_centre_standoff"] = (d.get("stud_thread_base_z", p["ball_stem_length"])
                                 + d["earpiece_total_length"])
    return d


def resolve(overrides=None, path=None):
    """Convenience: return (params, derived)."""
    p = load(overrides=overrides, path=path)
    return p, derive(p)


if __name__ == "__main__":   # library module: plain guard, run with python3
    P, D = resolve()
    print("--- parameters (%d) ---" % len(P))
    for k in sorted(P):
        flag = "  [PROVISIONAL]" if k in PROVISIONAL else ""
        print("  %-34s %s%s" % (k, P[k], flag))
    print("--- derived (%d) ---" % len(D))
    for k in sorted(D):
        v = D[k]
        print("  %-34s %s" % (k, round(v, 4) if isinstance(v, float) else v))
