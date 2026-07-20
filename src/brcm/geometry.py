"""Polygon and vertex behavior used by thermal-data validation."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from .constants import Constants
from .exceptions import ValidationError
from .primitives import Vertex

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_VERTEX = re.compile(rf"\(({_NUMBER}),({_NUMBER}),({_NUMBER})\)")


def parse_vertices(value: str) -> tuple[Vertex, ...] | str:
    """Port ``check_vertices`` with its NULL/empty sentinel behavior."""

    if not isinstance(value, str):
        raise ValidationError("Vertices must be supplied as a string")
    stripped = value.strip()
    if stripped.upper() == Constants.NULL:
        return Constants.NULL
    if stripped == Constants.NAN or stripped == Constants.EMPTY:
        return tuple()
    if re.search(r"\s", value):
        raise ValidationError("Vertex strings must not contain whitespace")
    matches = list(_VERTEX.finditer(value))
    if len(matches) < 3 or ",".join(match.group(0) for match in matches) != value:
        raise ValidationError(f"Vertices do not fulfill BRCM convention: {value!r}")
    vertices = tuple(Vertex(*(float(item) for item in match.groups())) for match in matches)
    points = vertices_matrix(vertices)
    origin = points[:, 0]
    normal = np.cross(points[:, 1] - origin, points[:, 2] - origin)
    norm = np.linalg.norm(normal)
    if norm == 0:
        raise ValidationError("The first three vertices are collinear")
    distances = np.abs((points.T - origin) @ normal / norm)
    if np.any(distances > Constants.TOL_PLANARITY):
        raise ValidationError("Vertices are not planar within BRCM tolerance")
    return vertices


def vertices_matrix(vertices: Sequence[Vertex]) -> np.ndarray:
    if not vertices:
        return np.empty((3, 0), dtype=float)
    return np.asarray([[v.x, v.y, v.z] for v in vertices], dtype=float).T


def polygon_normal(vertices: Sequence[Vertex]) -> np.ndarray:
    matrix = vertices_matrix(vertices)
    if matrix.shape[1] < 3:
        raise ValidationError("At least three vertices are required")
    normal = np.cross(matrix[:, 1] - matrix[:, 0], matrix[:, 2] - matrix[:, 0])
    magnitude = np.linalg.norm(normal)
    if magnitude == 0:
        raise ValidationError("Cannot compute a normal from collinear vertices")
    return normal / magnitude


def polygon_area_3d(vertices: Sequence[Vertex] | np.ndarray) -> float:
    """Area of a planar ordered 3-D polygon, matching MATLAB vertex order."""

    if isinstance(vertices, np.ndarray):
        matrix = np.asarray(vertices, dtype=float)
        if matrix.ndim != 2:
            raise ValidationError("Vertex matrix must be two-dimensional")
        if matrix.shape[0] != 3 and matrix.shape[1] == 3:
            matrix = matrix.T
    else:
        matrix = vertices_matrix(vertices)
    if matrix.shape[0] != 3 or matrix.shape[1] < 3:
        raise ValidationError("At least three 3-D vertices are required")

    shifted = matrix - matrix[:, [0]]
    normals: list[np.ndarray] = []
    for index in range(1, shifted.shape[1] - 1):
        candidate = np.cross(shifted[:, index], shifted[:, index + 1])
        magnitude = np.linalg.norm(candidate)
        if magnitude != 0:
            normals.append(candidate / magnitude)
    if not normals:
        raise ValidationError("Polygon vertices are collinear")
    for i, left in enumerate(normals):
        for right in normals[i + 1 :]:
            angle = abs(np.arctan2(np.linalg.norm(np.cross(left, right)), np.dot(left, right)))
            angle = min(angle, abs(angle - np.pi))
            if angle > np.deg2rad(1.0):
                raise ValidationError("Polygon tiltedness exceeds one degree")

    average = np.sum(normals, axis=0)
    if np.linalg.norm(average) == 0:
        normals[0] = -normals[0]
        average = np.sum(normals, axis=0)
    z_axis = average / np.linalg.norm(average)
    x_axis = shifted[:, 1] / np.linalg.norm(shifted[:, 1])
    y_axis = np.cross(z_axis, x_axis)
    transformed = np.linalg.solve(np.column_stack((x_axis, y_axis, z_axis)), shifted)
    x, y = transformed[0], transformed[1]
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    if not np.isfinite(area):
        raise ValidationError("Unable to compute polygon area")
    return float(area)


get_area_from_3d_polygon = polygon_area_3d

