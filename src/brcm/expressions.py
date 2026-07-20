"""Restricted arithmetic evaluation for BRCM parameter expressions."""

from __future__ import annotations

import ast
import math
import operator
import re
from collections.abc import Mapping

from .exceptions import ExpressionError

_NAME = re.compile(r"^[A-Za-z][A-Za-z_0-9]*$")
_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def expression_names(expression: str) -> set[str]:
    tree = _parse(expression)
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def _parse(expression: str) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        raise ExpressionError("Expression must be a non-empty string")
    # MATLAB exponentiation is ^. Reject Python's spelling rather than silently
    # accepting syntax that the source toolbox did not expose.
    if "**" in expression:
        raise ExpressionError("Unsupported operator '**'; BRCM expressions use '^'")
    translated = expression.replace("^", "**")
    try:
        return ast.parse(translated, mode="eval")
    except SyntaxError as error:
        raise ExpressionError(f"Invalid expression {expression!r}") from error


def evaluate_expression(expression: str, parameters: Mapping[str, float]) -> float:
    """Evaluate literals, names, parentheses, unary signs, and + - * / ^."""

    tree = _parse(expression)

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and _NAME.fullmatch(node.id):
            if node.id not in parameters:
                raise ExpressionError(f"Unknown parameter {node.id!r} in {expression!r}")
            return float(parameters[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            try:
                return float(_BINARY[type(node.op)](visit(node.left), visit(node.right)))
            except (ArithmeticError, OverflowError) as error:
                raise ExpressionError(f"Cannot evaluate expression {expression!r}: {error}") from error
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return float(_UNARY[type(node.op)](visit(node.operand)))
        raise ExpressionError(
            f"Unsupported syntax {type(node).__name__} in expression {expression!r}"
        )

    result = visit(tree)
    if not math.isfinite(result):
        raise ExpressionError(f"Expression {expression!r} did not produce a finite number")
    return result

