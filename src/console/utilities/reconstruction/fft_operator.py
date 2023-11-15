"""Implementation of FFT reconstruction operator."""
import torch

from console.utilities.reconstruction.abstract_operator import Operator


class FFTOperator(Operator):
    """FFT Operator."""

    def __init__(self, correction: torch.Tensor | float = 1, norm: str = "ortho") -> None:
        """Fourier operator initialization."""
        super().__init__()
        self.norm = norm

    def fwd(self, img: torch.Tensor) -> torch.Tensor:
        """Image to k-space operation.

        Parameters
        ----------
        data
            Data in k-space domain.

        Returns
        -------
            Data in image domain.
        """
        ksp = torch.fft.fftshift(
            torch.fft.fft2(torch.fft.ifftshift(img, dim=(-2, -1)), norm=self.norm),
            dim=(-2, -1),
        )
        return ksp

    def adj(self, ksp: torch.Tensor) -> torch.Tensor:
        """K-Space to image operation.

        Parameters
        ----------
        data
            Data in image domain.

        Returns
        -------
            Data in k-space domain.
        """
        img = torch.fft.fftshift(
            torch.fft.ifft2(torch.fft.ifftshift(ksp, dim=(-2, -1)), norm=self.norm),
            dim=(-2, -1),
        )
        return img
