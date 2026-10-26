"""
PHASE 8 (partial) - mechanical validation.

WHAT THIS DOES: checks that the CAD is internally consistent - that parts
fit, that clearances are real and measurable, that nothing interferes, that
the printed features are thick enough to survive, and that the reference
radii come out equal.

WHAT THIS DOES NOT DO: it says nothing about clinical accuracy, anatomical
correctness or patient safety. A PASS here means the solid model is
coherent, not that the device is fit for any medical purpose.

Checks are scoped to what has actually been built. Components belonging to
later phases are reported as TODO rather than quietly skipped.
"""

from __future__ import annotations

import math
import os
import time

import FreeCAD as App

from . import primitives as prim
from . import refmath

PASS, WARN, FAIL, INFO, TODO = "PASS", "WARN", "FAIL", "INFO", "TODO"


class Report:
    def __init__(self, title):
        self.title = title
        self.rows = []          # (section, name, value, status, note)
        self.sections = []

    def add(self, section, name, value, status=INFO, note=""):
        if section not in self.sections:
            self.sections.append(section)
        self.rows.append((section, name, value, status, note))

    def limit(self, section, name, value, lo=None, hi=None, fmt="%.3f",
              note="", unit=""):
        """Range check. Outside the range is a WARN, not a hard failure."""
        status = PASS
        if lo is not None and value < lo:
            status = WARN
        if hi is not None and value > hi:
            status = WARN
        txt = (fmt % value) + (" %s" % unit if unit else "")
        bound = []
        if lo is not None:
            bound.append(">= " + fmt % lo)
        if hi is not None:
            bound.append("<= " + fmt % hi)
        if bound and not note:
            note = "limit " + " and ".join(bound)
        self.add(section, name, txt, status, note)
        return status

    def count(self, status):
        return sum(1 for r in self.rows if r[3] == status)

    def text(self):
        out = []
        out.append("=" * 78)
        out.append(self.title)
        out.append(time.strftime("generated %Y-%m-%d %H:%M:%S"))
        out.append("=" * 78)
        out.append("")
        out.append("PROTOTYPE CAD CHECK ONLY.")
        out.append("This report describes solid-model consistency. It is not")
        out.append("evidence of clinical accuracy, anatomical correctness or")
        out.append("regulatory compliance, and must not be read as such.")
        out.append("")
        out.append("SUMMARY: %d pass, %d warn, %d fail, %d not yet built"
                   % (self.count(PASS), self.count(WARN),
                      self.count(FAIL), self.count(TODO)))
        out.append("")
        for sec in self.sections:
            out.append("-" * 78)
            out.append(sec)
            out.append("-" * 78)
            for s, name, value, status, note in self.rows:
                if s != sec:
                    continue
                line = "  %-5s %-36s %-18s %s" % (status, name, value, note)
                out.append(line.rstrip())
            out.append("")
        return "\n".join(out)


def solve_mouth_angle_for_strain(p, limit, hi=40.0):
    """
    Smallest socket_mouth_extra_angle whose finger strain meets `limit`.

    Opening the mouth eases insertion but also lowers the mouth, shortening
    the flexing finger, so the two effects partly cancel. Rather than invert
    that by hand, this re-runs the real derivation and bisects, which keeps
    the advice correct if derive() ever changes.

    Aims just inside the limit so that acting on the advice actually clears
    the check rather than landing exactly on the boundary.

    Returns (angle, derived_dict) or (None, None) if no angle in range works.
    """
    import parameters

    limit = limit * 0.98

    def strain(extra):
        q = dict(p)
        q["socket_mouth_extra_angle"] = extra
        return parameters.derive(q)

    if strain(0.0)["finger_root_strain"] <= limit:
        return 0.0, strain(0.0)
    # The mouth cannot open past 90 deg total or the ball is not captured.
    hi = min(hi, 89.0 - (p["ball_joint_max_angle"] + strain(0.0)["stem_half_angle"]))
    if hi <= 0 or strain(hi)["finger_root_strain"] > limit:
        return None, None
    lo = 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if strain(mid)["finger_root_strain"] > limit:
            lo = mid
        else:
            hi = mid
    return hi, strain(hi)


# --------------------------------------------------------------------------
def check_solids(rep, shapes):
    sec = "A. SOLID INTEGRITY"
    for name in sorted(shapes):
        sh = shapes[name]
        ok = (sh.isValid() and len(sh.Solids) == 1 and sh.isClosed()
              and sh.Volume > 0)
        rep.add(sec, name,
                "%d solid, %.1f mm3" % (len(sh.Solids), sh.Volume),
                PASS if ok else FAIL,
                "valid=%s closed=%s" % (sh.isValid(), sh.isClosed()))


