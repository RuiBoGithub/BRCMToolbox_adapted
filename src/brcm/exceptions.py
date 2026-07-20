class BRCMError(Exception):
    """Base exception for the Python BRCM port."""


class ValidationError(BRCMError, ValueError):
    """Input data violates a MATLAB BRCM convention."""


class ExpressionError(BRCMError, ValueError):
    """A parameter expression is invalid or unsupported."""


class DataFormatError(BRCMError, ValueError):
    """A thermal-model input file has an invalid layout."""

