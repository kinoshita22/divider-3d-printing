"""
Entry point. Builds the divider/compass, validates it and exports it.

RUN IT
    ./tools/run_freecad.sh main.py --stl
    ./tools/run_freecad.sh main.py --quick          (skip the slow checks)
    ./tools/run_freecad.sh main.py --set ref_arc_radius=150

FreeCAD parses the command line itself and rejects flags it does not know,
and its --pass escape reliably carries only ONE token, so options are taken
from the DIVIDER_ARGS environment variable instead; the wrapper sets it.

OPTIONS
    --params FILE   JSON of parameter overrides, merged over parameters.PARAMS
    --out DIR       output directory (default ./output)
    --stl           also export one STL per component, print-oriented
    --no-step       skip STEP export
    --quick         skip the slow checks (measured gaps, mesh, sweep)
    --set k=v       one-off parameter override, repeatable

WHAT GETS BUILT
    reference geometry, one ball joint, one ear piece, two legs, the main
    hinge and its lock, and the marker holder - assembled onto the reference
    head in the pose used to strike the anterior arc.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import FreeCAD as App
from FreeCAD import Vector

import parameters
from geometry import (ball_joint, compass, ear_piece, legs, main_hinge,
                      marker_holder, primitives as prim, reference_geometry,
                      refmath, validation)

DOC_NAME = "divider_prototype"

# Which module builds which component, and how many of each get printed.
COMPONENT_SOURCES = (
    ("Leg", legs, 2),
    ("HingeBolt", main_hinge, 1),
    ("HingeWasher", main_hinge, 1),
    ("HingeKnob", main_hinge, 1),
    ("BallStud", ball_joint, 1),
    ("Socket", ball_joint, 1),
    ("Collar", ball_joint, 1),
    ("EarPiece", ear_piece, 1),
    ("MarkerHolder", marker_holder, 1),
)


# --------------------------------------------------------------------------
def parse_args(argv):
    if "--pass" in argv:
        argv = argv[argv.index("--pass") + 1:]
    else:
        argv = shlex.split(os.environ.get("DIVIDER_ARGS", ""))
    opts = {"params": None, "out": os.path.join(HERE, "output"),
            "stl": False, "step": True, "quick": False, "set": {}}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--params":
            i += 1
            opts["params"] = argv[i]
        elif a == "--out":
            i += 1
            opts["out"] = argv[i]
        elif a == "--stl":
            opts["stl"] = True
        elif a == "--no-step":
            opts["step"] = False
        elif a == "--quick":
            opts["quick"] = True
        elif a == "--set":
            i += 1
            k, v = argv[i].split("=", 1)
            try:
                v = json.loads(v)
            except ValueError:
                pass
            opts["set"][k] = v
        else:
            raise SystemExit("unknown option %r (set options via "
                             "tools/run_freecad.sh or DIVIDER_ARGS)" % a)
        i += 1
    return opts


def print_orientation(shape):
    """
    Placement that lays a part down for printing.

    The Eden 260V is priced by build height, so each part is turned to put
    its smallest overall dimension along Z. Only the three axis-aligned
    options are tried: a part that needs an oblique orientation to pack well
    is a design problem, not something to hide in the exporter.
    """
    bb = prim.tight_bbox(shape)
    dims = [bb.XLength, bb.YLength, bb.ZLength]
    axis = dims.index(min(dims))
    if axis == 0:
        return App.Placement(Vector(), App.Rotation(Vector(0, 1, 0), 90))
    if axis == 1:
        return App.Placement(Vector(), App.Rotation(Vector(1, 0, 0), 90))
    return App.Placement()


def export_step(objs, path):
    import Import
    Import.export(objs, path)
    return os.path.getsize(path)


def export_component(name, shape, step_dir, stl_dir, p, do_step, do_stl):
    """One component in its own frame; the STL additionally laid down flat."""
    out = {}
    tmp = App.newDocument("export_tmp")
    try:
        o = tmp.addObject("Part::Feature", name)
        o.Shape = shape
        tmp.recompute()
        if do_step:
            pth = os.path.join(step_dir, name + ".step")
            export_step([o], pth)
            out["step"] = pth
        if do_stl:
            import MeshPart
            laid = shape.copy()
            laid.Placement = print_orientation(shape)
            mesh = MeshPart.meshFromShape(
                Shape=laid,
                LinearDeflection=p["stl_linear_deflection"],
                AngularDeflection=p["stl_angular_deflection"],
                Relative=False)
            pth = os.path.join(stl_dir, name + ".stl")
            mesh.write(pth)
            out["stl"] = pth
    finally:
        App.closeDocument(tmp.Name)
    return out


# --------------------------------------------------------------------------
def build(opts):
    t0 = time.time()
    p = parameters.load(overrides=opts["set"] or None, path=opts["params"])
    d = parameters.derive(p)
    warnings = []

    step_dir = os.path.join(opts["out"], "STEP")
    stl_dir = os.path.join(opts["out"], "STL")
    for pth in (opts["out"], step_dir, stl_dir):
        if not os.path.isdir(pth):
            os.makedirs(pth)

    doc = App.newDocument(DOC_NAME)

    # --- PHASE 1: reference frame -----------------------------------------
    ref_group = doc.addObject("App::DocumentObjectGroup", "Reference")
    ref_group.Label = "Reference geometry (construction)"
    info = reference_geometry.build(doc, p, d, warnings, ref_group)

    # --- PHASE 7: solve the instrument and pose it ------------------------
    pivot_l, _pivot_r = refmath.pivot_points(p, d)
    target = info["marker_tip_anterior"]
    if target is None:
        raise prim.GeometryError(
            "arc radius %.1f mm never reaches the mid-sagittal scalp with "
            "pivot_mode=%r. Usable band is %.1f to %.1f mm."
            % (p["ref_arc_radius"], p["pivot_mode"],
               info["reachable_radius_min"], info["reachable_radius_max"]))
    asm = compass.assembly(p, d, pivot_point=pivot_l, target=target)
    if not asm["solved"]:
        raise prim.GeometryError(
            "arc radius %.1f mm is outside what the legs can span (%.1f to "
            "%.1f mm). Change ref_arc_radius or leg_chord_length."
            % (p["ref_arc_radius"], asm["radius_info"]["min"],
               asm["radius_info"]["max"]))
    asm["joint"] = compass.joint_demand(p, d, asm["half_angle"])
    pose = asm["pose"]

    # --- PHASES 2-6: the components ---------------------------------------
    local_shapes, placed_shapes, component_objs = {}, {}, []
    grp = doc.addObject("App::DocumentObjectGroup", "Compass")
    grp.Label = "Divider assembly"
    built = {}
    for name, module, _count in COMPONENT_SOURCES:
        if name not in built:
            built.update(module.components(p, d, warnings))

    # A leg is one design used twice; the second is the same part flipped.
    instances = [("Leg_Pivot", "Leg"), ("Leg_Drawing", "Leg")]
    instances += [(n, n) for n, _m, _c in COMPONENT_SOURCES if n != "Leg"]

    for inst_name, source in instances:
        shape = built[source]
        obj = doc.addObject("Part::Feature", inst_name)
        obj.Label = inst_name.replace("_", " ")
        obj.Shape = shape
        obj.Placement = pose.multiply(asm["placements"][inst_name])
        grp.addObject(obj)
        component_objs.append(obj)
        placed_shapes[inst_name] = obj.Shape
        loc = obj.Shape.copy()
        loc.Placement = App.Placement()
        local_shapes[inst_name] = loc

    # Where the marker tip actually lands, as built.
    tip_local = marker_holder.marker_tip_local(p, d)
    marker_tip_built = pose.multiply(asm["placements"]["MarkerHolder"]).multVec(tip_local)
    reference_geometry.add_built_marker_tip(doc, marker_tip_built, ref_group)

    doc.recompute()

    # --- PHASE 8: validation ----------------------------------------------
    report_path = os.path.join(opts["out"], "validation_report.txt")
    rep, text = validation.run(p, d, local_shapes, placed_shapes, warnings,
                               path=report_path,
                               measure_gaps=not opts["quick"],
                               check_mesh=not opts["quick"],
                               assembly=asm, info=info,
                               marker_tip_built=(marker_tip_built.x,
                                                marker_tip_built.y,
                                                marker_tip_built.z),
                               sweep=not opts["quick"])

    # --- PHASE 9: save and export -----------------------------------------
    fcstd = os.path.join(opts["out"], DOC_NAME + ".FCStd")
    doc.saveAs(fcstd)
    written = [fcstd, report_path]

    if opts["step"]:
        pth = os.path.join(step_dir, "divider_assembly.step")
        export_step(component_objs, pth)
        written.append(pth)
        ref_objs = [o for o in info["objects"] if o.Shape.Solids or o.Shape.Edges]
        pth = os.path.join(step_dir, "reference_geometry.step")
        export_step(ref_objs, pth)
        written.append(pth)

    if opts["step"] or opts["stl"]:
        for name, _module, _count in COMPONENT_SOURCES:
            res = export_component(name, built[name], step_dir, stl_dir, p,
                                   opts["step"], opts["stl"])
            written.extend(res.values())

    # --- console summary ---------------------------------------------------
    print("")
    print("=" * 74)
    print("DIVIDER PROTOTYPE - BUILD SUMMARY  (%.1f s)" % (time.time() - t0))
    print("=" * 74)
    print("  %-14s %10s  %-24s %s" % ("component", "volume", "bounding box (mm)",
                                      "print height"))
    for name, _module, count in COMPONENT_SOURCES:
        sh = built[name]
        bb = prim.tight_bbox(sh)
        laid = sh.copy()
        laid.Placement = print_orientation(sh)
        lb = prim.tight_bbox(laid)
        print("  %-14s %9.1f  %6.1f x %6.1f x %6.1f    %6.2f mm  (x%d)"
              % (name, sh.Volume, bb.XLength, bb.YLength, bb.ZLength,
                 lb.ZLength, count))
    print("")
    print("  arc radius        %.2f mm from the %s  (opening %.2f deg)"
          % (asm["functional"]["radius"], p["pivot_mode"], asm["opening_angle"]))
    print("  marker tip built  (%.2f, %.2f, %.2f)"
          % (marker_tip_built.x, marker_tip_built.y, marker_tip_built.z))
    print("  head clearance    %.2f mm  at roll %.1f deg"
          % (asm["clearance"], asm["roll"]))
    jd = asm.get("joint") or {}
    if jd.get("reachable"):
        print("  ball joint        spin %.0f deg sweeps the stroke; tilt %.1f-%.1f deg "
              "of %.0f available" % (jd["spin_swept"], jd["tilt_min"],
                                     jd["tilt_max"], jd["limit"]))
    print("")
    print("  validation: %d PASS  %d WARN  %d FAIL  %d TODO"
          % (rep.count(validation.PASS), rep.count(validation.WARN),
             rep.count(validation.FAIL), rep.count(validation.TODO)))
    for _, name, value, status, note in rep.rows:
        if status in (validation.WARN, validation.FAIL):
            print("    %-5s %-34s %-14s %s" % (status, name, value, note))
    print("")
    print("  files written: %d" % len(written))
    for f in written:
        print("    %s" % os.path.relpath(f, HERE))
    print("")
    if rep.count(validation.FAIL):
        print("  *** VALIDATION REPORTED FAILURES - see %s"
              % os.path.relpath(report_path, HERE))
    sys.stdout.flush()
    return doc, rep


def _invoked_as_script():
    """
    True only when this file was RUN, not imported. freecadcmd execs scripts
    under their basename, so a plain "__main__" guard never fires under
    FreeCAD, while guarding on "main" would make "import main" in the GUI
    console silently run a whole build.
    """
    if __name__ == "__main__":
        return True
    me = os.path.abspath(__file__)
    return any(os.path.abspath(a) == me for a in sys.argv[1:])


if _invoked_as_script():
    _opts = parse_args(sys.argv)
    _doc, _rep = build(_opts)
    sys.stdout.flush()
    if _rep.count(validation.FAIL):
        sys.exit(2)