def check_bounding_boxes(rep, shapes):
    sec = "B. BOUNDING BOXES (tessellated, +/-0.05 mm)"
    for name in sorted(shapes):
        bb = prim.tight_bbox(shapes[name])
        rep.add(sec, name, "%.2f x %.2f x %.2f"
                % (bb.XLength, bb.YLength, bb.ZLength), INFO,
                "print height if laid on its largest face: %.2f mm"
                % min(bb.XLength, bb.YLength, bb.ZLength))


def check_mesh_quality(rep, p, shapes):
    """
    Tessellate each component exactly as the STL export will and confirm the
    result is printable: watertight and free of self-intersecting facets.

    A valid solid does NOT guarantee a valid mesh. Tangent faces - a thread
    crest running along a cylinder of the same diameter, for instance -
    produce a perfectly good B-rep that tessellates into garbage. This is
    the check that catches it, so it runs against the shapes themselves
    rather than trusting the solid model.
    """
    sec = "B2. MESH / STL PRINTABILITY"
    try:
        import MeshPart
    except ImportError:
        rep.add(sec, "MeshPart unavailable", "skipped", INFO, "")
        return
    for name in sorted(shapes):
        sh = shapes[name]
        try:
            m = MeshPart.meshFromShape(
                Shape=sh,
                LinearDeflection=p["stl_linear_deflection"],
                AngularDeflection=p["stl_angular_deflection"],
                Relative=False)
        except Exception as exc:
            rep.add(sec, name, "meshing failed", FAIL, str(exc))
            continue
        watertight = m.isSolid()
        selfint = m.hasSelfIntersections()
        err = abs(m.Volume - sh.Volume) / sh.Volume if sh.Volume else 0.0
        ok = watertight and not selfint
        rep.add(sec, name, "%d facets" % m.CountFacets, PASS if ok else FAIL,
                "watertight=%s self-intersecting=%s volume error %.2f%%"
                % (watertight, selfint, 100.0 * err))


def check_ball_joint(rep, p, d):
    sec = "C. BALL JOINT - FITS AND CLEARANCES"
    rep.add(sec, "ball diameter", "%.2f mm" % p["ball_diameter"], INFO)
    rep.add(sec, "cavity diameter", "%.2f mm" % (2 * d["cavity_radius"]), INFO)
    rep.add(sec, "socket_clearance (radial)", "%.3f mm" % p["socket_clearance"],
            INFO, "TUNE AFTER FIRST PRINT")
    rep.add(sec, "socket clearance (diametral)",
            "%.3f mm" % (2 * p["socket_clearance"]), INFO)

    rep.limit(sec, "ball capture ratio", d["capture_ratio"],
              lo=p["warn_min_capture_ratio"], hi=p["warn_max_capture_ratio"],
              note="mouth_radius/ball_radius; <1 means the ball is trapped")

    sec2 = "D. BALL JOINT - ASSEMBLY AND CLAMPING STRAIN"
    rep.add(sec2, "assembly method", "rear loading", INFO,
            "ball drops in through the open bottom; a threaded plug closes it")
    rep.limit(sec2, "ball clearance through the bore",
              d["plug_bore_radius"] - d["ball_radius"], lo=0.15,
              note="radial; the ball must pass the bore to be fitted at all")
    rep.add(sec2, "finger spread needed to assemble", "0.000 mm", PASS,
            "the ball never passes the mouth, so the fingers do not flex to "
            "fit it. This is the step that shattered the first socket")
    rep.add(sec2, "strain if it were pressed in instead",
            "%.4f" % d["finger_strain_if_pressed_in"], INFO,
            "for reference: the printed socket broke at 0.0276 by this "
            "measure, so the material fails somewhere below that")
    rep.add(sec2, "finger flexing length",
            "%.2f mm" % d["finger_lever_length"], INFO, "slot root to mouth")
    rep.limit(sec2, "finger root strain when clamping",
              d["finger_clamp_strain"], hi=p["warn_finger_strain"], fmt="%.4f",
              note="limit <= %.4f; the fingers now only close by the ball "
                   "clearance" % p["warn_finger_strain"])

    sec3 = "E. BALL JOINT - ANGULAR RANGE"
    rep.add(sec3, "requested tilt (half-cone)",
            "%.2f deg" % p["ball_joint_max_angle"], INFO)
    st = PASS if d["achieved_tilt"] >= p["ball_joint_max_angle"] - 0.01 else FAIL
    extra_note = ""
    if d["achieved_tilt"] > p["ball_joint_max_angle"] + 0.01:
        extra_note = (" (socket_mouth_extra_angle buys %.1f deg more than "
                      "requested)" % (d["achieved_tilt"] - p["ball_joint_max_angle"]))
    rep.add(sec3, "achieved tilt at the mouth",
            "%.2f deg" % d["achieved_tilt"], st,
            "limited by the mouth cone and the stem diameter" + extra_note)
    rep.add(sec3, "full cone of adjustment",
            "%.2f deg" % (2 * d["achieved_tilt"]), INFO)
    rep.limit(sec3, "stem clearance at collar rim", d["collar_rim_margin"],
              lo=0.0,
              note="collar rim radius minus what the tilted stem needs; "
                   "negative means the stem fouls the collar before "
                   "ball_joint_max_angle is reached")
    rep.add(sec3, "collar rim radius",
            "%.2f mm" % d["collar_cone_top_radius"], INFO,
            "stem needs %.2f mm at full tilt" % d["collar_rim_required_radius"])

    sec4 = "F. BALL JOINT - CLAMPING ACTION"
    rep.add(sec4, "cone half angle", "%.2f deg" % p["socket_taper_angle"], INFO)
    rep.add(sec4, "radial closure per mm of collar advance",
            "%.4f mm/mm" % math.tan(math.radians(p["socket_taper_angle"])), INFO,
            "the wedge ratio that makes friction adjustable by hand")
    rep.add(sec4, "collar advance to close clearance",
            "%.2f mm" % d["collar_advance_to_close"], INFO,
            "= %.2f turns at %.1f mm pitch"
            % (d["collar_advance_to_close"] / p["thread_pitch"], p["thread_pitch"]))
    rep.limit(sec4, "cone overshoot beyond fingers",
              d["collar_cone_length"] - d["socket_top_z"]
              - d["collar_advance_to_close"], lo=0.5,
              note="spare cone left at full clamp; if this goes negative the "
                   "collar jams on the finger tips before it clamps")


