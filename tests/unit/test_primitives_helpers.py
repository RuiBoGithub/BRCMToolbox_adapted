import numpy as np
import pytest

from brcm.exceptions import ValidationError
from brcm.helpers import get_id_index, matlab_intersect, matlab_setdiff, matlab_unique, reshape_vector
from brcm.primitives import BoundaryCondition, Identifier, Vertex


def test_identifier_equality_and_independent_defaults():
    left = Identifier(x=["x_Z0001"], v=["v_Tamb"])
    right = Identifier(x=["x_Z0001"], v=["v_Tamb"])
    assert left == right
    left.x.append("x_Z0002")
    assert right.x == ["x_Z0001"]


def test_identifier_lookup_is_unique_and_explicitly_zero_based():
    identifiers = ["Z0001", "Z0002"]
    assert get_id_index(identifiers, "Z0001") == 0
    assert get_id_index(identifiers, "Z0001", matlab_index=True) == 1
    with pytest.raises(ValidationError):
        get_id_index(["Z0001", "Z0001"], "Z0001")
    with pytest.raises(ValidationError):
        get_id_index(identifiers, "Z9999")


def test_matlab_set_ordering_helpers_sort_observable_results():
    assert matlab_unique(["b", "a", "b"]) == ["a", "b"]
    assert matlab_setdiff(["c", "a", "b"], ["b"]) == ["a", "c"]
    assert matlab_intersect(["c", "a", "b"], ["b", "c"]) == ["b", "c"]


def test_vertex_boundary_and_orientation_helpers():
    vertex = Vertex(1, 2, 3)
    np.testing.assert_array_equal(vertex.as_column(), [[1], [2], [3]])
    assert BoundaryCondition() == BoundaryCondition("", "", 0.0)
    assert reshape_vector(["a", "b"], "row").shape == (1, 2)
    assert reshape_vector(["a", "b"], "col").shape == (2, 1)
    with pytest.raises(ValidationError):
        reshape_vector([1], "diagonal")

