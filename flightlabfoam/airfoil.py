"""Airfoil coordinates: bundled files, NACA 4-digit sections, and uploaded ``.dat`` text.

Every airfoil is stored as an (n, 2) array of ``(x/c, y/c)`` in Selig order: trailing
edge, over the upper surface to the leading edge, and back along the lower surface.
:func:`normalize` puts the leading edge at (0, 0) and the chord at 1, and
:class:`Surfaces` turns a coordinate loop into smooth upper and lower surface
functions of ``x/c`` so that root and tip sections can be sampled at matching stations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).parent / "data" / "airfoils"

_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def available() -> list[str]:
    """Names of the bundled airfoil files."""
    return sorted(p.stem for p in DATA_DIR.glob("*.dat"))


def key(name: str) -> str:
    """Lookup key for an airfoil name: lowercase, no spaces or dashes."""
    return name.strip().lower().replace(" ", "").replace("-", "")


def parse_dat(text: str) -> tuple[str, np.ndarray]:
    """Parse ``.dat`` text in Selig or Lednicer layout; return ``(name, coordinates)``.

    The first line is always the name. A Lednicer file is recognised by its point-count
    line, whose two values are both greater than one; no normalized coordinate is.
    """
    lines = text.splitlines()
    name = lines[0].strip() if lines else ""
    pts = []
    for raw in lines[1:]:
        nums = _NUMBER.findall(raw)
        if len(nums) >= 2:
            pts.append((float(nums[0]), float(nums[1])))
    if len(pts) < 5:
        raise ValueError("could not find airfoil coordinates in the file (need at least 5 points)")

    if pts[0][0] > 1.5 and pts[0][1] > 1.5:
        n_upper, n_lower = int(round(pts[0][0])), int(round(pts[0][1]))
        body = pts[1:]
        if len(body) < n_upper + n_lower:
            raise ValueError(
                f"Lednicer header promises {n_upper}+{n_lower} points but the file has {len(body)}"
            )
        upper = np.array(body[:n_upper])
        lower = np.array(body[n_upper : n_upper + n_lower])
        # upper runs LE -> TE in Lednicer files; reverse it and drop the shared LE point
        coords = np.vstack([upper[::-1], lower[1:]])
    else:
        coords = np.array(pts)
    return name, normalize(coords)


def naca4(designation: str, n: int = 121) -> np.ndarray:
    """NACA 4-digit section, cosine spaced, ``2n - 1`` points in Selig order."""
    digits = re.sub(r"[^0-9]", "", designation)
    if len(digits) != 4:
        raise ValueError(f"{designation!r} is not a NACA 4-digit designation")
    m = int(digits[0]) / 100.0
    p = int(digits[1]) / 10.0
    t = int(digits[2:]) / 100.0

    x = (1.0 - np.cos(np.linspace(0.0, np.pi, n))) / 2.0
    yt = 5.0 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4)
    if m > 0.0 and 0.0 < p < 1.0:
        yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2))
        dyc = np.where(x < p, 2 * m / p**2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    else:
        yc = np.zeros_like(x)
        dyc = np.zeros_like(x)
    theta = np.arctan(dyc)
    xu, yu = x - yt * np.sin(theta), yc + yt * np.cos(theta)
    xl, yl = x + yt * np.sin(theta), yc - yt * np.cos(theta)
    coords = np.vstack([np.column_stack([xu[::-1], yu[::-1]]), np.column_stack([xl[1:], yl[1:]])])
    return normalize(coords)


def is_naca4(name: str) -> bool:
    k = key(name)
    digits = re.sub(r"[^0-9]", "", k)
    return len(digits) == 4 and (k == digits or k == "naca" + digits)


def load(name: str, embedded: dict | None = None) -> np.ndarray:
    """Coordinates for an airfoil name.

    Resolution order: ``embedded`` (the design's own uploaded airfoils, keyed by name),
    a bundled file, then a NACA 4-digit designation such as ``naca2412`` or ``0012``.
    """
    if embedded:
        if name in embedded:
            return normalize(np.asarray(embedded[name], dtype=float))
        by_key = {key(k): v for k, v in embedded.items()}
        if key(name) in by_key:
            return normalize(np.asarray(by_key[key(name)], dtype=float))
    path = DATA_DIR / f"{key(name)}.dat"
    if path.exists():
        return parse_dat(path.read_text(errors="replace"))[1]
    if is_naca4(name):
        return naca4(name)
    raise ValueError(
        f"unknown airfoil {name!r}. Use a bundled airfoil ({', '.join(available())}), "
        "a NACA 4-digit code such as naca2412, or upload a .dat file."
    )


def normalize(coords: np.ndarray) -> np.ndarray:
    """Put a coordinate loop in Selig order with the leading edge at (0, 0) and chord 1.

    The leading edge is the point farthest from the trailing edge (the midpoint of the
    first and last points). The section is translated, rotated so the chord line is
    horizontal, and scaled. Files in 0..100 or with a small incidence are handled the
    same way.
    """
    c = np.asarray(coords, dtype=float)
    if c.ndim != 2 or c.shape[1] != 2 or len(c) < 5:
        raise ValueError("airfoil coordinates must be an (n, 2) array with at least 5 points")
    # drop consecutive duplicates, which some files repeat at the leading edge
    keep = np.ones(len(c), dtype=bool)
    keep[1:] = np.any(np.abs(np.diff(c, axis=0)) > 1e-12, axis=1)
    c = c[keep]

    te = 0.5 * (c[0] + c[-1])
    i_le = int(np.argmax(np.linalg.norm(c - te, axis=1)))
    if i_le in (0, len(c) - 1):
        raise ValueError("airfoil coordinates must run trailing edge -> leading edge -> trailing edge")
    chord_vec = te - c[i_le]
    chord = float(np.linalg.norm(chord_vec))
    ang = np.arctan2(chord_vec[1], chord_vec[0])
    rot = np.array([[np.cos(ang), np.sin(ang)], [-np.sin(ang), np.cos(ang)]])
    c = (c - c[i_le]) @ rot.T / chord

    # Selig order means the first half is the upper surface
    if np.mean(c[:i_le, 1]) < np.mean(c[i_le + 1 :, 1]):
        c = c[::-1]
    return c


@dataclass
class Surfaces:
    """Upper and lower surfaces of a normalized airfoil as smooth functions of ``x/c``.

    Each surface is an Akima spline through the file's points in ``u = sqrt(x/c)``.
    Near the round leading edge ``y`` grows like ``sqrt(x)``, which no polynomial in
    ``x`` can follow, but it is smooth in ``u``. So the nose stays round between
    sparse data points instead of becoming a sharp corner.
    """

    x_upper: np.ndarray
    y_upper: np.ndarray
    x_lower: np.ndarray
    y_lower: np.ndarray

    def __post_init__(self):
        self._upper = _Akima(np.sqrt(self.x_upper), self.y_upper)
        self._lower = _Akima(np.sqrt(self.x_lower), self.y_lower)

    @classmethod
    def from_coords(cls, coords: np.ndarray) -> "Surfaces":
        c = normalize(coords)
        i_le = int(np.argmin(c[:, 0]))
        upper = c[: i_le + 1][::-1]  # LE -> TE
        lower = c[i_le:]  # LE -> TE
        xu, yu = _monotone(upper)
        xl, yl = _monotone(lower)
        return cls(xu, yu, xl, yl)

    def upper(self, x):
        return self._upper(np.sqrt(np.clip(x, 0.0, 1.0)))

    def lower(self, x):
        return self._lower(np.sqrt(np.clip(x, 0.0, 1.0)))

    def thickness(self, x):
        return self.upper(x) - self.lower(x)

    def max_thickness(self) -> float:
        x = np.linspace(0.0, 1.0, 401)
        return float(np.max(self.thickness(x)))


def _monotone(surface: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Clip a LE -> TE surface to 0 <= x <= 1 with strictly increasing x for interpolation.

    Points that step backwards in x (a blunt leading edge sampled very finely), or that
    sit within 1e-6 of the previous point, are dropped. The last point is moved to
    x = 1 if it is close, or the surface is extended flat to x = 1 if it stops short.
    """
    x, y = np.minimum(surface[:, 0], 1.0), surface[:, 1]
    xs, ys = [0.0], [float(y[0])]
    for xi, yi in zip(x[1:], y[1:]):
        if xi > xs[-1] + 1e-6:
            xs.append(float(xi))
            ys.append(float(yi))
    if xs[-1] > 1.0 - 1e-3:
        xs[-1] = 1.0
    else:
        xs.append(1.0)
        ys.append(ys[-1])
    return np.array(xs), np.array(ys)


class _Akima:
    """Akima spline through ``(u, y)``; linear if under 3 points.

    Translated from ``Akima`` in FLOWMath.jl (src/interpolate.jl), with ``delta_x = 0``.
    The slope at each point is a weighted average of the neighbouring segment slopes.
    So the curve depends only on nearby points and does not overshoot the way a
    global cubic spline can.
    """

    def __init__(self, u: np.ndarray, y: np.ndarray, eps: float = 1e-30):
        self.u = u
        n = len(u)
        self.p = None
        if n < 3:
            self.y = y
            return
        # segment slopes, with two extrapolated slopes at each end: m[k + 2] is segment k
        m = np.empty(n + 3)
        m[2 : n + 1] = np.diff(y) / np.diff(u)
        m[1] = 2.0 * m[2] - m[3]
        m[0] = 2.0 * m[1] - m[2]
        m[n + 1] = 2.0 * m[n] - m[n - 1]
        m[n + 2] = 2.0 * m[n + 1] - m[n]

        # slope at each point
        m1, m2, m3, m4 = m[0:n], m[1 : n + 1], m[2 : n + 2], m[3 : n + 3]
        w1, w2 = np.abs(m4 - m3), np.abs(m2 - m1)
        flat = (w1 < eps) & (w2 < eps)
        t = np.where(flat, 0.5 * (m2 + m3), (w1 * m2 + w2 * m3) / np.where(flat, 1.0, w1 + w2))

        # cubic coefficients on each segment
        dx = np.diff(u)
        mk = m[2 : n + 1]
        self.p = (y[:-1], t[:-1], (3.0 * mk - 2.0 * t[:-1] - t[1:]) / dx, (t[:-1] + t[1:] - 2.0 * mk) / dx**2)

    def __call__(self, uq):
        uq = np.asarray(uq, dtype=float)
        if self.p is None:
            return np.interp(uq, self.u, self.y)
        j = np.clip(np.searchsorted(self.u, uq, side="right") - 1, 0, len(self.u) - 2)
        d = uq - self.u[j]
        p0, p1, p2, p3 = (c[j] for c in self.p)
        return p0 + d * (p1 + d * (p2 + d * p3))


def stations(n: int, clustering: float = 1.25) -> np.ndarray:
    """``n`` chord stations from 0 to 1, clustered at the leading edge.

    A half-cosine, ``x = 1 - cos(pi/2 * t**p)`` for evenly spaced ``t``. With ``p = 1``
    the spacing along the surface is about even near the nose and widens aft. Larger
    ``p`` packs more points around the nose. The trailing edge gets no extra points,
    since the surface is nearly straight there.
    """
    t = np.linspace(0.0, 1.0, n)
    return 1.0 - np.cos(np.pi / 2 * t**clustering)
