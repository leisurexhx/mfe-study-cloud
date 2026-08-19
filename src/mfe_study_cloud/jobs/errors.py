"""Internal worker coordination failures."""


class LeaseLostError(RuntimeError):
    """The job lease moved to another worker before a state transition."""