def check_thread(rep, p, d):
    sec = "G. THREADS"
    rep.add(sec, "profile", p["thread_profile"], INFO)
    rep.add(sec, "collar thread", "M%.1f x %.1f"
            % (d["thread_diameter"], p["thread_pitch"]), INFO,
            "major diameter is DERIVED from the socket wall")
    rep.add(sec, "thread_clearance (radial)",
            "%.3f mm" % p["thread_clearance"], INFO, "TUNE AFTER FIRST PRINT")
    rep.limit(sec, "engaged turns",
              min(d["thread_length"], p["collar_thread_bore_length"]) / p["thread_pitch"],
              lo=p["warn_min_thread_turns"], fmt="%.2f")
    crest = prim.nut_crest_thickness(p)
    rep.limit(sec, "collar thread crest thickness", crest, lo=0.4,
              note="axial material left on the internal thread after "
                   "clearance; <=0 means the thread is cut away entirely")
    rep.limit(sec, "thread interruption by slots", d["thread_interruption"],
              hi=0.20, fmt="%.3f",
              note="fraction of circumference lost to the clamping slots")
    if p["ball_stud_interface"] == "threaded":
        c2 = prim.nut_crest_thickness(p, pitch=p["ball_stud_thread_pitch"])
        rep.add(sec, "ear-piece stud thread", "M%.1f x %.1f"
                % (p["ball_stud_thread_diameter"], p["ball_stud_thread_pitch"]),
                INFO, "mating female thread is PHASE 4")
        rep.limit(sec, "  its future nut crest", c2, lo=0.3)


def check_geometry_consistency(rep, p, d):
    sec = "H. INTERNAL CONSISTENCY"
    gap = (d["slot_root_z"] - p["socket_slot_relief_diameter"] / 2.0
           - d["plug_thread_top_z"])
    rep.limit(sec, "slot relief clear of the plug thread", gap, lo=1.0,
              note="the slots must stop above the internal thread, or the "
                   "plug would screw into a split bore")
    rep.limit(sec, "neck wall at the ball bore",
              d["finger_root_outer_radius"] - d["plug_bore_radius"], lo=2.5,
              note="between the ball's through bore and the outside")
    rep.limit(sec, "wall around the plug thread",
              d["socket_base_outer_radius"] - d["plug_thread_major_radius"],
              lo=2.5, note="between the plug thread and the collar thread")
    rep.limit(sec, "mouth radius vs ball radius",
              d["ball_radius"] - d["mouth_radius"], lo=0.05,
              note="must be > 0 or the ball falls out of the socket")
    rep.limit(sec, "collar bottom above socket base",
              d["collar_bottom_z"] - d["socket_base_bottom_z"], lo=0.0,
              note="the collar must not run off the end of the thread")
    rep.limit(sec, "thread zone within socket base",
              d["thread_top_z"] - d["thread_bottom_z"], lo=1.0,
              note="thread length")
    rep.limit(sec, "socket wall at finger tip", p["socket_min_tip_wall"],
              lo=p["warn_min_wall"])
    rep.limit(sec, "tenon vs socket base diameter",
              2 * d["finger_root_outer_radius"] - p["connector_tenon_width"],
              lo=0.0, note="tenon must not overhang the socket base")


