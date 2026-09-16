"""
Measure an adult head from an open research CT skull mesh.

Usage:
    python3 tools/measure_ct.py <skull.stl> [-o ct_measurements.json]

Reads a binary STL of segmented bone, works out its anatomical axes, and
reports the dimensions the divider actually needs: head width, head length,
vault height above the ear axis, and a least-squares ellipsoid fit of the
cranial vault. Output feeds the ref_* parameters in parameters.py.

WHAT THIS IS NOT:
  * It measures BONE. The arcs are struck on the SCALP, so a soft-tissue
    thickness has to be added (ref_scalp_thickness).
  * It is ONE individual. One scan is not a population, and the resulting
    numbers size a prototype - they do not define a device.
  * The ear reference height is NOT detected anatomically. The external
    auditory meatus cannot be located reliably by geometry alone, so the
    script reports the skull's width profile against height and leaves the
    choice of ear level to a clinician. See ear_level_candidates below.

Requires numpy only.
"""

from __future__ import annotations

import json
import struct
import sys

import numpy as np


def load_binary_stl(path):
    """Vertices of a binary STL as an (N,3) array."""
    with open(path, "rb") as fh:
        header = fh.read(84)
        if len(header) < 84:
            raise ValueError("%s: too short to be a binary STL" % path)
        count = struct.unpack("<I", header[80:84])[0]
        raw = fh.read(count * 50)
    if len(raw) < count * 50:
        raise ValueError("%s: truncated (ASCII STL?)" % path)
    rec = np.frombuffer(raw, dtype=np.uint8).reshape(count, 50)
    tri = rec[:, 12:48].copy().view(np.float32).reshape(count, 3, 3)
    return tri.reshape(-1, 3).astype(np.float64)


def identify_axes(v):
    """
    Map array columns to anatomy by extent.

    An adult head is longest front-to-back, then top-to-bottom, and narrowest
    side-to-side. The narrowest axis is therefore left-right, and of the
    remaining two the longer is anterior-posterior. Verified against the
    reported extents before use; the caller should sanity-check the result.
    """
    ext = v.max(0) - v.min(0)
    order = np.argsort(ext)              # ascending
    lr = int(order[0])                   # narrowest  -> left-right
    rest = [i for i in (0, 1, 2) if i != lr]
    ap = int(rest[0]) if ext[rest[0]] >= ext[rest[1]] else int(rest[1])
    si = int([i for i in rest if i != ap][0])
    return {"lr": lr, "ap": ap, "si": si, "extent": ext.tolist()}


def width_profile(v, ax, bins=40):
    """Left-right width of the skull at each height band."""
    lr, si = ax["lr"], ax["si"]
    z = v[:, si]
    lo, hi = z.min(), z.max()
    edges = np.linspace(lo, hi, bins + 1)
    out = []
    for i in range(bins):
        sel = (z >= edges[i]) & (z < edges[i + 1])
        if sel.sum() < 50:
            continue
        x = v[sel, lr]
        out.append({
            "z_from_top": float(hi - 0.5 * (edges[i] + edges[i + 1])),
            "width": float(x.max() - x.min()),
            "points": int(sel.sum()),
        })
    return out


