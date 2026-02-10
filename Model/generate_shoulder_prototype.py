#!/usr/bin/env python3
"""
Generate prototype shoulder OBJ files for the SkinFlaps surgical simulator.

These are simple geometric approximations for pipeline testing, NOT anatomically
precise models. Generated shapes are scaled to match the coordinate system of
the existing face model (wholeFace_NasalCartilage.obj), which uses units where
the full face spans roughly:
    X: [-12.6, 12.6]  (lateral, ~25 units)
    Y: [-21, 11.3]    (vertical, ~32 units)
    Z: [-14.8, 7.9]   (depth, ~22 units)

Shoulder model is centered at origin with:
    X: lateral (right positive)
    Y: superior-inferior (up positive)
    Z: anterior-posterior (forward positive)

Author: shoulder_model_agent (prototype)
"""

import math
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def write_obj(filepath, vertices, faces, texcoords=None, material=None,
              comment="Generated shoulder prototype"):
    """Write an OBJ file with the given vertices and faces.

    Args:
        filepath: Output file path.
        vertices: List of (x, y, z) tuples.
        faces: List of (i, j, k) tuples (1-indexed).
        texcoords: Optional list of (u, v) tuples. If provided, faces
                   reference them as v/vt.
        material: Optional material ID string (e.g. "2").
        comment: Header comment.
    """
    with open(filepath, 'w') as f:
        f.write("# {}\n".format(comment))
        f.write("# Prototype for SkinFlaps shoulder simulation\n")

        for vx, vy, vz in vertices:
            f.write("v {:.6f} {:.6f} {:.6f}\n".format(vx, vy, vz))

        if texcoords:
            for u, v in texcoords:
                f.write("vt {:.6f} {:.6f}\n".format(u, v))

        if material is not None:
            f.write("usemtl {}\n".format(material))

        for face in faces:
            if texcoords:
                f.write("f {}/{} {}/{} {}/{}\n".format(
                    face[0], face[0], face[1], face[1], face[2], face[2]))
            else:
                f.write("f {} {} {}\n".format(face[0], face[1], face[2]))

    name = os.path.basename(filepath)
    print("  Written: {} ({} verts, {} faces{})".format(
        name, len(vertices), len(faces),
        ", {} texcoords".format(len(texcoords)) if texcoords else ""))


# ---------------------------------------------------------------------------
# Geometry helpers - pole-safe versions
# ---------------------------------------------------------------------------

def _ellipsoid_pos(cx, cy, cz, rx, ry, rz, lat, lon):
    """Compute position on an ellipsoid surface."""
    x = cx + rx * math.sin(lat) * math.cos(lon)
    y = cy + ry * math.cos(lat)
    z = cz + rz * math.sin(lat) * math.sin(lon)
    return (x, y, z)