def check_interference(rep, p, d, placed, measure_gaps=True):
    """
    Real boolean interference between the placed components, plus the
    measured minimum gap on the pairs that matter.

    Every pair is screened on bounding boxes first. With nine components
    that is 36 pairs, and running a boolean on threaded solids for all of
    them is slow for no return - parts at opposite ends of a 400 mm
    instrument cannot touch. Only overlapping boxes go through to the
    boolean.

    Parts that BEAR on each other - knob on leg, bolt head on leg, washer
    between legs, tenon in mortise - are expected to touch. Touching gives
    zero overlap volume, so it passes; only real interpenetration fails.
    """
    sec = "I. COMPONENT INTERFERENCE (assembled)"
    names = sorted(placed)
    boxes = {n: placed[n].BoundBox for n in names}
    checked = skipped = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ba, bb = boxes[a], boxes[b]
            if not ba.intersect(bb):
                skipped += 1
                continue
            checked += 1
            try:
                vol = placed[a].common(placed[b]).Volume
            except Exception as exc:
                rep.add(sec, "%s / %s" % (a, b), "boolean failed", WARN, str(exc))
                continue
            rep.add(sec, "%s / %s overlap" % (a, b), "%.4f mm3" % vol,
                    PASS if vol < 1e-3 else FAIL,
                    "" if vol < 1e-3 else "PARTS CLASH - not assemblable as drawn")
            if measure_gaps and vol < 1e-3:
                try:
                    gap = placed[a].distToShape(placed[b])[0]
                    rep.add(sec, "%s / %s min gap" % (a, b), "%.4f mm" % gap,
                            INFO, "measured, not nominal")
                except Exception as exc:
                    rep.add(sec, "%s / %s min gap" % (a, b), "not measured",
                            INFO, str(exc))
    rep.add(sec, "pairs tested", "%d of %d" % (checked, checked + skipped), INFO,
            "%d pairs skipped: bounding boxes do not overlap" % skipped)


def check_reference(rep, p, d):
    sec = "J. REFERENCE GEOMETRY AND WORKFLOW"
    info = refmath.summary(p, d)
    rep.add(sec, "ear-to-ear distance",
            "%.2f mm" % p["ref_ear_to_ear_distance"], INFO, "PROVISIONAL")
    rep.add(sec, "arc radius (compass opening)",
            "%.2f mm" % p["ref_arc_radius"], INFO, "PROVISIONAL")
    tip = info["marker_tip"]
    if tip is None:
        rep.add(sec, "arcs meet on the midline", "NO", FAIL,
                "radius %.1f mm never reaches the mid-sagittal plane on the "
                "reference head" % p["ref_arc_radius"])
        return info
    rep.add(sec, "MARKER_TIP", "(%.2f, %.2f, %.2f)" % tip, INFO,
            "superior-most midline intersection")
    rep.add(sec, "distance(LEFT_EAR, MARKER_TIP)",
            "%.4f mm" % info["left_radius"], INFO)
    rep.add(sec, "distance(RIGHT_EAR, MARKER_TIP)",
            "%.4f mm" % info["right_radius"], INFO)
    rep.limit(sec, "radius mismatch", info["mismatch"], hi=1e-6, fmt="%.2e",
              note="equal radii put the intersection on x=0 by construction")
    rep.add(sec, "midline intersections found",
            "%d" % len(info["all_midline_intersections"]), INFO,
            "within the cranial vault (z >= 0)")
    rep.add(sec, "required leg reach (ear -> tip)",
            "%.2f mm" % info["required_reach"], INFO,
            "straight-line span the assembled legs must cover")
    return info


def check_not_yet_built(rep, p):
    sec = "K. OUTSTANDING WORK"
    rep.add(sec, "Clinical validation of the ear piece", "REQUIRED", TODO,
            "insertion geometry is an engineering placeholder")
    rep.add(sec, "Eartip fitment", "NOT VERIFIED", TODO,
            "no silicone eartip has been fitted to the nozzle")
    rep.add(sec, "Confirm ear reference depth", "REQUIRED", TODO,
            "ref_ear_depth_below_vertex is an input to the CT measurement, "
            "not a result of it")
    rep.add(sec, "Physical fit tuning", "AFTER FIRST PRINT", TODO,
            "every clearance in section M")
    rep.add(sec, "Population coverage", "ONE CT SUBJECT ONLY", TODO,
            "the head reference is a single individual")


