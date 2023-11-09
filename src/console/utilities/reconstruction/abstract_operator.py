"""Definition of abstract reconstruction operator with forward and adjoint operation."""
from abc import ABC, abstractmethod
import torch


class Operator(ABC):
    """Abstract operator class."""
    
    @abstractmethod
    def fwd(self, data: torch.Tensor) -> torch.Tensor:
        """Abstract forward operations.

        Parameters
        ----------
        data
            Data vector the operator is applied to.

        Returns
        -------
            Result of forward operator applied to input data.
        """
        return data
    
    @abstractmethod
    def adj(self, data: torch.Tensor) -> torch.Tensor:
        """_summary_

        Parameters
        ----------
        data
            Data vector the operator is applied to.

        Returns
        -------
            Result of adjoint operator applied to input data.
        """
        return data
