"""Implementation of nexus acquisition manager for multiprocessing."""
import traceback
from multiprocessing.managers import BaseManager

from console.spcm_control.acquisition_control import AcquisitionControl


class AcquisitionControlManager(BaseManager):
    """Acquisition control manager."""

    def __init__(
        self,
        address=('localhost', 50000),
        authkey=b'secretkey',
        callable_acq_control=None,
        **kwargs
    ):
        super().__init__(address=address, authkey=authkey, **kwargs)
        # Dynamically register acquisition control and the acquisition parameter proxy
        if callable_acq_control:
            self.register('AcquisitionControl', callable=callable_acq_control)
        else:
            self.register('AcquisitionControl')

    def __enter__(self) -> "AcquisitionControlManager":
        """Enter with context."""
        try:
            self.connect()
            self.acquisition: AcquisitionControl = getattr(self, "AcquisitionControl")()
            return self
        except Exception as e:
            print(f"Error connecting to AcquisitionControlManager: {e}")
            raise

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Exit with context."""
        # Explicitly remove the proxy references
        if hasattr(self, "acquisition"):
            del self.acquisition

        if exc_type is not None:
            print(f"An error occurred: {exc_value}")
            traceback.print_tb(exc_tb)

        return False  # Propagate exceptions if they occur