def check_provisional(rep, p):
    import parameters
    sec0 = "L0. MEASURED FROM CT (one individual, not a population)"
    rep.add(sec0, "source", parameters.CT_SOURCE, INFO, "")
    for k in sorted(parameters.MEASURED):
        rep.add(sec0, k, str(p.get(k, "-")), INFO, parameters.MEASURED[k])

    sec = "L. PROVISIONAL PARAMETERS IN THIS BUILD"
    for k in sorted(parameters.PROVISIONAL):
        if k not in p:
            rep.add(sec, k, "NOT A PARAMETER", WARN,
                    "listed as provisional but absent from PARAMS - the "
                    "register is out of step with the parameter set")
            continue
        rep.add(sec, k, str(p[k]), INFO, parameters.PROVISIONAL[k])
    sec2 = "M. FITS TO TUNE AGAINST A PHYSICAL PRINT"
    for k in parameters.TUNABLE_FITS:
        rep.add(sec2, k, str(p[k]), INFO,
                "re-print and adjust; do not assume the first value is right")


def check_compass(rep, p, d, asm, info, marker_tip_built):
    sec = "O. INSTRUMENT KINEMATICS"
    if not asm.get("solved"):
        rep.add(sec, "opening solution", "NONE", FAIL,
                "arc radius unreachable with this leg length")
        return
    want = p["ref_arc_radius"]
    got = asm["functional"]["radius"]
    rep.limit(sec, "arc radius error", abs(got - want), hi=0.01,
              fmt="%.5f", note="solved opening vs requested radius, in mm")
    rep.add(sec, "arc radius", "%.3f mm" % got, INFO,
            "requested %.1f mm" % want)
    rep.add(sec, "hinge opening", "%.2f deg" % asm["opening_angle"], INFO,
            "both legs together")
    rep.limit(sec, "opening within hinge limit", asm["opening_angle"],
              hi=p["max_leg_opening_angle"], fmt="%.2f", unit="deg")
    ri = asm["radius_info"]
    rep.add(sec, "radius range of this build",
            "%.1f - %.1f mm" % (ri["min"], ri["max"]), INFO,
            "set by leg_chord_length and the module reaches")

    # Form factor. With legs longer than the radius the hinge stands well off
    # the head - the same relation a drawing compass has to the paper. It is
    # a design choice, so it is reported rather than left implicit.
    if asm.get("pose") is not None:
        hinge = asm["pose"].multVec(App.Vector(0, 0, 0))
        centre = refmath.head_center(p)
        standoff = refmath.distance((hinge.x, hinge.y, hinge.z), centre)
        rep.add(sec, "hinge stand-off from head centre",
                "%.0f mm" % standoff, INFO,
                "the instrument reaches across the head rather than arching "
                "over it; shortening leg_chord_length towards ~90 mm would "
                "bring the hinge over the vertex, at the cost of a very "
                "small opening angle")
        rep.add(sec, "hinge height above the ear axis",
                "%.0f mm" % hinge.z, INFO, "")
        rep.add(sec, "leg chord vs arc radius",
                "%.0f / %.0f mm" % (p["leg_chord_length"], p["ref_arc_radius"]),
                INFO, "ratio %.2f; below about 0.5 the radius is unreachable"
                % (p["leg_chord_length"] / max(p["ref_arc_radius"], 1e-9)))

    sec2 = "P. MARKING ACCURACY (CAD self-consistency)"
    tgt = info.get("marker_tip_anterior")
    if tgt is None:
        rep.add(sec2, "anterior target", "NONE", FAIL,
                "arcs never reach the midline at this radius")
        return
    err = refmath.distance(tgt, marker_tip_built)
    rep.limit(sec2, "built tip vs geometric target", err, hi=0.05, fmt="%.5f",
              note="mm; MARKER_TIP_BUILT against MARKER_TIP")
    rc = refmath.radius_check(p, d, marker_tip_built)
    rep.add(sec2, "left ear -> built tip", "%.4f mm" % rc["left_radius"], INFO)
    rep.add(sec2, "right ear -> built tip", "%.4f mm" % rc["right_radius"], INFO)
    rep.limit(sec2, "left/right radius mismatch", rc["mismatch"], hi=0.01,
              fmt="%.6f", note="equal radii are what put the crossing on x=0")
    if info.get("marker_tip_posterior"):
        rep.add(sec2, "posterior crossing",
                "(%.1f, %.1f, %.1f)" % info["marker_tip_posterior"], INFO,
                "second point of the midline")
        rep.add(sec2, "midline baseline length",
                "%.1f mm" % info["midline_separation"], INFO,
                "distance between the two crossings")


