"""
Reference-frame mathematics. PURE PYTHON - imports no FreeCAD.

Everything here concerns the clinical geometry of the marking workflow:

    Two arcs of equal radius R are struck on the scalp, one centred on each
    ear reference point. Because both centres lie on the X axis at +/-e and
    both radii are equal, every point equidistant from them lies on the
    plane x = 0. The arcs therefore meet on the mid-sagittal plane, and the
    line through their intersections IS the perpendicular bisector of the
    ear-to-ear segment.

That statement is exact and needs no head model. The head ellipsoid is only
used to work out WHERE on the scalp the intersection falls, i.e. whether the
chosen radius R actually reaches the midline at all. The ellipsoid is a
crude placeholder (see PROVISIONAL in parameters.py) and must not be read
as an anatomical model.
"""

from __future__ import annotations

import math


def ear_points(p, d):
    """(left, right) ear reference points. Left is +X by convention."""
    e = d["ear_half_distance"]
    return (e, 0.0, 0.0), (-e, 0.0, 0.0)


def head_center(p):
    return (0.0, p["ref_head_center_y"], p["ref_head_center_z"])


def head_top(p):
    return (0.0, p["ref_head_center_y"], p["ref_head_center_z"] + p["ref_head_semi_z"])


def distance(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def midline_ellipse_point(p, t):
    """Point on the x=0 cross-section of the reference ellipsoid, at param t."""
    cy, cz = p["ref_head_center_y"], p["ref_head_center_z"]
    b, c = p["ref_head_semi_y"], p["ref_head_semi_z"]
    return 0.0, cy + b * math.cos(t), cz + c * math.sin(t)


def arc_intersections(p, d, radius=None, samples=2048):
    """
    Points on the mid-sagittal ellipse that lie at `radius` from BOTH ears.

    Solves  y(t)^2 + z(t)^2 = R^2 - e^2  round the ellipse by sign change +
    bisection. Returns a list of (x, y, z), sorted by descending z, and
    filtered to z >= 0 (the cranial vault; the lower half of the reference
    ellipsoid is anatomically meaningless).

    An empty list means the chosen radius never reaches the midline on this
    reference head - a real and useful failure signal.
    """
    R = p["ref_arc_radius"] if radius is None else radius
    e = pivot_half_distance(p, d)
    target = R * R - e * e
    if target < 0.0:
        return []                      # radius cannot even span to the midline

    def f(t):
        _, y, z = midline_ellipse_point(p, t)
        return y * y + z * z - target

    roots = []
    step = 2.0 * math.pi / samples
    t0, f0 = 0.0, f(0.0)
    for i in range(1, samples + 1):
        t1 = i * step
        f1 = f(t1)
        if f0 == 0.0:
            roots.append(t0)
        elif f0 * f1 < 0.0:
            lo, hi, flo = t0, t1, f0
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                fm = f(mid)
                if flo * fm <= 0.0:
                    hi = mid
                else:
                    lo, flo = mid, fm
            roots.append(0.5 * (lo + hi))
        t0, f0 = t1, f1

    pts = [midline_ellipse_point(p, t) for t in roots]
    pts = [q for q in pts if q[2] >= 0.0]
    pts.sort(key=lambda q: q[2], reverse=True)
    return pts


def marker_tip_target(p, d, radius=None, which="anterior"):
    """
    A midline intersection the marker has to reach.

    The workflow strikes both arcs and uses BOTH crossings - one on the
    forehead, one on the occiput. The line through them is the midline, so
    the instrument must be able to reach each in turn, and "which" selects
    the one being checked.
    """
    pts = arc_intersections(p, d, radius=radius)
    if not pts:
        return None
    if which == "anterior":
        return max(pts, key=lambda q: q[1])
    if which == "posterior":
        return min(pts, key=lambda q: q[1])
    if which == "superior":
        return max(pts, key=lambda q: q[2])
    raise ValueError("which must be anterior, posterior or superior")


def ellipsoid_clearance(p, point):
    """
    Approximate signed distance from the reference head surface: positive
    outside, negative inside.

    Measured along the ray from the ellipsoid centre, which is exact for a
    sphere and slightly optimistic for an elongated ellipsoid. The reference
    head is close to spherical (semi-axes within about 20% of each other),
    so the error is small - but this is a clearance INDICATOR, not a
    certified minimum distance.
    """
    c = (0.0, p["ref_head_center_y"], p["ref_head_center_z"])
    semi = (p["ref_head_semi_x"], p["ref_head_semi_y"], p["ref_head_semi_z"])
    dq = [point[i] - c[i] for i in range(3)]
    f = math.sqrt(sum((dq[i] / semi[i]) ** 2 for i in range(3)))
    r = math.sqrt(sum(v * v for v in dq))
    if f <= 1e-9:
        return -min(semi)
    return r * (1.0 - 1.0 / f)


def radius_check(p, d, point, from_pivots=True):
    """
    Left/right radii to a point, and their mismatch.

    Measured from the PIVOTS by default, since those are the centres the
    arcs are actually struck about. Equal radii are what force the crossing
    onto x = 0, so the mismatch is the number that matters.
    """
    left, right = pivot_points(p, d) if from_pivots else ear_points(p, d)
    dl, dr = distance(left, point), distance(right, point)
    return {"left_radius": dl, "right_radius": dr, "mismatch": abs(dl - dr)}


def required_reach(p, d, point=None):   # noqa: D401
    """
    Straight-line distance an assembled leg must cover: ear reference point
    to marker tip. This is what sets leg_length in Phase 5.
    """
    if point is None:
        point = marker_tip_target(p, d)
    if point is None:
        return None
    left, _ = pivot_points(p, d)
    return distance(left, point)



def ear_axis(p, d, side="left"):
    """
    Unit vector along the ear canal, pointing OUTWARD (away from the head).

    Both angles zero means the canal runs straight across, so the left axis
    is +X. Neither angle is measured - the canal's true direction is a
    clinical question, and both are exposed so it can be corrected.
    """
    a = math.radians(p["ref_ear_axis_anterior_angle"])
    s_ = math.radians(p["ref_ear_axis_superior_angle"])
    v = (math.cos(a) * math.cos(s_), math.sin(a), math.sin(s_))
    n = math.sqrt(sum(c * c for c in v))
    v = tuple(c / n for c in v)
    return v if side == "left" else (-v[0], v[1], v[2])


def pivot_points(p, d):
    """
    The two points the instrument actually turns about, one per ear.

    With the ball joint locked these are the ear reference points. With it
    free - the way the client intends to use it - the ear piece stays in the
    ear and the compass swings about the BALL CENTRE, which sits
    ball_centre_standoff further out along the canal axis.

    Either way the two pivots stay symmetric about x = 0, so the
    perpendicular-bisector construction is still exact. What changes is how
    far apart they are, and therefore what radius is needed to reach the
    midline at all.
    """
    left, right = ear_points(p, d)
    if p.get("pivot_mode", "ball_centre") == "ear_point":
        return left, right
    off = d["ball_centre_standoff"]
    ul, ur = ear_axis(p, d, "left"), ear_axis(p, d, "right")
    return (tuple(left[i] + ul[i] * off for i in range(3)),
            tuple(right[i] + ur[i] * off for i in range(3)))


def pivot_half_distance(p, d):
    """Half the separation of the two pivots."""
    left, right = pivot_points(p, d)
    return 0.5 * distance(left, right)


def reachable_radius_range(p, d, samples=720):
    """
    The radii that actually put a crossing on the midline scalp.

    An arc struck from a pivot only meets the mid-sagittal scalp if its
    radius is large enough to span from the pivot to the midline, and small
    enough not to overshoot the vault. Sweeping the cranial ellipse gives
    both ends directly, and this is what catches a radius that cannot work
    before anyone prints anything.
    """
    e = pivot_half_distance(p, d)
    lo = hi = None
    for i in range(samples):
        t = 2.0 * math.pi * i / samples
        _, y, z = midline_ellipse_point(p, t)
        if z < 0.0:
            continue
        r = math.sqrt(e * e + y * y + z * z)
        lo = r if lo is None else min(lo, r)
        hi = r if hi is None else max(hi, r)
    return lo, hi


def _orthonormal_frame(u):
    """Right-handed frame whose first axis is the unit vector u."""
    ux, uy, uz = u
    helper = (0.0, 0.0, 1.0) if abs(uz) < 0.9 else (1.0, 0.0, 0.0)
    vx = uy * helper[2] - uz * helper[1]
    vy = uz * helper[0] - ux * helper[2]
    vz = ux * helper[1] - uy * helper[0]
    n = math.sqrt(vx * vx + vy * vy + vz * vz)
    v = (vx / n, vy / n, vz / n)
    w = (uy * v[2] - uz * v[1], uz * v[0] - ux * v[2], ux * v[1] - uy * v[0])
    return v, w


def scalp_arc_points(p, d, ear_point, radius=None, count=72):
    """
    Points where an arc of the given radius, struck from `ear_point`, meets
    the reference head: the path the marker actually travels.

    Found by sweeping azimuth about the ear-to-head-centre axis and, for each
    azimuth, bisecting the polar angle until the point lands on the ellipsoid.
    Azimuths where the sphere never meets the head are skipped, so a radius
    that only grazes the scalp returns a short list rather than nonsense.
    """
    R = p["ref_arc_radius"] if radius is None else radius
    c = head_center(p)
    semi = (p["ref_head_semi_x"], p["ref_head_semi_y"], p["ref_head_semi_z"])
    du = [c[i] - ear_point[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in du))
    u = tuple(x / n for x in du)
    v, w = _orthonormal_frame(u)

    def surface_f(point):
        return sum(((point[i] - c[i]) / semi[i]) ** 2 for i in range(3))

    def point_at(alpha, psi):
        ca, sa = math.cos(alpha), math.sin(alpha)
        cp, sp = math.cos(psi), math.sin(psi)
        return tuple(ear_point[i] + R * (ca * u[i] + sa * (cp * v[i] + sp * w[i]))
                     for i in range(3))

    out = []
    for k in range(count):
        psi = 2.0 * math.pi * k / count
        lo, hi = 0.0, math.pi * 0.95
        f_lo = surface_f(point_at(lo, psi)) - 1.0
        f_hi = surface_f(point_at(hi, psi)) - 1.0
        if f_lo * f_hi > 0.0:
            continue                       # no crossing along this azimuth
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if (surface_f(point_at(mid, psi)) - 1.0) * f_lo > 0.0:
                lo, f_lo = mid, surface_f(point_at(mid, psi)) - 1.0
            else:
                hi = mid
        q = point_at(0.5 * (lo + hi), psi)
        out.append({"psi": math.degrees(psi), "point": q,
                    "on_midline": abs(q[0]) < 1.0})
    return out


def sweep_targets(p, d, ear_point, radius=None, count=72):
    """
    The stretch of scalp arc the marker is actually driven along.

    An arc of fixed radius about an ear point closes into a loop right round
    the head, but only part of that loop is used: the surgeon runs from the
    anterior midline crossing, over the vault, to the posterior one. The rest
    of the loop drops below the ear axis and is never drawn.

    So find where the loop crosses x = 0, split it there, and return the half
    that goes over the top - identified by mean height, not by assumption.
    """
    pts = scalp_arc_points(p, d, ear_point, radius, count)
    if len(pts) < 4:
        return pts
    n = len(pts)
    crossings = [i for i in range(n)
                 if pts[i]["point"][0] * pts[(i + 1) % n]["point"][0] <= 0.0]
    if len(crossings) < 2:
        return pts
    a, b = crossings[0] + 1, crossings[1] + 1
    seg1 = [pts[i % n] for i in range(a, b + 1)]
    seg2 = [pts[i % n] for i in range(b, a + n + 1)]

    def mean_z(seg):
        return sum(r["point"][2] for r in seg) / max(len(seg), 1)

    return seg1 if mean_z(seg1) >= mean_z(seg2) else seg2


def summary(p, d):
    """Everything the reference frame can tell us, as a plain dict."""
    left, right = ear_points(p, d)
    ant = marker_tip_target(p, d, which="anterior")
    post = marker_tip_target(p, d, which="posterior")
    pl, pr = pivot_points(p, d)
    lo_r, hi_r = reachable_radius_range(p, d)
    out = {
        "left_ear_reference": left,
        "right_ear_reference": right,
        "pivot_mode": p.get("pivot_mode", "ball_centre"),
        "left_pivot": pl,
        "right_pivot": pr,
        "pivot_half_distance": pivot_half_distance(p, d),
        "reachable_radius_min": lo_r,
        "reachable_radius_max": hi_r,
        "head_center": head_center(p),
        "head_top": head_top(p),
        "arc_radius": p["ref_arc_radius"],
        "ear_to_ear": p["ref_ear_to_ear_distance"],
        "marker_tip": ant,
        "marker_tip_anterior": ant,
        "marker_tip_posterior": post,
        "all_midline_intersections": arc_intersections(p, d),
    }
    if ant is not None:
        out.update(radius_check(p, d, ant))
        out["required_reach"] = required_reach(p, d, ant)
    if post is not None:
        rp = radius_check(p, d, post)
        out["posterior_left_radius"] = rp["left_radius"]
        out["posterior_right_radius"] = rp["right_radius"]
        out["posterior_mismatch"] = rp["mismatch"]
        out["midline_separation"] = distance(ant, post) if ant else None
    return out


if __name__ == "__main__":   # library module: plain guard, run with python3
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import parameters
    P, D = parameters.resolve()
    for k, v in summary(P, D).items():
        print("%-28s %s" % (k, v))
