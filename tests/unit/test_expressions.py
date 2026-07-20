import pytest

from brcm.exceptions import ExpressionError
from brcm.expressions import evaluate_expression, expression_names


def test_restricted_expression_grammar():
    parameters = {"a": 2.0, "b_1": 3.0}
    assert evaluate_expression("a", parameters) == 2
    assert evaluate_expression("(a+b_1)*2/5-1", parameters) == 1
    assert evaluate_expression("2^3", parameters) == 8
    assert evaluate_expression("-1.5e2 + 151", parameters) == 1
    assert expression_names("a*(b_1+2)") == {"a", "b_1"}


@pytest.mark.parametrize(
    "expression",
    ["abs(a)", "a.x", "a[0]", "[1, 2]", "__import__('os')", "2**3", "a < 2"],
)
def test_unsupported_expression_syntax_is_rejected(expression):
    with pytest.raises(ExpressionError):
        evaluate_expression(expression, {"a": 1})


def test_unknown_and_nonfinite_expressions_fail_clearly():
    with pytest.raises(ExpressionError, match="Unknown parameter"):
        evaluate_expression("missing + 1", {})
    with pytest.raises(ExpressionError):
        evaluate_expression("1/0", {})