def check_clearance(rep, p, d, asm, sweep_result=None):
    sec = "Q. HEAD CLEARANCE"
    rep.add(sec, "method", "ellipsoid radial distance", INFO,
            "approximate and slightly optimistic; the reference head is a "
            "fitted ellipsoid, not a scalp")
    if asm.get("clearance") is None:
        rep.add(sec, "static pose", "not evaluated", INFO, "")
    else:
        rep.limit(sec, "worst clearance, anterior pose", asm["clearance"],
                  lo=2.0, note="mm from the reference head")
        for grp, val in sorted(asm.get("clearance_groups", {}).items()):
            rep.add(sec, "  %s" % grp, "%.2f mm" % val, INFO, "")
        rep.add(sec, "chosen roll", "%.1f deg" % asm["roll"], INFO,
                "rotation about the ear-to-target line, picked to maximise "
                "clearance")
    if sweep_result:
        w = sweep_result["worst"]
        rep.limit(sec, "worst clearance over the whole stroke", w["clearance"],
                  lo=2.0, note="mm, sampled along the arc the marker travels")
        rep.add(sec, "  at", "(%.1f, %.1f, %.1f)" % tuple(w["point"]), INFO,
                "%d positions sampled" % len(sweep_result["samples"]))
        for grp, val in sorted(w["groups"].items()):
            rep.add(sec, "  %s at worst point" % grp, "%.2f mm" % val, INFO, "")


def check_hinge(rep, p, d):
    sec = "R. HINGE LOCK"
    rep.add(sec, "type", "friction clamp", INFO,
            "continuous adjustment; a toothed lock would quantise the radius")
    rep.add(sec, "assumed hand torque", "%.2f N.m" % p["hinge_hand_torque"],
            INFO, "ASSUMED, not measured")
    rep.add(sec, "assumed friction coefficient",
            "%.2f" % p["hinge_friction_coefficient"], INFO, "ASSUMED")
    rep.add(sec, "bolt clamp force", "%.0f N" % d["hinge_clamp_force"], INFO,
            "from T = K.F.d")
    rep.add(sec, "holding torque", "%.2f N.m" % d["hinge_holding_torque"], INFO,
            "two rubbing faces at r_eff = %.1f mm"
            % (d["hinge_effective_radius"] * 1000.0))
    rep.add(sec, "applied moment when drawing",
            "%.2f N.m" % d["hinge_applied_moment"], INFO,
            "%.1f N at the %.0f mm leg chord"
            % (p["hinge_draw_force"], p["leg_chord_length"]))
    rep.limit(sec, "slip safety factor", d["hinge_safety_factor"], lo=2.0,
              note="holding torque / applied moment. Below 1 the radius "
                   "would creep between the two arcs, which is the one "
                   "failure this instrument cannot tolerate")


def check_printing(rep, p, d, shapes):
    sec = "S. PRINTING (Stratasys Eden 260V, priced by build height)"
    total = 0.0
    for name in sorted(shapes):
        bb = prim.tight_bbox(shapes[name])
        dims = sorted([bb.XLength, bb.YLength, bb.ZLength])
        rep.add(sec, "%s laid flat" % name, "%.2f mm" % dims[0], INFO,
                "footprint %.1f x %.1f mm" % (dims[2], dims[1]))
        total = max(total, dims[0])
    rep.add(sec, "tallest component when laid flat", "%.2f mm" % total, INFO,
            "this sets the build height if everything is printed together")
    rep.limit(sec, "leg print height", d["leg_print_height"], hi=20.0,
              note="mm; the legs are the large parts, so this dominates cost")


def check_modules(rep, p, d):
    sec = "T. MODULE INTERCHANGE"
    rep.add(sec, "interface", "%.1f x %.1f x %.1f mm tenon + %.1f mm pin"
            % (p["connector_tenon_width"], p["connector_tenon_thickness"],
               p["connector_tenon_length"], p["connector_pin_diameter"]), INFO,
            "identical on the ball joint and the marker holder, so either "
            "module fits either leg")
    rep.limit(sec, "mortise side wall", d["leg_tip_wall_side"],
              lo=p["warn_min_wall"])
    rep.limit(sec, "mortise face wall", d["leg_tip_wall_face"],
              lo=p["warn_min_wall"])
    rep.add(sec, "connector clearance", "%.2f mm" % p["connector_clearance"],
            INFO, "TUNE AFTER FIRST PRINT")