def make_ellipsoid_cap(cx, cy, cz, rx, ry, rz, n_lat, n_lon,
                       lat_min=0.0, lat_max=math.pi,
                       with_uv=False):
    """Generate an ellipsoid cap mesh with proper pole handling.

    Uses a single vertex at each pole (when lat_min=0 or lat_max=pi)
    to avoid degenerate triangles.

    lat_min=0 is north pole, lat_max=pi is south pole.
    Returns (vertices, faces, texcoords_or_None).
    """
    vertices = []
    texcoords = [] if with_uv else None
    faces = []

    has_north_pole = abs(lat_min) < 1e-12
    has_south_pole = abs(lat_max - math.pi) < 1e-12

    # Determine latitude rows to generate (excluding poles which get single verts)
    lat_start = 1 if has_north_pole else 0
    lat_end = n_lat - 1 if has_south_pole else n_lat

    # North pole vertex (single point)
    if has_north_pole:
        north_idx = len(vertices) + 1  # 1-based
        vertices.append((cx, cy + ry, cz))
        if with_uv:
            texcoords.append((0.5, 1.0))

    # Generate ring vertices (no duplicate at seam - we use modular indexing)
    ring_start_idx = len(vertices) + 1  # 1-based index of first ring vertex
    n_rings = 0

    for i in range(lat_start, lat_end + 1):
        lat = lat_min + (lat_max - lat_min) * i / n_lat
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            vertices.append(_ellipsoid_pos(cx, cy, cz, rx, ry, rz, lat, lon))
            if with_uv:
                u = j / n_lon
                v = 1.0 - i / n_lat
                texcoords.append((u, v))
        n_rings += 1

    # South pole vertex (single point)
    if has_south_pole:
        south_idx = len(vertices) + 1
        vertices.append((cx, cy - ry, cz))
        if with_uv:
            texcoords.append((0.5, 0.0))

    # Helper to get the 1-based index of ring vertex (ring r, segment j)
    def ring_vert(r, j):
        return ring_start_idx + r * n_lon + (j % n_lon)

    # North pole fan
    if has_north_pole and n_rings > 0:
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((north_idx, ring_vert(0, j1), ring_vert(0, j)))

    # Ring-to-ring quads
    for r in range(n_rings - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            p0 = ring_vert(r, j)
            p1 = ring_vert(r, j1)
            p2 = ring_vert(r + 1, j)
            p3 = ring_vert(r + 1, j1)
            faces.append((p0, p2, p1))
            faces.append((p1, p2, p3))

    # South pole fan
    if has_south_pole and n_rings > 0:
        last_ring = n_rings - 1
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((ring_vert(last_ring, j), ring_vert(last_ring, j1),
                          south_idx))

    return vertices, faces, texcoords


def make_partial_ellipsoid(cx, cy, cz, rx, ry, rz, n_lat, n_lon,
                           lat_min, lat_max, with_uv=False):
    """Generate a partial ellipsoid mesh (no poles - both rims are open rings).

    Used for caps that don't include the actual pole points.
    Returns (vertices, faces, texcoords_or_None).
    Also returns metadata: (first_ring_start_1based, last_ring_start_1based, n_lon).
    """
    vertices = []
    texcoords = [] if with_uv else None
    faces = []

    ring_start = len(vertices) + 1
    for i in range(n_lat + 1):
        lat = lat_min + (lat_max - lat_min) * i / n_lat
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            vertices.append(_ellipsoid_pos(cx, cy, cz, rx, ry, rz, lat, lon))
            if with_uv:
                u = j / n_lon
                v = 1.0 - (lat - lat_min) / (lat_max - lat_min)
                texcoords.append((u, v))

    n_rings = n_lat + 1

    def ring_vert(r, j):
        return ring_start + r * n_lon + (j % n_lon)

    for r in range(n_rings - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            p0 = ring_vert(r, j)
            p1 = ring_vert(r, j1)
            p2 = ring_vert(r + 1, j)
            p3 = ring_vert(r + 1, j1)
            faces.append((p0, p2, p1))
            faces.append((p1, p2, p3))

    first_ring = ring_start
    last_ring = ring_start + n_lat * n_lon
    return vertices, faces, texcoords, (first_ring, last_ring, n_lon)


def make_sphere(cx, cy, cz, radius, n_lat, n_lon):
    """Generate a complete sphere mesh (pole-safe)."""
    return make_ellipsoid_cap(cx, cy, cz, radius, radius, radius,
                              n_lat, n_lon, 0.0, math.pi)


def make_half_ellipsoid_with_cap(cx, cy, cz, rx, ry, rz, n_lat, n_lon):
    """Generate upper half-ellipsoid dome with flat bottom cap.

    Uses pole-safe geometry. The dome spans from north pole to equator,
    with a flat disc closing the bottom.
    Returns (vertices, faces, texcoords).
    """
    vertices = []
    texcoords = []
    faces = []

    # North pole (single vertex)
    pole_idx = 1
    vertices.append((cx, cy + ry, cz))
    texcoords.append((0.5, 1.0))

    # Generate latitude rings from just below pole to equator
    for i in range(1, n_lat + 1):
        lat = (math.pi / 2.0) * i / n_lat  # 0 at pole, pi/2 at equator
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            x = cx + rx * math.sin(lat) * math.cos(lon)
            y = cy + ry * math.cos(lat)
            z = cz + rz * math.sin(lat) * math.sin(lon)
            vertices.append((x, y, z))
            u = j / n_lon
            v = 1.0 - i / n_lat
            texcoords.append((u, v))

    def ring_vert(ring, j):
        """Get 1-based index for ring vertex. ring=0 is first ring after pole."""
        return 2 + ring * n_lon + (j % n_lon)  # 1-based, pole is vertex 1

    # Pole fan (connect pole to first ring)
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((pole_idx, ring_vert(0, j1), ring_vert(0, j)))

    # Ring-to-ring quads
    for r in range(n_lat - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((ring_vert(r, j), ring_vert(r + 1, j),
                          ring_vert(r, j1)))
            faces.append((ring_vert(r, j1), ring_vert(r + 1, j),
                          ring_vert(r + 1, j1)))

    # Flat bottom cap: center vertex + fan connecting to equator ring
    cap_center_idx = len(vertices) + 1
    vertices.append((cx, cy, cz))
    texcoords.append((0.5, 0.0))

    equator_ring = n_lat - 1  # last ring = equator
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        # Winding for downward-facing normal
        faces.append((cap_center_idx, ring_vert(equator_ring, j),
                      ring_vert(equator_ring, j1)))

    return vertices, faces, texcoords


def make_curved_plate(cx, cy, cz, width, length, curvature, nx, ny):
    """Generate a curved rectangular plate (for acromion).

    The plate extends in X and Z, curved along Z axis (bending in Y).
    Returns (vertices, faces).
    """
    vertices = []
    for iy in range(ny + 1):
        fz = -length / 2.0 + length * iy / ny
        curve_offset = curvature * (1.0 - (2.0 * iy / ny - 1.0) ** 2)
        for ix in range(nx + 1):
            fx = -width / 2.0 + width * ix / nx
            vertices.append((cx + fx, cy + curve_offset, cz + fz))

    faces = []
    for iy in range(ny):
        for ix in range(nx):
            p0 = iy * (nx + 1) + ix + 1
            p1 = p0 + 1
            p2 = p0 + (nx + 1)
            p3 = p2 + 1
            faces.append((p0, p2, p1))
            faces.append((p1, p2, p3))

    return vertices, faces


def make_closed_thick_shell(cx, cy, cz,
                            ro_x, ro_y, ro_z,
                            ri_x, ri_y, ri_z,
                            n_lat, n_lon):
    """Generate a closed manifold thick shell (upper half-ellipsoid).

    Creates outer surface, inner surface (reversed), and stitches the
    pole and equator rims to form a watertight volume.

    The shell spans from the north pole to the equator.
    At the pole, both surfaces converge to the same single pole vertex.
    At the equator, a ring of quads connects outer and inner rims.
    """
    vertices = []
    faces = []

    # --- Outer surface ---
    # North pole (shared between outer and inner)
    outer_pole_idx = 1
    vertices.append((cx, cy + ro_y, cz))

    # Outer rings: lat from just below pole to equator
    outer_ring_base = len(vertices) + 1  # 1-based
    for i in range(1, n_lat + 1):
        lat = (math.pi / 2.0) * i / n_lat
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            x = cx + ro_x * math.sin(lat) * math.cos(lon)
            y = cy + ro_y * math.cos(lat)
            z = cz + ro_z * math.sin(lat) * math.sin(lon)
            vertices.append((x, y, z))

    def outer_ring(r, j):
        return outer_ring_base + r * n_lon + (j % n_lon)

    # Outer pole fan (CCW from outside)
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((outer_pole_idx, outer_ring(0, j1), outer_ring(0, j)))

    # Outer ring-to-ring
    for r in range(n_lat - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((outer_ring(r, j), outer_ring(r + 1, j),
                          outer_ring(r, j1)))
            faces.append((outer_ring(r, j1), outer_ring(r + 1, j),
                          outer_ring(r + 1, j1)))

    # --- Inner surface ---
    # Inner pole (shared - use the same pole vertex but offset slightly
    # for a real shell; for a thin shell prototype, use a separate vertex
    # at the inner radius)
    inner_pole_idx = len(vertices) + 1
    vertices.append((cx, cy + ri_y, cz))

    inner_ring_base = len(vertices) + 1
    for i in range(1, n_lat + 1):
        lat = (math.pi / 2.0) * i / n_lat
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            x = cx + ri_x * math.sin(lat) * math.cos(lon)
            y = cy + ri_y * math.cos(lat)
            z = cz + ri_z * math.sin(lat) * math.sin(lon)
            vertices.append((x, y, z))

    def inner_ring(r, j):
        return inner_ring_base + r * n_lon + (j % n_lon)

    # Inner pole fan (CW from outside = reversed winding)
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((inner_pole_idx, inner_ring(0, j), inner_ring(0, j1)))

    # Inner ring-to-ring (reversed winding)
    for r in range(n_lat - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((inner_ring(r, j), inner_ring(r, j1),
                          inner_ring(r + 1, j)))
            faces.append((inner_ring(r, j1), inner_ring(r + 1, j1),
                          inner_ring(r + 1, j)))

    # --- Stitch pole caps ---
    # Connect outer pole to inner pole with a small triangle fan
    # The two poles are very close, so we stitch the first rings together
    # via a band that connects outer_pole -> inner_ring(0,j) and
    # inner_pole -> outer_ring(0,j)
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((outer_pole_idx, inner_pole_idx, outer_ring(0, j)))
        faces.append((inner_pole_idx, inner_ring(0, j), outer_ring(0, j)))

    # Wait, this creates a non-manifold at the pole. Better approach:
    # Connect the two poles with triangles bridging to the first rings.
    # Actually, let me reconsider. The simplest watertight approach is:
    # Use a SINGLE shared pole vertex. Then outer first ring and inner first
    # ring both fan to that same pole. This makes the pole manifold.

    # Let me redo this with a shared pole approach...
    # Clear and restart
    vertices.clear()
    faces.clear()

    # Shared north pole
    pole_idx = 1
    # Use the midpoint between outer and inner pole positions
    vertices.append((cx, cy + (ro_y + ri_y) / 2.0, cz))

    # Outer rings
    outer_ring_base = len(vertices) + 1
    for i in range(1, n_lat + 1):
        lat = (math.pi / 2.0) * i / n_lat
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            x = cx + ro_x * math.sin(lat) * math.cos(lon)
            y = cy + ro_y * math.cos(lat)
            z = cz + ro_z * math.sin(lat) * math.sin(lon)
            vertices.append((x, y, z))

    def outer_ring2(r, j):
        return outer_ring_base + r * n_lon + (j % n_lon)

    # Inner rings
    inner_ring_base2 = len(vertices) + 1
    for i in range(1, n_lat + 1):
        lat = (math.pi / 2.0) * i / n_lat
        for j in range(n_lon):
            lon = 2.0 * math.pi * j / n_lon
            x = cx + ri_x * math.sin(lat) * math.cos(lon)
            y = cy + ri_y * math.cos(lat)
            z = cz + ri_z * math.sin(lat) * math.sin(lon)
            vertices.append((x, y, z))

    def inner_ring2(r, j):
        return inner_ring_base2 + r * n_lon + (j % n_lon)

    # Outer surface: pole fan + ring quads
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((pole_idx, outer_ring2(0, j1), outer_ring2(0, j)))

    for r in range(n_lat - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((outer_ring2(r, j), outer_ring2(r + 1, j),
                          outer_ring2(r, j1)))
            faces.append((outer_ring2(r, j1), outer_ring2(r + 1, j),
                          outer_ring2(r + 1, j1)))

    # Inner surface: pole fan + ring quads (reversed winding)
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((pole_idx, inner_ring2(0, j), inner_ring2(0, j1)))

    for r in range(n_lat - 1):
        for j in range(n_lon):
            j1 = (j + 1) % n_lon
            faces.append((inner_ring2(r, j), inner_ring2(r, j1),
                          inner_ring2(r + 1, j)))
            faces.append((inner_ring2(r, j1), inner_ring2(r + 1, j1),
                          inner_ring2(r + 1, j)))

    # Stitch equator rims (outer last ring to inner last ring)
    eq = n_lat - 1  # equator ring index
    for j in range(n_lon):
        j1 = (j + 1) % n_lon
        faces.append((outer_ring2(eq, j), outer_ring2(eq, j1),
                      inner_ring2(eq, j1)))
        faces.append((outer_ring2(eq, j), inner_ring2(eq, j1),
                      inner_ring2(eq, j)))

    return vertices, faces


def make_closed_tube(cx, cy, cz, radius, length, direction, n_seg, n_len):
    """Generate a closed tube (cylinder with hemispherical end caps).

    direction: 'x', 'y', or 'z' for tube axis.
    Returns (vertices, faces) - guaranteed closed manifold.
    """
    vertices = []
    faces = []

    def remap(lx, ly, lz):
        if direction == 'x':
            return (cx + ly, cy + lx, cz + lz)
        elif direction == 'z':
            return (cx + lx, cy + lz, cz + ly)
        else:
            return (cx + lx, cy + ly, cz + lz)

    half_len = length / 2.0

    # Bottom pole
    bottom_pole_idx = len(vertices) + 1
    vertices.append(remap(0, -half_len - radius, 0))

    # Bottom hemisphere rings (from pole toward equator)
    # Stop before the last ring (i=n_cap) which overlaps with cylinder ring 0
    n_cap = 4
    n_bottom_rings = n_cap - 1  # exclude ring that coincides with cylinder
    bottom_ring_base = len(vertices) + 1
    for i in range(1, n_bottom_rings + 1):
        lat = (math.pi / 2.0) * i / n_cap
        cap_r = radius * math.sin(lat)
        cap_y = -half_len - radius * math.cos(lat)
        for j in range(n_seg):
            angle = 2.0 * math.pi * j / n_seg
            vertices.append(remap(cap_r * math.cos(angle), cap_y,
                                  cap_r * math.sin(angle)))

    def bottom_cap_ring(r, j):
        return bottom_ring_base + r * n_seg + (j % n_seg)

    # Bottom pole fan
    for j in range(n_seg):
        j1 = (j + 1) % n_seg
        faces.append((bottom_pole_idx, bottom_cap_ring(0, j),
                      bottom_cap_ring(0, j1)))

    # Bottom cap ring-to-ring
    for r in range(n_bottom_rings - 1):
        for j in range(n_seg):
            j1 = (j + 1) % n_seg
            faces.append((bottom_cap_ring(r, j), bottom_cap_ring(r, j1),
                          bottom_cap_ring(r + 1, j)))
            faces.append((bottom_cap_ring(r, j1), bottom_cap_ring(r + 1, j1),
                          bottom_cap_ring(r + 1, j)))

    # Cylinder body rings
    cyl_ring_base = len(vertices) + 1
    for i in range(n_len + 1):
        y = -half_len + length * i / n_len
        for j in range(n_seg):
            angle = 2.0 * math.pi * j / n_seg
            vertices.append(remap(radius * math.cos(angle), y,
                                  radius * math.sin(angle)))

    def cyl_ring(r, j):
        return cyl_ring_base + r * n_seg + (j % n_seg)

    # Connect bottom cap last ring to cylinder first ring
    last_bottom = n_bottom_rings - 1
    for j in range(n_seg):
        j1 = (j + 1) % n_seg
        faces.append((bottom_cap_ring(last_bottom, j),
                      bottom_cap_ring(last_bottom, j1),
                      cyl_ring(0, j)))
        faces.append((bottom_cap_ring(last_bottom, j1),
                      cyl_ring(0, j1), cyl_ring(0, j)))

    # Cylinder body
    for r in range(n_len):
        for j in range(n_seg):
            j1 = (j + 1) % n_seg
            faces.append((cyl_ring(r, j), cyl_ring(r, j1),
                          cyl_ring(r + 1, j)))
            faces.append((cyl_ring(r, j1), cyl_ring(r + 1, j1),
                          cyl_ring(r + 1, j)))

    # Top hemisphere rings (from equator toward pole)
    # Stop before the last ring (i=n_cap) where cos(pi/2)=0 makes radius zero
    top_ring_base = len(vertices) + 1
    n_top_rings = n_cap - 1  # exclude the degenerate zero-radius ring
    for i in range(1, n_top_rings + 1):
        lat = (math.pi / 2.0) * i / n_cap
        cap_r = radius * math.cos(lat)
        cap_y = half_len + radius * math.sin(lat)
        for j in range(n_seg):
            angle = 2.0 * math.pi * j / n_seg
            vertices.append(remap(cap_r * math.cos(angle), cap_y,
                                  cap_r * math.sin(angle)))

    def top_cap_ring(r, j):
        return top_ring_base + r * n_seg + (j % n_seg)

    # Top pole
    top_pole_idx = len(vertices) + 1
    vertices.append(remap(0, half_len + radius, 0))

    # Connect cylinder last ring to top cap first ring
    for j in range(n_seg):
        j1 = (j + 1) % n_seg
        faces.append((cyl_ring(n_len, j), cyl_ring(n_len, j1),
                      top_cap_ring(0, j1)))
        faces.append((cyl_ring(n_len, j), top_cap_ring(0, j1),
                      top_cap_ring(0, j)))

    # Top cap ring-to-ring
    for r in range(n_top_rings - 1):
        for j in range(n_seg):
            j1 = (j + 1) % n_seg
            faces.append((top_cap_ring(r, j), top_cap_ring(r, j1),
                          top_cap_ring(r + 1, j1)))
            faces.append((top_cap_ring(r, j), top_cap_ring(r + 1, j1),
                          top_cap_ring(r + 1, j)))

    # Top pole fan (connect last non-degenerate ring directly to pole)
    last_top = n_top_rings - 1
    for j in range(n_seg):
        j1 = (j + 1) % n_seg
        faces.append((top_cap_ring(last_top, j), top_cap_ring(last_top, j1),
                      top_pole_idx))

    return vertices, faces


# ---------------------------------------------------------------------------
# Model generators
# ---------------------------------------------------------------------------

def generate_shoulder_skin():
    """Generate ShoulderSkin.obj - outer skin surface as a half-ellipsoid dome.

    Semi-axes: rx=10, ry=7.5, rz=6 (matching face model scale).
    The dome opens downward (inferior), representing the shoulder cap.
    """
    print("Generating ShoulderSkin.obj ...")

    n_lat = 16
    n_lon = 24

    verts, faces, tcs = make_half_ellipsoid_with_cap(
        cx=0, cy=0, cz=0,
        rx=10.0, ry=7.5, rz=6.0,
        n_lat=n_lat, n_lon=n_lon
    )

    filepath = os.path.join(OUTPUT_DIR, "ShoulderSkin.obj")
    write_obj(filepath, verts, faces, texcoords=tcs, material="2",
              comment="ShoulderSkin - outer skin surface (half-ellipsoid dome)")


def generate_humerus():
    """Generate ShoulderBone_humerus.obj - humeral head as a sphere.

    Radius ~2.5, centered slightly below the dome center.
    """
    print("Generating ShoulderBone_humerus.obj ...")

    verts, faces, _ = make_sphere(
        cx=0, cy=-1.0, cz=0,
        radius=2.5,
        n_lat=10, n_lon=16
    )

    filepath = os.path.join(OUTPUT_DIR, "ShoulderBone_humerus.obj")
    write_obj(filepath, verts, faces,
              comment="ShoulderBone_humerus - humeral head collision sphere")


def generate_glenoid():
    """Generate ShoulderBone_glenoid.obj - glenoid fossa as a concave dish.

    A partial sphere segment (concave side facing laterally).
    Uses pole-safe generation.
    """
    print("Generating ShoulderBone_glenoid.obj ...")

    n_rings = 8
    n_seg = 12
    radius = 3.0
    cap_angle = math.pi / 4.0

    gx, gy, gz = -3.0, -1.0, -1.0

    vertices = []
    faces = []

    # Center vertex of the dish
    center_idx = 1
    vertices.append((gx, gy, gz))

    # Concentric rings outward from center
    for i in range(1, n_rings + 1):
        lat = cap_angle * i / n_rings
        for j in range(n_seg):
            lon = 2.0 * math.pi * j / n_seg
            x = gx - radius * (1.0 - math.cos(lat))
            y = gy + radius * math.sin(lat) * math.cos(lon)
            z = gz + radius * math.sin(lat) * math.sin(lon)
            vertices.append((x, y, z))

    def ring_vert(r, j):
        """r is 0-based ring (0 = innermost), j is segment."""
        return 2 + r * n_seg + (j % n_seg)

    # Center fan
    for j in range(n_seg):
        j1 = (j + 1) % n_seg
        faces.append((center_idx, ring_vert(0, j), ring_vert(0, j1)))

    # Ring-to-ring quads
    for r in range(n_rings - 1):
        for j in range(n_seg):
            j1 = (j + 1) % n_seg
            faces.append((ring_vert(r, j), ring_vert(r + 1, j),
                          ring_vert(r, j1)))
            faces.append((ring_vert(r, j1), ring_vert(r + 1, j),
                          ring_vert(r + 1, j1)))

    filepath = os.path.join(OUTPUT_DIR, "ShoulderBone_glenoid.obj")
    write_obj(filepath, vertices, faces,
              comment="ShoulderBone_glenoid - glenoid socket (concave dish)")


def generate_acromion():
    """Generate ShoulderBone_acromion.obj - acromion as a curved plate.

    Positioned above the humeral head.
    """
    print("Generating ShoulderBone_acromion.obj ...")

    verts, faces = make_curved_plate(
        cx=0, cy=4.5, cz=-1.0,
        width=6.0, length=4.0, curvature=1.0,
        nx=8, ny=6
    )

    filepath = os.path.join(OUTPUT_DIR, "ShoulderBone_acromion.obj")
    write_obj(filepath, verts, faces,
              comment="ShoulderBone_acromion - acromion plate above humeral head")


def generate_deep_bed():
    """Generate ShoulderDeepBed.obj - fascial plane between skin and bone.

    A half-ellipsoid offset inward from the skin surface.
    """
    print("Generating ShoulderDeepBed.obj ...")

    n_lat = 12
    n_lon = 20

    verts, faces, tcs = make_half_ellipsoid_with_cap(
        cx=0, cy=0, cz=0,
        rx=8.5, ry=6.0, rz=4.5,
        n_lat=n_lat, n_lon=n_lon
    )

    filepath = os.path.join(OUTPUT_DIR, "ShoulderDeepBed.obj")
    write_obj(filepath, verts, faces, texcoords=tcs,
              comment="ShoulderDeepBed - fascial plane (deep bed surface)")


def generate_deltoid():
    """Generate ShoulderMuscle_deltoid.obj - deltoid volume as a closed shell.

    A thick shell between the skin and deep bed ellipsoids.
    Must be a CLOSED manifold (watertight).
    """
    print("Generating ShoulderMuscle_deltoid.obj ...")

    n_lat = 10
    n_lon = 16

    verts, faces = make_closed_thick_shell(
        cx=0, cy=0, cz=0,
        ro_x=9.5, ro_y=7.0, ro_z=5.5,
        ri_x=8.8, ri_y=6.3, ri_z=4.8,
        n_lat=n_lat, n_lon=n_lon
    )

    filepath = os.path.join(OUTPUT_DIR, "ShoulderMuscle_deltoid.obj")
    write_obj(filepath, verts, faces,
              comment="ShoulderMuscle_deltoid - deltoid volume (closed manifold)")


def generate_supraspinatus():
    """Generate ShoulderTendon_supraspinatus.obj - supraspinatus tendon.

    A small closed tube positioned at the superior aspect of the humeral head.
    Must be a CLOSED manifold.
    """
    print("Generating ShoulderTendon_supraspinatus.obj ...")

    verts, faces = make_closed_tube(
        cx=0, cy=3.5, cz=0,
        radius=0.6,
        length=4.0,
        direction='x',
        n_seg=10,
        n_len=8
    )

    filepath = os.path.join(OUTPUT_DIR, "ShoulderTendon_supraspinatus.obj")
    write_obj(filepath, verts, faces,
              comment="ShoulderTendon_supraspinatus - tendon tube (closed manifold)")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_obj(filepath):
    """Thorough validation of an OBJ file."""
    name = os.path.basename(filepath)
    verts = []
    faces = []
    errors = []

    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == 'v' and len(parts) >= 4:
                verts.append((float(parts[1]), float(parts[2]),
                              float(parts[3])))
            elif parts[0] == 'f':
                indices = []
                for p in parts[1:]:
                    idx = int(p.split('/')[0])
                    indices.append(idx)
                if len(indices) != 3:
                    errors.append(
                        "  Line {}: face with {} verts (expected 3)".format(
                            line_num, len(indices)))
                else:
                    faces.append(tuple(indices))

    # Check face index bounds
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        for idx in face:
            if idx < 1 or idx > n_verts:
                errors.append(
                    "  Face {}: index {} out of range [1, {}]".format(
                        fi + 1, idx, n_verts))

    # Check for degenerate triangles (zero area)
    degen_count = 0
    for face in faces:
        v0 = verts[face[0] - 1]
        v1 = verts[face[1] - 1]
        v2 = verts[face[2] - 1]
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        cross_x = e1[1] * e2[2] - e1[2] * e2[1]
        cross_y = e1[2] * e2[0] - e1[0] * e2[2]
        cross_z = e1[0] * e2[1] - e1[1] * e2[0]
        area = math.sqrt(cross_x ** 2 + cross_y ** 2 + cross_z ** 2)
        if area < 1e-10:
            degen_count += 1

    if degen_count > 0:
        errors.append("  {} degenerate triangle(s)".format(degen_count))

    # Check manifold property for closed meshes
    is_closed_mesh = "Muscle" in name or "Tendon" in name
    if is_closed_mesh:
        edge_count = {}
        for face in faces:
            for i in range(3):
                e = (min(face[i], face[(i + 1) % 3]),
                     max(face[i], face[(i + 1) % 3]))
                edge_count[e] = edge_count.get(e, 0) + 1
        boundary_edges = sum(1 for c in edge_count.values() if c == 1)
        non_manifold = sum(1 for c in edge_count.values() if c > 2)
        if boundary_edges > 0:
            errors.append(
                "  {} boundary edge(s) - NOT closed manifold".format(
                    boundary_edges))
        if non_manifold > 0:
            errors.append(
                "  {} non-manifold edge(s)".format(non_manifold))

    # Check for duplicate face indices (e.g., f 1 1 2)
    dup_idx_count = 0
    for face in faces:
        if face[0] == face[1] or face[1] == face[2] or face[0] == face[2]:
            dup_idx_count += 1
    if dup_idx_count > 0:
        errors.append(
            "  {} face(s) with duplicate vertex indices".format(dup_idx_count))

    if errors:
        print("  ISSUES in {}:".format(name))
        for e in errors:
            print(e)
        return False
    else:
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        print("  OK: {} - {} verts, {} faces, bbox: X[{:.1f},{:.1f}] "
              "Y[{:.1f},{:.1f}] Z[{:.1f},{:.1f}]".format(
                  name, len(verts), len(faces),
                  min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Shoulder Prototype OBJ Generator")
    print("Output directory: {}".format(OUTPUT_DIR))
    print("=" * 60)
    print()

    generate_shoulder_skin()
    generate_humerus()
    generate_glenoid()
    generate_acromion()
    generate_deep_bed()
    generate_deltoid()
    generate_supraspinatus()

    print()
    print("Validating generated files ...")
    print("-" * 40)

    obj_files = [
        "ShoulderSkin.obj",
        "ShoulderBone_humerus.obj",
        "ShoulderBone_glenoid.obj",
        "ShoulderBone_acromion.obj",
        "ShoulderDeepBed.obj",
        "ShoulderMuscle_deltoid.obj",
        "ShoulderTendon_supraspinatus.obj",
    ]

    all_ok = True
    total_verts = 0
    total_faces = 0
    for name in obj_files:
        filepath = os.path.join(OUTPUT_DIR, name)
        if not os.path.exists(filepath):
            print("  MISSING: {}".format(name))
            all_ok = False
            continue
        ok = validate_obj(filepath)
        if not ok:
            all_ok = False
        with open(filepath) as f:
            for line in f:
                p = line.strip().split()
                if not p:
                    continue
                if p[0] == 'v' and len(p) >= 4:
                    total_verts += 1
                elif p[0] == 'f':
                    total_faces += 1

    print("-" * 40)
    print("Total: {} vertices, {} faces across {} files".format(
        total_verts, total_faces, len(obj_files)))

    if all_ok:
        print("\nAll validations PASSED.")
    else:
        print("\nSome validations FAILED - see above.")

    print("\nDone.")


if __name__ == "__main__":
    main()