def fit_ellipsoid_vault(v, ax, top_fraction=0.55):
    """
    Least-squares axis-aligned ellipsoid through the upper vault surface.

    Only the top `top_fraction` of the skull is used: below that the mesh is
    face, skull base and mandible, which are not part of the surface an arc
    is drawn on. Solves for centre and semi-axes by linear least squares on
      Ax^2+By^2+Cz^2+Dx+Ey+Fz = 1.
    """
    lr, ap, si = ax["lr"], ax["ap"], ax["si"]
    p = np.column_stack([v[:, lr], v[:, ap], v[:, si]])
    z = p[:, 2]
    cut = z.min() + (z.max() - z.min()) * (1.0 - top_fraction)
    p = p[z >= cut]

    # Keep only outer-surface points: farthest point per angular bin, so the
    # inner table of the skull does not drag the fit inwards.
    c0 = p.mean(0)
    d = p - c0
    r = np.linalg.norm(d, axis=1)
    theta = np.arctan2(d[:, 1], d[:, 0])
    phi = np.arccos(np.clip(d[:, 2] / np.maximum(r, 1e-9), -1, 1))
    ti = np.floor((theta + np.pi) / (2 * np.pi) * 72).astype(int)
    pi_ = np.floor(phi / np.pi * 36).astype(int)
    key = ti * 100 + pi_
    order = np.lexsort((-r, key))
    keep = np.ones(len(key), bool)
    keep[1:] = key[order][1:] != key[order][:-1]
    outer = p[order][keep]

    # Centre before fitting. CT coordinates sit far from the origin (this
    # scan runs to y = 268 mm), and the squared terms then dominate the
    # normal equations badly enough that the solve returns a non-ellipsoid.
    shift = outer.mean(0)
    q = outer - shift
    x, y, zz = q[:, 0], q[:, 1], q[:, 2]
    A = np.column_stack([x * x, y * y, zz * zz, x, y, zz])
    coef, *_ = np.linalg.lstsq(A, np.ones(len(x)), rcond=None)
    a, b, c, dd, e, f = coef
    if min(a, b, c) <= 0:
        raise ValueError("ellipsoid fit did not converge to an ellipsoid")
    cx, cy, cz = -dd / (2 * a), -e / (2 * b), -f / (2 * c)
    k = 1.0 + a * cx ** 2 + b * cy ** 2 + c * cz ** 2
    semi = np.sqrt(k / np.array([a, b, c]))
    pred = (a * x * x + b * y * y + c * zz * zz + dd * x + e * y + f * zz)
    resid = np.abs(pred - 1.0) / (2.0 * np.sqrt(np.maximum(a, 1e-12)))
    centre = np.array([cx, cy, cz]) + shift
    return {
        "centre": [float(v) for v in centre],
        "semi_axes": [float(s) for s in semi],
        "outer_points_used": int(len(outer)),
        "fit_residual_mm_approx": float(np.median(resid)),
    }



def anterior_sign(v, ax):
    """
    Which way along the A-P axis is anterior (+1 or -1)?

    The face and mandible project forward of the cranial vault, so compare
    how far the lower third of the scan reaches in each A-P direction
    against the vault. The side with the larger overhang is anterior.
    """
    ap, si = ax["ap"], ax["si"]
    z = v[:, si]
    top = z.min() + (z.max() - z.min()) * 0.55
    vault, lower = v[z >= top], v[z < top]
    if len(lower) < 100:
        return 1
    plus = lower[:, ap].max() - vault[:, ap].max()
    minus = vault[:, ap].min() - lower[:, ap].min()
    return 1 if plus >= minus else -1


def ear_reference(v, ax, depth_below_vertex, band=6.0):
    """
    Estimate the ear reference points at a chosen depth below the vertex.

    The external auditory meatus opens on the lateral surface of the temporal
    bone, so at the correct height the skull's left and right extremes sit
    essentially at the canal openings. This routine reports that width and
    where those extreme points lie fore-and-aft.

    The DEPTH IS AN INPUT, not a measurement: the canal cannot be found
    reliably from geometry alone. A clinician should confirm it. Vertex-to-
    canal in adults is roughly 125-135 mm, which is the default elsewhere.
    """
    lr, ap, si = ax["lr"], ax["ap"], ax["si"]
    z_ear = v[:, si].max() - depth_below_vertex
    sel = np.abs(v[:, si] - z_ear) <= band * 0.5
    if sel.sum() < 100:
        raise ValueError("no mesh at %.1f mm below vertex - depth outside the "
                         "cropped scan" % depth_below_vertex)
    band_pts = v[sel]
    right = band_pts[band_pts[:, lr] <= np.percentile(band_pts[:, lr], 1)]
    left = band_pts[band_pts[:, lr] >= np.percentile(band_pts[:, lr], 99)]
    width = float(left[:, lr].mean() - right[:, lr].mean())
    return {
        "depth_below_vertex": float(depth_below_vertex),
        "z_ear_in_scan": float(z_ear),
        "inter_aural_distance": abs(width),
        "ear_ap_position": float(0.5 * (left[:, ap].mean() + right[:, ap].mean())),
        "ear_lr_midpoint": float(0.5 * (left[:, lr].mean() + right[:, lr].mean())),
        "band_mm": float(band),
        "points_used": int(sel.sum()),
    }