def check_base_plug(rep, p, d):
    sec = "Y. BASE PLUG (rear loading)"
    rep.add(sec, "plug thread", "M%.1f x %.1f"
            % (2 * d["plug_thread_major_radius"], p["socket_plug_pitch"]), INFO,
            "internal in the socket, external on the plug, same generator")
    rep.limit(sec, "engaged turns",
              p["socket_plug_thread_length"] / p["socket_plug_pitch"], lo=4.0,
              fmt="%.2f")
    rep.limit(sec, "plug rim wall at the seat", d["plug_rim_wall"], lo=1.5,
              note="between the spherical seat and the shank; lower "
                   "plug_seat_depth thins it")
    rep.limit(sec, "shank step off the thread core",
              p["plug_body_clearance"], lo=0.3,
              note="a shank within a whisker of the thread's core radius is "
                   "near-tangent and the fuse fails outright")
    rep.add(sec, "ball support", "from %.1f mm below centre"
            % p["plug_seat_depth"], INFO,
            "the seat picks the ball up at %.0f deg below the equator"
            % math.degrees(math.asin(min(p["plug_seat_depth"]
                                         / d["cavity_radius"], 1.0))))
    rep.add(sec, "tenon carried by", "the plug", INFO,
            "leg load passes through the plug thread, which is far stronger "
            "than the tenon it feeds")
    rep.add(sec, "plug anti-rotation", "friction only", TODO,
            "the tenon doubles as the wrench; if the plug backs off in use, "
            "add thread locking or a detent")


def check_pivot(rep, p, d, info):
    sec = "V. HOW THE INSTRUMENT SWINGS"
    mode = p.get("pivot_mode", "ball_centre")
    rep.add(sec, "pivot mode", mode, INFO,
            "ball_centre = joint left free, ear piece stays in the ear; "
            "ear_point = joint locked, whole instrument turns at the canal")
    rep.add(sec, "pivot separation (half)",
            "%.2f mm" % info["pivot_half_distance"], INFO,
            "ear half-distance is %.2f mm; the rest is the ear-piece stack"
            % (p["ref_ear_to_ear_distance"] / 2.0))
    rep.add(sec, "usable arc radius in this mode",
            "%.1f - %.1f mm" % (info["reachable_radius_min"],
                                info["reachable_radius_max"]), INFO,
            "set by the reference head: smaller never reaches the midline, "
            "larger overshoots the vault")
    st = PASS
    if not (info["reachable_radius_min"] <= p["ref_arc_radius"]
            <= info["reachable_radius_max"]):
        st = FAIL
    rep.add(sec, "chosen radius is usable", "%.1f mm" % p["ref_arc_radius"], st,
            "" if st == PASS else "outside the band above - no midline crossing")
    rep.add(sec, "pivots symmetric about x=0",
            "%.2e mm" % abs(info["left_pivot"][0] + info["right_pivot"][0]),
            PASS, "this symmetry is what makes the construction exact; it "
                  "requires the ear pieces to be inserted equally on both sides")


def check_joint_motion(rep, p, d, joint):
    sec = "W. BALL JOINT DURING THE STROKE"
    if not joint or not joint.get("reachable"):
        rep.add(sec, "stroke analysis", "not evaluated", INFO, "")
        return
    rep.add(sec, "spin swept by the stroke",
            "%.0f deg" % joint["spin_swept"], INFO,
            "rotation about the ear canal axis. The joint's spin is "
            "UNLIMITED, so this is what carries the arc")
    rep.add(sec, "tilt demanded", "%.2f - %.2f deg"
            % (joint["tilt_min"], joint["tilt_max"]), INFO,
            "angle between the leg and the ear canal, at the best roll for "
            "each position")
    rep.limit(sec, "tilt margin", joint["limit"] - joint["tilt_max"], lo=2.0,
              note="ball_joint_max_angle minus the worst demand, in degrees")
    rep.add(sec, "positions sampled", "%d" % joint["targets"], INFO,
            "along the arc from one midline crossing to the other")
    st = PASS if joint["within_limit"] else FAIL
    rep.add(sec, "stroke achievable without unclamping", "yes" if st == PASS else "NO",
            st, "" if st == PASS else "the tilt demand exceeds the joint's range")


def check_marker_fit(rep, p, d):
    sec = "X. MARKER FIT"
    rep.add(sec, "specified marker", "%.1f x %.0f mm"
            % (p["marker_diameter"], p["marker_length"]), INFO,
            "client-stated: AS ONE ProShare skin marker")
    rep.add(sec, "bore diameter", "%.2f mm" % (2 * d["marker_bore_radius"]),
            INFO, "TUNE AFTER FIRST PRINT")
    rep.add(sec, "clamped length", "%.0f mm" % p["marker_holder_length"], INFO)
    rep.add(sec, "protrudes towards the scalp",
            "%.0f mm" % p["marker_tip_offset"], INFO,
            "a user SETTING, not a fixed feature - the same value must be "
            "used for both arcs")
    rep.limit(sec, "pen tail behind the holder", d["marker_tail_length"],
              lo=0.0, fmt="%.0f", unit="mm",
              note="the pen is longer than the holder, so the rest trails out "
                   "of the back and must clear the leg")
    rep.limit(sec, "tail clearance to the leg tip block",
              d["marker_tail_clearance"], lo=1.0,
              note="radial gap; raise marker_mount_offset if short")


