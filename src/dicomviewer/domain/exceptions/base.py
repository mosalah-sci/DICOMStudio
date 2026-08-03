"""Base exception type for the entire application."""


class DicomViewerError(Exception):
    """Base class for all errors raised by this application.

    Every domain and infrastructure error should derive from this type so
    that known failures can be handled uniformly at the application boundary.
    """
