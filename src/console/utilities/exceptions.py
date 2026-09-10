"""Exceptions raised by the nexus console."""


class NexusError(Exception):
    """Base class for all nexus console errors."""


class NexusServiceError(NexusError):
    """Errors relating to the acquisition service and its transport."""


class NexusNotRunningError(NexusServiceError):
    """The acquisition service is not running."""


class HardwareBusyError(NexusServiceError):
    """The measurement hardware is in use by another session."""