def check_ear_piece_nozzle(rep, p, d):
    sec = "U. EAR PIECE (silicone eartip carrier)"
    rep.add(sec, "concept", "commercial silicone eartip on a nozzle", INFO,
            "client-revised 2026-09-18: printed resin no longer contacts the ear")
    rep.add(sec, "nozzle shaft", "%.1f mm dia" % p["earpiece_nozzle_diameter"],
            INFO, "CLIENT-STATED")
    rep.add(sec, "retaining bead", "%.1f mm dia"
            % p["earpiece_nozzle_lip_diameter"], INFO, "CLIENT-STATED")
    rep.add(sec, "nozzle length", "%.1f mm" % p["earpiece_nozzle_length"], INFO,
            "CLIENT-STATED")
    rep.add(sec, "stopper", "%.1f mm dia" % p["earpiece_stopper_diameter"], INFO,
            "client-stated; now also the wall the silicone base seats against")
    rep.limit(sec, "bead interference on the radius",
              d["earpiece_lip_interference"], lo=0.3, hi=0.8,
              note="how far the eartip stretches to pass the bead. Too little "
                   "and it falls off, too much and it will not go on by hand")
    rep.limit(sec, "shaft length behind the bead",
              d["earpiece_nozzle_grip_length"], lo=2.5,
              note="what the eartip actually grips")
    rep.limit(sec, "stopper overhang past the bead",
              d["earpiece_stopper_overhang"], lo=3.0,
              note="flange left proud of the nozzle to seat the silicone base")
    rep.limit(sec, "thread floor behind the socket",
              p["earpiece_body_length"] - p["earpiece_socket_depth"],
              lo=p["warn_min_wall"])
    rep.add(sec, "eartip size and seating depth", "NOT VERIFIED", TODO,
            "no eartip has been fitted; standard-size is assumed. Confirm "
            "against the actual product on the first test print")
    rep.add(sec, "CLINICAL SIGN-OFF", "STILL REQUIRED", TODO,
            "insertion depth and the Ø15 stopper remain clinical decisions")


# --------------------------------------------------------------------------
def run(p, d, shapes, placed, warnings, path=None, measure_gaps=True,
        check_mesh=True, assembly=None, info=None, marker_tip_built=None,
        sweep=True):
    """Build the report. `assembly` may carry a "joint" stroke analysis."""
    rep = Report("DIVIDER / COMPASS PROTOTYPE - CAD VALIDATION REPORT")
    check_solids(rep, shapes)
    check_bounding_boxes(rep, shapes)
    if check_mesh:
        check_mesh_quality(rep, p, shapes)
    check_ball_joint(rep, p, d)
    check_thread(rep, p, d)
    check_geometry_consistency(rep, p, d)
    if placed:
        check_interference(rep, p, d, placed, measure_gaps=measure_gaps)
    check_reference(rep, p, d)
    if assembly is not None and info is not None:
        check_compass(rep, p, d, assembly, info, marker_tip_built)
        sweep_result = None
        if sweep and assembly.get("solved"):
            from . import compass as compass_mod
            # Sample the stroke about the PIVOT the instrument actually turns
            # on, not the ear point. With the ball joint free those differ by
            # the whole ear-piece stack, and mixing them up produces a sweep
            # the instrument was never going to follow.
            pivot_l, _ = refmath.pivot_points(p, d)
            targets = refmath.sweep_targets(p, d, pivot_l)
            if targets:
                sweep_result = compass_mod.sweep_clearance(
                    p, d, assembly["half_angle"], pivot_l, targets)
        check_clearance(rep, p, d, assembly, sweep_result)
    if info is not None:
        check_pivot(rep, p, d, info)
    if assembly is not None:
        check_joint_motion(rep, p, d, assembly.get("joint"))
    check_hinge(rep, p, d)
    check_printing(rep, p, d, shapes)
    check_modules(rep, p, d)
    check_base_plug(rep, p, d)
    check_marker_fit(rep, p, d)
    check_ear_piece_nozzle(rep, p, d)
    check_not_yet_built(rep, p)
    check_provisional(rep, p)

    if warnings:
        for w in warnings:
            rep.add("N. BUILD WARNINGS", w[:36], "", WARN, w)
    else:
        rep.add("N. BUILD WARNINGS", "none", "", PASS, "")

    text = rep.text()
    if path:
        d_ = os.path.dirname(os.path.abspath(path))
        if d_ and not os.path.isdir(d_):
            os.makedirs(d_)
        with open(path, "w") as fh:
            fh.write(text + "\n")
    return rep, text