def to_divider_frame(res, scalp_thickness, depth_below_vertex):
    """
    Convert the measurements into this project's ref_* parameters.

    Divider frame: origin at the ear-axis midpoint, +X towards the left ear,
    +Y anterior, +Z superior. The CT measures BONE, so the scalp offset is
    added to every semi-axis to approximate the skin surface the marker
    actually runs on.
    """
    ell = res["vault_ellipsoid"]
    ear = res["ear_reference"]
    sgn = res["anterior_sign"]
    cx, cy, cz = ell["centre"]
    sx, sy, sz = ell["semi_axes"]
    return {
        "ref_ear_to_ear_distance": round(ear["inter_aural_distance"], 1),
        "ref_head_semi_x": round(sx + scalp_thickness, 1),
        "ref_head_semi_y": round(sy + scalp_thickness, 1),
        "ref_head_semi_z": round(sz + scalp_thickness, 1),
        "ref_head_center_y": round(sgn * (cy - ear["ear_ap_position"]), 1),
        "ref_head_center_z": round(cz - ear["z_ear_in_scan"], 1),
        "ref_scalp_thickness": scalp_thickness,
        "ref_ear_depth_below_vertex": depth_below_vertex,
    }


def measure(path, top_fraction=0.55, ear_depth=130.0, scalp=6.0):
    v = load_binary_stl(path)
    ax = identify_axes(v)
    lr, ap, si = ax["lr"], ax["ap"], ax["si"]
    ell = fit_ellipsoid_vault(v, ax, top_fraction)
    prof = width_profile(v, ax)
    widest = max(prof, key=lambda r: r["width"])
    res = {
        "source_file": path,
        "triangle_vertices": int(len(v)),
        "axis_mapping": {"left_right": lr, "anterior_posterior": ap,
                         "superior_inferior": si},
        "bounding_box_mm": {
            "left_right": float(v[:, lr].max() - v[:, lr].min()),
            "anterior_posterior": float(v[:, ap].max() - v[:, ap].min()),
            "superior_inferior": float(v[:, si].max() - v[:, si].min()),
        },
        "vertex_z": float(v[:, si].max()),
        "widest_band": widest,
        "vault_ellipsoid": ell,
        "width_profile": prof,
    }
    res["anterior_sign"] = int(anterior_sign(v, ax))
    res["ear_reference"] = ear_reference(v, ax, ear_depth)
    res["divider_parameters"] = to_divider_frame(res, scalp, ear_depth)
    return res


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        raise SystemExit(__doc__)
    out = None
    if "-o" in sys.argv:
        out = sys.argv[sys.argv.index("-o") + 1]
    depth = 130.0
    scalp = 6.0
    if "--ear-depth" in sys.argv:
        depth = float(sys.argv[sys.argv.index("--ear-depth") + 1])
    if "--scalp" in sys.argv:
        scalp = float(sys.argv[sys.argv.index("--scalp") + 1])
    res = measure(args[0], ear_depth=depth, scalp=scalp)
    bb = res["bounding_box_mm"]
    print("source            : %s" % res["source_file"])
    print("axis mapping      : %s" % res["axis_mapping"])
    print("head width  (L-R) : %.1f mm" % bb["left_right"])
    print("head length (A-P) : %.1f mm" % bb["anterior_posterior"])
    print("scan height (S-I) : %.1f mm  (CROPPED - not a body measurement)"
          % bb["superior_inferior"])
    e = res["vault_ellipsoid"]
    print("vault ellipsoid   : semi-axes %.1f / %.1f / %.1f mm, median fit error %.2f mm"
          % (e["semi_axes"][0], e["semi_axes"][1], e["semi_axes"][2],
             e["fit_residual_mm_approx"]))
    print("                    centre %s" % [round(c, 1) for c in e["centre"]])
    w = res["widest_band"]
    print("widest band       : %.1f mm wide, %.1f mm below vertex"
          % (w["width"], w["z_from_top"]))
    print("")
    print("width vs depth below vertex (choose the ear level clinically):")
    for r in res["width_profile"]:
        if int(r["z_from_top"]) % 10 < 4.5:
            print("   %6.1f mm below vertex : width %6.1f mm"
                  % (r["z_from_top"], r["width"]))
    ear = res["ear_reference"]
    print("")
    print("ear reference (depth %.0f mm below vertex is an INPUT, not measured):"
          % ear["depth_below_vertex"])
    print("   inter-aural distance : %.1f mm" % ear["inter_aural_distance"])
    print("   anterior direction   : %+d along the A-P axis" % res["anterior_sign"])
    print("")
    print("parameters for this project (bone + %.1f mm scalp):" % scalp)
    for k, val in res["divider_parameters"].items():
        print("   %-28s %s" % (k, val))
    if out:
        with open(out, "w") as fh:
            json.dump(res, fh, indent=2)
        print("\nwritten: %s" % out)
        pj = out.replace(".json", "_params.json")
        with open(pj, "w") as fh:
            json.dump(res["divider_parameters"], fh, indent=2)
        print("written: %s   (use: run_freecad.sh main.py --params %s)"
              % (pj, pj))
